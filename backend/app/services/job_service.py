from datetime import UTC, datetime
from uuid import UUID

from celery.result import AsyncResult
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.metrics import active_jobs, job_duration, jobs_completed, jobs_created
from app.models.job import Job, JobStatus
from app.schemas.job import CreateJobRequest

logger = get_logger("job_service")

TERMINAL_STATUSES = {
    JobStatus.COMPLETED.value,
    JobStatus.FAILED.value,
    JobStatus.CANCELLED.value,
}


class JobNotFoundError(Exception):
    pass


def _new_job(user_id: UUID, request: CreateJobRequest) -> Job:
    return Job(
        user_id=user_id,
        prompt=request.prompt,
        mode=request.mode,
        detail_level=request.detail_level,
        model_source=request.model_source,
        status=JobStatus.PENDING.value,
        progress=0,
        cost_estimate_usd=0.0,
        metadata={},
    )


async def create_job(db: AsyncSession, user_id: UUID, request: CreateJobRequest) -> Job:
    job = _new_job(user_id, request)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    jobs_created.labels(mode=job.mode, detail_level=job.detail_level).inc()
    active_jobs.inc()
    return job


async def get_job(db: AsyncSession, job_id: UUID, user_id: UUID) -> Job | None:
    job = await db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))
    return job


async def list_jobs(db: AsyncSession, user_id: UUID, limit: int = 50, offset: int = 0) -> list[Job]:
    result = await db.scalars(
        select(Job)
        .where(Job.user_id == user_id)
        .order_by(Job.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result)


def _record_terminal(created_at: datetime, status_str: str) -> None:
    duration = (datetime.now(UTC) - created_at).total_seconds()
    jobs_completed.labels(status=status_str).inc()
    job_duration.labels(status=status_str).observe(duration)
    active_jobs.dec()


async def update_job_status(
    db: AsyncSession,
    job_id: UUID,
    status: JobStatus,
    progress: int | None = None,
    result_url: str | None = None,
    error_message: str | None = None,
    metadata: dict | None = None,
) -> Job:
    job = await db.get(Job, job_id)
    if not job:
        raise JobNotFoundError(f"Job {job_id} not found")

    was_terminal = job.status in TERMINAL_STATUSES
    job.status = status.value
    if progress is not None:
        job.progress = progress
    if result_url is not None:
        job.result_url = result_url
    if error_message is not None:
        job.error_message = error_message
    if metadata:
        job.meta = {**(job.meta or {}), **metadata}
    if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        job.completed_at = datetime.now(UTC)
        if not was_terminal:
            _record_terminal(job.created_at, status.value)

    await db.commit()
    await db.refresh(job)
    return job


async def cancel_job(db: AsyncSession, job_id: UUID, user_id: UUID) -> Job | None:
    job = await get_job(db, job_id, user_id)
    if not job:
        return None
    if job.status not in (
        JobStatus.COMPLETED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value,
    ):
        cancelled_at = datetime.now(UTC).isoformat()
        return await update_job_status(
            db, job_id, JobStatus.CANCELLED, metadata={"cancelled_at": cancelled_at}
        )
    return job


async def delete_job(db: AsyncSession, job_id: UUID, user_id: UUID) -> Job | None:
    """Hard-delete a job owned by the user (also revokes a running pipeline)."""
    job = await get_job(db, job_id, user_id)
    if not job:
        return None
    if job.status not in TERMINAL_STATUSES:
        task_id = (job.meta or {}).get("celery_task_id")
        if task_id:
            try:
                AsyncResult(task_id).revoke(terminate=True)
            except Exception:
                logger.warning("job.delete_revoke_failed", job_id=str(job_id))
    await db.delete(job)
    await db.commit()
    return job


# --- Sync variants used by Celery workers ---

def get_job_sync(db: Session, job_id: UUID) -> Job | None:
    return db.get(Job, job_id)


def update_job_status_sync(
    db: Session,
    job_id: UUID,
    status: JobStatus,
    progress: int | None = None,
    result_url: str | None = None,
    error_message: str | None = None,
    metadata: dict | None = None,
) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise JobNotFoundError(f"Job {job_id} not found")

    was_terminal = job.status in TERMINAL_STATUSES
    job.status = status.value
    if progress is not None:
        job.progress = progress
    if result_url is not None:
        job.result_url = result_url
    if error_message is not None:
        job.error_message = error_message
    if metadata:
        job.meta = {**(job.meta or {}), **metadata}
    if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        job.completed_at = datetime.now(UTC)
        if not was_terminal:
            _record_terminal(job.created_at, status.value)

    db.commit()
    db.refresh(job)
    return job
