from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

ModeType = Literal["part", "assembly", "sketch"]
OutputType = Literal["2d_vector", "surface", "3d_solid"]
JobStatus = Literal["submitted", "validated", "queued", "running", "completed", "failed"]
ArtifactKind = Literal["stl", "step", "preview", "other"]
GenerationMode = Literal["reuse", "extend", "new"]
SymmetryType = Literal["bilateral", "radial", "asymmetric", "none"]
ValueType = int | float | str | bool


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


class SemanticPart(BaseModel):
    category: str | None = None
    function: str | None = None
    topology: list[str] = Field(default_factory=list)
    symmetry: SymmetryType = "none"


class GeometryFeature(BaseModel):
    name: str
    feature_type: str
    count: int | None = None
    attributes: dict[str, ValueType] = Field(default_factory=dict)


class GeometryPlan(BaseModel):
    primitive_strategy: list[str] = Field(default_factory=list)
    features: list[GeometryFeature] = Field(default_factory=list)


class ConstraintRecord(BaseModel):
    kind: str
    target: str
    value: ValueType | None = None
    reference: str | None = None
    notes: str | None = None


class SemanticStyle(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    symmetry: SymmetryType = "none"
    manufacturing_bias: str = "generic"


class FamilyHint(BaseModel):
    name: str | None = None
    generation_mode: GenerationMode = "new"
    parent_family: str | None = None
    confidence: float | None = None
    novelty_score: float | None = None


class DedupeHint(BaseModel):
    canonical_signature: str | None = None
    similar_to_job_id: str | None = None
    is_likely_duplicate: bool = False


class SemanticCadSpec(BaseModel):
    spec_version: str = "1.1"
    intent: str
    mode: ModeType = "part"
    output_type: OutputType = "3d_solid"
    units: str = "mm"
    semantic_part: SemanticPart = Field(default_factory=SemanticPart)
    family_hint: FamilyHint = Field(default_factory=FamilyHint)
    geometry: GeometryPlan = Field(default_factory=GeometryPlan)
    dimensions: dict[str, ValueType] = Field(default_factory=dict)
    constraints: list[ConstraintRecord] = Field(default_factory=list)
    style: SemanticStyle = Field(default_factory=SemanticStyle)
    dedupe: DedupeHint = Field(default_factory=DedupeHint)
    notes: list[str] = Field(default_factory=list)


class GenerateSpecResponse(BaseModel):
    ok: bool = True
    cached: bool = False
    prompt_hash: str
    spec: CadSpec | SemanticCadSpec
    notes: list[str] = []
    model: str = "stub/template-router"
    suspicious_input: bool = False
    fallback_level: str = "normal"


class ArtifactRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str
    kind: ArtifactKind
    storage_key: str
    size_bytes: int | None = None
    url: str | None = None
    created_at: str | None = None


class JobRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: JobStatus = "submitted"
    prompt: str
    mode: ModeType = "part"
    output_type: OutputType = "3d_solid"
    session_id: str | None = None
    prompt_hash: str | None = None
    spec: CadSpec | SemanticCadSpec | None = None
    notes: list[str] = Field(default_factory=list)
    error: str | None = None
    artifacts: list[ArtifactRecord] = Field(default_factory=list)


class ArtifactUploadResponse(BaseModel):
    ok: bool = True
    artifact: ArtifactRecord


class HealthResponse(BaseModel):
    status: str
    environment: str
    rate_limit_per_hour: int
    cache_entries: int
    jobs_in_memory: int
