FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/scripts/*.sh

# Run as non-root. Fresh named volumes inherit ownership from these dirs.
RUN addgroup --system app \
    && adduser --system --ingroup app app \
    && chown -R app:app /app \
    && mkdir -p /var/lib/metrics /var/lib/celery \
    && chown app:app /var/lib/metrics /var/lib/celery

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health/live || exit 1

CMD ["/app/scripts/entrypoint.sh"]
