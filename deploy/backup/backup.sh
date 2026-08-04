#!/bin/bash
# Daily backup: PostgreSQL dump + MinIO bucket mirror + rotation.
# All output goes to stdout so it is visible via `docker compose logs backup`.
set -euo pipefail

TS=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/backups
STAMP="$BACKUP_DIR/$TS"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

echo "[backup] starting $TS"

mkdir -p "$STAMP"

# 1) PostgreSQL logical dump
echo "[backup] dumping postgres"
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
    -h "$POSTGRES_HOST" \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    --no-owner \
    -F c \
    -f "$STAMP/db.dump"

# 2) MinIO bucket mirror
echo "[backup] mirroring minio bucket $MINIO_BUCKET"
if [ ! -f /root/.mc/config.json ]; then
  mc alias set "$MINIO_ALIAS" "http://$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" >/dev/null
fi
mc mirror --overwrite "$MINIO_ALIAS/$MINIO_BUCKET" "$STAMP/artifacts"

# 3) Compress
echo "[backup] compressing"
tar -czf "$STAMP.tar.gz" -C "$BACKUP_DIR" "$TS"
rm -rf "$STAMP"

# 4) Retention
echo "[backup] pruning backups older than ${RETENTION_DAYS} days"
find "$BACKUP_DIR" -name "*.tar.gz" -type f -mtime +"$RETENTION_DAYS" -delete

# 5) Health probe: report the newest backup for monitoring
NEWEST=$(ls -1t "$BACKUP_DIR"/*.tar.gz 2>/dev/null | head -1 || true)
echo "[backup] done. newest=$NEWEST"
