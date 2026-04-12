from __future__ import annotations

import hashlib
import os
import posixpath
import re
import time
from typing import cast

import httpx
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile

from .config import settings
from .models import (
    ArtifactKind,
    ArtifactRecord,
    ArtifactUploadResponse,
    ConstraintRecord,
    CreateJobRequest,
    DedupeHint,
    FamilyHint,
    GenerateSpecRequest,
    GenerateSpecResponse,
    GeometryFeature,
    GeometryPlan,
    HealthResponse,
    JobRecord,
    ModeType,
    OutputType,
    SemanticCadSpec,
    SemanticPart,
    SemanticStyle,
)

# Stub renderer for worker - generates a simple bracket plate
def render_code_from_spec(spec: dict) -> str:
    # Normalize to legacy format for rendering
    spec = _legacy_spec_from_semantic(spec)
    geometry_family = spec.get("geometry_family", "bracket_plate")
    output_type = spec.get("output_type", "3d_solid")
    params = spec.get("parameters", {})
    
    width = params.get("width", 60)
    height = params.get("height", 40)
    thickness = params.get("thickness", 6)
    return f'''from build123d import *

width = {width}
height = {height}
with BuildPart() as bp:
    with BuildSketch(Plane.XY) as base:
        Rectangle(width, height)
    extrude(amount={thickness})

result = bp.part
'''


def _legacy_spec_from_semantic(spec: dict) -> dict:
    """Bridge v1.1 semantic spec to legacy family + parameters."""
    if spec.get("spec_version") == "1.1":
        semantic = spec.get("semantic_parts", [])[0] if spec.get("semantic_parts") else {}
        geometry = semantic.get("geometry", {})
        dims = geometry.get("dimensions", {})
        
        family_hint = spec.get("family_hint", {}).get("preferred", "bracket_plate")
        params = {}
        if dims:
            params = {
                "width": round(dims.get("width_mm", 60)),
                "height": round(dims.get("depth_mm", 40)),
                "thickness": round(dims.get("thickness_mm", 6)),
            }
        return {
            "geometry_family": family_hint,
            "output_type": spec.get("output_type", "3d_solid"),
            "parameters": params,
        }
    # Already legacy or empty
    return spec

from .repository import create_artifact as repo_create_artifact
from .repository import get_job as repo_get_job, save_job
from .repository import list_artifacts as repo_list_artifacts
from .store import _CACHE, _JOBS, _REQUESTS

app = FastAPI(title=settings.app_name, version="0.4.0")


def _storage_ready() -> bool:
    return bool(settings.supabase_url and settings.supabase_service_role_key and settings.supabase_bucket)


def _build_public_artifact_url(storage_key: str) -> str:
    return f"{settings.supabase_url}/storage/v1/object/public/{settings.supabase_bucket}/{storage_key}"


def _upload_bytes_to_supabase_storage(storage_key: str, blob: bytes, content_type: str) -> None:
    if not _storage_ready():
        raise HTTPException(status_code=503, detail="Artifact storage not configured")

    url = f"{settings.supabase_url}/storage/v1/object/{settings.supabase_bucket}/{storage_key}"
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "x-upsert": "true",
        "content-type": content_type,
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, content=blob, headers=headers)
    if resp.status_code >= 300:
        raise HTTPException(status_code=502, detail=f"Supabase upload failed: {resp.text[:300]}")


def _artifact_url_for(storage_key: str) -> str | None:
    if not settings.supabase_url:
        return None
    return _build_public_artifact_url(storage_key)


def _artifact_to_record(row: dict) -> ArtifactRecord:
    return ArtifactRecord(
        id=str(row.get("id")),
        job_id=str(row.get("job_id")),
        kind=cast(ArtifactKind, row.get("kind", "other")),
        storage_key=str(row.get("storage_key")),
        size_bytes=row.get("size_bytes"),
        url=_artifact_url_for(str(row.get("storage_key"))),
        created_at=row.get("created_at"),
    )


def _job_with_artifacts(job: dict) -> JobRecord:
    artifacts = [_artifact_to_record(a) for a in repo_list_artifacts(str(job["id"]))]
    # Supabase may already include artifacts in the job dict from the SQL join
    job_clean = {k: v for k, v in job.items() if k != "artifacts"}
    return JobRecord(**job_clean, artifacts=artifacts)


def _check_auth(header_value: str | None) -> None:
    if settings.api_shared_secret and header_value != settings.api_shared_secret:
        raise HTTPException(status_code=401, detail="Invalid shared secret")


def _rate_limit_key(request: Request, session_id: str | None) -> str:
    client_ip = request.client.host if request.client else "unknown"
    return session_id or client_ip


def _enforce_rate_limit(key: str) -> None:
    now = time.time()
    cutoff = now - 3600
    bucket = _REQUESTS[key]
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= settings.rate_limit_per_hour:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    bucket.append(now)


def _normalize_prompt(prompt: str) -> str:
    return " ".join(prompt.lower().strip().split())


def _assess_prompt(prompt: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    suspicious_patterns = [
        r"```",
        r"\bimport\b",
        r"\bexec\b",
        r"\beval\b",
        r"__import__",
        r"subprocess",
        r"os\.system",
        r"rm\s+-rf",
        r"curl\s+",
        r"wget\s+",
    ]
    for pattern in suspicious_patterns:
        if re.search(pattern, prompt):
            reasons.append(f"matched:{pattern}")

    if len(prompt) > settings.max_prompt_length:
        reasons.append("too_long")

    if prompt.count("\n") > 20:
        reasons.append("too_many_lines")

    return bool(reasons), reasons


def _prompt_hash(prompt: str, mode: str, output_type: str) -> str:
    digest = hashlib.sha256(f"{mode}|{output_type}|{prompt}".encode()).hexdigest()
    return digest[:16]


def _extract_number(prompt: str, keywords: list[str], default: float) -> float:
    for keyword in keywords:
        pattern = rf"{keyword}\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)"
        match = re.search(pattern, prompt)
        if match:
            return float(match.group(1))
    return default


def _extract_count(prompt: str, nouns: list[str], default: int) -> int:
    word_map = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    for noun in nouns:
        digit_match = re.search(rf"(\d+)\s+{noun}", prompt)
        if digit_match:
            return int(digit_match.group(1))
        for word, value in word_map.items():
            if re.search(rf"{word}\s+{noun}", prompt):
                return value
    return default


def _style_keywords_from_prompt(prompt: str, default_keyword: str) -> list[str]:
    keywords = [default_keyword]
    for word in ["industrial", "structural", "smooth", "diagrammatic", "heavy-duty", "lightweight", "architectural"]:
        if word in prompt and word not in keywords:
            keywords.append(word)
    if any(word in prompt for word in ["steel", "metal", "brutal"]):
        keywords.append("industrial")
    if any(word in prompt for word in ["truss", "frame", "girder"]):
        keywords.append("structural")
    if any(word in prompt for word in ["roof", "canopy", "shell"]):
        keywords.append("smooth")
    return list(dict.fromkeys(keywords))


def _infer_semantic_spec(prompt: str, mode: ModeType, output_type: OutputType) -> SemanticCadSpec:
    p = prompt.lower()

    if output_type == "2d_vector" or mode == "sketch":
        family = "truss_elevation" if any(word in p for word in ["truss", "beam", "frame", "elevation"]) else "plate_profile"
        if family == "truss_elevation":
            dimensions = {
                "span": _extract_number(p, ["span", "length", "width"], 140),
                "height": _extract_number(p, ["height", "rise"], 24),
                "panel_count": _extract_count(p, ["panels", "bays", "segments"], 7),
                "member_size": _extract_number(p, ["member", "thickness", "depth"], 3),
                "preview_thickness": 1,
            }
            geometry = GeometryPlan(
                primitive_strategy=["sketch", "extrude"],
                features=[
                    GeometryFeature(name="chords", feature_type="parallel_members", count=2),
                    GeometryFeature(name="posts", feature_type="vertical_members", count=int(dimensions["panel_count"]) + 1),
                ],
            )
            semantic_part = SemanticPart(category="diagram", function="structural elevation", topology=["top chord", "bottom chord", "posts"], symmetry="bilateral")
        else:
            dimensions = {
                "width": _extract_number(p, ["width", "span"], 80),
                "height": _extract_number(p, ["height"], 50),
                "hole_count": _extract_count(p, ["holes", "bolt holes", "openings"], 4),
                "hole_diameter": _extract_number(p, ["hole diameter", "hole", "diameter"], 10),
                "preview_thickness": 1,
            }
            geometry = GeometryPlan(
                primitive_strategy=["sketch", "extrude"],
                features=[
                    GeometryFeature(name="base_profile", feature_type="rectangle"),
                    GeometryFeature(name="holes", feature_type="circular_cutouts", count=int(dimensions["hole_count"])),
                ],
            )
            semantic_part = SemanticPart(category="profile", function="cut pattern", topology=["base plate", "openings"], symmetry="bilateral")
        return SemanticCadSpec(
            intent=prompt.strip(),
            mode=mode,
            output_type="2d_vector",
            semantic_part=semantic_part,
            family_hint=FamilyHint(name=family, generation_mode="reuse", confidence=0.75, novelty_score=0.25),
            geometry=geometry,
            dimensions=dimensions,
            constraints=[],
            style=SemanticStyle(keywords=_style_keywords_from_prompt(p, "diagrammatic"), symmetry=semantic_part.symmetry, manufacturing_bias="sheet_metal"),
            dedupe=DedupeHint(canonical_signature=f"{family}|{sorted(dimensions.items())}"),
            notes=["Concept-grade sketch/profile interpretation."],
        )

    if output_type == "surface":
        family = "canopy_surface" if any(word in p for word in ["roof", "canopy", "shell", "surface"]) else "lofted_panel"
        if family == "canopy_surface":
            dimensions = {
                "span": _extract_number(p, ["span", "width"], 160),
                "depth": _extract_number(p, ["depth", "length"], 90),
                "peak_height": _extract_number(p, ["peak", "height", "rise"], 38),
                "thickness": _extract_number(p, ["thickness"], 2),
            }
            features = [
                GeometryFeature(name="base_section", feature_type="rectangle_profile"),
                GeometryFeature(name="top_section", feature_type="scaled_rectangle_profile"),
            ]
            topology = ["base perimeter", "raised perimeter", "lofted shell"]
        else:
            dimensions = {
                "width": _extract_number(p, ["width", "span"], 80),
                "depth": _extract_number(p, ["depth", "length"], 50),
                "rise": _extract_number(p, ["rise", "height"], 18),
                "thickness": _extract_number(p, ["thickness"], 2),
            }
            features = [
                GeometryFeature(name="lower_frame", feature_type="rectangle_profile"),
                GeometryFeature(name="upper_frame", feature_type="scaled_rectangle_profile"),
            ]
            topology = ["lower frame", "upper frame", "lofted skin"]
        return SemanticCadSpec(
            intent=prompt.strip(),
            mode=mode,
            output_type="surface",
            semantic_part=SemanticPart(category="surface", function="enclosure/canopy", topology=topology, symmetry="bilateral"),
            family_hint=FamilyHint(name=family, generation_mode="extend", confidence=0.7, novelty_score=0.45),
            geometry=GeometryPlan(primitive_strategy=["loft", "offset"], features=features),
            dimensions=dimensions,
            constraints=[ConstraintRecord(kind="min", target="thickness", value=1.0)],
            style=SemanticStyle(keywords=_style_keywords_from_prompt(p, "smooth"), symmetry="bilateral", manufacturing_bias="generic"),
            dedupe=DedupeHint(canonical_signature=f"{family}|{sorted(dimensions.items())}"),
            notes=["Surface interpretation remains concept-grade and may simplify shell behavior."],
        )

    if any(word in p for word in ["truss", "beam", "frame", "girder"]):
        dimensions = {
            "span": _extract_number(p, ["span", "length"], 140),
            "height": _extract_number(p, ["height", "rise"], 24),
            "panel_count": _extract_count(p, ["panels", "bays", "segments"], 7),
            "member_size": _extract_number(p, ["member", "thickness", "depth"], 3),
        }
        return SemanticCadSpec(
            intent=prompt.strip(),
            mode=mode,
            output_type="3d_solid",
            semantic_part=SemanticPart(category="structure", function="spanning member", topology=["top chord", "bottom chord", "posts"], symmetry="bilateral"),
            family_hint=FamilyHint(name="truss_beam", generation_mode="reuse", confidence=0.82, novelty_score=0.28),
            geometry=GeometryPlan(
                primitive_strategy=["extrude", "array", "boolean_compound"],
                features=[
                    GeometryFeature(name="top_chord", feature_type="beam_member"),
                    GeometryFeature(name="bottom_chord", feature_type="beam_member"),
                    GeometryFeature(name="posts", feature_type="vertical_members", count=int(dimensions["panel_count"]) + 1),
                ],
            ),
            dimensions=dimensions,
            constraints=[ConstraintRecord(kind="min", target="panel_count", value=3)],
            style=SemanticStyle(keywords=_style_keywords_from_prompt(p, "structural"), symmetry="bilateral", manufacturing_bias="machined"),
            dedupe=DedupeHint(canonical_signature=f"truss_beam|{sorted(dimensions.items())}"),
            notes=["Maps to the current truss generator for execution."],
        )

    if any(word in p for word in ["tower", "block", "monolith"]):
        dimensions = {
            "width": _extract_number(p, ["width"], 30),
            "length": _extract_number(p, ["length", "depth"], 30),
            "height": _extract_number(p, ["height"], 120),
            "notch": _extract_number(p, ["notch", "cut"], 10),
        }
        return SemanticCadSpec(
            intent=prompt.strip(),
            mode=mode,
            output_type="3d_solid",
            semantic_part=SemanticPart(category="mass", function="vertical block study", topology=["primary mass", "subtractive notches"], symmetry="bilateral"),
            family_hint=FamilyHint(name="tower_block", generation_mode="extend", confidence=0.74, novelty_score=0.52),
            geometry=GeometryPlan(
                primitive_strategy=["box", "boolean_subtract"],
                features=[
                    GeometryFeature(name="main_mass", feature_type="box"),
                    GeometryFeature(name="notches", feature_type="subtractive_blocks", count=2),
                ],
            ),
            dimensions=dimensions,
            constraints=[],
            style=SemanticStyle(keywords=_style_keywords_from_prompt(p, "industrial"), symmetry="bilateral", manufacturing_bias="generic"),
            dedupe=DedupeHint(canonical_signature=f"tower_block|{sorted(dimensions.items())}"),
            notes=["Keeps tower prompts broad while still routing to the existing massing generator."],
        )

    dimensions = {
        "width": _extract_number(p, ["width", "span"], 80),
        "height": _extract_number(p, ["height"], 50),
        "thickness": _extract_number(p, ["thickness"], 6),
        "hole_count": _extract_count(p, ["holes", "bolt holes", "openings"], 4),
        "hole_diameter": _extract_number(p, ["hole diameter", "hole", "diameter"], 10),
    }
    return SemanticCadSpec(
        intent=prompt.strip(),
        mode=mode,
        output_type="3d_solid",
        semantic_part=SemanticPart(category="support", function="mounting/support part", topology=["plate body", "openings"], symmetry="bilateral"),
        family_hint=FamilyHint(name="bracket_plate", generation_mode="extend", confidence=0.6, novelty_score=0.58),
        geometry=GeometryPlan(
            primitive_strategy=["extrude", "boolean_subtract"],
            features=[
                GeometryFeature(name="base_plate", feature_type="rectangular_plate"),
                GeometryFeature(name="holes", feature_type="circular_cutouts", count=int(dimensions["hole_count"])),
            ],
        ),
        dimensions=dimensions,
        constraints=[ConstraintRecord(kind="min", target="thickness", value=2.0)],
        style=SemanticStyle(keywords=_style_keywords_from_prompt(p, "industrial"), symmetry="bilateral", manufacturing_bias="machined"),
        dedupe=DedupeHint(canonical_signature=f"bracket_plate|{sorted(dimensions.items())}"),
        notes=["Default concept-grade support interpretation. Replace with true model output later for broader novelty."],
    )


def _generate_spec(payload: GenerateSpecRequest) -> GenerateSpecResponse:
    normalized = _normalize_prompt(payload.prompt)
    suspicious_input, suspicious_reasons = _assess_prompt(payload.prompt)
    key = _prompt_hash(normalized, payload.mode, payload.output_type)

    if key in _CACHE:
        cached = dict(_CACHE[key])
        cached["cached"] = True
        return GenerateSpecResponse(**cached)

    safe_prompt = normalized
    fallback_level = "normal"
    notes = [
        f"Mode: {payload.mode}",
        f"Output type: {payload.output_type}",
    ]

    if suspicious_input:
        safe_prompt = "simple industrial bracket plate with 4 holes"
        fallback_level = "guardrailed"
        notes.extend([
            "Input looked more like code or hostile instructions than a CAD prompt.",
            "Using a safe fallback prompt for MVP robustness.",
            *[f"Guardrail: {reason}" for reason in suspicious_reasons],
        ])
    elif len(normalized.split()) < 3:
        fallback_level = "underspecified"
        notes.extend([
            "Prompt was underspecified.",
            "Using conservative defaults and a simple geometry family.",
        ])

    spec = _infer_semantic_spec(safe_prompt, payload.mode, payload.output_type)
    response = GenerateSpecResponse(
        prompt_hash=key,
        spec=spec,
        notes=notes + [
            "Prompt mapped into a structured compositional CAD spec.",
            "This is still a stub translator, not the final model stage.",
            "Replace the stub router with a real HF endpoint later.",
        ],
        suspicious_input=suspicious_input,
        fallback_level=fallback_level,
    )
    _CACHE[key] = response.model_dump()
    return response


@app.get("/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        environment=settings.app_env,
        rate_limit_per_hour=settings.rate_limit_per_hour,
        cache_entries=len(_CACHE),
        jobs_in_memory=len(_JOBS),
    )


@app.post("/v1/generate-spec", response_model=GenerateSpecResponse)
def generate_spec(payload: GenerateSpecRequest, request: Request, x_api_key: str | None = Header(default=None)) -> GenerateSpecResponse:
    _check_auth(x_api_key)
    _enforce_rate_limit(_rate_limit_key(request, payload.session_id))
    return _generate_spec(payload)


@app.post("/v1/jobs", response_model=JobRecord)
def create_job(payload: CreateJobRequest, request: Request, x_api_key: str | None = Header(default=None)) -> JobRecord:
    _check_auth(x_api_key)
    _enforce_rate_limit(_rate_limit_key(request, payload.session_id))

    if len(payload.prompt.strip()) > settings.max_prompt_length:
        raise HTTPException(status_code=400, detail="Prompt too long")

    spec_response = _generate_spec(GenerateSpecRequest(**payload.model_dump()))
    job = JobRecord(
        status="validated",
        prompt=payload.prompt,
        mode=payload.mode,
        output_type=payload.output_type,
        session_id=payload.session_id,
        prompt_hash=spec_response.prompt_hash,
        spec=spec_response.spec,
        notes=[
            "Job created in backend scaffold.",
            "Next step: persist to Supabase and enqueue worker execution.",
        ],
    )
    job.status = cast(str, "queued")
    save_job(job)
    job.artifacts = []
    return job


@app.get("/v1/jobs/{job_id}", response_model=JobRecord)
def get_job(job_id: str, x_api_key: str | None = Header(default=None)) -> JobRecord:
    _check_auth(x_api_key)
    job = repo_get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_with_artifacts(job)


@app.post("/v1/jobs/{job_id}/artifacts", response_model=ArtifactUploadResponse)
async def upload_job_artifact(
    job_id: str,
    kind: ArtifactKind = Form(...),
    file: UploadFile = File(...),
    x_api_key: str | None = Header(default=None),
) -> ArtifactUploadResponse:
    _check_auth(x_api_key)

    job = repo_get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not _storage_ready():
        raise HTTPException(status_code=503, detail="Supabase storage not configured")

    blob = await file.read()
    if not blob:
        raise HTTPException(status_code=400, detail="Empty file upload")
    if len(blob) > settings.storage_max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large for configured upload limit")

    suffix = os.path.splitext(file.filename or "")[1].lower()
    safe_suffix = suffix if suffix in {".stl", ".step", ".stp", ".png", ".jpg", ".jpeg", ".webp"} else ""
    storage_key = posixpath.join("jobs", job_id, f"{kind}{safe_suffix}")
    content_type = file.content_type or "application/octet-stream"

    _upload_bytes_to_supabase_storage(storage_key, blob, content_type)
    saved = repo_create_artifact(job_id, kind, storage_key, len(blob))
    return ArtifactUploadResponse(artifact=_artifact_to_record(saved))


@app.post("/v1/generate")
def generate_and_return(request: GenerateSpecRequest, x_api_key: str | None = Header(default=None)):
    _check_auth(x_api_key)
    
    # Generate spec using existing endpoint
    spec = _generate_spec(request)
    
    # Generate build123d code
    code = render_code_from_spec(spec.model_dump())
    
    # Return the code as text
    return {"code": code, "status": "ready"}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": settings.app_name,
        "docs": "/docs",
        "health": "/v1/health",
        "jobs": "/v1/jobs",
    }
