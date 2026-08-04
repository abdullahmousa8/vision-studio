# Gemini Vision Studio

Turn a text prompt into a validated, printable 3D model (STL). FastAPI +
Celery pipeline calls an LLM to decompose the request into parts and generate
OpenSCAD, validates and renders each part, assembles, and exports an STL you
can preview in the browser and print.

**Status: MVP complete — launch pack ready (Week 12).**

## Architecture

```
Browser (Vite + React, Three.js viewer)
   │  /api /health
   ▼
Traefik ── HTTPS + Let's Encrypt (production) / Vite proxy (local)
   ▼
FastAPI (auth, jobs API, /metrics)
   │                          ┌─ worker ─ Celery pipeline: decompose → generate → validate → assemble → export
   │                          └─ beat   ─ periodic infra metrics (queue depth, VRAM)
   ▼
PostgreSQL  Redis  MinIO (STL artifacts)  Ollama/OpenRouter/GROK (LLM)
   ▼
Prometheus + Grafana (observability)   backup cron (pg_dump + MinIO mirror)
```

- Pipeline state machine (ADR-001), Celery queues `pipeline` / `dlq` / `default`.
- LLM routing: Ollama (local) → OpenRouter → GROK, with retries and metrics.
- Metrics in multiprocess mode shared by API + worker (Prometheus scrapes API once).
- Beat runs as a separate process (Celery `-B` is unsupported on Windows).

## Repository layout

```
backend/    FastAPI app, Celery workers, OpenSCAD pipeline, alembic, local scripts
frontend/   React + Vite + Three.js (ModelViewer), nginx/Dockerfile for prod
monitoring/ dev Prometheus + Grafana (docker compose)
deploy/     production launch pack (compose, Traefik, backups, security audit)
docker-compose.prod.yml   production stack (single command)
```

## Local development (Windows)

Requires local Postgres, Redis, MinIO, Ollama (see `backend/scripts/local/README.md`).

```powershell
# one command: postgres + redis + minio + ollama + api + worker + beat
powershell -ExecutionPolicy Bypass -File backend\scripts\local\Start-All.ps1
Invoke-RestMethod http://localhost:8000/health

# frontend
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api → :8000)
```

Tests: `backend\.venv\Scripts\python -m pytest tests -q` (35 passed / 5 skipped).

Metrics: `http://localhost:8000/metrics`. Full monitoring stack (dev):
`docker compose -f monitoring\docker-compose.yml up -d` → Prometheus :9090, Grafana :3000.

## Production deployment (Linux VPS, Docker + Compose v2)

### Prerequisites
- Ubuntu/Debian VPS with Docker + Compose v2 (`docker compose version`).
- DNS `A` records: `APP_DOMAIN` and `API_DOMAIN` → server IP.
- Ports 80/443 open. (Ollama/GPU optional: either a separate host, or a GPU
  server with `nvidia-container-toolkit` and `--profile llm`.)

### Steps
```bash
cd /opt/gemini-vision-studio
cp deploy/.env.production.example .env
# edit .env: APP_DOMAIN, API_DOMAIN, LETSENCRYPT_EMAIL,
#            POSTGRES_PASSWORD, MINIO_ROOT_PASSWORD, GF_ADMIN_PASSWORD,
#            OLLAMA_BASE_URL (Linux: http://<ollama-host-ip>:11434)

bash deploy/init-secrets.sh      # writes ./secrets/*.txt (JWT + API keys)

docker compose -f docker-compose.prod.yml up -d --build
```

### Verify
```bash
docker compose -f docker-compose.prod.yml ps
curl -s https://<APP_DOMAIN>/health        # {"database":"ok","redis":"ok","minio":"ok"}
curl -s https://<API_DOMAIN>/docs          # Swagger
docker compose -f docker-compose.prod.yml logs -f api worker beat backup
```
First Let's Encrypt issuance takes ~1 min; until then the site answers on HTTP
(redirect) only.

### Set the LLM source
Register, log in, create a job with `model_source=local` for Ollama or
`model_source=openrouter` for OpenRouter. GROK requires credits at
https://console.x.ai (currently: team has no credits).

## Backup & disaster recovery

Automatic daily backup (default 03:00 UTC, configurable via `BACKUP_SCHEDULE`):
- PostgreSQL logical dump (`pg_dump -F c`)
- MinIO `artifacts` bucket mirror (`mc mirror`)
- compressed into `./backups/<timestamp>.tar.gz`, 7-day retention.

```bash
# run manually
docker compose -f docker-compose.prod.yml run --rm backup /usr/local/bin/backup.sh
# restore newest (or a specific <timestamp>)
docker compose -f docker-compose.prod.yml run --rm backup /usr/local/bin/restore.sh [timestamp]
```
Targets: **RPO = 24h, RTO ≈ 1h** (DR procedure in `deploy/backup/restore.sh`).

## Monitoring

- Grafana: `https://<APP_DOMAIN>:3000` is NOT exposed; use SSH tunnel:
  `ssh -L 3000:localhost:3000 user@server`, then open `http://localhost:3000`
  (admin / `GF_ADMIN_PASSWORD`). Dashboard: Studio Overview.
- Prometheus: alerts for API down, high failure rates, queue backlog, VRAM.
- Metrics exported by the app: `jobs_created_total`, `jobs_completed_total`,
  `active_jobs`, `api_calls_total`, `http_requests_total`,
  `http_request_duration_seconds`, `celery_queue_depth`, `ollama_vram_usage_mb`.

**Native Windows (no Docker):** `monitoring\native\run-monitoring.ps1` starts
Prometheus :9090 + Grafana :3000, `run-traefik.ps1` serves the whole app over
HTTPS at `https://localhost`. See `monitoring\native\README.md` (includes the
single-origin artifact endpoint used by the 3D viewer and the gotchas hit on a
non-admin Win11 host).

## Operations

- **Rotating secrets:** regenerate `./secrets/jwt_secret.txt` (invalidates all
  sessions) or API keys, then `docker compose -f docker-compose.prod.yml up -d --force-recreate api worker beat`.
- **Upgrading:** pull new code, `docker compose -f docker-compose.prod.yml up -d --build` (migrate runs automatically via `entrypoint.sh`).
- **Security:** see `deploy/SECURITY.md` (audit checklist). Backend runs non-root;
  secrets via Docker secrets; TLS/HSTS via Traefik.

## Demo script (record a launch video)

1. `Start-All.ps1` (or prod stack up) → open app, register a fresh user.
2. Create job: prompt `a simple drinking cup`, mode `3D model`, `model_source=local`.
3. Show progress transitions decomposing → generating → assembling → exporting.
4. Open the 3D viewer (STL renders in-browser via Three.js), rotate/zoom.
5. Show `http://localhost:8000/metrics` counters; open Grafana Studio Overview.
6. Explain the DR story: `./backups` + restore script.

## Roadmap

12-week MVP:

| Week | Deliverable | Status |
|------|-------------|--------|
| 1–2 | Infra + auth/API | done |
| 3–4 | Celery pipeline + Ollama | done |
| 5–6 | Part decomposition + OpenSCAD validation/export | done |
| 7–8 | Frontend UI + 3D viewer | done |
| 9–10 | Monitoring + OpenRouter fallback | done |
| 11 | Testing + polish | done |
| 12 | Launch prep (compose, SSL, backups, security, README) | done |

Deferred to v2: image generation, Blender bridge, sub-decomposition, semantic cache, real-time collaboration.
