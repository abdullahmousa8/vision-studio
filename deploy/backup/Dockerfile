# Backup container: PostgreSQL dump + MinIO mirror on a cron schedule.
# The schedule comes from the SCHEDULE env var (cron format), default "0 3 * * *".
# Backups are written to /backups (bind-mounted to ${BACKUP_DIR:-./backups}).
FROM alpine:3.20

RUN apk add --no-cache \
        bash \
        postgresql16-client \
        curl \
        tzdata \
    && curl -fsSLo /usr/local/bin/mc \
        https://dl.min.io/client/mc/release/linux-amd64/mc \
    && chmod +x /usr/local/bin/mc

COPY backup.sh /usr/local/bin/backup.sh
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /usr/local/bin/backup.sh /entrypoint.sh

ENV TZ=UTC
ENTRYPOINT ["/entrypoint.sh"]
