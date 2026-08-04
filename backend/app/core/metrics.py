from prometheus_client import Counter, Gauge, Histogram

# All metrics live on the default registry. When PROMETHEUS_MULTIPROC_DIR is
# set (see api.cmd / worker.cmd), prometheus_client transparently persists each
# process's samples to shared .db files; the /metrics endpoint collects them
# through a MultiProcessCollector so counters from the API and the Celery
# worker processes are merged.

# Counters
jobs_created = Counter(
    "jobs_created_total", "Total jobs created", ["mode", "detail_level"]
)
jobs_completed = Counter("jobs_completed_total", "Total jobs completed", ["status"])
api_calls_total = Counter(
    "api_calls_total", "Total API calls", ["provider", "model", "status"]
)
http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status"]
)

# Histograms
job_duration = Histogram(
    "job_duration_seconds", "Job duration", ["status"], buckets=(5, 15, 30, 60, 120, 300, 600)
)
api_latency = Histogram(
    "api_latency_seconds", "API latency", ["provider", "model"]
)
http_request_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# Gauges
active_jobs = Gauge("active_jobs", "Currently active jobs", multiprocess_mode="liveall")
queue_depth = Gauge("celery_queue_depth", "Celery queue depth", multiprocess_mode="livesum")
ollama_vram_usage = Gauge("ollama_vram_usage_mb", "Ollama VRAM usage", multiprocess_mode="livesum")
