from contextlib import asynccontextmanager
import os
from pathlib import Path
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    generate_latest,
    multiprocess,
)
from starlette.responses import Response

from app.api.v1 import endpoints
from app.core import (
    metrics,  # noqa: F401
    retry_config,  # noqa: F401  (registers retry/failure signals)
)
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.core.minio_client import ensure_bucket
from app.workers import dlq, pipeline  # noqa: F401  (registers Celery tasks)

setup_logging()
logger = get_logger("main")


def _scrape_registry() -> CollectorRegistry | None:
    """Multiprocess-aware registry when the shared metrics dir is configured.

    Returns None when running without PROMETHEUS_MULTIPROC_DIR (e.g. tests),
    in which case the default in-process registry is scraped instead.
    """
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        try:
            multiprocess.MultiProcessCollector(registry)
            return registry
        except Exception as exc:
            logger.warning("metrics.multiprocess_collector_failed", error=str(exc))
    return None


SCRAPE_REGISTRY = _scrape_registry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ensure_bucket()
        logger.info("main.minio_bucket_ready", bucket=settings.minio_bucket)
    except Exception as exc:
        logger.warning("main.minio_bucket_unavailable", error=str(exc))
    yield


app = FastAPI(
    title="Gemini Vision Studio API",
    version="0.1.0",
    description="AI 3D content generation pipeline: text -> OpenSCAD -> STL",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("api.unhandled_error", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "request_id": request.headers.get("x-request-id", ""),
        },
    )


@app.middleware("http")
async def http_metrics_middleware(request: Request, call_next):
    path = request.url.path
    if path == "/metrics" or path.startswith("/assets/"):
        return await call_next(request)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        metrics.http_requests_total.labels(method=request.method, path=path, status="500").inc()
        raise
    else:
        metrics.http_requests_total.labels(
            method=request.method, path=path, status=str(response.status_code)
        ).inc()
    finally:
        metrics.http_request_duration.labels(method=request.method, path=path).observe(
            time.perf_counter() - start
        )
    return response


app.include_router(endpoints.health.router)
app.include_router(endpoints.auth.router, prefix=settings.api_v1_prefix)
app.include_router(endpoints.users.router, prefix=settings.api_v1_prefix)
app.include_router(endpoints.jobs.router, prefix=settings.api_v1_prefix)


@app.get("/metrics", include_in_schema=False)
async def metrics_endpoint():
    if SCRAPE_REGISTRY is not None:
        return Response(content=generate_latest(SCRAPE_REGISTRY), media_type=CONTENT_TYPE_LATEST)
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
SPA_ENABLED = (FRONTEND_DIST / "index.html").is_file()


@app.get("/", include_in_schema=False)
async def root():
    if SPA_ENABLED:
        return FileResponse(FRONTEND_DIST / "index.html")
    return {"name": settings.app_name, "docs": "/docs", "health": "/health"}


# Single-origin production serving: when a built frontend exists (frontend/dist),
# FastAPI serves the SPA so the app runs from one origin (e.g. behind Traefik)
# without a separate static server. Dev mode uses Vite on :5173 and is unaffected.
if SPA_ENABLED:
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/health", include_in_schema=False)
    async def health_no_slash():
        return RedirectResponse("/health/")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        # API-ish paths that reach the SPA fallback do not exist -> real 404,
        # not index.html.
        if full_path.startswith(("api/", "metrics/", "docs/", "health/")):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
