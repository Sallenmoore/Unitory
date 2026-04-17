from pathlib import Path

import pytest

from app.services.node_exporter import parse_metrics

FIXTURE = Path(__file__).parent / "fixtures" / "node_exporter_sample.txt"

pytestmark = pytest.mark.unit


def test_parse_metrics_extracts_system_info():
    data = parse_metrics(FIXTURE.read_text())

    assert data["fqdn"] == "host1.binghamton.edu"
    assert data["os_name"] == "Rocky Linux"
    assert data["os_version"] == "9.3"
    assert data["kernel"].startswith("5.14.0")


def test_parse_metrics_extracts_hardware():
    data = parse_metrics(FIXTURE.read_text())

    assert data["vendor"] == "Dell Inc."
    assert data["product_name"] == "PowerEdge R740"
    assert data["serial_number"] == "ABC12345"
    assert data["ram_bytes"] == 134925033472
    assert data["cpu_cores"] == 2


def test_parse_metrics_sums_real_filesystems_only():
    data = parse_metrics(FIXTURE.read_text())

    # 500G + 100G, excluding the 64MB tmpfs mount
    assert data["disk_bytes"] == 600_000_000_000


def test_parse_metrics_collects_ip_addresses():
    data = parse_metrics(FIXTURE.read_text())

    assert data["ip_addresses"] == ["10.0.1.5", "10.0.1.6"]


def test_parse_metrics_handles_empty_input():
    assert parse_metrics("") == {}
