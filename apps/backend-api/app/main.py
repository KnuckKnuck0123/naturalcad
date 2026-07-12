from __future__ import annotations

import secrets
import uuid
from datetime import timedelta
from typing import Any

import httpx
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .generation import process_generation
from .models import (
    AttachmentInitRequest, AttachmentResponse, AuthSessionRequest, ClarificationRequest,
    CreateProjectRequest, GenerateRequest, GenerationRequest, GenerationRunResponse,
    GuestSessionRequest, HealthResponse, ModelProfile, ProjectDetailResponse, ProjectPublicResponse,
    ProjectResponse, SessionResponse, UpdateParametersRequest, VersionResponse, utc_now,
)
from .repository import InMemoryRepo, extract_slider_controls
from .repository_supabase import SupabaseRepo
from .storage import StorageError, SupabaseImageStorage, sanitize_image

app = FastAPI(title=settings.app_name, version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["content-type", "x-api-key", "x-session-id", "idempotency-key"],
)
repo = (
    SupabaseRepo(url=settings.supabase_url, service_role_key=settings.supabase_service_role_key)
    if settings.supabase_url and settings.supabase_service_role_key else InMemoryRepo()
)
storage = SupabaseImageStorage()

MODEL_PROFILES = {
    "fast": ModelProfile(id="fast", label="Fast", model=settings.mode_fast_model, max_prompt_chars=700, max_tokens=800, timeout_seconds=45),
    "balanced": ModelProfile(id="balanced", label="Balanced", model=settings.mode_balanced_model, max_prompt_chars=1200, max_tokens=1800, timeout_seconds=90),
    "quality": ModelProfile(id="quality", label="Quality", model=settings.mode_quality_model, max_prompt_chars=1800, max_tokens=2600, timeout_seconds=140),
}


@app.middleware("http")
async def reject_untrusted_browser_origins(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method in {"POST", "PATCH", "DELETE"} and origin and origin not in settings.allowed_origins:
        return Response(status_code=403, content="Untrusted origin")
    return await call_next(request)


def _gateway(x_api_key: str | None) -> None:
    if settings.environment == "production" and not settings.api_shared_secret:
        raise HTTPException(503, detail={"error": "Gateway authentication is not configured"})
    if settings.api_shared_secret and (
        not x_api_key or not secrets.compare_digest(x_api_key, settings.api_shared_secret)
    ):
        raise HTTPException(401, detail={"error": "Invalid API key"})


def _session(x_session_id: str | None) -> SessionResponse:
    if not x_session_id:
        raise HTTPException(401, detail={"error": "Missing session"})
    session = repo.get_session(x_session_id)
    if not session:
        raise HTTPException(401, detail={"error": "Unknown session"})
    return session


def _project(project_id: str, session: SessionResponse) -> ProjectResponse:
    project = repo.get_project(project_id)
    if not project:
        raise HTTPException(404, detail={"error": "Project not found"})
    if project.owner_session_id != session.session_id:
        raise HTTPException(403, detail={"error": "Project access denied"})
    return project


def _authorize(x_api_key: str | None, x_session_id: str | None, project_id: str) -> tuple[SessionResponse, ProjectResponse]:
    _gateway(x_api_key)
    session = _session(x_session_id)
    return session, _project(project_id, session)


def _enforce_profile_message_length(profile_id: str, message: str) -> None:
    profile = MODEL_PROFILES[profile_id]
    if len(message) > profile.max_prompt_chars:
        raise HTTPException(
            422,
            detail={
                "error": f"Message exceeds the {profile.label.lower()} profile limit",
                "profile": profile.id,
                "max_prompt_chars": profile.max_prompt_chars,
            },
        )


def _count_total_tokens(payload: Any) -> int:
    if isinstance(payload, dict):
        total = int(payload.get("total_tokens", 0) or 0)
        return total + sum(_count_total_tokens(value) for key, value in payload.items() if key != "total_tokens")
    if isinstance(payload, list):
        return sum(_count_total_tokens(item) for item in payload)
    return 0


def _project_guest_generation_count(project_id: str, session_id: str) -> int:
    return sum(1 for run in repo.list_runs(project_id) if run.session_id == session_id)


def _project_guest_token_total(project_id: str, session_id: str) -> int:
    total = 0
    for run in repo.list_runs(project_id):
        if run.session_id != session_id:
            continue
        total += _count_total_tokens(run.telemetry)
    return total


def _estimated_generation_token_cost(profile_id: str, attachment_count: int) -> int:
    profile = MODEL_PROFILES[profile_id]
    estimate = profile.max_tokens + settings.spec_resolution_max_tokens
    if attachment_count:
        estimate += settings.vision_summary_max_tokens
    return estimate


def _enforce_guest_project_limits(
    session: SessionResponse,
    project_id: str,
    *,
    profile_id: str,
    attachment_count: int = 0,
    count_as_new_generation: bool,
) -> None:
    if session.actor_type != "guest":
        return

    if settings.guest_project_generation_cap > 0 and count_as_new_generation:
        generation_count = _project_guest_generation_count(project_id, session.session_id)
        if generation_count >= settings.guest_project_generation_cap:
            raise HTTPException(
                429,
                detail={
                    "error": "Guest project generation cap reached",
                    "limit_type": "project_generation_cap",
                    "project_generation_cap": settings.guest_project_generation_cap,
                },
            )

    if settings.guest_project_token_cap > 0:
        used_tokens = _project_guest_token_total(project_id, session.session_id)
        estimated_cost = _estimated_generation_token_cost(profile_id, attachment_count)
        remaining_tokens = settings.guest_project_token_cap - used_tokens
        if remaining_tokens <= 0 or remaining_tokens < estimated_cost:
            raise HTTPException(
                429,
                detail={
                    "error": "Guest project token budget reached",
                    "limit_type": "project_token_cap",
                    "project_token_cap": settings.guest_project_token_cap,
                    "used_tokens": used_tokens,
                    "estimated_next_run_tokens": estimated_cost,
                },
            )


@app.get("/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version="0.2.0")


@app.post("/v1/auth/guest", response_model=SessionResponse)
def create_guest_session(payload: GuestSessionRequest, x_api_key: str | None = Header(None)) -> SessionResponse:
    _gateway(x_api_key)
    return repo.create_guest_session(settings.guest_runs_per_window)


@app.post("/v1/auth/session", response_model=SessionResponse)
async def create_user_session(payload: AuthSessionRequest, x_api_key: str | None = Header(None)) -> SessionResponse:
    _gateway(x_api_key)
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(503, detail={"error": "Supabase auth is not configured"})
    headers = {"Authorization": f"Bearer {payload.access_token}", "apikey": settings.supabase_service_role_key}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{settings.supabase_url.rstrip('/')}/auth/v1/user", headers=headers)
    if response.status_code >= 400 or not response.json().get("id"):
        raise HTTPException(401, detail={"error": "Invalid access token"})
    return repo.create_user_session(response.json()["id"], settings.signed_runs_per_window)


@app.get("/v1/models", response_model=list[ModelProfile])
def list_models(x_api_key: str | None = Header(None)) -> list[ModelProfile]:
    _gateway(x_api_key)
    return list(MODEL_PROFILES.values())


@app.post("/v1/projects", response_model=ProjectPublicResponse)
def create_project(payload: CreateProjectRequest, x_api_key: str | None = Header(None), x_session_id: str | None = Header(None)) -> ProjectResponse:
    _gateway(x_api_key)
    session = _session(x_session_id)
    return repo.create_project(session.session_id, payload.title, payload.mode, payload.output_type)


@app.get("/v1/projects/{project_id}", response_model=ProjectDetailResponse)
def get_project(project_id: str, x_api_key: str | None = Header(None), x_session_id: str | None = Header(None)) -> ProjectDetailResponse:
    _, project = _authorize(x_api_key, x_session_id, project_id)
    return ProjectDetailResponse(
        project=ProjectPublicResponse(**project.model_dump()), versions=repo.list_versions(project_id), messages=repo.list_messages(project_id),
        runs=repo.list_runs(project_id), attachments=_attachments_with_previews(project_id),
    )


def _attachments_with_previews(project_id: str) -> list[AttachmentResponse]:
    rows = repo.list_attachments(project_id)
    if not storage.configured:
        return rows
    out = []
    for row in rows:
        key = row.sanitized_storage_key if row.status == "ready" else None
        preview = storage.create_signed_read(key, 600) if key else None
        out.append(row.model_copy(update={"upload_url": None, "preview_url": preview}))
    return out


@app.post("/v1/projects/{project_id}/attachments/init", response_model=AttachmentResponse, status_code=201)
def init_attachment(project_id: str, payload: AttachmentInitRequest, x_api_key: str | None = Header(None), x_session_id: str | None = Header(None)) -> AttachmentResponse:
    session, _ = _authorize(x_api_key, x_session_id, project_id)
    if not storage.configured:
        raise HTTPException(503, detail={"error": "Private image storage is not configured"})
    attachment_id = f"att_{uuid.uuid4().hex[:12]}"
    key = f"quarantine/{session.session_id}/{project_id}/{attachment_id}"
    try:
        attachment = repo.create_attachment(
            project_id=project_id, session_id=session.session_id, content_type=payload.content_type,
            size_bytes=payload.size_bytes, storage_key=key, upload_url=None,
            max_active=settings.max_guest_attachments,
        )
    except ValueError as exc:
        raise HTTPException(409, detail={"error": str(exc)}) from exc
    try:
        upload_url = storage.create_signed_upload(key)
        return attachment.model_copy(update={"upload_url": upload_url})
    except StorageError as exc:
        repo.update_attachment(project_id, attachment.id, status="failed")
        raise HTTPException(502, detail={"error": str(exc)}) from exc


@app.post("/v1/projects/{project_id}/attachments/{attachment_id}/complete", response_model=AttachmentResponse)
def complete_attachment(project_id: str, attachment_id: str, x_api_key: str | None = Header(None), x_session_id: str | None = Header(None)) -> AttachmentResponse:
    session, _ = _authorize(x_api_key, x_session_id, project_id)
    attachment = repo.get_attachment(project_id, attachment_id)
    if not attachment or attachment.owner_session_id != session.session_id:
        raise HTTPException(404, detail={"error": "Attachment not found"})
    if attachment.status == "ready":
        preview = storage.create_signed_read(attachment.sanitized_storage_key, 600) if attachment.sanitized_storage_key else None
        return attachment.model_copy(update={"preview_url": preview, "upload_url": None})
    repo.update_attachment(project_id, attachment_id, status="processing", upload_url=None)
    try:
        raw = storage.download(attachment.storage_key)
        clean = sanitize_image(raw, attachment.content_type)
        sanitized_key = f"sanitized/{session.session_id}/{project_id}/{attachment.id}.jpg"
        storage.upload(sanitized_key, clean.data, clean.content_type)
        storage.delete([attachment.storage_key])
        ready = repo.update_attachment(
            project_id, attachment_id, status="ready", sanitized_storage_key=sanitized_key,
            content_type=clean.content_type, size_bytes=len(clean.data), width=clean.width, height=clean.height,
            checksum_sha256=clean.checksum_sha256, upload_url=None,
        )
        return ready.model_copy(update={"preview_url": storage.create_signed_read(sanitized_key, 600)})
    except StorageError as exc:
        repo.update_attachment(project_id, attachment_id, status="failed", upload_url=None)
        raise HTTPException(400, detail={"error": str(exc)}) from exc


@app.get("/v1/projects/{project_id}/attachments", response_model=list[AttachmentResponse])
def list_attachments(project_id: str, x_api_key: str | None = Header(None), x_session_id: str | None = Header(None)) -> list[AttachmentResponse]:
    _authorize(x_api_key, x_session_id, project_id)
    return _attachments_with_previews(project_id)


@app.delete("/v1/projects/{project_id}/attachments/{attachment_id}", status_code=204)
def delete_attachment(project_id: str, attachment_id: str, x_api_key: str | None = Header(None), x_session_id: str | None = Header(None)) -> Response:
    session, _ = _authorize(x_api_key, x_session_id, project_id)
    attachment = repo.get_attachment(project_id, attachment_id)
    if not attachment or attachment.owner_session_id != session.session_id:
        raise HTTPException(404, detail={"error": "Attachment not found"})
    storage.delete([key for key in [attachment.storage_key, attachment.sanitized_storage_key] if key])
    repo.update_attachment(project_id, attachment_id, status="deleted", upload_url=None, preview_url=None)
    return Response(status_code=204)


@app.post("/v1/internal/cleanup-attachments")
def cleanup_expired_attachments(x_api_key: str | None = Header(None)) -> dict[str, int]:
    _gateway(x_api_key)
    if not settings.api_shared_secret:
        raise HTTPException(503, detail={"error": "Cleanup requires a configured gateway secret"})
    cleaned = 0
    for attachment in repo.list_expired_attachments():
        try:
            storage.delete([key for key in [attachment.storage_key, attachment.sanitized_storage_key] if key])
            repo.update_attachment(attachment.project_id, attachment.id, status="deleted", upload_url=None, preview_url=None)
            cleaned += 1
        except StorageError:
            continue
    return {"cleaned": cleaned}


@app.post("/v1/projects/{project_id}/generations", response_model=GenerationRunResponse, status_code=status.HTTP_202_ACCEPTED)
def create_generation(project_id: str, payload: GenerationRequest, background: BackgroundTasks, x_api_key: str | None = Header(None), x_session_id: str | None = Header(None)) -> GenerationRunResponse:
    session, project = _authorize(x_api_key, x_session_id, project_id)
    _enforce_profile_message_length(payload.profile, payload.message)
    _enforce_guest_project_limits(
        session,
        project_id,
        profile_id=payload.profile,
        attachment_count=len(payload.attachment_ids),
        count_as_new_generation=True,
    )
    if payload.parent_version_id and not repo.get_version(project_id, payload.parent_version_id):
        raise HTTPException(404, detail={"error": "Parent version not found"})
    for attachment_id in payload.attachment_ids:
        attachment = repo.get_attachment(project_id, attachment_id)
        if not attachment or attachment.owner_session_id != session.session_id or attachment.status != "ready":
            raise HTTPException(400, detail={"error": "Invalid or unready attachment"})
    run, created = repo.create_run(
        project_id=project_id, session_id=session.session_id, parent_version_id=payload.parent_version_id,
        idempotency_key=payload.idempotency_key, message=payload.message, attachment_ids=payload.attachment_ids,
        profile=payload.profile,
    )
    if not created:
        return run
    max_runs = settings.guest_runs_per_window if session.actor_type == "guest" else settings.signed_runs_per_window
    allowed, _ = repo.check_and_consume_quota(session.session_id, max_runs=max_runs, window_seconds=settings.rate_window_seconds)
    if not allowed:
        repo.update_run(project_id, run.id, status="failed", error="Quota exceeded")
        raise HTTPException(429, detail={"error": "Quota exceeded"})
    repo.create_message(project_id=project_id, role="user", content=payload.message, attachment_ids=payload.attachment_ids, run_id=run.id)
    background.add_task(process_generation, repo, run.id, project)
    return run


@app.get("/v1/projects/{project_id}/generations/{run_id}", response_model=GenerationRunResponse)
def get_generation(project_id: str, run_id: str, background: BackgroundTasks, x_api_key: str | None = Header(None), x_session_id: str | None = Header(None)) -> GenerationRunResponse:
    _, project = _authorize(x_api_key, x_session_id, project_id)
    run = repo.get_run(project_id, run_id)
    if not run:
        raise HTTPException(404, detail={"error": "Generation not found"})
    active = {"submitted", "resolving_spec", "generating_code", "executing", "publishing"}
    recovery_count = int(run.telemetry.get("recovery_count", 0))
    if run.status in active and run.updated_at < utc_now() - timedelta(minutes=5):
        if recovery_count >= 2:
            return repo.update_run(project_id, run.id, status="failed", error="Generation worker did not complete")
        telemetry = {**run.telemetry, "recovery_count": recovery_count + 1}
        run = repo.update_run(project_id, run.id, status="submitted", telemetry=telemetry)
        background.add_task(process_generation, repo, run.id, project)
    return run


@app.post("/v1/projects/{project_id}/generations/{run_id}/clarification", response_model=GenerationRunResponse, status_code=202)
def clarify_generation(project_id: str, run_id: str, payload: ClarificationRequest, background: BackgroundTasks, x_api_key: str | None = Header(None), x_session_id: str | None = Header(None)) -> GenerationRunResponse:
    session, project = _authorize(x_api_key, x_session_id, project_id)
    run = repo.get_run(project_id, run_id)
    if not run or run.status != "awaiting_clarification":
        raise HTTPException(409, detail={"error": "Generation is not awaiting clarification"})
    message = f"{run.message}\n\nClarification: {payload.answer}"
    _enforce_profile_message_length(run.profile, message)
    _enforce_guest_project_limits(
        session,
        project_id,
        profile_id=run.profile,
        attachment_count=len(run.attachment_ids),
        count_as_new_generation=False,
    )
    updated = repo.update_run(project_id, run_id, status="submitted", message=message, clarification_questions=[])
    repo.create_message(project_id=project_id, role="user", content=payload.answer, run_id=run.id)
    background.add_task(process_generation, repo, run.id, project)
    return updated


@app.post("/v1/projects/{project_id}/generate", response_model=VersionResponse)
def legacy_generate(project_id: str, payload: GenerateRequest, x_api_key: str | None = Header(None), x_session_id: str | None = Header(None)) -> VersionResponse:
    session, project = _authorize(x_api_key, x_session_id, project_id)
    _enforce_profile_message_length(payload.profile, payload.prompt)
    _enforce_guest_project_limits(
        session,
        project_id,
        profile_id=payload.profile,
        count_as_new_generation=True,
    )
    parent = repo.list_versions(project_id)[0] if repo.list_versions(project_id) else None
    run, _ = repo.create_run(
        project_id=project_id, session_id=session.session_id, parent_version_id=parent.id if parent else None,
        idempotency_key=f"legacy-{uuid.uuid4().hex}", message=payload.prompt, attachment_ids=[], profile=payload.profile,
    )
    repo.create_message(project_id=project_id, role="user", content=payload.prompt, run_id=run.id)
    process_generation(repo, run.id, project)
    completed = repo.get_run(project_id, run.id)
    if not completed or completed.status != "completed" or not completed.version_id:
        raise HTTPException(409, detail={"error": completed.error if completed else "Generation incomplete"})
    version = repo.get_version(project_id, completed.version_id)
    assert version is not None
    return version


@app.patch("/v1/projects/{project_id}/versions/{version_id}/parameters", response_model=VersionResponse)
def update_parameters(project_id: str, version_id: str, payload: UpdateParametersRequest, x_api_key: str | None = Header(None), x_session_id: str | None = Header(None)) -> VersionResponse:
    _authorize(x_api_key, x_session_id, project_id)
    base = repo.get_version(project_id, version_id)
    if not base:
        raise HTTPException(404, detail={"error": "Version not found"})
    controls = [c.model_copy(update={"value": max(c.min, min(c.max, float(payload.updates[c.key])))}) if c.key in payload.updates else c for c in base.parameters]
    return repo.create_version(
        project_id=project_id, prompt=f"Parameter update from {version_id}", profile=base.profile,
        model=base.model, artifacts=base.artifacts, generated_code=base.generated_code, status="completed",
        error=None, parent_version_id=base.id, parameters=controls, spec=base.spec,
        spec_delta=[{"op": "parameter_update", "value": payload.updates}], change_summary="Updated parameters.",
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"name": settings.app_name, "health": "/v1/health", "docs": "/docs"}
