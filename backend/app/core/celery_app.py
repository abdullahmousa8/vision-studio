from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "gemini_vision_studio",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_default_queue="default",
    task_routes={
        "app.workers.pipeline.*": {"queue": "pipeline"},
        "app.workers.dlq.*": {"queue": "dlq"},
    },
    beat_schedule={
        "report-infra-metrics": {
            "task": "app.workers.metrics_beat.report_infra_metrics",
            "schedule": 15.0,
        },
    },
)

celery_app.autodiscover_tasks(["app.workers"])

# Explicit registration: autodiscover only finds a `tasks` submodule, which we
# don't have, so every task module must be imported here to be visible to the
# worker and beat processes.
from app.workers import dlq, metrics_beat, pipeline  # noqa: E402,F401
