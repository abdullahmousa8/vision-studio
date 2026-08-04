from contextlib import contextmanager
from datetime import timedelta
from io import BytesIO
from uuid import UUID

from celery import Task, chain, chord, group
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.core.minio_client import minio_client
from app.models.job import Job, JobStatus
from app.schemas.job import PartManifest
from app.services.assembly_engine import AssemblyEngine
from app.services.export_engine import ExportEngine
from app.services.job_service import (
    update_job_status_sync,
)
from app.services.model_router import CodeGenerator, LLMClientError, ModelRouter, Planner
from app.services.validators import OpenSCADValidator

logger = get_logger("pipeline")

ARTIFACTS_BUCKET = settings.minio_bucket


@contextmanager
def sync_session():
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class PipelineTask(Task):
    """Base task that marks the job FAILED and forwards to the DLQ on terminal failure."""

    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        job_id = self._extract_job_id(args, kwargs)
        if job_id:
            try:
                with sync_session() as db:
                    update_job_status_sync(
                        db,
                        job_id,
                        JobStatus.FAILED,
                        error_message=str(exc),
                        metadata={"failed_task": self.name},
                    )
            except Exception:
                logger.exception("pipeline.failed_state_update", job_id=str(job_id))
            celery_app.send_task(
                "app.workers.dlq.review_task",
                args=[str(job_id), self.name, str(exc), einfo.traceback],
                queue="dlq",
            )
        logger.error("pipeline.task_failed", task_name=self.name, job_id=str(job_id), error=str(exc))
        super().on_failure(exc, task_id, args, kwargs, einfo)

    @staticmethod
    def _extract_job_id(args, kwargs) -> UUID | None:
        """Locate a job UUID inside task args/kwargs (chain links receive the
        previous task's result dict as their first positional arg)."""
        import re

        candidate = args[0] if args else kwargs.get("job_id")
        text = str(candidate)
        match = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", text)
        if match:
            try:
                return UUID(match.group(0))
            except ValueError:
                return None
        return None


def _mark(job_id: str, status: JobStatus, progress: int, **extra):
    with sync_session() as db:
        return update_job_status_sync(db, UUID(job_id), status, progress=progress, **extra)


def _resolve_client(source: str, task_type: str):
    """Return a client honoring the circuit breaker with remote fallback."""
    client = ModelRouter.select(source, task_type)
    if client.provider == "openrouter" and not settings.openrouter_api_key:
        logger.warning("pipeline.no_openrouter_key_fallback_to_ollama")
        from app.services.model_router import OllamaClient

        return OllamaClient()
    return client


@celery_app.task(
    base=PipelineTask,
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    name="app.workers.pipeline.pipeline_task",
)
def pipeline_task(self, job_id: str):
    """Entry point: runs the full pipeline as a Celery chain."""
    workflow = chain(
        decompose_task.s(job_id),
        generate_parts_task.s(),
    )
    workflow.apply_async()
    return {"job_id": job_id, "status": "scheduled"}


@celery_app.task(base=PipelineTask, bind=True, max_retries=2, name="app.workers.pipeline.decompose_task")
def decompose_task(self, job_id: str):
    """Stage 1: decompose the object description into a part manifest."""
    logger.info("job.decompose_started", job_id=job_id)
    _mark(job_id, JobStatus.DECOMPOSING, 10)

    try:
        with sync_session() as db:
            job = db.get(Job, UUID(job_id))
            source = job.model_source if job else "auto"
            prompt = job.prompt if job else ""
            detail_level = job.detail_level if job else "medium"

        client = _resolve_client(source, "planning")
        planner = Planner(client)
        manifest = planner.decompose(prompt, detail_level)

        with sync_session() as db:
            job = db.get(Job, UUID(job_id))
            job.meta = {**(job.meta or {}), "part_manifest": manifest.model_dump()}
            job.meta["estimated_parts"] = len(manifest.parts)
            db.commit()

        logger.info("job.decompose_completed", job_id=job_id, parts_count=len(manifest.parts))
        return {"job_id": job_id, "manifest": manifest.model_dump()}
    except (LLMClientError, ValueError) as exc:
        logger.error("job.decompose_failed", job_id=job_id, error=str(exc))
        raise self.retry(exc=exc) from exc


@celery_app.task(base=PipelineTask, bind=True, max_retries=2, name="app.workers.pipeline.generate_parts_task")
def generate_parts_task(self, previous_result: dict):
    """Stage 2: generate each part's OpenSCAD source in parallel (chord)."""
    job_id = previous_result["job_id"]
    manifest_data = previous_result["manifest"]
    logger.info("job.generate_started", job_id=job_id, parts_count=len(manifest_data["parts"]))

    _mark(job_id, JobStatus.GENERATING, 30)

    parts = [PartManifest.model_validate(p) for p in manifest_data["parts"]]
    part_tasks = [generate_single_part_task.s(job_id, part.model_dump()) for part in parts]

    # Apply the chord; its callback (collect_parts_task) continues the remaining
    # stages. We must NOT return the AsyncResult (not JSON serializable), nor a
    # returned chord signature (not executed as a continuation by Celery).
    chord(group(part_tasks), collect_parts_task.s(job_id)).apply_async()
    return {"job_id": job_id, "parts": []}


@celery_app.task(base=PipelineTask, bind=True, max_retries=3, name="app.workers.pipeline.generate_single_part_task")
def generate_single_part_task(self, job_id: str, part_data: dict):
    """Generate OpenSCAD source for a single part and store it in MinIO.

    Tries each model candidate in order and only persists a part once its
    code passes deterministic OpenSCAD validation (free LLMs are flaky).
    """
    part = PartManifest.model_validate(part_data)

    with sync_session() as db:
        job = db.get(Job, UUID(job_id))
        source = job.model_source if job else "auto"

    validator = OpenSCADValidator()
    code = None
    last_error = "no models attempted"
    attempts = []
    for client, model in ModelRouter.client_candidates(source, "coding"):
        generator = CodeGenerator(client)
        try:
            candidate = generator.generate(part, object_name=part.name, model=model)
        except LLMClientError as exc:
            last_error = str(exc)
            attempts.append(f"{model}:{last_error}")
            continue
        result = validator.check_syntax(f"{candidate}\n{part.name}();\n")
        if not validator.available or result.valid:
            code = candidate
            logger.info("job.part_generated", job_id=job_id, part_id=part.id, model=model)
            break
        last_error = result.error
        attempts.append(f"{model}:{last_error}")

    if code is None:
        raise LLMClientError(
            f"All models produced invalid OpenSCAD for part {part.id} ({part.name}): "
            f"{last_error} | attempts: {', '.join(attempts)}"
        )

    object_name = f"jobs/{job_id}/parts/{part.id}.scad"
    payload = code.encode("utf-8")
    minio_client.put_object(
        ARTIFACTS_BUCKET,
        object_name,
        BytesIO(payload),
        length=len(payload),
    )
    return {"part_id": part.id, "name": part.name, "object_name": object_name, "code_length": len(code)}


@celery_app.task(base=PipelineTask, name="app.workers.pipeline.collect_parts_task")
def collect_parts_task(results: list, job_id: str):
    """Chord callback: merge per-part results and continue the remaining stages."""
    logger.info("job.parts_collected", job_id=job_id, parts_count=len(results))

    chain(
        validate_parts_task.s({"job_id": job_id, "parts": results}),
        assemble_task.s(),
        export_task.s(),
    ).apply_async()

    return {"job_id": job_id, "parts": results}


@celery_app.task(base=PipelineTask, bind=True, max_retries=1, name="app.workers.pipeline.validate_parts_task")
def validate_parts_task(self, previous_result: dict):
    """Stage 3: deterministically validate every generated part's syntax."""
    job_id = previous_result["job_id"]
    parts = previous_result["parts"]
    logger.info("job.validate_started", job_id=job_id)

    _mark(job_id, JobStatus.VALIDATING, 60)

    validator = OpenSCADValidator()
    errors = []

    for part_info in parts:
        response = minio_client.get_object(ARTIFACTS_BUCKET, part_info["object_name"])
        code = response.read().decode("utf-8")
        # Parts are generated as module definitions only; instantiate the module
        # at top level so standalone validation renders real geometry.
        result = validator.check_syntax(f"{code}\n{part_info['name']}();\n")
        if not result.valid:
            errors.append(
                {"part_id": part_info["part_id"], "error": result.error, "line": result.line_number}
            )

    if errors:
        logger.warning("job.validation_failed", job_id=job_id, errors=errors)
        # v2: send to LLM-based auto-fix. MVP: fail directly.
        raise ValueError(f"Validation failed for {len(errors)} parts: {errors[:3]}")

    logger.info("job.validation_passed", job_id=job_id)
    return previous_result


@celery_app.task(base=PipelineTask, bind=True, max_retries=2, name="app.workers.pipeline.assemble_task")
def assemble_task(self, previous_result: dict):
    """Stage 4: merge validated part sources into one assembly SCAD file."""
    job_id = previous_result["job_id"]
    parts = previous_result["parts"]
    logger.info("job.assemble_started", job_id=job_id)

    _mark(job_id, JobStatus.ASSEMBLING, 75)

    assembled_parts = []
    for part_info in parts:
        response = minio_client.get_object(ARTIFACTS_BUCKET, part_info["object_name"])
        code = response.read().decode("utf-8")
        assembled_parts.append(
            {
                "id": part_info["part_id"],
                "name": part_info["name"],
                "code": code,
            }
        )

    assembly_code = AssemblyEngine().build(assembled_parts, job_id)
    object_name = f"jobs/{job_id}/assembly.scad"
    assembly_payload = assembly_code.encode("utf-8")
    minio_client.put_object(
        ARTIFACTS_BUCKET, object_name, BytesIO(assembly_payload), length=len(assembly_payload)
    )

    return {"job_id": job_id, "assembly_object": object_name}


@celery_app.task(base=PipelineTask, bind=True, max_retries=2, name="app.workers.pipeline.export_task")
def export_task(self, previous_result: dict):
    """Stage 5: render STL + PNG and publish presigned download URLs."""
    job_id = previous_result["job_id"]
    assembly_object = previous_result["assembly_object"]
    logger.info("job.export_started", job_id=job_id)

    _mark(job_id, JobStatus.EXPORTING, 90)

    exporter = ExportEngine()
    stl_object = exporter.to_stl(assembly_object, job_id)
    preview_object = exporter.to_preview(assembly_object, job_id)

    result_url = minio_client.presigned_get_object(ARTIFACTS_BUCKET, stl_object, expires=timedelta(hours=24))
    preview_url = minio_client.presigned_get_object(ARTIFACTS_BUCKET, preview_object, expires=timedelta(hours=24))

    _mark(
        job_id,
        JobStatus.COMPLETED,
        100,
        result_url=result_url,
        metadata={"preview_url": preview_url, "stl_object": stl_object, "preview_object": preview_object},
    )

    logger.info("job.completed", job_id=job_id, result_url=result_url)
    return {"job_id": job_id, "status": "completed"}
