"""UniFi Network HA binary sensor platform.

Provides binary sensors for gateway connectivity, WAN health, speedtest
status, and per-WAN-interface link/internet state.  Dynamic sensors
(per-WAN) are discovered at setup time based on the interfaces reported
by the gateway device.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ENABLE_DEVICE_SENSORS, CONF_ENABLE_PROTECT, CONF_ENABLE_VPN
from .coordinators.base import UniFiDataUpdateCoordinator
from .entity import UniFiEntity
from .hub import UniFiHub

# Type alias used in __init__.py — import so the platform signature matches.
from . import UniFiConfigEntry

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Binary sensor description
# ---------------------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class UniFiBinarySensorDescription(BinarySensorEntityDescription):
    """Extended binary-sensor description with a value-extraction callback.

    Attributes
    ----------
    value_fn:
        Called with the ``UniFiHub`` instance; must return ``True``/``False``
        (or ``None`` when unavailable).
    coordinator_key:
        Selects which coordinator the entity subscribes to for updates.
        One of ``"device"``, ``"health"``, or ``"wan_rate"``.
    """

    value_fn: Callable[[UniFiHub], bool | None]
    coordinator_key: str = "device"


# ---------------------------------------------------------------------------
# Coordinator lookup helper
# ---------------------------------------------------------------------------

def _get_coordinator(hub: UniFiHub, key: str) -> UniFiDataUpdateCoordinator:
    """Return the coordinator that matches *key*."""
    mapping: dict[str, UniFiDataUpdateCoordinator | None] = {
        "device": hub.device_coordinator,
        "health": hub.health_coordinator,
        "wan_rate": hub.wan_rate_coordinator,
        "protect": hub.protect_coordinator,
    }
    coordinator = mapping.get(key)
    if coordinator is None:
        raise ValueError(f"Unknown or uninitialised coordinator key: {key!r}")
    return coordinator


# ---------------------------------------------------------------------------
# Value-extraction helpers
# ---------------------------------------------------------------------------

def _gateway_device(hub: UniFiHub):
    """Return the gateway ``Device`` from the device coordinator, or *None*."""
    if hub.device_coordinator is None:
        return None
    return hub.device_coordinator.devices.get(hub.gateway_mac)


def _wan_iface(hub: UniFiHub, wan_name: str):
    """Return the WAN interface with *wan_name* from the device coordinator."""
    gw = _gateway_device(hub)
    if gw is None:
        return None
    for wi in gw.wan_interfaces:
        if wi.name == wan_name:
            return wi
    return None


# ---------------------------------------------------------------------------
# Static gateway binary sensors
# ---------------------------------------------------------------------------

GATEWAY_BINARY_SENSORS: tuple[UniFiBinarySensorDescription, ...] = (
    # Internet connectivity (from device coordinator)
    UniFiBinarySensorDescription(
        key="internet_connected",
        translation_key="internet_connected",
        name="Internet connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda hub: _gw_internet(hub),
        coordinator_key="device",
    ),
    # WAN health — problem sensor (inverted: on = problem exists)
    UniFiBinarySensorDescription(
        key="wan_health",
        translation_key="wan_health",
        name="WAN health problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda hub: _wan_health_problem(hub),
        coordinator_key="health",
    ),
    # Speedtest in progress
    UniFiBinarySensorDescription(
        key="speedtest_in_progress",
        translation_key="speedtest_in_progress",
        name="Speedtest in progress",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda hub: _speedtest_running(hub),
        coordinator_key="device",
    ),
)


def _gw_internet(hub: UniFiHub) -> bool | None:
    """Return whether the gateway reports internet connectivity."""
    gw = _gateway_device(hub)
    if gw is None:
        return None
    return gw.internet


def _wan_health_problem(hub: UniFiHub) -> bool | None:
    """Return True when the WAN health status is *not* 'ok'."""
    if hub.health_coordinator is None:
        return None
    wan = hub.health_coordinator.subsystems.get("wan")
    if wan is None:
        return None
    return wan.status != "ok"


def _speedtest_running(hub: UniFiHub) -> bool | None:
    """Return whether a speedtest is currently in progress."""
    gw = _gateway_device(hub)
    if gw is None:
        return None
    return gw.speedtest.in_progress if gw.speedtest else False


# ---------------------------------------------------------------------------
# VPN binary sensors (conditional on CONF_ENABLE_VPN)
# ---------------------------------------------------------------------------

VPN_BINARY_SENSORS: tuple[UniFiBinarySensorDescription, ...] = (
    UniFiBinarySensorDescription(
        key="vpn_active",
        translation_key="vpn_active",
        name="VPN active",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda hub: _vpn_active(hub),
        coordinator_key="health",
    ),
)


def _vpn_active(hub: UniFiHub) -> bool | None:
    """Return True if any VPN connection (remote user or site-to-site) is active."""
    if hub.health_coordinator is None:
        return None
    vpn = hub.health_coordinator.subsystems.get("vpn")
    if vpn is None:
        return None
    return (vpn.remote_user_num_active > 0) or (vpn.site_to_site_num_active > 0)


# ---------------------------------------------------------------------------
# VRRP / Shadow Mode binary sensors (conditional on gateway VRRP data)
# ---------------------------------------------------------------------------

VRRP_BINARY_SENSORS: tuple[UniFiBinarySensorDescription, ...] = (
    UniFiBinarySensorDescription(
        key="shadow_mode_active",
        name="Shadow Mode active",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:shield-sync",
        value_fn=lambda hub: _gw_vrrp(hub),
        coordinator_key="device",
    ),
)


def _gw_vrrp(hub: UniFiHub) -> bool | None:
    """Return True when VRRP / Shadow Mode is enabled on the gateway."""
    gw = _gateway_device(hub)
    if gw is None:
        return None
    return gw.vrrp_enabled


# ---------------------------------------------------------------------------
# Dynamic per-WAN binary sensor factories
# ---------------------------------------------------------------------------

def _make_wan_binary_sensors(wan_name: str) -> list[UniFiBinarySensorDescription]:
    """Create binary sensor descriptions for a single WAN interface."""
    safe_key = wan_name.lower().replace(" ", "_").replace("-", "_")
    label = wan_name.upper() if len(wan_name) <= 4 else wan_name.title()

    return [
        # Link up
        UniFiBinarySensorDescription(
            key=f"{safe_key}_link_up",
            name=f"{label} link up",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            value_fn=lambda hub, _wn=wan_name: _wan_link_up(hub, _wn),
            coordinator_key="device",
        ),
        # Internet reachable on this WAN
        UniFiBinarySensorDescription(
            key=f"{safe_key}_internet",
            name=f"{label} internet",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            value_fn=lambda hub, _wn=wan_name: _wan_internet(hub, _wn),
            coordinator_key="device",
        ),
    ]


def _wan_link_up(hub: UniFiHub, wan_name: str) -> bool | None:
    """Return whether the given WAN interface link is up."""
    wi = _wan_iface(hub, wan_name)
    if wi is None:
        return None
    return wi.up


def _wan_internet(hub: UniFiHub, wan_name: str) -> bool | None:
    """Return whether the given WAN interface has internet."""
    wi = _wan_iface(hub, wan_name)
    if wi is None:
        return None
    return wi.internet


# ---------------------------------------------------------------------------
# Dynamic per-switch-port binary sensor factories
# ---------------------------------------------------------------------------

def _get_device_port(hub: UniFiHub, mac: str, port_idx: int):
    """Return the port with *port_idx* on the device with *mac*."""
    if hub.device_coordinator is None:
        return None
    device = hub.device_coordinator.devices.get(mac)
    if device is None:
        return None
    for port in device.ports:
        if port.idx == port_idx:
            return port
    return None


def _make_switch_port_binary_sensors(
    mac: str, port_idx: int, port_label: str
) -> list[UniFiBinarySensorDescription]:
    """Create binary sensor descriptions for a single port on a switch."""
    prefix = f"port_{port_idx}"

    return [
        # SFP detected
        UniFiBinarySensorDescription(
            key=f"{prefix}_sfp_detected",
            name=f"{port_label} SFP detected",
            icon="mdi:chip",
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda hub, _m=mac, _i=port_idx: (
                getattr(_get_device_port(hub, _m, _i), "sfp_found", None)
            ),
            coordinator_key="device",
        ),
    ]


# ---------------------------------------------------------------------------
# Protect camera helpers
# ---------------------------------------------------------------------------

def _camera_connected(hub: UniFiHub, cam_id: str) -> bool | None:
    """Return whether the camera with *cam_id* is connected."""
    if not hub.protect_coordinator:
        return None
    cam = hub.protect_coordinator.cameras.get(cam_id)
    return cam.is_connected if cam else None


# ---------------------------------------------------------------------------
# Binary sensor entity
# ---------------------------------------------------------------------------

class UniFiBinarySensorEntity(UniFiEntity, BinarySensorEntity):
    """Binary sensor entity for UniFi Network HA."""

    entity_description: UniFiBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        """Return the current binary sensor state."""
        try:
            return self.entity_description.value_fn(self._hub)
        except (KeyError, AttributeError, TypeError):
            _LOGGER.debug(
                "Error reading value for binary sensor %s",
                self.entity_description.key,
                exc_info=True,
            )
            return None


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    entry: UniFiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UniFi Network HA binary sensor entities."""
    hub: UniFiHub = entry.runtime_data
    entities: list[UniFiBinarySensorEntity] = []

    # We need a gateway to create any binary sensors.
    if not hub.gateway_mac or hub.device_coordinator is None:
        _LOGGER.debug("No gateway or device coordinator — skipping binary sensor setup")
        return

    gateway = hub.device_coordinator.devices.get(hub.gateway_mac)
    if gateway is None:
        _LOGGER.debug("Gateway MAC %s not found in devices", hub.gateway_mac)
        return

    gw_name = gateway.name or "Gateway"
    gw_model = gateway.model_name or gateway.model or "UniFi Gateway"

    # -- Static gateway binary sensors ---------------------------------------
    for desc in GATEWAY_BINARY_SENSORS:
        coordinator = _get_coordinator(hub, desc.coordinator_key)
        entities.append(
            UniFiBinarySensorEntity(
                coordinator=coordinator,
                description=desc,
                hub=hub,
                mac=hub.gateway_mac,
                device_name=gw_name,
                device_model=gw_model,
            )
        )

    # -- VPN binary sensors (optional) -----------------------------------------
    if hub.get_option(CONF_ENABLE_VPN, True) and hub.health_coordinator is not None:
        for desc in VPN_BINARY_SENSORS:
            coordinator = _get_coordinator(hub, desc.coordinator_key)
            entities.append(
                UniFiBinarySensorEntity(
                    coordinator=coordinator,
                    description=desc,
                    hub=hub,
                    mac=hub.gateway_mac,
                    device_name=gw_name,
                    device_model=gw_model,
                )
            )

    # -- VRRP / Shadow Mode binary sensors (conditional on gateway VRRP) ------
    if gateway.vrrp_enabled or gateway.vrrp_state:
        for desc in VRRP_BINARY_SENSORS:
            coordinator = _get_coordinator(hub, desc.coordinator_key)
            entities.append(
                UniFiBinarySensorEntity(
                    coordinator=coordinator,
                    description=desc,
                    hub=hub,
                    mac=hub.gateway_mac,
                    device_name=gw_name,
                    device_model=gw_model,
                )
            )

    # -- Dynamic per-WAN binary sensors --------------------------------------
    for wan in gateway.wan_interfaces:
        if not wan.name:
            continue
        for desc in _make_wan_binary_sensors(wan.name):
            coordinator = _get_coordinator(hub, desc.coordinator_key)
            entities.append(
                UniFiBinarySensorEntity(
                    coordinator=coordinator,
                    description=desc,
                    hub=hub,
                    mac=hub.gateway_mac,
                    device_name=gw_name,
                    device_model=gw_model,
                )
            )

    # -- Dynamic per-switch-port binary sensors (SFP) -------------------------
    if hub.get_option(CONF_ENABLE_DEVICE_SENSORS, True) and hub.device_coordinator is not None:
        for mac, device in hub.device_coordinator.devices.items():
            if device.type != "usw":
                continue
            dev_name = device.name or f"Switch {mac}"
            dev_model = device.model_name or device.model or "UniFi Switch"
            for port in device.ports:
                if port.idx <= 0:
                    continue
                # Only create SFP binary sensors for ports that have SFP capability
                if not port.sfp_found:
                    continue
                port_label = port.name or f"Port {port.idx}"
                for desc in _make_switch_port_binary_sensors(mac, port.idx, port_label):
                    coordinator = _get_coordinator(hub, desc.coordinator_key)
                    entities.append(
                        UniFiBinarySensorEntity(
                            coordinator=coordinator,
                            description=desc,
                            hub=hub,
                            mac=mac,
                            device_name=dev_name,
                            device_model=dev_model,
                        )
                    )

    # -- Protect camera binary sensors (connectivity) ----------------------
    if (
        hub.get_option(CONF_ENABLE_PROTECT, False)
        and hub.protect_coordinator is not None
        and hub.protect_coordinator.available
    ):
        for cam_id, camera in hub.protect_coordinator.cameras.items():
            desc = UniFiBinarySensorDescription(
                key=f"camera_{cam_id}_connected",
                name=f"{camera.name} connected",
                device_class=BinarySensorDeviceClass.CONNECTIVITY,
                value_fn=lambda hub, _id=cam_id: _camera_connected(hub, _id),
                coordinator_key="protect",
            )
            entities.append(
                UniFiBinarySensorEntity(
                    coordinator=hub.protect_coordinator,
                    description=desc,
                    hub=hub,
                    mac=hub.gateway_mac,
                    device_name=gw_name,
                    device_model=gw_model,
                )
            )

    _LOGGER.debug(
        "Setting up %d binary sensor entities for gateway %s",
        len(entities),
        gw_name,
    )
    async_add_entities(entities)
