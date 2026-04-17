#!/usr/bin/env bash
# Railway start command — runs Alembic migrations, then boots the API.
set -e

echo "[start] Running database migrations..."
alembic upgrade head

echo "[start] Launching gunicorn on 0.0.0.0:${PORT:-8000} ..."
exec gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'
