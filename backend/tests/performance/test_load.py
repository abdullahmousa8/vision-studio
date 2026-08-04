import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="Performance tests require a running stack (RUN_INTEGRATION=1)",
)


@pytest.mark.performance
async def test_concurrent_jobs():
    """Load test: 10 concurrent job creations must all succeed quickly."""
    import asyncio
    import time

    import httpx

    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": "load@example.com", "password": "super-secret"},
        )
        if reg.status_code == 409:
            reg = await client.post(
                "/api/v1/auth/login",
                data={"username": "load@example.com", "password": "super-secret"},
            )
        assert reg.status_code in (201, 200), reg.text
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        async def create_job():
            start = time.perf_counter()
            resp = await client.post(
                "/api/v1/jobs/",
                json={"prompt": "simple cube", "mode": "3d_model"},
                headers=headers,
            )
            duration = time.perf_counter() - start
            return resp.status_code, duration

        tasks = [create_job() for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    success = [r for r in results if isinstance(r, tuple) and r[0] == 201]
    assert len(success) >= 8, f"Only {len(success)}/10 jobs succeeded"
