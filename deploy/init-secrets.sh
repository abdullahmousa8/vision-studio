#!/bin/bash
# Generate strong secrets for the production stack.
# Writes ./secrets/*.txt which docker-compose.prod.yml mounts as Docker secrets.
# Run once on the deploy server:  bash deploy/init-secrets.sh
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
SECRETS="$DIR/secrets"
mkdir -p "$SECRETS"
chmod 700 "$SECRETS"

gen() { # $1 = file, $2 = length
  if [ ! -s "$SECRETS/$1" ]; then
    openssl rand -hex "$2" > "$SECRETS/$1"
    echo "generated $1"
  else
    echo "kept existing $1"
  fi
}

gen jwt_secret.txt       32
gen openrouter_key.txt   24
gen grok_key.txt         24

echo
echo "secrets written to $SECRETS (git-ignored, keep offline)."
echo "MinIO credentials are shared via .env: set MINIO_ROOT_USER/MINIO_ROOT_PASSWORD"
echo "there and make sure they match MINIO_ACCESS_KEY/MINIO_SECRET_KEY expectations."
