import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

_PING_TIMEOUT_SECONDS = 1.5


def _ping_mongo() -> None:
    from pymongo import MongoClient

    client = MongoClient(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        username=os.environ.get("DB_USERNAME") or None,
        password=os.environ.get("DB_PASSWORD") or None,
        serverSelectionTimeoutMS=int(_PING_TIMEOUT_SECONDS * 1000),
        connectTimeoutMS=int(_PING_TIMEOUT_SECONDS * 1000),
    )
    try:
        client.admin.command("ping")
    finally:
        client.close()


def _ping_redis() -> None:
    import redis as redis_lib

    client = redis_lib.Redis(
        host=os.environ["REDIS_HOST"],
        port=int(os.environ["REDIS_PORT"]),
        password=os.environ.get("REDIS_PASSWORD") or None,
        socket_connect_timeout=_PING_TIMEOUT_SECONDS,
        socket_timeout=_PING_TIMEOUT_SECONDS,
    )
    try:
        client.ping()
    finally:
        client.close()


@router.get("/healthz", include_in_schema=False)
def healthz() -> JSONResponse:
    checks: dict[str, str] = {}
    overall_ok = True

    try:
        _ping_mongo()
        checks["db"] = "ok"
    except Exception as exc:
        checks["db"] = f"fail: {type(exc).__name__}"
        overall_ok = False

    try:
        _ping_redis()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"fail: {type(exc).__name__}"
        overall_ok = False

    return JSONResponse(checks, status_code=200 if overall_ok else 503)
