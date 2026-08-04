# Security Audit — Gemini Vision Studio (production checklist)

Scope: single-server Docker Compose launch (Traefik + Postgres + Redis + MinIO
+ FastAPI/Celery + Vite/React). Status verified against `docker-compose.prod.yml`
and the application source. Items marked **MANUAL** need an operator action on
first deploy.

## Secrets

| # | Item | Status | Evidence |
|---|------|--------|----------|
| S1 | No secrets in source control | PASS | `.env` is git-ignored; backend `.dockerignore` excludes `.env` |
| S2 | Strong JWT signing secret, non-default | PASS* | `deploy/init-secrets.sh` writes `secrets/jwt_secret.txt`; read via `/run/secrets` in `config.py` |
| S3 | API keys via Docker secrets, not env for app keys | PASS* | `openrouter_key`, `grok_key`, `jwt_secret` mounted to `/run/secrets`; `config.py:get_secret` prefers secrets |
| S4 | DB / MinIO passwords not hard-coded in compose | PASS | `${POSTGRES_PASSWORD}`, `${MINIO_ROOT_PASSWORD}` required from `.env` (`:?` guard) |
| S5 | Secrets files permissions locked down | PASS* | `init-secrets.sh` sets `chmod 700` on `secrets/` |
| S6 | Restart secrets on rotation documented | PASS | README section "Rotating secrets" |

\* = MANUAL: run `bash deploy/init-secrets.sh` and fill `.env` before first deploy.

## Transport & TLS

| # | Item | Status | Evidence |
|---|------|--------|----------|
| T1 | TLS termination with valid certs | PASS* | Traefik + Let's Encrypt (`certificatesResolvers.letsencrypt`, HTTP-01) |
| T2 | Automatic HTTP→HTTPS redirect | PASS | `traefik.yml` entryPoint `web` redirect to `websecure` |
| T3 | HSTS headers | PASS | `dynamic.yml` middleware `security-headers`: `forceSTSHeader`, `stsSeconds=31536000` |
| T4 | No plaintext service ports exposed publicly | PASS | Only Traefik publishes 80/443; Postgres/Redis/MinIO are network-internal |
| T5 | Dashboard not internet-accessible | PASS | Traefik dashboard bound to `127.0.0.1:8080` |

\* = MANUAL: DNS records (`APP_DOMAIN`, `API_DOMAIN`) must point at the server.

## Application hardening

| # | Item | Status | Evidence |
|---|------|--------|----------|
| A1 | Never run user input as code (`eval`/`exec`) | PASS | Pipeline generates OpenSCAD source, validated and rendered by OpenSCAD CLI subprocess; no dynamic code execution |
| A2 | Parameterized DB queries | PASS | SQLAlchemy ORM/asyncpg across app |
| A3 | No prompt / user data logged verbatim | PASS | Structured logging truncates prompt (`prompt[:50]`) |
| A4 | CORS restricted to own origin | PASS | `CORS_ORIGINS=https://<APP_DOMAIN>` only |
| A5 | Rate limiting on auth/job endpoints | PASS | `RATE_LIMIT_PER_MINUTE` (default 10) enforced in app |
| A6 | Payload size cap on uploads | PASS | nginx `client_max_body_size 25m` |
| A7 | Health endpoints do not leak internals | PASS | `/health` returns only status names |
| A8 | Auth token expiry bounded | PASS | `JWT_EXPIRES_MINUTES` default 60 |
| A9 | Docker images run as non-root | PASS | Backend Dockerfile creates `app` user and runs as `app`; metrics/celery volume dirs pre-created with correct ownership |
| A10 | Dependency scanning enabled | MANUAL | Recommended: enable Dependabot/Snyk on the repo |

## Infrastructure & data

| # | Item | Status | Evidence |
|---|------|--------|----------|
| I1 | PostgreSQL durable storage | PASS | named volume `pgdata` |
| I2 | Redis persistence | PASS | `--appendonly yes` + volume |
| I3 | MinIO object storage durable | PASS | named volume `miniodata` |
| I4 | Daily automated backups (DB + objects) | PASS | `backup` service cron; `backup.sh` (pg_dump + mc mirror, 7-day retention) |
| I5 | Documented restore procedure | PASS | `deploy/backup/restore.sh` + README DR section |
| I6 | Service auto-restart on crash | PASS | `restart: unless-stopped` on all long-running services |
| I7 | Health-check gated startup | PASS | `depends_on: condition: service_healthy`; image HEALTHCHECK on `/health/live` |
| I8 | Capacity/VRAM monitoring + alerts | PASS | Prometheus + Grafana; alerts for VRAM, queue depth, failure rates |
| I9 | Cost guardrails for LLM APIs | PASS | `DAILY_BUDGET_USD` + `ALERT_THRESHOLD` settings |

## Corrective actions

- **S2 (first deploy):** verify `JWT_SECRET_KEY` is NOT the documented default.
  config.py falls back to `change-me-in-production-32-char-min` only when the
  secret file is missing — confirm `/run/secrets/jwt_secret` exists.

- **A10 (recommended):** enable dependency scanning (GitHub Dependabot / Snyk).

- **Network (advisory):** single-VPS default; for multi-host, move Postgres/Redis
  off the public host firewall port range and require a VPC.

## Cost-control summary

- Local inference (Ollama) costs nothing per token; OpenRouter usage is capped
  by `DAILY_BUDGET_USD` with an alert at `ALERT_THRESHOLD` (80%).
- GROK is currently unusable ("team has no credits") — do not configure until
  credits exist, else the router must fall back to Ollama/OpenRouter.
