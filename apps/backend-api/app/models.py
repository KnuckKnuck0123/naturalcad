from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

ModeType = Literal["fast", "balanced", "quality"]
CadModeType = Literal["part", "assembly", "sketch"]
OutputType = Literal["3d_solid", "surface", "2d_vector", "1d_path"]
ActorType = Literal["guest", "user"]
RunStatus = Literal[
    "submitted",
    "resolving_spec",
    "awaiting_clarification",
    "generating_code",
    "executing",
    "publishing",
    "completed",
    "failed",
]
AttachmentStatus = Literal["reserved", "processing", "ready", "failed", "deleted"]


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


class HealthResponse(BaseModel):
    status: str
    version: str


class GuestSessionRequest(BaseModel):
    device_id: str | None = Field(default=None, max_length=256)


class AuthSessionRequest(BaseModel):
    access_token: str = Field(min_length=20)


class SessionResponse(BaseModel):
    session_id: str
    actor_type: ActorType
    created_at: datetime
    expires_at: datetime
    quotas: dict[str, int]


class ModelProfile(BaseModel):
    id: ModeType
    label: str
    model: str
    max_prompt_chars: int
    max_tokens: int
    timeout_seconds: int


class CreateProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    mode: CadModeType = "part"
    output_type: OutputType = "3d_solid"


class ProjectResponse(BaseModel):
    id: str
    title: str
    mode: CadModeType
    output_type: OutputType
    owner_session_id: str
    created_at: datetime
    updated_at: datetime


class ProjectPublicResponse(BaseModel):
    id: str
    title: str
    mode: CadModeType
    output_type: OutputType
    created_at: datetime
    updated_at: datetime


class PartSpec(BaseModel):
    spec_version: str = "2.0"
    intent: str
    mode: CadModeType = "part"
    output_type: OutputType = "3d_solid"
    units: Literal["mm"] = "mm"
    semantic_part: dict[str, Any] = Field(default_factory=dict)
    geometry: dict[str, Any] = Field(default_factory=dict)
    dimensions: dict[str, float] = Field(default_factory=dict)
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class ParameterControl(BaseModel):
    key: str
    label: str
    min: float
    max: float
    step: float
    value: float


class VersionResponse(BaseModel):
    id: str
    project_id: str
    parent_version_id: str | None = None
    prompt: str
    profile: ModeType
    model: str
    artifacts: dict[str, str] = Field(default_factory=dict)
    generated_code: str = ""
    parameters: list[ParameterControl] = Field(default_factory=list)
    spec: PartSpec | None = None
    spec_delta: list[dict[str, Any]] = Field(default_factory=list)
    change_summary: str = ""
    status: Literal["completed", "failed"]
    error: str | None = None
    created_at: datetime


class MessageResponse(BaseModel):
    id: str
    project_id: str
    role: Literal["user", "assistant"]
    content: str
    attachment_ids: list[str] = Field(default_factory=list)
    run_id: str | None = None
    version_id: str | None = None
    created_at: datetime


class GenerationRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    profile: ModeType = "balanced"
    parent_version_id: str | None = None
    attachment_ids: list[str] = Field(default_factory=list, max_length=3)
    idempotency_key: str = Field(min_length=8, max_length=128)


class ClarificationRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=2000)


class GenerationRunResponse(BaseModel):
    id: str
    project_id: str
    session_id: str
    parent_version_id: str | None = None
    idempotency_key: str
    message: str
    attachment_ids: list[str] = Field(default_factory=list)
    profile: ModeType = "balanced"
    status: RunStatus
    draft_spec: PartSpec | None = None
    spec_delta: list[dict[str, Any]] = Field(default_factory=list)
    change_summary: str = ""
    clarification_questions: list[str] = Field(default_factory=list)
    error: str | None = None
    version_id: str | None = None
    telemetry: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class AttachmentInitRequest(BaseModel):
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    size_bytes: int = Field(gt=0, le=8 * 1024 * 1024)


class AttachmentResponse(BaseModel):
    id: str
    project_id: str
    owner_session_id: str
    status: AttachmentStatus
    content_type: str
    size_bytes: int
    storage_key: str
    sanitized_storage_key: str | None = None
    width: int | None = None
    height: int | None = None
    checksum_sha256: str | None = None
    upload_url: str | None = None
    preview_url: str | None = None
    expires_at: datetime
    created_at: datetime


# Kept during the client migration; new callers use GenerationRequest.
class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    profile: ModeType = "balanced"


class UpdateParametersRequest(BaseModel):
    updates: dict[str, float]


class ProjectDetailResponse(BaseModel):
    project: ProjectPublicResponse
    versions: list[VersionResponse]
    messages: list[MessageResponse] = Field(default_factory=list)
    runs: list[GenerationRunResponse] = Field(default_factory=list)
    attachments: list[AttachmentResponse] = Field(default_factory=list)
