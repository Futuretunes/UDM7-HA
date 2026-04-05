"""Wrapper for the legacy UniFi API v1 endpoints.

These endpoints live under ``/api/s/{site}/...`` and cover the bulk of
device, client, and site management operations available on all UniFi
controllers (standalone and UniFi OS).
"""

from __future__ import annotations

import logging
from typing import Any

from .client import UniFiApiClient

_LOGGER = logging.getLogger(__name__)


class LocalLegacyApi:
    """UniFi Legacy API v1 wrapper."""

    def __init__(self, client: UniFiApiClient) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _site_path(self, path: str) -> str:
        """Build ``/api/s/{site}/{path}``."""
        return f"/api/s/{self._client.site}/{path}"

    # ==================================================================
    # Read endpoints
    # ==================================================================

    async def get_devices(self) -> list[dict]:
        """Return all adopted devices.

        ``GET /api/s/{site}/stat/device``
        """
        data = await self._client.get(self._site_path("stat/device"))
        return data if isinstance(data, list) else []

    async def get_device(self, mac: str) -> dict | None:
        """Return a single device by MAC address, or *None* if not found.

        ``GET /api/s/{site}/stat/device/{mac}``
        """
        data = await self._client.get(self._site_path(f"stat/device/{mac}"))
        if isinstance(data, list) and data:
            return data[0]
        return None

    async def get_clients(self) -> list[dict]:
        """Return all currently-connected clients.

        ``GET /api/s/{site}/stat/sta``
        """
        data = await self._client.get(self._site_path("stat/sta"))
        return data if isinstance(data, list) else []

    async def get_all_users(self) -> list[dict]:
        """Return every known client (including offline / historical).

        ``GET /api/s/{site}/rest/user``
        """
        data = await self._client.get(self._site_path("rest/user"))
        return data if isinstance(data, list) else []

    async def get_health(self) -> list[dict]:
        """Return site health subsystem summaries.

        ``GET /api/s/{site}/stat/health``
        """
        data = await self._client.get(self._site_path("stat/health"))
        return data if isinstance(data, list) else []

    async def get_alarms(self, archived: bool = False) -> list[dict]:
        """Return alarms for the site.

        ``GET /api/s/{site}/stat/alarm``

        Args:
            archived: When *False* (default) only unarchived alarms are
                returned.  When *True* all alarms are returned.
        """
        data = await self._client.get(self._site_path("stat/alarm"))
        if not isinstance(data, list):
            return []
        if not archived:
            data = [a for a in data if not a.get("archived", False)]
        return data

    async def get_events(self, limit: int = 100) -> list[dict]:
        """Return recent events.

        ``GET /api/s/{site}/stat/event``

        Args:
            limit: Maximum number of events to retrieve (default 100).
        """
        data = await self._client.get(
            self._site_path("stat/event"),
            params={"_limit": str(limit)},
        )
        return data if isinstance(data, list) else []

    async def get_site_dpi(self) -> list[dict]:
        """Return DPI (Deep Packet Inspection) stats for the site.

        ``GET /api/s/{site}/stat/sitedpi``
        """
        data = await self._client.get(self._site_path("stat/sitedpi"))
        return data if isinstance(data, list) else []

    async def get_sysinfo(self) -> list[dict]:
        """Return controller system information.

        ``GET /api/s/{site}/stat/sysinfo``
        """
        data = await self._client.get(self._site_path("stat/sysinfo"))
        return data if isinstance(data, list) else []

    async def get_sites(self) -> list[dict]:
        """Return all sites visible to the current user.

        ``GET /api/self/sites``
        """
        data = await self._client.get("/api/self/sites")
        return data if isinstance(data, list) else []

    async def get_wlans(self) -> list[dict]:
        """Return WLAN configurations.

        ``GET /api/s/{site}/rest/wlanconf``
        """
        data = await self._client.get(self._site_path("rest/wlanconf"))
        return data if isinstance(data, list) else []

    async def get_port_forwards(self) -> list[dict]:
        """Return port-forwarding rules.

        ``GET /api/s/{site}/rest/portforward``
        """
        data = await self._client.get(self._site_path("rest/portforward"))
        return data if isinstance(data, list) else []

    async def get_dpi_apps(self) -> list[dict]:
        """Return DPI application definitions.

        ``GET /api/s/{site}/rest/dpiapp``
        """
        data = await self._client.get(self._site_path("rest/dpiapp"))
        return data if isinstance(data, list) else []

    async def get_dpi_groups(self) -> list[dict]:
        """Return DPI groups.

        ``GET /api/s/{site}/rest/dpigroup``
        """
        data = await self._client.get(self._site_path("rest/dpigroup"))
        return data if isinstance(data, list) else []

    async def get_network_conf(self) -> list[dict]:
        """Return network configurations (VLANs, subnets, etc.).

        ``GET /api/s/{site}/rest/networkconf``
        """
        data = await self._client.get(self._site_path("rest/networkconf"))
        return data if isinstance(data, list) else []

    async def get_vouchers(self) -> list[dict]:
        """Return guest-portal vouchers.

        ``GET /api/s/{site}/stat/voucher``
        """
        data = await self._client.get(self._site_path("stat/voucher"))
        return data if isinstance(data, list) else []

    async def get_traffic_report(
        self, interval: str = "hourly", attrs: list[str] | None = None
    ) -> list[dict]:
        """Return traffic stats for the site.

        ``GET /api/s/{site}/stat/report/{interval}.site``

        Args:
            interval: ``"5minutes"``, ``"hourly"``, ``"daily"``, ``"monthly"``
            attrs: List of attributes to include, e.g.
                ``["bytes", "num_sta", "time", "wan-rx_bytes", "wan-tx_bytes"]``
        """
        params: dict[str, Any] = {}
        if attrs:
            params["attrs"] = attrs
        data = await self._client.get(
            self._site_path(f"stat/report/{interval}.site"), params=params
        )
        return data if isinstance(data, list) else []

    async def create_voucher(
        self,
        count: int = 1,
        quota: int = 1,
        expire: int = 1440,
        up_bandwidth: int | None = None,
        down_bandwidth: int | None = None,
        byte_quota: int | None = None,
        note: str = "",
    ) -> list[dict]:
        """Create guest vouchers.

        ``POST /api/s/{site}/cmd/hotspot`` with ``cmd=create-voucher``

        Args:
            count: Number of vouchers to create.
            quota: Number of uses per voucher (``0`` = unlimited).
            expire: Validity period in minutes (default 1440 = 24 h).
            up_bandwidth: Upload bandwidth limit in kbps.
            down_bandwidth: Download bandwidth limit in kbps.
            byte_quota: Data transfer limit in megabytes.
            note: Optional note attached to the voucher(s).
        """
        payload: dict[str, Any] = {
            "cmd": "create-voucher",
            "n": count,
            "quota": quota,
            "expire": expire,
        }
        if up_bandwidth is not None:
            payload["up"] = up_bandwidth
        if down_bandwidth is not None:
            payload["down"] = down_bandwidth
        if byte_quota is not None:
            payload["bytes"] = byte_quota
        if note:
            payload["note"] = note
        data = await self._client.post(
            self._site_path("cmd/hotspot"), json=payload
        )
        return data if isinstance(data, list) else []

    async def revoke_voucher(self, voucher_id: str) -> dict:
        """Revoke a voucher.

        ``POST /api/s/{site}/cmd/hotspot`` with ``cmd=delete-voucher``

        Args:
            voucher_id: The ``_id`` of the voucher to revoke.
        """
        data = await self._client.post(
            self._site_path("cmd/hotspot"),
            json={"cmd": "delete-voucher", "_id": voucher_id},
        )
        return data if isinstance(data, dict) else {}

    # ==================================================================
    # Command endpoints
    # ==================================================================

    async def run_speedtest(self, mac: str, interface: str = "wan") -> dict:
        """Trigger a speed test on a gateway device.

        ``POST /api/s/{site}/cmd/devmgr``

        Args:
            mac: MAC address of the gateway.
            interface: Interface to test (default ``"wan"``).
        """
        data = await self._client.post(
            self._site_path("cmd/devmgr"),
            json={"cmd": "speedtest", "mac": mac, "interface": interface},
        )
        return data if isinstance(data, dict) else {}

    async def restart_device(self, mac: str) -> dict:
        """Restart (reboot) a device.

        ``POST /api/s/{site}/cmd/devmgr``
        """
        data = await self._client.post(
            self._site_path("cmd/devmgr"),
            json={"cmd": "restart", "mac": mac},
        )
        return data if isinstance(data, dict) else {}

    async def force_provision(self, mac: str) -> dict:
        """Force re-provision a device.

        ``POST /api/s/{site}/cmd/devmgr``
        """
        data = await self._client.post(
            self._site_path("cmd/devmgr"),
            json={"cmd": "force-provision", "mac": mac},
        )
        return data if isinstance(data, dict) else {}

    async def locate_device(self, mac: str, enable: bool = True) -> dict:
        """Enable or disable the locate LED on a device.

        ``POST /api/s/{site}/cmd/devmgr``

        Args:
            mac: MAC address of the device.
            enable: *True* to turn on the locate LED, *False* to turn it off.
        """
        cmd = "set-locate" if enable else "unset-locate"
        data = await self._client.post(
            self._site_path("cmd/devmgr"),
            json={"cmd": cmd, "mac": mac},
        )
        return data if isinstance(data, dict) else {}

    async def power_cycle_port(self, mac: str, port_idx: int) -> dict:
        """Power-cycle a PoE port on a switch.

        ``POST /api/s/{site}/cmd/devmgr``

        Args:
            mac: MAC address of the switch.
            port_idx: 1-based port index to power-cycle.
        """
        data = await self._client.post(
            self._site_path("cmd/devmgr"),
            json={"cmd": "power-cycle", "mac": mac, "port_idx": port_idx},
        )
        return data if isinstance(data, dict) else {}

    async def upgrade_device(self, mac: str) -> dict:
        """Trigger firmware upgrade on a device.

        ``POST /api/s/{site}/cmd/devmgr``
        """
        data = await self._client.post(
            self._site_path("cmd/devmgr"),
            json={"cmd": "upgrade", "mac": mac},
        )
        return data if isinstance(data, dict) else {}

    async def block_client(self, mac: str) -> dict:
        """Block a client from accessing the network.

        ``POST /api/s/{site}/cmd/stamgr``
        """
        data = await self._client.post(
            self._site_path("cmd/stamgr"),
            json={"cmd": "block-sta", "mac": mac},
        )
        return data if isinstance(data, dict) else {}

    async def unblock_client(self, mac: str) -> dict:
        """Unblock a previously blocked client.

        ``POST /api/s/{site}/cmd/stamgr``
        """
        data = await self._client.post(
            self._site_path("cmd/stamgr"),
            json={"cmd": "unblock-sta", "mac": mac},
        )
        return data if isinstance(data, dict) else {}

    async def kick_client(self, mac: str) -> dict:
        """Disconnect (kick) a client from the network.

        ``POST /api/s/{site}/cmd/stamgr``
        """
        data = await self._client.post(
            self._site_path("cmd/stamgr"),
            json={"cmd": "kick-sta", "mac": mac},
        )
        return data if isinstance(data, dict) else {}

    async def forget_client(self, macs: list[str]) -> dict:
        """Remove one or more clients from the known-clients list.

        ``POST /api/s/{site}/cmd/stamgr``

        Args:
            macs: List of MAC addresses to forget.
        """
        data = await self._client.post(
            self._site_path("cmd/stamgr"),
            json={"cmd": "forget-sta", "macs": macs},
        )
        return data if isinstance(data, dict) else {}

    async def archive_alarms(self) -> dict:
        """Archive all alarms.

        ``POST /api/s/{site}/cmd/evtmgt``
        """
        data = await self._client.post(
            self._site_path("cmd/evtmgt"),
            json={"cmd": "archive-all-alarms"},
        )
        return data if isinstance(data, dict) else {}

    # ==================================================================
    # Config (REST) endpoints
    # ==================================================================

    async def set_wlan(self, wlan_id: str, data: dict) -> dict:
        """Update a WLAN configuration.

        ``PUT /api/s/{site}/rest/wlanconf/{id}``

        Args:
            wlan_id: The ``_id`` of the WLAN to update.
            data: Dictionary of fields to change.
        """
        result = await self._client.put(
            self._site_path(f"rest/wlanconf/{wlan_id}"),
            json=data,
        )
        return result if isinstance(result, dict) else {}

    async def set_device(self, device_id: str, data: dict) -> dict:
        """Update a device configuration.

        ``PUT /api/s/{site}/rest/device/{id}``

        Args:
            device_id: The ``_id`` of the device to update.
            data: Dictionary of fields to change.
        """
        result = await self._client.put(
            self._site_path(f"rest/device/{device_id}"),
            json=data,
        )
        return result if isinstance(result, dict) else {}

    async def set_port_forward(self, pf_id: str, data: dict) -> dict:
        """Update a port-forwarding rule.

        ``PUT /api/s/{site}/rest/portforward/{id}``

        Args:
            pf_id: The ``_id`` of the port-forward rule to update.
            data: Dictionary of fields to change.
        """
        result = await self._client.put(
            self._site_path(f"rest/portforward/{pf_id}"),
            json=data,
        )
        return result if isinstance(result, dict) else {}

    async def set_dpi_group(self, group_id: str, data: dict) -> dict:
        """Update a DPI restriction group.

        ``PUT /api/s/{site}/rest/dpigroup/{id}``

        Args:
            group_id: The ``_id`` of the DPI group to update.
            data: Dictionary of fields to change (e.g. ``{"enabled": True}``).
        """
        result = await self._client.put(
            self._site_path(f"rest/dpigroup/{group_id}"),
            json=data,
        )
        return result if isinstance(result, dict) else {}
