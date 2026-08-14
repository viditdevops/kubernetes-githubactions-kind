#!/bin/sh
# Vault Agent writes rendered secrets to /vault/secrets/db-env before this container's
# main process starts (init container sidecar pattern via annotations).
# This script sources that file so the values become real env vars for the app.

set -e

if [ ! -f /vault/secrets/db-env ]; then
  echo "FATAL: /vault/secrets/db-env not found. Vault Agent sidecar did not inject secrets." >&2
  exit 1
fi

. /vault/secrets/db-env

exec uvicorn main:app --host 0.0.0.0 --port 8000
