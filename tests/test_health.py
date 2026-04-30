import json

import pytest

from app.routes import health

pytestmark = pytest.mark.unit


def _read_body(response) -> dict:
    return json.loads(bytes(response.body))


def test_healthz_returns_200_when_both_pings_succeed(monkeypatch):
    monkeypatch.setattr(health, "_ping_mongo", lambda: None)
    monkeypatch.setattr(health, "_ping_redis", lambda: None)

    response = health.healthz()

    assert response.status_code == 200
    assert _read_body(response) == {"db": "ok", "redis": "ok"}


def test_healthz_returns_503_when_mongo_ping_raises(monkeypatch):
    def boom():
        raise ConnectionError("mongo down")

    monkeypatch.setattr(health, "_ping_mongo", boom)
    monkeypatch.setattr(health, "_ping_redis", lambda: None)

    response = health.healthz()

    assert response.status_code == 503
    body = _read_body(response)
    assert body["db"].startswith("fail: ")
    assert "ConnectionError" in body["db"]
    assert body["redis"] == "ok"


def test_healthz_returns_503_when_redis_ping_raises(monkeypatch):
    def boom():
        raise TimeoutError("redis timeout")

    monkeypatch.setattr(health, "_ping_mongo", lambda: None)
    monkeypatch.setattr(health, "_ping_redis", boom)

    response = health.healthz()

    assert response.status_code == 503
    body = _read_body(response)
    assert body["db"] == "ok"
    assert body["redis"].startswith("fail: ")
    assert "TimeoutError" in body["redis"]


def test_healthz_reports_both_failures_when_both_pings_raise(monkeypatch):
    monkeypatch.setattr(health, "_ping_mongo", lambda: (_ for _ in ()).throw(RuntimeError("a")))
    monkeypatch.setattr(health, "_ping_redis", lambda: (_ for _ in ()).throw(RuntimeError("b")))

    response = health.healthz()

    assert response.status_code == 503
    body = _read_body(response)
    assert body["db"].startswith("fail: ")
    assert body["redis"].startswith("fail: ")
