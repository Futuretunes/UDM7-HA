"""UniFi Network HA device tracker platform.

Each connected (or recently connected) network client is represented as a
``ScannerEntity`` device tracker.  A heartbeat mechanism keeps a client
marked as "home" for a configurable period after it disappears from the
active-client list, avoiding flapping when clients momentarily drop off Wi-Fi.

New clients discovered during coordinator updates are added dynamically so
there is no need for a restart.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.models import Client
from .const import (
    CONF_CLIENT_HEARTBEAT,
    CONF_SSID_FILTER,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_WIRED,
    CONF_TRACK_WIRELESS,
    DEFAULT_CLIENT_HEARTBEAT,
    DEFAULT_TRACK_CLIENTS,
    DEFAULT_TRACK_WIRED,
    DEFAULT_TRACK_WIRELESS,
    DOMAIN,
)
from .coordinators.client import ClientCoordinator

if TYPE_CHECKING:
    from .hub import UniFiHub

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------


class UniFiClientTracker(CoordinatorEntity[ClientCoordinator], ScannerEntity):
    """Device tracker entity for a single UniFi network client."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ClientCoordinator,
        hub: UniFiHub,
        client: Client,
    ) -> None:
        super().__init__(coordinator)
        self._hub = hub
        self._client_mac = client.mac
        self._attr_unique_id = f"{client.mac}_tracker"
        self._attr_name = "Tracker"
        self._last_seen: float = time.time() if client.mac in coordinator.clients else 0
        self._heartbeat_timeout: int = hub.get_option(
            CONF_CLIENT_HEARTBEAT, DEFAULT_CLIENT_HEARTBEAT
        )

    # -- ScannerEntity interface -------------------------------------------

    @property
    def is_connected(self) -> bool:
        """Return True if the client is considered connected.

        A client is "connected" while it appears in the active-client dict.
        After it drops off, the heartbeat keeps it connected for a
        configurable grace period.
        """
        client = self._hub.client_coordinator.clients.get(self._client_mac)
        if client is not None:
            self._last_seen = time.time()
            return True
        # Grace period — still "home" if recently seen.
        if self._last_seen and (time.time() - self._last_seen) < self._heartbeat_timeout:
            return True
        return False

    @property
    def source_type(self) -> SourceType:
        """Return the source type — ROUTER for all clients."""
        return SourceType.ROUTER

    @property
    def hostname(self) -> str | None:
        """Return the hostname of the client."""
        client = self._hub.client_coordinator.all_known.get(self._client_mac)
        if client:
            return client.hostname or None
        return None

    @property
    def ip_address(self) -> str | None:
        """Return the IP address of the client."""
        client = self._hub.client_coordinator.all_known.get(self._client_mac)
        if client:
            return client.ip or None
        return None

    @property
    def mac_address(self) -> str:
        """Return the MAC address of the client."""
        return self._client_mac

    # -- Extra attributes --------------------------------------------------

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes about the client.

        Includes connection details, wireless stats, and bandwidth figures
        so the data is available without needing separate sensor entities.
        """
        client = self._hub.client_coordinator.all_known.get(self._client_mac)
        if not client:
            return {}

        attrs: dict[str, Any] = {}

        # Connection type
        if client.is_wired:
            attrs["wired"] = True
            if client.sw_mac:
                attrs["switch_mac"] = client.sw_mac
            if client.sw_port:
                attrs["switch_port"] = client.sw_port
        else:
            attrs["wired"] = False
            if client.essid:
                attrs["ssid"] = client.essid
            if client.ap_mac:
                attrs["ap_mac"] = client.ap_mac
            if client.signal:
                attrs["signal"] = client.signal
            if client.rssi:
                attrs["rssi"] = client.rssi
            if client.channel:
                attrs["channel"] = client.channel
            if client.radio:
                attrs["radio"] = client.radio
            if client.radio_proto:
                attrs["wifi_standard"] = client.radio_proto
            if client.satisfaction:
                attrs["satisfaction"] = client.satisfaction

        # Network / IP
        if client.ip:
            attrs["ip"] = client.ip
        if client.network:
            attrs["network"] = client.network
        if client.vlan:
            attrs["vlan"] = client.vlan

        # Bandwidth (only when non-zero to avoid clutter)
        if client.rx_rate:
            attrs["rx_rate"] = client.rx_rate
        if client.tx_rate:
            attrs["tx_rate"] = client.tx_rate
        if client.rx_bytes_r:
            attrs["rx_bytes_r"] = client.rx_bytes_r
        if client.tx_bytes_r:
            attrs["tx_bytes_r"] = client.tx_bytes_r

        # Misc
        if client.uptime:
            attrs["uptime"] = client.uptime
        if client.os_name:
            attrs["os"] = client.os_name
        if client.is_guest:
            attrs["guest"] = True
        if client.blocked:
            attrs["blocked"] = True

        # Device fingerprinting
        if client.dev_cat:
            attrs["device_category"] = client.dev_cat
        if client.dev_family:
            attrs["device_family"] = client.dev_family
        if client.dev_vendor:
            attrs["device_vendor"] = client.dev_vendor

        return attrs

    # -- Device registry ---------------------------------------------------

    @property
    def device_info(self) -> DeviceInfo:
        """Each client gets its own HA device, identified by MAC."""
        client = self._hub.client_coordinator.all_known.get(self._client_mac)
        name = "Unknown"
        if client:
            name = client.name or client.hostname or client.mac
        info = DeviceInfo(
            identifiers={(DOMAIN, self._client_mac)},
            connections={(CONNECTION_NETWORK_MAC, self._client_mac)},
            name=name if name != self._client_mac else f"Client {self._client_mac}",
            manufacturer=client.oui if client and client.oui else "Unknown",
            model="Network Client",
        )
        # Link clients to their connected AP/switch → creates device hierarchy
        if client:
            parent_mac = client.ap_mac or client.sw_mac
            if parent_mac:
                info["via_device"] = (DOMAIN, parent_mac)
            elif self._hub.gateway_mac:
                info["via_device"] = (DOMAIN, self._hub.gateway_mac)
        return info


# ---------------------------------------------------------------------------
# Filtering helper
# ---------------------------------------------------------------------------


def _should_track(hub: UniFiHub, client: Client) -> bool:
    """Return True if the client matches the user's tracking options."""
    track_wired = hub.get_option(CONF_TRACK_WIRED, DEFAULT_TRACK_WIRED)
    track_wireless = hub.get_option(CONF_TRACK_WIRELESS, DEFAULT_TRACK_WIRELESS)
    ssid_filter_raw: str = hub.get_option(CONF_SSID_FILTER, "")

    if client.is_wired and not track_wired:
        return False
    if not client.is_wired and not track_wireless:
        return False

    # SSID allow-list: if configured, only track wireless clients on
    # the listed SSIDs.  Wired clients pass through unconditionally.
    if ssid_filter_raw and not client.is_wired:
        allowed = {s.strip() for s in ssid_filter_raw.split(",") if s.strip()}
        if allowed and client.essid and client.essid not in allowed:
            return False

    return True


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UniFi client device tracker entities."""
    hub: UniFiHub = entry.runtime_data

    # Guard: client tracking may be globally disabled, or the coordinator
    # may not have been initialised.
    if not hub.get_option(CONF_TRACK_CLIENTS, DEFAULT_TRACK_CLIENTS):
        _LOGGER.debug("Client tracking disabled by configuration")
        return

    if not hub.client_coordinator:
        _LOGGER.debug("Client coordinator not available — skipping device tracker setup")
        return

    tracked_macs: set[str] = set()

    @callback
    def _async_add_new_clients() -> None:
        """Discover and register tracker entities for newly seen clients."""
        new_entities: list[UniFiClientTracker] = []
        for mac, client in hub.client_coordinator.clients.items():
            if mac not in tracked_macs and _should_track(hub, client):
                tracked_macs.add(mac)
                new_entities.append(
                    UniFiClientTracker(hub.client_coordinator, hub, client)
                )
        if new_entities:
            _LOGGER.debug(
                "Adding %d new client tracker(s): %s",
                len(new_entities),
                ", ".join(e.mac_address for e in new_entities),
            )
            async_add_entities(new_entities)

    # Add entities for clients already known at startup.
    _async_add_new_clients()

    # Re-evaluate on every coordinator update so newly discovered clients
    # are picked up dynamically.
    entry.async_on_unload(
        hub.client_coordinator.async_add_listener(_async_add_new_clients)
    )
