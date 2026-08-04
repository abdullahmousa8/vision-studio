from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger("dlq")


@celery_app.task(name="app.workers.dlq.review_task", bind=True, max_retries=1)
def review_task(self, job_id: str, task_name: str, error: str, traceback: str):
    """Consumes permanently failed tasks for manual/automated review."""
    logger.error(
        "dlq.review",
        job_id=job_id,
        failed_task=task_name,
        error=error,
        traceback=traceback[-2000:],
    )
    # v2: enqueue an auto-fix job, notify the user, etc.
    return {"job_id": job_id, "reviewed": True}
