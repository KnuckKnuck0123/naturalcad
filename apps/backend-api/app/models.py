from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

ModeType = Literal["part", "assembly", "sketch"]
OutputType = Literal["2d_vector", "surface", "3d_solid"]
JobStatus = Literal["submitted", "validated", "queued", "running", "completed", "failed"]


class GenerateSpecRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=1000)
    mode: ModeType = "part"
    output_type: OutputType = "3d_solid"
    session_id: str | None = None


class CreateJobRequest(BaseModel):
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
    suspicious_input: bool = False
    fallback_level: str = "normal"


class JobRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: JobStatus = "submitted"
    prompt: str
    mode: ModeType = "part"
    output_type: OutputType = "3d_solid"
    session_id: str | None = None
    prompt_hash: str | None = None
    spec: CadSpec | None = None
    notes: list[str] = []
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    environment: str
    rate_limit_per_hour: int
    cache_entries: int
    jobs_in_memory: int
