#!/usr/bin/env python3
"""Healthcheck for the RQ worker container: ping Redis using the same
credentials the worker entrypoint uses. Exit 0 on success, 1 on any
failure. Stdout/stderr go to docker's healthcheck log."""
import os
import sys

import redis

# Docker healthcheck spawns a fresh process with the container's Config.Env,
# which does NOT include REDIS_PASSWORD: the entrypoint shell-exports it from
# /run/secrets/redis.pass at startup, but that export is local to the worker
# process tree. Read it directly here so the healthcheck and the worker share
# a source of truth.
SECRET_PATH = "/run/secrets/redis.pass"


def _redis_password() -> str | None:
    env = os.environ.get("REDIS_PASSWORD")
    if env:
        return env
    try:
        with open(SECRET_PATH) as fh:
            value = fh.read().strip()
        return value or None
    except OSError:
        return None


def main() -> int:
    try:
        client = redis.Redis(
            host=os.environ["REDIS_HOST"],
            port=int(os.environ["REDIS_PORT"]),
            password=_redis_password(),
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
            retry_on_error=[],
            health_check_interval=0,
        )
        client.ping()
    except Exception as exc:
        print(f"healthcheck: {exc!r}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
