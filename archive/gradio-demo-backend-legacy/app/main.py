from __future__ import annotations

import hashlib
import os
import re
import time
from collections import defaultdict, deque
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

load_dotenv()

APP_NAME = "NaturalCAD Backend"
API_SHARED_SECRET = os.getenv("API_SHARED_SECRET", "")
RATE_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", "20"))

app = FastAPI(title=APP_NAME, version="0.3.0")

_REQUESTS: dict[str, deque[float]] = defaultdict(deque)
_CACHE: dict[str, dict] = {}

ModeType = Literal["part", "assembly", "sketch"]
OutputType = Literal["2d_vector", "surface", "3d_solid"]


class GenerateSpecRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=1000)
    mode: ModeType = "part"
    output_type: OutputType = "3d_solid"
    session_id: str | None = None


class CadStyle(BaseModel):
    family: str = "industrial"
    heaviness: float = 0.6


class CadSpec(BaseModel):
    output_type: OutputType
    geometry_family: str
    units: str = "mm"
    parameters: dict[str, int | float | str]
    style: CadStyle


class GenerateSpecResponse(BaseModel):
    ok: bool = True
    cached: bool = False
    prompt_hash: str
    spec: CadSpec
    notes: list[str] = []
    model: str = "stub/template-router"


class HealthResponse(BaseModel):
    status: str
    rate_limit_per_hour: int
    cache_entries: int


def _check_auth(header_value: str | None) -> None:
    if API_SHARED_SECRET and header_value != API_SHARED_SECRET:
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
    if len(bucket) >= RATE_LIMIT_PER_HOUR:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    bucket.append(now)


def _normalize_prompt(prompt: str) -> str:
    return " ".join(prompt.lower().strip().split())


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


def _style_from_prompt(prompt: str, default_family: str) -> CadStyle:
    heaviness = 0.6
    family = default_family
    if any(word in prompt for word in ["heavy", "massive", "thick", "brutal"]):
        heaviness = 0.85
    elif any(word in prompt for word in ["light", "slim", "thin", "delicate"]):
        heaviness = 0.35

    if any(word in prompt for word in ["industrial", "steel", "metal"]):
        family = "industrial"
    elif any(word in prompt for word in ["structural", "truss", "frame"]):
        family = "structural"
    elif any(word in prompt for word in ["smooth", "soft", "shell", "canopy"]):
        family = "smooth"
    elif any(word in prompt for word in ["diagram", "profile", "elevation", "line"]):
        family = "diagrammatic"

    return CadStyle(family=family, heaviness=heaviness)


def _infer_spec(prompt: str, mode: ModeType, output_type: OutputType) -> CadSpec:
    p = prompt.lower()

    if output_type == "2d_vector" or mode == "sketch":
        family = "truss_elevation" if any(word in p for word in ["truss", "beam", "frame", "elevation"]) else "plate_profile"
        if family == "truss_elevation":
            params = {
                "span": _extract_number(p, ["span", "length", "width"], 140),
                "height": _extract_number(p, ["height", "rise"], 24),
                "panel_count": _extract_count(p, ["panels", "bays", "segments"], 7),
                "member_size": _extract_number(p, ["member", "thickness", "depth"], 3),
                "preview_thickness": 1,
            }
        else:
            params = {
                "width": _extract_number(p, ["width", "span"], 80),
                "height": _extract_number(p, ["height"], 50),
                "hole_count": _extract_count(p, ["holes", "bolt holes", "openings"], 4),
                "hole_diameter": _extract_number(p, ["hole diameter", "hole", "diameter"], 10),
                "preview_thickness": 1,
            }
        return CadSpec(
            output_type="2d_vector",
            geometry_family=family,
            parameters=params,
            style=_style_from_prompt(p, "diagrammatic"),
        )

    if output_type == "surface":
        family = "canopy_surface" if any(word in p for word in ["roof", "canopy", "shell", "surface"]) else "lofted_panel"
        if family == "canopy_surface":
            params = {
                "span": _extract_number(p, ["span", "width"], 160),
                "depth": _extract_number(p, ["depth", "length"], 90),
                "peak_height": _extract_number(p, ["peak", "height", "rise"], 38),
                "thickness": _extract_number(p, ["thickness"], 2),
            }
        else:
            params = {
                "width": _extract_number(p, ["width", "span"], 80),
                "depth": _extract_number(p, ["depth", "length"], 50),
                "rise": _extract_number(p, ["rise", "height"], 18),
                "thickness": _extract_number(p, ["thickness"], 2),
            }
        return CadSpec(
            output_type="surface",
            geometry_family=family,
            parameters=params,
            style=_style_from_prompt(p, "smooth"),
        )

    if any(word in p for word in ["truss", "beam", "frame", "girder"]):
        return CadSpec(
            output_type="3d_solid",
            geometry_family="truss_beam",
            parameters={
                "span": _extract_number(p, ["span", "length"], 140),
                "height": _extract_number(p, ["height", "rise"], 24),
                "panel_count": _extract_count(p, ["panels", "bays", "segments"], 7),
                "member_size": _extract_number(p, ["member", "thickness", "depth"], 3),
            },
            style=_style_from_prompt(p, "structural"),
        )

    if any(word in p for word in ["tower", "block", "monolith"]):
        return CadSpec(
            output_type="3d_solid",
            geometry_family="tower_block",
            parameters={
                "width": _extract_number(p, ["width"], 30),
                "length": _extract_number(p, ["length", "depth"], 30),
                "height": _extract_number(p, ["height"], 120),
                "notch": _extract_number(p, ["notch", "cut"], 10),
            },
            style=_style_from_prompt(p, "industrial"),
        )

    return CadSpec(
        output_type="3d_solid",
        geometry_family="bracket_plate",
        parameters={
            "width": _extract_number(p, ["width", "span"], 80),
            "height": _extract_number(p, ["height"], 50),
            "thickness": _extract_number(p, ["thickness"], 6),
            "hole_count": _extract_count(p, ["holes", "bolt holes", "openings"], 4),
            "hole_diameter": _extract_number(p, ["hole diameter", "hole", "diameter"], 10),
        },
        style=_style_from_prompt(p, "industrial"),
    )


@app.get("/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", rate_limit_per_hour=RATE_LIMIT_PER_HOUR, cache_entries=len(_CACHE))


@app.post("/v1/generate-spec", response_model=GenerateSpecResponse)
def generate_spec(payload: GenerateSpecRequest, request: Request, x_api_key: str | None = Header(default=None)) -> GenerateSpecResponse:
    _check_auth(x_api_key)
    _enforce_rate_limit(_rate_limit_key(request, payload.session_id))

    normalized = _normalize_prompt(payload.prompt)
    key = _prompt_hash(normalized, payload.mode, payload.output_type)

    if key in _CACHE:
        cached = dict(_CACHE[key])
        cached["cached"] = True
        return GenerateSpecResponse(**cached)

    spec = _infer_spec(normalized, payload.mode, payload.output_type)
    response = GenerateSpecResponse(
        prompt_hash=key,
        spec=spec,
        notes=[
            f"Mode: {payload.mode}",
            f"Output type: {payload.output_type}",
            "Prompt mapped into a structured CAD spec.",
            "Replace the stub router with a real HF endpoint later.",
        ],
    )
    _CACHE[key] = response.model_dump()
    return response


@app.get("/")
def root() -> dict[str, str]:
    return {"message": APP_NAME, "docs": "/docs", "health": "/v1/health"}
