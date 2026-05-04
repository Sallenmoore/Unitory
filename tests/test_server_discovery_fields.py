"""Unit tests for DISCOVERY_FIELDS — the human-fields-are-sacred boundary.

Importing the model is heavy (pulls autonomous-app + Mongo client setup), so
these tests live in their own file and are kept minimal.
"""

import pytest

from app.models.server import DISCOVERY_FIELDS

pytestmark = pytest.mark.unit


# Fields that scans are allowed to overwrite. Update this set with intent —
# adding a name here means autodiscovery is permitted to clobber whatever a
# human wrote on that field.
EXPECTED_DISCOVERY_FIELDS = frozenset(
    {
        # identity / network
        "fqdn",
        "ip_addresses",
        "mac_addresses",
        # type
        "server_type",
        "hypervisor",
        # OS
        "os_name",
        "os_version",
        "os_id",
        "os_id_like",
        "os_codename",
        "kernel",
        "architecture",
        # cpu / memory / disk totals
        "cpu_model",
        "cpu_cores",
        "ram_bytes",
        "disk_bytes",
        # asset / DMI / BIOS
        "vendor",
        "product_name",
        "product_uuid",
        "serial_number",
        "bios_vendor",
        "bios_version",
        "bios_date",
        # operational
        "boot_time",
        "exporter_version",
        "timezone",
        # structured
        "filesystems",
        "network_interfaces",
        "disks",
        # bookkeeping
        "last_discovered",
        "discovery_data",
    }
)

HUMAN_FIELDS = {"owner", "notes", "rack", "tags", "compliance_tags", "purpose",
                "patch_window", "warranty_expires", "asset_tag", "vlan",
                "location", "environment", "status"}


def test_discovery_fields_match_expected():
    assert DISCOVERY_FIELDS == EXPECTED_DISCOVERY_FIELDS


def test_human_fields_excluded_from_discovery():
    assert HUMAN_FIELDS.isdisjoint(DISCOVERY_FIELDS)
