#!/bin/bash
# Disaster recovery: restore PostgreSQL + MinIO from the newest local backup.
#
# Usage:
#   docker compose -f docker-compose.prod.yml run --rm backup \
#       /usr/local/bin/restore.sh [STAMP]
#
# STAMP defaults to the newest .tar.gz under /backups, e.g. 20260804_031500.
# Target (RTO ~1h, RPO = last successful backup, see BACKUP_SCHEDULE).
set -euo pipefail

BACKUP_DIR=/backups
STAMP="${1:-$(ls -1t "$BACKUP_DIR"/*.tar.gz 2>/dev/null | head -1 | xargs -r basename | sed 's/\.tar\.gz$//')}"

if [ -z "$STAMP" ] || [ ! -f "$BACKUP_DIR/$STAMP.tar.gz" ]; then
  echo "error: no backup found. pass a stamp like 20260804_031500"
  exit 1
fi

echo "[restore] restoring $STAMP"

WORK=$(mktemp -d)
tar -xzf "$BACKUP_DIR/$STAMP.tar.gz" -C "$WORK"

# 1) PostgreSQL
echo "[restore] postgres"
PGPASSWORD="$POSTGRES_PASSWORD" pg_restore \
    -h "$POSTGRES_HOST" \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    --clean --if-exists --no-owner \
    "$WORK/$STAMP/db.dump"

# 2) MinIO
echo "[restore] minio"
if [ ! -f /root/.mc/config.json ]; then
  mc alias set "$MINIO_ALIAS" "http://$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" >/dev/null
fi
mc mirror --overwrite "$WORK/$STAMP/artifacts" "$MINIO_ALIAS/$MINIO_BUCKET"

rm -rf "$WORK"
echo "[restore] done. verify with: curl https://<APP_DOMAIN>/health"
