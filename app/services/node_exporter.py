"""Fetch and parse Prometheus `node_exporter` metrics into a Server-shaped dict."""

from __future__ import annotations

import re
import socket
from datetime import datetime, timezone
from typing import Iterable

import httpx
from prometheus_client.parser import text_string_to_metric_families

_FS_SKIP_TYPES = {"tmpfs", "devtmpfs", "overlay", "squashfs", "proc", "sysfs"}
_DISK_SKIP_PREFIXES = ("dm-", "loop", "sr")

_HYPERVISOR_BY_VENDOR = {
    "VMware, Inc.": "VMware ESXi",
    "QEMU": "KVM/QEMU",
    "Xen": "Xen",
    "Microsoft Corporation": "Hyper-V",
    "innotek GmbH": "VirtualBox",
}


def fetch_metrics(hostname: str, port: int = 9100, timeout: float = 5.0) -> str:
    url = f"http://{hostname}:{port}/metrics"
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


def parse_metrics(text: str) -> dict:
    """Extract a Server-shaped dict from raw node_exporter output.

    Returned keys mirror `app.models.server.DISCOVERY_FIELDS` (minus
    `last_discovered` / `discovery_data` which are set by the caller).
    Missing metrics produce missing keys rather than errors.
    """
    families = list(text_string_to_metric_families(text))
    by_name = {f.name: f for f in families}

    out: dict = {}

    # OS / kernel / hostname
    if (f := by_name.get("node_uname_info")) and f.samples:
        labels = f.samples[0].labels
        sysname = labels.get("sysname", "")
        release = labels.get("release", "")
        nodename = labels.get("nodename", "")
        machine = labels.get("machine", "")
        if nodename:
            out["fqdn"] = nodename
        if sysname:
            out["os_name"] = sysname
        if release:
            out["kernel"] = release
        if machine:
            out["architecture"] = machine

    if (f := by_name.get("node_os_info")) and f.samples:
        labels = f.samples[0].labels
        if name := labels.get("name") or labels.get("pretty_name"):
            out["os_name"] = name
        if version := labels.get("version_id") or labels.get("version"):
            out["os_version"] = version
        if v := labels.get("id"):
            out["os_id"] = v
        if v := labels.get("id_like"):
            out["os_id_like"] = v
        if v := labels.get("version_codename"):
            out["os_codename"] = v

    # Hardware / DMI / BIOS
    if (f := by_name.get("node_dmi_info")) and f.samples:
        labels = f.samples[0].labels
        if v := labels.get("system_vendor") or labels.get("board_vendor"):
            out["vendor"] = v
        if v := labels.get("product_name"):
            out["product_name"] = v
        if v := labels.get("product_serial") or labels.get("chassis_asset_tag"):
            out["serial_number"] = v
        if v := labels.get("product_uuid"):
            out["product_uuid"] = v
        if v := labels.get("bios_vendor"):
            out["bios_vendor"] = v
        if v := labels.get("bios_version"):
            out["bios_version"] = v
        if v := labels.get("bios_date"):
            out["bios_date"] = v

    # Memory
    if (f := by_name.get("node_memory_MemTotal_bytes")) and f.samples:
        out["ram_bytes"] = int(f.samples[0].value)

    # CPU cores: unique `cpu` label values on node_cpu_seconds_total.
    # prometheus_client strips the `_total` suffix from counter family names.
    cpu_family = by_name.get("node_cpu_seconds") or by_name.get("node_cpu_seconds_total")
    if cpu_family:
        cpus = {s.labels.get("cpu") for s in cpu_family.samples if s.labels.get("cpu") is not None}
        if cpus:
            out["cpu_cores"] = len(cpus)

    # CPU model
    if (f := by_name.get("node_cpu_info")) and f.samples:
        labels = f.samples[0].labels
        if model := labels.get("model_name"):
            out["cpu_model"] = model

    # Boot time → datetime (UTC)
    if (f := by_name.get("node_boot_time_seconds")) and f.samples:
        try:
            out["boot_time"] = datetime.fromtimestamp(float(f.samples[0].value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            pass

    # Exporter version
    if (f := by_name.get("node_exporter_build_info")) and f.samples:
        if v := f.samples[0].labels.get("version"):
            out["exporter_version"] = v

    # Timezone (label, not the offset value)
    if (f := by_name.get("node_time_zone_offset_seconds")) and f.samples:
        if v := f.samples[0].labels.get("time_zone"):
            out["timezone"] = v

    # Filesystems (list) + disk_bytes (sum)
    fs_uuid_by_device = {
        s.labels.get("device"): s.labels.get("uuid")
        for s in (by_name.get("node_disk_filesystem_info").samples if by_name.get("node_disk_filesystem_info") else [])
        if s.labels.get("device")
    }
    if f := by_name.get("node_filesystem_size_bytes"):
        seen: set = set()
        filesystems: list[dict] = []
        total = 0
        for s in f.samples:
            fstype = s.labels.get("fstype", "")
            device = s.labels.get("device", "")
            mountpoint = s.labels.get("mountpoint", "")
            if fstype in _FS_SKIP_TYPES:
                continue
            key = (device, mountpoint)
            if key in seen:
                continue
            seen.add(key)
            try:
                size = int(s.value)
            except (TypeError, ValueError):
                size = 0
            total += size
            filesystems.append(
                {
                    "device": device,
                    "mountpoint": mountpoint,
                    "fstype": fstype,
                    "size_bytes": size,
                    "uuid": fs_uuid_by_device.get(_basename(device)),
                }
            )
        if total:
            out["disk_bytes"] = total
        if filesystems:
            out["filesystems"] = filesystems

    # Network interfaces (list) + mac_addresses (flat list, kept for back-compat)
    macs: list[str] = []
    interfaces: list[dict] = []
    if f := by_name.get("node_network_info"):
        seen_devs: set = set()
        for s in f.samples:
            labels = s.labels
            device = labels.get("device") or ""
            if not device or device == "lo" or device in seen_devs:
                continue
            seen_devs.add(device)
            mac = labels.get("address") or ""
            if mac and _looks_like_mac(mac) and mac != "00:00:00:00:00:00":
                macs.append(mac)
            interfaces.append(
                {
                    "device": device,
                    "mac": mac,
                    "operstate": labels.get("operstate") or "",
                    "adminstate": labels.get("adminstate") or "",
                    "duplex": labels.get("duplex") or "",
                }
            )
    if macs:
        out["mac_addresses"] = _dedupe(macs)
    if interfaces:
        out["network_interfaces"] = interfaces

    # IP addresses — newer exporters expose node_network_address_info; older
    # ones don't, so fall back to a DNS lookup of the discovered fqdn.
    ips: list[str] = []
    if f := by_name.get("node_network_address_info"):
        for s in f.samples:
            if addr := s.labels.get("address"):
                ips.append(addr)
    if not ips and out.get("fqdn"):
        ips = _resolve_ips(out["fqdn"])
    if ips:
        out["ip_addresses"] = _dedupe(ips)

    # Disks (list) — physical block devices only
    if f := by_name.get("node_disk_info"):
        seen_disks: set = set()
        disks: list[dict] = []
        for s in f.samples:
            device = s.labels.get("device") or ""
            if not device or device.startswith(_DISK_SKIP_PREFIXES) or device in seen_disks:
                continue
            seen_disks.add(device)
            disks.append(
                {
                    "device": device,
                    "model": (s.labels.get("model") or "").strip() or None,
                    "path": (s.labels.get("path") or "").strip() or None,
                    "size_bytes": None,
                }
            )
        if disks:
            out["disks"] = disks

    # Virtualization / hypervisor
    if (f := by_name.get("node_dmi_info")) and f.samples:
        labels = f.samples[0].labels
        system_vendor = labels.get("system_vendor") or ""
        product = (labels.get("product_name") or "").lower()
        if hyper := _HYPERVISOR_BY_VENDOR.get(system_vendor):
            # Hyper-V vendor string also covers Surface laptops; only flag VM
            # when the product name is the canonical VM product.
            if system_vendor != "Microsoft Corporation" or "virtual machine" in product:
                out["server_type"] = "vm"
                out["hypervisor"] = hyper
        elif any(k in product for k in ("vmware", "virtualbox", "kvm", "qemu", "xen", "hyper-v")):
            out["server_type"] = "vm"
            out["hypervisor"] = product

    return out


def _looks_like_mac(value: str) -> bool:
    parts = value.split(":")
    return len(parts) == 6 and all(len(p) == 2 for p in parts)


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


_DEV_NAME_RE = re.compile(r"[^/]+$")


def _basename(path: str) -> str:
    """Return the trailing path segment so /dev/mapper/foo and dm-N can map by uuid."""
    if not path:
        return ""
    m = _DEV_NAME_RE.search(path)
    return m.group(0) if m else path


def _resolve_ips(fqdn: str, timeout: float = 1.0) -> list[str]:
    """Forward-resolve fqdn → IP list via DNS. Used when the exporter doesn't
    emit node_network_address_info (older RHEL/OL fleet)."""
    socket.setdefaulttimeout(timeout)
    try:
        infos = socket.getaddrinfo(fqdn, None)
    except OSError:
        return []
    finally:
        socket.setdefaulttimeout(None)
    return _dedupe([info[4][0] for info in infos])
