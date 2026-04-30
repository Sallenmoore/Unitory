#!/usr/bin/env bash
set -euo pipefail

cd /app
exec rq worker --url "redis://:${REDIS_PASSWORD}@${REDIS_HOST:-redis}:${REDIS_PORT:-6379}/${REDIS_DB:-0}" high default low
