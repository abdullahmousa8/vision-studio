#!/usr/bin/env sh
set -e

exec celery -A app.core.celery_app worker \
    --loglevel=info \
    --concurrency="${CELERY_CONCURRENCY:-2}" \
    --queues=pipeline,dlq,default
