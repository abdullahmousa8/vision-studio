# Monitoring — Gemini Vision Studio

Prometheus + Grafana setup for the local stack. Metrics are exposed by the API
at `http://localhost:8000/metrics` (Prometheus text format).

## How metrics flow

- The API and the Celery worker are **separate processes**, so `prometheus_client`
  runs in **multiprocess mode**: both processes write to a shared directory
  (`backend\logs\prom`, set via `PROMETHEUS_MULTIPROC_DIR` in `api.cmd` /
  `worker.cmd`). The `/metrics` endpoint collects through a
  `MultiProcessCollector` and merges samples from both processes.
- The directory is cleaned on every launcher start (`del /q logs\prom\*.db`).
- A Celery **beat** task (`app.workers.metrics_beat.report_infra_metrics`, every
  15 s) pushes `celery_queue_depth` and `ollama_vram_usage_mb`. Beat runs inside
  the worker (`--beat` flag).

## Metrics exposed

| Metric | Type | Labels |
|---|---|---|
| `http_requests_total` | counter | method, path, status |
| `http_request_duration_seconds` | histogram | method, path |
| `jobs_created_total` | counter | mode, detail_level |
| `jobs_completed_total` | counter | status |
| `job_duration_seconds` | histogram | status |
| `api_calls_total` | counter | provider, model, status |
| `api_latency_seconds` | histogram | provider, model |
| `active_jobs` | gauge | — |
| `celery_queue_depth` | gauge | — |
| `ollama_vram_usage_mb` | gauge | — |

## Quick check (no Prometheus needed)

```powershell
(Invoke-WebRequest http://localhost:8000/metrics).Content
```

## Option A — native Windows binaries (no Docker)

1. Download `prometheus.exe` from <https://prometheus.io/download/> and put it in
   this folder (or point it at the config):
   ```powershell
   .\prometheus.exe --config.file=prometheus.yml --web.listen-address=:9090
   ```
2. Download Grafana OSS from <https://grafana.com/grafana/download> and run it
   (default port `3000`).
3. Open <http://localhost:3000> (admin/admin), add the Prometheus data source
   `http://localhost:9090`, and import
   `grafana/dashboards/studio-overview.json`.
   - The dashboard + data source are also auto-provisioned if you point Grafana
     at `grafana/provisioning`.

## Option B — Docker (when available)

```powershell
docker compose -f monitoring\docker-compose.yml up -d
```

- Prometheus: <http://localhost:9090>
- Grafana: <http://localhost:3000> (admin/admin) — dashboard is provisioned
  automatically under *Studio* → *Gemini Vision Studio*.
- `prometheus.yml` scrapes the host API via `host.docker.internal:8000`.

## Alert rules (`alerts.yml`)

- `StudioAPIDown` — API unreachable (critical).
- `HighJobFailureRate` — >50% of jobs fail over 15 min.
- `HighLLMErrorRate` — >0.3 LLM calls/s failing.
- `HighHTTP5xxRate` — >20% of HTTP responses are 5xx.
- `QueueBacklog` — Celery queue depth > 15 for 5 min.
- `LowVRAMHeadroom` — Ollama VRAM usage high (info).

Alert delivery (e.g. email/Slack) requires Alertmanager; point `alertmanager`
in `prometheus.yml` and reload.
