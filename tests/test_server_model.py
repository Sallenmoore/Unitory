"""Integration tests — require a running MongoDB. Run inside the web container:

    docker compose run --rm web pytest tests/test_server_model.py
"""

import pytest

pymongo = pytest.importorskip("pymongo")


def _mongo_available() -> bool:
    import os
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError

    try:
        client = MongoClient(
            host=os.getenv("DB_HOST", "mongo"),
            port=int(os.getenv("DB_PORT", "27017")),
            username=os.getenv("DB_USERNAME"),
            password=os.getenv("DB_PASSWORD"),
            authSource="admin",
            serverSelectionTimeoutMS=500,
        )
        client.admin.command("ping")
        return True
    except PyMongoError:
        return False


pytestmark = pytest.mark.skipif(not _mongo_available(), reason="MongoDB not reachable")


def test_server_summary_shape():
    from app.models.server import Server

    s = Server(hostname="integration-test-host", environment="dev", status="active")
    s.save()
    try:
        payload = s.summary()
        assert set(payload.keys()) == {
            "id", "hostname", "fqdn", "environment", "status",
            "os_name", "os_version", "last_updated",
        }
        assert payload["hostname"] == "integration-test-host"
    finally:
        s.delete()


def test_server_to_dict_includes_extended_fields():
    from app.models.server import Server

    s = Server(
        hostname="integration-test-host-2",
        tags=["web", "public"],
        compliance_tags=["PCI"],
        ip_addresses=["10.0.0.1"],
    )
    s.save()
    try:
        payload = s.to_dict()
        assert payload["tags"] == ["web", "public"]
        assert payload["compliance_tags"] == ["PCI"]
        assert payload["ip_addresses"] == ["10.0.0.1"]
    finally:
        s.delete()
