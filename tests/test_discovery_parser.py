from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.services.node_exporter import parse_metrics

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURES / "node_exporter_sample.txt"
RSCTDB_FIXTURE = FIXTURES / "node_exporter_rsctdb.txt"

pytestmark = pytest.mark.unit


# ---------- Original fixture (newer-exporter Rocky Linux 9.3 host) ----------


def test_parse_metrics_extracts_system_info():
    data = parse_metrics(FIXTURE.read_text())

    assert data["fqdn"] == "host1.binghamton.edu"
    assert data["os_name"] == "Rocky Linux"
    assert data["os_version"] == "9.3"
    assert data["kernel"].startswith("5.14.0")
    assert data["architecture"] == "x86_64"


def test_parse_metrics_extracts_os_family():
    data = parse_metrics(FIXTURE.read_text())

    assert data["os_id"] == "rocky"
    assert data["os_id_like"] == "rhel centos fedora"
    assert data["os_codename"] == "blue_onyx"


def test_parse_metrics_extracts_hardware():
    data = parse_metrics(FIXTURE.read_text())

    assert data["vendor"] == "Dell Inc."
    assert data["product_name"] == "PowerEdge R740"
    assert data["serial_number"] == "ABC12345"
    assert data["ram_bytes"] == 134925033472
    assert data["cpu_cores"] == 2


def test_parse_metrics_extracts_bios_and_uuid():
    data = parse_metrics(FIXTURE.read_text())

    assert data["bios_vendor"] == "Dell Inc."
    assert data["bios_version"] == "2.18.1"
    assert data["bios_date"] == "10/10/2023"
    assert data["product_uuid"] == "4c4c4544-0042-4310-8033-c8c04f4d3032"


def test_parse_metrics_extracts_boot_time():
    data = parse_metrics(FIXTURE.read_text())

    assert isinstance(data["boot_time"], datetime)
    assert data["boot_time"].tzinfo == timezone.utc


def test_parse_metrics_extracts_exporter_version_and_timezone():
    data = parse_metrics(FIXTURE.read_text())

    assert data["exporter_version"] == "1.8.2"
    assert data["timezone"] == "America/New_York"


def test_parse_metrics_sums_real_filesystems_only():
    data = parse_metrics(FIXTURE.read_text())

    # 500G + 100G, excluding the 64MB tmpfs mount
    assert data["disk_bytes"] == 600_000_000_000


def test_parse_metrics_filesystems_excludes_skip_types():
    data = parse_metrics(FIXTURE.read_text())

    devices = {fs["device"] for fs in data["filesystems"]}
    assert "tmpfs" not in devices
    assert {"/dev/sda1", "/dev/sda2"} <= devices
    assert all(fs["fstype"] != "tmpfs" for fs in data["filesystems"])


def test_parse_metrics_filesystems_carry_uuid_when_known():
    data = parse_metrics(FIXTURE.read_text())

    by_device = {fs["device"]: fs for fs in data["filesystems"]}
    assert by_device["/dev/sda1"]["uuid"] == "aaaa-1111"
    assert by_device["/dev/sda2"]["uuid"] == "bbbb-2222"


def test_parse_metrics_collects_ip_addresses():
    data = parse_metrics(FIXTURE.read_text())

    assert data["ip_addresses"] == ["10.0.1.5", "10.0.1.6"]


def test_parse_metrics_network_interfaces_excludes_loopback():
    data = parse_metrics(FIXTURE.read_text())

    devices = [i["device"] for i in data["network_interfaces"]]
    assert "lo" not in devices
    assert devices == ["eth0", "eth1"]
    eth0 = next(i for i in data["network_interfaces"] if i["device"] == "eth0")
    assert eth0["mac"] == "aa:bb:cc:dd:ee:01"
    assert eth0["operstate"] == "up"
    assert eth0["duplex"] == "full"


def test_parse_metrics_disks_excludes_dm_and_loop():
    data = parse_metrics(FIXTURE.read_text())

    devices = {d["device"] for d in data["disks"]}
    assert devices == {"sda", "sdb"}
    assert all(d["model"] == "PERC H730P Mini" for d in data["disks"])
    assert all(d["path"] is not None for d in data["disks"])


def test_parse_metrics_handles_empty_input():
    assert parse_metrics("") == {}


# ---------- rsctdb fixture (older exporter, no node_network_address_info) ----------


def test_rsctdb_extracts_oracle_linux_family():
    data = parse_metrics(RSCTDB_FIXTURE.read_text())

    assert data["os_id"] == "ol"
    assert data["os_id_like"] == "fedora"
    assert data["os_version"] == "7.9"


def test_rsctdb_hypervisor_is_vmware_esxi():
    data = parse_metrics(RSCTDB_FIXTURE.read_text())

    assert data["server_type"] == "vm"
    assert data["hypervisor"] == "VMware ESXi"
    assert data["vendor"] == "VMware, Inc."


def test_rsctdb_dns_fallback_fires_when_address_info_missing(monkeypatch):
    def fake_getaddrinfo(host, *_args, **_kwargs):
        assert host == "rsctdb.cc.binghamton.edu"
        return [
            (None, None, None, "", ("128.226.10.20", 0)),
            (None, None, None, "", ("128.226.10.20", 0)),  # dupe — should dedupe
        ]

    monkeypatch.setattr("app.services.node_exporter.socket.getaddrinfo", fake_getaddrinfo)

    data = parse_metrics(RSCTDB_FIXTURE.read_text())

    assert data["ip_addresses"] == ["128.226.10.20"]


def test_rsctdb_dns_fallback_swallows_resolver_errors(monkeypatch):
    def fake_getaddrinfo(*_args, **_kwargs):
        raise OSError("name resolution failed")

    monkeypatch.setattr("app.services.node_exporter.socket.getaddrinfo", fake_getaddrinfo)

    data = parse_metrics(RSCTDB_FIXTURE.read_text())

    assert "ip_addresses" not in data


def test_rsctdb_disks_excludes_sr_cdrom_and_dm():
    data = parse_metrics(RSCTDB_FIXTURE.read_text())

    devices = {d["device"] for d in data["disks"]}
    assert devices == {"sda", "sdb"}


def test_rsctdb_filesystem_uuid_joins_via_basename():
    """device label is `/dev/mapper/ol_rhel7lamp-root` but uuid is keyed by `dm-0`.
    The uuid join is best-effort — when the basename doesn't match a dm-name,
    uuid is None. This locks in that behavior and surfaces the limitation."""
    data = parse_metrics(RSCTDB_FIXTURE.read_text())

    # All four mounts should be present (one tmpfs filtered)
    devices = {fs["device"] for fs in data["filesystems"]}
    assert "/dev/mapper/ol_rhel7lamp-root" in devices
    assert "/dev/sda1" in devices
    assert "tmpfs" not in devices


def test_no_dns_lookup_when_fqdn_missing(monkeypatch):
    """If node_uname_info is absent, _resolve_ips must not be called."""
    called = {"n": 0}

    def fake_getaddrinfo(*_args, **_kwargs):
        called["n"] += 1
        return []

    monkeypatch.setattr("app.services.node_exporter.socket.getaddrinfo", fake_getaddrinfo)
    parse_metrics("")
    assert called["n"] == 0
