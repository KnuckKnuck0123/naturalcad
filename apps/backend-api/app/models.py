from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

ModeType = Literal["fast", "balanced", "quality"]
CadModeType = Literal["part", "assembly", "sketch"]
OutputType = Literal["3d_solid", "surface", "2d_vector", "1d_path"]
ActorType = Literal["guest", "user"]


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


class HealthResponse(BaseModel):
    status: str
    version: str


class GuestSessionRequest(BaseModel):
    device_id: str | None = Field(default=None, max_length=256)


class SessionResponse(BaseModel):
    session_id: str
    actor_type: ActorType
    created_at: datetime
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


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    profile: ModeType = "balanced"
    image_urls: list[str] = Field(default_factory=list, max_length=3)


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
    status: Literal["completed", "failed"]
    error: str | None = None
    created_at: datetime


class UpdateParametersRequest(BaseModel):
    updates: dict[str, float]


class ProjectDetailResponse(BaseModel):
    project: ProjectResponse
    versions: list[VersionResponse]
