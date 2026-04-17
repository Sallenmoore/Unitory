"""Fetch and parse Prometheus `node_exporter` metrics into a Server-shaped dict."""

from __future__ import annotations

from typing import Iterable

import httpx
from prometheus_client.parser import text_string_to_metric_families

_FS_SKIP_TYPES = {"tmpfs", "devtmpfs", "overlay", "squashfs", "proc", "sysfs"}


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
        version = labels.get("version", "")
        nodename = labels.get("nodename", "")
        machine = labels.get("machine", "")
        if nodename:
            out["fqdn"] = nodename
        out["os_name"] = sysname
        out["kernel"] = release
        # node_uname_info version is the kernel build string; try to pick up
        # distro info from node_os_info if present (newer node_exporter).
        if version:
            out.setdefault("_uname_version", version)
        if machine:
            out.setdefault("_machine", machine)

    if (f := by_name.get("node_os_info")) and f.samples:
        labels = f.samples[0].labels
        if name := labels.get("name") or labels.get("pretty_name"):
            out["os_name"] = name
        if version := labels.get("version_id") or labels.get("version"):
            out["os_version"] = version

    # Hardware / DMI
    if (f := by_name.get("node_dmi_info")) and f.samples:
        labels = f.samples[0].labels
        if v := labels.get("system_vendor") or labels.get("board_vendor"):
            out["vendor"] = v
        if v := labels.get("product_name"):
            out["product_name"] = v
        if v := labels.get("product_serial") or labels.get("chassis_asset_tag"):
            out["serial_number"] = v

    # Memory
    if (f := by_name.get("node_memory_MemTotal_bytes")) and f.samples:
        out["ram_bytes"] = int(f.samples[0].value)

    # CPU cores: unique `cpu` label values on node_cpu_seconds_total.
    # prometheus_client strips the `_total` suffix from counter family names,
    # so the family key is `node_cpu_seconds`.
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

    # Disk: sum of real filesystems' node_filesystem_size_bytes
    if f := by_name.get("node_filesystem_size_bytes"):
        seen = set()
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
            total += int(s.value)
        if total:
            out["disk_bytes"] = total

    # IPs: node_network_address_info (newer) or node_network_info (older)
    ips: list[str] = []
    macs: list[str] = []
    if f := by_name.get("node_network_address_info"):
        for s in f.samples:
            if addr := s.labels.get("address"):
                ips.append(addr)
    if f := by_name.get("node_network_info"):
        for s in f.samples:
            labels = s.labels
            if mac := labels.get("address"):
                if _looks_like_mac(mac):
                    macs.append(mac)
    if ips:
        out["ip_addresses"] = _dedupe(ips)
    if macs:
        out["mac_addresses"] = _dedupe(macs)

    # Virtualization hint → server_type
    for name in ("node_virtualization_system", "node_dmi_info"):
        if name in by_name and by_name[name].samples:
            labels = by_name[name].samples[0].labels
            if name == "node_virtualization_system":
                out["server_type"] = "vm"
                out["hypervisor"] = labels.get("system") or out.get("hypervisor", "")
                break
            product = (labels.get("product_name") or "").lower()
            if any(k in product for k in ("vmware", "virtualbox", "kvm", "qemu", "xen", "hyper-v")):
                out["server_type"] = "vm"
                out["hypervisor"] = product
                break

    # Drop private scratch keys
    for k in list(out.keys()):
        if k.startswith("_"):
            out.pop(k, None)

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
