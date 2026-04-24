from __future__ import annotations

from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request

from .config import settings
from .models import (
    CreateProjectRequest,
    GenerateRequest,
    GuestSessionRequest,
    HealthResponse,
    ModelProfile,
    ProjectDetailResponse,
    ProjectResponse,
    SessionResponse,
    UpdateParametersRequest,
    VersionResponse,
)
from .repository import InMemoryRepo, extract_slider_controls

app = FastAPI(title=settings.app_name, version=settings.app_version)
repo = InMemoryRepo()

MODEL_PROFILES: dict[str, ModelProfile] = {
    "fast": ModelProfile(
        id="fast",
        label="Fast",
        model=settings.mode_fast_model,
        max_prompt_chars=700,
        max_tokens=800,
        timeout_seconds=45,
    ),
    "balanced": ModelProfile(
        id="balanced",
        label="Balanced",
        model=settings.mode_balanced_model,
        max_prompt_chars=1200,
        max_tokens=1800,
        timeout_seconds=90,
    ),
    "quality": ModelProfile(
        id="quality",
        label="Quality",
        model=settings.mode_quality_model,
        max_prompt_chars=1800,
        max_tokens=2600,
        timeout_seconds=140,
    ),
}


def _validate_gateway_secret(x_api_key: str | None) -> None:
    if settings.api_shared_secret and x_api_key != settings.api_shared_secret:
        raise HTTPException(status_code=401, detail={"error": "Invalid API key"})


def _session_from_header(x_session_id: str | None) -> SessionResponse:
    if not x_session_id:
        raise HTTPException(status_code=401, detail={"error": "Missing x-session-id"})
    session = repo.get_session(x_session_id)
    if not session:
        raise HTTPException(status_code=401, detail={"error": "Unknown session"})
    return session


def _assert_project_access(project: ProjectResponse, session: SessionResponse) -> None:
    if project.owner_session_id != session.session_id:
        raise HTTPException(status_code=403, detail={"error": "Project access denied"})


async def _call_cad_worker(prompt: str, mode: str, output_type: str) -> dict[str, Any]:
    if not settings.cad_worker_url:
        return {
            "success": True,
            "urls": {},
            "generated_code": "",
            "model": "local/mock",
        }

    headers = {}
    if settings.cad_worker_api_key:
        headers["x-api-key"] = settings.cad_worker_api_key

    payload = {
        "prompt": prompt,
        "mode": mode,
        "output_type": output_type,
    }

    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(settings.cad_worker_url, json=payload, headers=headers)

    if resp.status_code >= 400:
        detail = resp.text[:500]
        raise HTTPException(status_code=502, detail={"error": f"CAD worker failed: {detail}"})

    return resp.json()


@app.get("/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.app_version)


@app.post("/v1/auth/guest", response_model=SessionResponse)
def create_guest_session(
    payload: GuestSessionRequest,
    x_api_key: str | None = Header(default=None),
) -> SessionResponse:
    _validate_gateway_secret(x_api_key)
    return repo.create_guest_session(settings.guest_runs_per_window)


@app.get("/v1/models", response_model=list[ModelProfile])
def list_models(
    x_api_key: str | None = Header(default=None),
) -> list[ModelProfile]:
    _validate_gateway_secret(x_api_key)
    return [MODEL_PROFILES["fast"], MODEL_PROFILES["balanced"], MODEL_PROFILES["quality"]]


@app.post("/v1/projects", response_model=ProjectResponse)
def create_project(
    payload: CreateProjectRequest,
    x_api_key: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
) -> ProjectResponse:
    _validate_gateway_secret(x_api_key)
    session = _session_from_header(x_session_id)
    return repo.create_project(session.session_id, payload.title, payload.mode, payload.output_type)


@app.get("/v1/projects/{project_id}", response_model=ProjectDetailResponse)
def get_project(
    project_id: str,
    x_api_key: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
) -> ProjectDetailResponse:
    _validate_gateway_secret(x_api_key)
    session = _session_from_header(x_session_id)

    project = repo.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"error": "Project not found"})

    _assert_project_access(project, session)
    return ProjectDetailResponse(project=project, versions=repo.list_versions(project_id))


@app.post("/v1/projects/{project_id}/generate", response_model=VersionResponse)
async def generate_version(
    project_id: str,
    payload: GenerateRequest,
    request: Request,
    x_api_key: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
) -> VersionResponse:
    _validate_gateway_secret(x_api_key)
    session = _session_from_header(x_session_id)

    project = repo.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"error": "Project not found"})
    _assert_project_access(project, session)

    profile = MODEL_PROFILES[payload.profile]
    if len(payload.prompt) > profile.max_prompt_chars:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Prompt too long for {payload.profile} mode (max {profile.max_prompt_chars})"},
        )

    max_runs = settings.guest_runs_per_window if session.actor_type == "guest" else settings.signed_runs_per_window
    allowed, remaining = repo.check_and_consume_quota(
        session.session_id,
        max_runs=max_runs,
        window_seconds=settings.rate_window_seconds,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail={"error": "Quota exceeded for this session window"})

    versions = repo.list_versions(project_id)
    parent_version = versions[-1] if versions else None
    final_prompt = payload.prompt
    if parent_version:
        final_prompt = (
            f"Continue from previous version {parent_version.id}. "
            f"Previous prompt: {parent_version.prompt}\n\n"
            f"User refinement: {payload.prompt}"
        )

    worker = await _call_cad_worker(final_prompt, project.mode, project.output_type)
    success = bool(worker.get("success")) and not worker.get("error")

    return repo.create_version(
        project_id=project_id,
        prompt=payload.prompt,
        profile=payload.profile,
        model=profile.model,
        artifacts=worker.get("urls", {}),
        generated_code=worker.get("generated_code", ""),
        status="completed" if success else "failed",
        error=worker.get("error"),
        parent_version_id=parent_version.id if parent_version else None,
        parameters=extract_slider_controls(payload.prompt),
    )


@app.patch("/v1/projects/{project_id}/versions/{version_id}/parameters", response_model=VersionResponse)
def update_parameters(
    project_id: str,
    version_id: str,
    payload: UpdateParametersRequest,
    x_api_key: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
) -> VersionResponse:
    _validate_gateway_secret(x_api_key)
    session = _session_from_header(x_session_id)

    project = repo.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"error": "Project not found"})
    _assert_project_access(project, session)

    versions = repo.list_versions(project_id)
    base = next((v for v in versions if v.id == version_id), None)
    if not base:
        raise HTTPException(status_code=404, detail={"error": "Version not found"})

    controls = []
    for control in base.parameters:
        if control.key in payload.updates:
            value = float(payload.updates[control.key])
            value = max(control.min, min(control.max, value))
            control = control.model_copy(update={"value": value})
        controls.append(control)

    update_note = ", ".join(f"{k}={v}" for k, v in payload.updates.items())
    return repo.create_version(
        project_id=project_id,
        prompt=f"Parameter update from {version_id}: {update_note}",
        profile=base.profile,
        model=base.model,
        artifacts=base.artifacts,
        generated_code=base.generated_code,
        status="completed",
        error=None,
        parent_version_id=base.id,
        parameters=controls,
    )


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "health": "/v1/health",
        "docs": "/docs",
    }
