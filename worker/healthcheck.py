#!/usr/bin/env python3
"""Healthcheck for the RQ worker container: ping Redis using the same
credentials the worker entrypoint uses. Exit 0 on success, 1 on any
failure. Stdout/stderr go to docker's healthcheck log."""
import os
import sys

import redis


def main() -> int:
    try:
        client = redis.Redis(
            host=os.environ["REDIS_HOST"],
            port=int(os.environ["REDIS_PORT"]),
            password=os.environ.get("REDIS_PASSWORD") or None,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )
        client.ping()
    except Exception as exc:
        print(f"healthcheck: {exc!r}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
