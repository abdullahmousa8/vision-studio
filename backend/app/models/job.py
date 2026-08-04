from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.part import Part
    from app.models.user import User


class JobStatus(enum.StrEnum):
    PENDING = "pending"
    DECOMPOSING = "decomposing"
    GENERATING = "generating"
    VALIDATING = "validating"
    ASSEMBLING = "assembling"
    EXPORTING = "exporting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(50), default="3d_model")
    detail_level: Mapped[str] = mapped_column(String(20), default="medium")
    model_source: Mapped[str] = mapped_column(String(20), default="auto")
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.PENDING.value, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    result_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_estimate_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0.0)
    cost_actual_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0.0)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="jobs")
    parts: Mapped[list[Part]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
