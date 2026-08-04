from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    name: str
    priority: int
    status: str
    code_object: str | None = None
    error_message: str | None = None
    created_at: datetime
