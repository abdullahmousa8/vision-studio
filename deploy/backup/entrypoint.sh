#!/bin/sh
# Write the cron schedule from $SCHEDULE, then start crond in the foreground.
set -e

SCHEDULE="${SCHEDULE:-0 3 * * *}"

if [ ! -f /etc/crontabs/root ] || ! grep -q "backup.sh" /etc/crontabs/root; then
  echo "${SCHEDULE} /usr/local/bin/backup.sh >> /var/log/backup.log 2>&1" > /etc/crontabs/root
fi

echo "backup: schedule = '${SCHEDULE}'"
exec crond -f -l 2
