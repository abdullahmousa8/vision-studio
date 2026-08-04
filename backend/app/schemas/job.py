from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.job import JobStatus


class BoundingBox(BaseModel):
    x: float = Field(..., gt=0, description="Length in mm")
    y: float = Field(..., gt=0, description="Width in mm")
    z: float = Field(..., gt=0, description="Height in mm")


class PartManifest(BaseModel):
    id: int
    name: str = Field(..., pattern=r"^[a-z_][a-z0-9_]*$")
    priority: int = Field(..., ge=1, le=10)
    dependencies: list[int] = Field(default_factory=list)
    bounding_box: BoundingBox
    key_features: list[str] = Field(default_factory=list, max_length=20)
    material: str | None = None
    manufacturing_hint: str | None = None

    @field_validator("dependencies")
    @classmethod
    def no_self_dependency(cls, v, info):
        if "id" in info.data and info.data["id"] in v:
            raise ValueError("Part cannot depend on itself")
        return v


class DecompositionResult(BaseModel):
    task_type: Literal["3d_model"] = "3d_model"
    object_name: str
    complexity_score: float = Field(..., ge=1.0, le=10.0)
    estimated_parts: int = Field(..., ge=1, le=50)
    global_parameters: dict[str, Any]
    parts: list[PartManifest]
    assembly_order: list[int]

    @field_validator("assembly_order")
    @classmethod
    def valid_assembly_order(cls, v, info):
        part_ids = {p.id for p in info.data.get("parts", [])}
        if not all(pid in part_ids for pid in v):
            raise ValueError("assembly_order contains invalid part IDs")
        return v


class CreateJobRequest(BaseModel):
    prompt: str = Field(..., min_length=5, max_length=2000)
    mode: Literal["3d_model"] = "3d_model"
    detail_level: Literal["low", "medium", "high"] = "medium"
    model_source: Literal["local", "remote", "auto"] = "auto"
    reference_image: str | None = Field(None, max_length=5_000_000)


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    status: JobStatus
    progress: int
    created_at: datetime
    updated_at: datetime
    result_url: str | None = None
    preview_url: str | None = None
    error_message: str | None = None
    cost_estimate_usd: float = 0.0
    cost_actual_usd: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: dict[str, Any] | None = None
    request_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
