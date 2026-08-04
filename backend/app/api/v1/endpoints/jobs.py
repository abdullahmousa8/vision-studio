import uuid
from typing import Literal

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import get_db
from app.core.minio_client import minio_client
from app.models.user import User
from app.schemas.job import CreateJobRequest, JobResponse
from app.services import job_service
from app.workers.pipeline import pipeline_task

ARTIFACT_KINDS: dict[str, tuple[str, str]] = {
    "model": ("stl_object", "model.stl"),
    "preview": ("preview_object", "preview.png"),
}

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _to_response(job) -> JobResponse:
    return JobResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        created_at=job.created_at,
        updated_at=job.updated_at,
        result_url=job.result_url,
        preview_url=(job.meta or {}).get("preview_url"),
        error_message=job.error_message,
        cost_estimate_usd=float(job.cost_estimate_usd or 0.0),
        cost_actual_usd=float(job.cost_actual_usd or 0.0),
        metadata=job.meta or {},
    )


@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    request: CreateJobRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await job_service.create_job(db, current_user.id, request)

    # Dispatch the pipeline to Celery (fire and forget) and remember the task id
    # so the job can be revoked later.
    task_result = pipeline_task.delay(job_id=str(job.id))
    job.meta = {**(job.meta or {}), "celery_task_id": task_result.id}
    await db.commit()
    await db.refresh(job)

    return _to_response(job)


@router.get("/", response_model=list[JobResponse])
async def list_jobs(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    jobs = await job_service.list_jobs(db, current_user.id, limit=min(limit, 100), offset=offset)
    return [_to_response(job) for job in jobs]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await job_service.get_job(db, job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _to_response(job)


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await job_service.cancel_job(db, job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    # Revoke the Celery workflow by the stored task id (terminate running tasks).
    task_id = (job.meta or {}).get("celery_task_id")
    if task_id:
        AsyncResult(task_id, app=celery_app).revoke(terminate=True)
    return {"status": "cancelled"}


@router.delete("/{job_id}")
async def delete_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await job_service.delete_job(db, job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    for key in ("stl_object", "preview_object"):
        object_name = (job.meta or {}).get(key)
        if object_name:
            try:
                minio_client.remove_object(settings.minio_bucket, object_name)
            except Exception:
                pass
    return {"status": "deleted"}


@router.get("/{job_id}/artifact/{kind}")
async def get_artifact(
    job_id: uuid.UUID,
    kind: Literal["model", "preview"],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await job_service.get_job(db, job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not ready")

    meta_key, filename = ARTIFACT_KINDS[kind]
    object_name = (job.meta or {}).get(meta_key)
    if not object_name:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    try:
        response = minio_client.get_object(settings.minio_bucket, object_name)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    media_type = "model/stl" if kind == "model" else "image/png"

    def _iter():
        try:
            yield from response.stream(amt=1024 * 256)
        finally:
            response.release_conn()

    return StreamingResponse(
        _iter(),
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
