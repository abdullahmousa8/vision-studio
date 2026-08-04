import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="Integration tests require a running Postgres/Redis/MinIO stack (RUN_INTEGRATION=1)",
)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def _auth_headers(client, email="test@example.com"):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "super-secret"},
    )
    if resp.status_code == 409:
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "super-secret"},
        )
    assert resp.status_code in (201, 200), resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


class TestJobPipeline:
    def test_register_and_me(self, client):
        headers = _auth_headers(client, "me@example.com")
        resp = client.get("/api/v1/users/me", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == "me@example.com"

    def test_create_and_poll_job(self, client):
        headers = _auth_headers(client, "job@example.com")
        create = client.post(
            "/api/v1/jobs/",
            json={"prompt": "simple cube 10mm", "mode": "3d_model", "detail_level": "low"},
            headers=headers,
        )
        assert create.status_code == 201
        job_id = create.json()["job_id"]

        import time

        status = "pending"
        # Free-tier remote models are slow (~1 min per LLM call) and the worker
        # runs jobs serially, so allow several minutes for a terminal state.
        for _ in range(360):
            resp = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
            status = resp.json()["status"]
            if status in ("completed", "failed", "cancelled"):
                break
            time.sleep(1)

        assert status in ("completed", "failed"), f"job ended in unexpected state: {status}"

    def test_cancel_job(self, client):
        headers = _auth_headers(client, "cancel@example.com")
        create = client.post(
            "/api/v1/jobs/",
            json={"prompt": "a very slow complex object", "mode": "3d_model"},
            headers=headers,
        )
        assert create.status_code == 201
        job_id = create.json()["job_id"]

        cancel = client.post(f"/api/v1/jobs/{job_id}/cancel", headers=headers)
        assert cancel.status_code == 200

    def test_job_not_found(self, client):
        headers = _auth_headers(client, "other@example.com")
        resp = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000", headers=headers)
        assert resp.status_code == 404
