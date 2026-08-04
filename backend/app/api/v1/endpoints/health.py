
import asyncio

import httpx
from fastapi import APIRouter, HTTPException
from redis import Redis
from sqlalchemy import text

from app.core.config import settings
from app.core.minio_client import minio_client

router = APIRouter(prefix="/health", tags=["health"])


async def _run_blocking(fn):
    return await asyncio.to_thread(fn)


def _check_database() -> str:
    from app.core.database import sync_engine

    try:
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:
        return f"error: {exc}"


def _check_redis() -> str:
    try:
        Redis.from_url(settings.redis_url).ping()
        return "ok"
    except Exception as exc:
        return f"error: {exc}"


def _check_minio() -> str:
    try:
        minio_client.list_buckets()
        return "ok"
    except Exception as exc:
        return f"error: {exc}"


def _check_ollama() -> str:
    try:
        resp = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        return "ok" if resp.status_code == 200 else "unreachable"
    except Exception as exc:
        return f"error: {exc}"


@router.get("/")
async def health_check():
    checks = {
        "database": await _run_blocking(_check_database),
        "redis": await _run_blocking(_check_redis),
        "minio": await _run_blocking(_check_minio),
        "ollama": await asyncio.wait_for(_run_blocking(_check_ollama), timeout=8),
    }
    all_ok = all(v == "ok" for v in checks.values())
    if not all_ok:
        raise HTTPException(
            status_code=503,
            detail={"status": "unhealthy", "checks": checks},
        )
    return {"status": "healthy", "checks": checks}


@router.get("/live")
async def liveness_check():
    return {"status": "alive"}


@router.get("/ready")
async def readiness_check():
    return {"status": "ready"}
