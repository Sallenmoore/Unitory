from datetime import datetime

from autonomous.model.autoattr import (
    DateTimeAttr,
    DictAttr,
    IntAttr,
    ListAttr,
    StringAttr,
)
from autonomous.model.automodel import AutoModel

SERVER_TYPES = ["physical", "vm", "container"]
ENVIRONMENTS = ["prod", "stage", "dev", "lab"]
STATUSES = ["active", "maintenance", "decommissioned", "discovered"]

# Fields that autodiscovery is allowed to overwrite. Everything else on the
# model is considered human-authored and is preserved across scans.
DISCOVERY_FIELDS = frozenset(
    {
        "fqdn",
        "ip_addresses",
        "mac_addresses",
        "server_type",
        "hypervisor",
        "os_name",
        "os_version",
        "os_id",
        "os_id_like",
        "os_codename",
        "kernel",
        "architecture",
        "cpu_model",
        "cpu_cores",
        "ram_bytes",
        "disk_bytes",
        "vendor",
        "product_name",
        "product_uuid",
        "serial_number",
        "bios_vendor",
        "bios_version",
        "bios_date",
        "boot_time",
        "exporter_version",
        "timezone",
        "filesystems",
        "network_interfaces",
        "disks",
        "last_discovered",
        "discovery_data",
    }
)


class Server(AutoModel):
    meta = {"collection": "servers", "indexes": ["hostname"]}

    hostname = StringAttr(required=True, unique=True)
    fqdn = StringAttr()
    ip_addresses = ListAttr(StringAttr())
    mac_addresses = ListAttr(StringAttr())

    server_type = StringAttr(choices=SERVER_TYPES, default="physical")
    hypervisor = StringAttr()

    os_name = StringAttr()
    os_version = StringAttr()
    os_id = StringAttr()
    os_id_like = StringAttr()
    os_codename = StringAttr()
    kernel = StringAttr()
    architecture = StringAttr()

    cpu_model = StringAttr()
    cpu_cores = IntAttr()
    ram_bytes = IntAttr()
    disk_bytes = IntAttr()

    vendor = StringAttr()
    product_name = StringAttr()
    product_uuid = StringAttr()
    serial_number = StringAttr()
    asset_tag = StringAttr()
    bios_vendor = StringAttr()
    bios_version = StringAttr()
    bios_date = StringAttr()

    boot_time = DateTimeAttr()
    exporter_version = StringAttr()
    timezone = StringAttr()

    filesystems = ListAttr(DictAttr())
    network_interfaces = ListAttr(DictAttr())
    disks = ListAttr(DictAttr())

    rack = StringAttr()
    location = StringAttr()
    vlan = StringAttr()

    environment = StringAttr(choices=ENVIRONMENTS, default="prod")
    purpose = StringAttr()
    owner = StringAttr()
    status = StringAttr(choices=STATUSES, default="active")
    patch_window = StringAttr()
    warranty_expires = DateTimeAttr()

    compliance_tags = ListAttr(StringAttr())
    tags = ListAttr(StringAttr())

    notes = StringAttr()

    last_discovered = DateTimeAttr()
    discovery_data = DictAttr()

    def __repr__(self):
        return f"<Server {self.pk} {self.hostname}>"

    def summary(self) -> dict:
        """Limited payload for list-style API responses."""
        return {
            "id": str(self.pk),
            "hostname": self.hostname,
            "fqdn": self.fqdn,
            "environment": self.environment,
            "status": self.status,
            "os_name": self.os_name,
            "os_version": self.os_version,
            "last_updated": _iso(self.last_updated),
        }

    def to_dict(self) -> dict:
        return {
            "id": str(self.pk),
            "hostname": self.hostname,
            "fqdn": self.fqdn,
            "ip_addresses": list(self.ip_addresses or []),
            "mac_addresses": list(self.mac_addresses or []),
            "server_type": self.server_type,
            "hypervisor": self.hypervisor,
            "os_name": self.os_name,
            "os_version": self.os_version,
            "os_id": self.os_id,
            "os_id_like": self.os_id_like,
            "os_codename": self.os_codename,
            "kernel": self.kernel,
            "architecture": self.architecture,
            "cpu_model": self.cpu_model,
            "cpu_cores": self.cpu_cores,
            "ram_bytes": self.ram_bytes,
            "disk_bytes": self.disk_bytes,
            "vendor": self.vendor,
            "product_name": self.product_name,
            "product_uuid": self.product_uuid,
            "serial_number": self.serial_number,
            "asset_tag": self.asset_tag,
            "bios_vendor": self.bios_vendor,
            "bios_version": self.bios_version,
            "bios_date": self.bios_date,
            "boot_time": _iso(self.boot_time),
            "exporter_version": self.exporter_version,
            "timezone": self.timezone,
            "filesystems": list(self.filesystems or []),
            "network_interfaces": list(self.network_interfaces or []),
            "disks": list(self.disks or []),
            "rack": self.rack,
            "location": self.location,
            "vlan": self.vlan,
            "environment": self.environment,
            "purpose": self.purpose,
            "owner": self.owner,
            "status": self.status,
            "patch_window": self.patch_window,
            "warranty_expires": _iso(self.warranty_expires),
            "compliance_tags": list(self.compliance_tags or []),
            "tags": list(self.tags or []),
            "notes": self.notes,
            "last_discovered": _iso(self.last_discovered),
            "last_updated": _iso(self.last_updated),
        }


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if isinstance(dt, datetime) else None
