from celery.signals import task_failure, task_retry

from app.core.logging import get_logger

logger = get_logger("retry")

RETRY_POLICY = {
    "app.workers.pipeline.decompose_task": {"max_retries": 2},
    "app.workers.pipeline.generate_single_part_task": {"max_retries": 3},
    "app.workers.pipeline.validate_parts_task": {"max_retries": 1},
    "app.workers.pipeline.assemble_task": {"max_retries": 2},
    "app.workers.pipeline.export_task": {"max_retries": 2},
}


@task_retry.connect
def log_retry(sender=None, task_id=None, exception=None, **kwargs):
    logger.warning(
        "task.retrying",
        task_name=sender.name,
        task_id=task_id,
        exception=str(exception),
    )


@task_failure.connect
def log_failure(sender=None, task_id=None, exception=None, **kwargs):
    logger.error(
        "task.failed",
        task_name=sender.name,
        task_id=task_id,
        exception=str(exception),
        args=kwargs.get("args"),
    )
