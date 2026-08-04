"""Periodic (Celery beat) metric reporters.

Runs inside the worker and pushes infra gauges that only it can observe
(Redis queue depth, Ollama/GPU VRAM) into the shared multiprocess metrics dir.
"""

from redis import Redis

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import ollama_vram_usage, queue_depth
from app.services.model_router import ModelRouter

logger = get_logger("metrics_beat")

QUEUES = ("celery", "pipeline", "dlq")


@celery_app.task(name="app.workers.metrics_beat.report_infra_metrics", ignore_result=True)
def report_infra_metrics() -> None:
    try:
        client = Redis.from_url(settings.celery_broker_url, socket_timeout=5)
        total = sum(int(client.llen(q) or 0) for q in QUEUES)
        queue_depth.set(total)
    except Exception as exc:
        logger.warning("metrics_beat.queue_depth_failed", error=str(exc))

    try:
        vram = ModelRouter.vram_free_mb()
        if vram is not None:
            ollama_vram_usage.set(vram)
    except Exception as exc:
        logger.warning("metrics_beat.vram_failed", error=str(exc))
