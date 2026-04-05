"""UniFi Network HA button platform.

Provides action buttons for running speed tests, restarting the gateway,
and forcing a re-provision.  Dynamic buttons (per-WAN speedtest) are
discovered at setup time based on the interfaces reported by the gateway.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ENABLE_ALARMS, CONF_ENABLE_DEVICE_CONTROLS
from .coordinators.base import UniFiDataUpdateCoordinator
from .entity import UniFiEntity
from .hub import UniFiHub

# Type alias used in __init__.py — import so the platform signature matches.
from . import UniFiConfigEntry

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Button description
# ---------------------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class UniFiButtonDescription(ButtonEntityDescription):
    """Extended button description with an async press callback.

    Attributes
    ----------
    press_fn:
        Called with the ``UniFiHub`` instance when the button is pressed.
    """

    press_fn: Callable[[UniFiHub], Awaitable[Any]]


# ---------------------------------------------------------------------------
# Static gateway buttons
# ---------------------------------------------------------------------------

GATEWAY_BUTTONS: tuple[UniFiButtonDescription, ...] = (
    # Run speedtest on default WAN
    UniFiButtonDescription(
        key="run_speedtest",
        translation_key="run_speedtest",
        name="Run speedtest",
        icon="mdi:speedometer",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda hub: hub.legacy.run_speedtest(hub.gateway_mac),
    ),
    # Restart gateway
    UniFiButtonDescription(
        key="restart_gateway",
        translation_key="restart_gateway",
        name="Restart gateway",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda hub: hub.legacy.restart_device(hub.gateway_mac),
    ),
    # Force provision
    UniFiButtonDescription(
        key="force_provision",
        translation_key="force_provision",
        name="Force provision",
        icon="mdi:cog-sync",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda hub: hub.legacy.force_provision(hub.gateway_mac),
    ),
)


# ---------------------------------------------------------------------------
# Alarm buttons (conditional on CONF_ENABLE_ALARMS)
# ---------------------------------------------------------------------------

ALARM_BUTTONS: tuple[UniFiButtonDescription, ...] = (
    UniFiButtonDescription(
        key="archive_alarms",
        translation_key="archive_alarms",
        name="Archive all alarms",
        icon="mdi:archive-arrow-down",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda hub: _archive_alarms(hub),
    ),
)


async def _archive_alarms(hub: UniFiHub) -> None:
    """Archive all alarms and refresh the alarm coordinator."""
    await hub.legacy.archive_alarms()
    if hub.alarm_coordinator:
        await hub.alarm_coordinator.async_request_refresh()


# ---------------------------------------------------------------------------
# Dynamic per-WAN speedtest button factory
# ---------------------------------------------------------------------------

def _make_wan_speedtest_button(wan_name: str) -> UniFiButtonDescription:
    """Create a speedtest button description for a specific WAN interface."""
    safe_key = wan_name.lower().replace(" ", "_").replace("-", "_")
    label = wan_name.upper() if len(wan_name) <= 4 else wan_name.title()

    return UniFiButtonDescription(
        key=f"run_speedtest_{safe_key}",
        name=f"Run speedtest {label}",
        icon="mdi:speedometer",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda hub, _wn=wan_name: hub.legacy.run_speedtest(
            hub.gateway_mac, interface=_wn
        ),
    )


# ---------------------------------------------------------------------------
# Per-device button factories (restart, locate)
# ---------------------------------------------------------------------------

def _make_device_buttons(mac: str, device_name: str) -> list[UniFiButtonDescription]:
    """Create restart and locate buttons for an adopted device."""
    return [
        UniFiButtonDescription(
            key=f"restart_{mac}",
            translation_key="restart_device",
            name="Restart",
            device_class=ButtonDeviceClass.RESTART,
            entity_category=EntityCategory.CONFIG,
            press_fn=lambda hub, _m=mac: hub.legacy.restart_device(_m),
        ),
        UniFiButtonDescription(
            key=f"locate_{mac}",
            translation_key="locate_device",
            name="Locate",
            icon="mdi:crosshairs-gps",
            entity_category=EntityCategory.DIAGNOSTIC,
            press_fn=lambda hub, _m=mac: hub.legacy.locate_device(_m, enable=True),
        ),
    ]


# ---------------------------------------------------------------------------
# Per-PoE-port power-cycle button factory
# ---------------------------------------------------------------------------

def _make_power_cycle_button(
    mac: str, port_idx: int, port_name: str,
) -> UniFiButtonDescription:
    """Create a power-cycle button for a PoE port."""
    return UniFiButtonDescription(
        key=f"power_cycle_port_{port_idx}",
        translation_key="power_cycle_port",
        name=f"Power cycle {port_name}",
        icon="mdi:power-cycle",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda hub, _m=mac, _i=port_idx: hub.legacy.power_cycle_port(_m, _i),
    )


# ---------------------------------------------------------------------------
# Button entity
# ---------------------------------------------------------------------------

class UniFiButtonEntity(UniFiEntity, ButtonEntity):
    """Button entity for UniFi Network HA."""

    entity_description: UniFiButtonDescription

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_fn(self._hub)


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    entry: UniFiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UniFi Network HA button entities."""
    hub: UniFiHub = entry.runtime_data
    entities: list[UniFiButtonEntity] = []

    # We need a gateway and the legacy API to create button entities.
    if not hub.gateway_mac or hub.device_coordinator is None:
        _LOGGER.debug("No gateway or device coordinator — skipping button setup")
        return

    if hub.legacy is None:
        _LOGGER.debug("Legacy API not available — skipping button setup")
        return

    gateway = hub.device_coordinator.devices.get(hub.gateway_mac)
    if gateway is None:
        _LOGGER.debug("Gateway MAC %s not found in devices", hub.gateway_mac)
        return

    gw_name = gateway.name or "Gateway"
    gw_model = gateway.model_name or gateway.model or "UniFi Gateway"

    # Buttons don't need real-time data — attach to device_coordinator so
    # they belong to the coordinator entity group.
    coordinator = hub.device_coordinator

    # -- Static gateway buttons ----------------------------------------------
    for desc in GATEWAY_BUTTONS:
        entities.append(
            UniFiButtonEntity(
                coordinator=coordinator,
                description=desc,
                hub=hub,
                mac=hub.gateway_mac,
                device_name=gw_name,
                device_model=gw_model,
            )
        )

    # -- Alarm buttons (optional) -----------------------------------------------
    if hub.get_option(CONF_ENABLE_ALARMS, True) and hub.alarm_coordinator is not None:
        for desc in ALARM_BUTTONS:
            entities.append(
                UniFiButtonEntity(
                    coordinator=coordinator,
                    description=desc,
                    hub=hub,
                    mac=hub.gateway_mac,
                    device_name=gw_name,
                    device_model=gw_model,
                )
            )

    # -- Dynamic per-WAN speedtest buttons -----------------------------------
    for wan in gateway.wan_interfaces:
        if not wan.name:
            continue
        desc = _make_wan_speedtest_button(wan.name)
        entities.append(
            UniFiButtonEntity(
                coordinator=coordinator,
                description=desc,
                hub=hub,
                mac=hub.gateway_mac,
                device_name=gw_name,
                device_model=gw_model,
            )
        )

    # -- Per-device restart and locate buttons (all adopted devices) ---------
    if hub.get_option(CONF_ENABLE_DEVICE_CONTROLS, True):
        for mac, device in hub.device_coordinator.devices.items():
            if not device.adopted:
                continue
            # Skip the gateway — it already has a restart button above.
            if mac == hub.gateway_mac:
                continue

            dev_name = device.name or f"Device {mac}"
            dev_model = device.model_name or device.model or "UniFi Device"

            for desc in _make_device_buttons(mac, dev_name):
                entities.append(
                    UniFiButtonEntity(
                        coordinator=coordinator,
                        description=desc,
                        hub=hub,
                        mac=mac,
                        device_name=dev_name,
                        device_model=dev_model,
                    )
                )

    # -- PoE port power-cycle buttons (per PoE port on switches) ------------
    if hub.get_option(CONF_ENABLE_DEVICE_CONTROLS, True):
        for mac, device in hub.device_coordinator.devices.items():
            if device.type != "usw":
                continue

            dev_name = device.name or f"Switch {mac}"
            dev_model = device.model_name or device.model or "UniFi Switch"

            for port in device.ports:
                if port.idx <= 0:
                    continue
                if not (port.poe_enable or port.poe_mode):
                    continue

                port_name = port.name or f"Port {port.idx}"
                desc = _make_power_cycle_button(mac, port.idx, port_name)
                entities.append(
                    UniFiButtonEntity(
                        coordinator=coordinator,
                        description=desc,
                        hub=hub,
                        mac=mac,
                        device_name=dev_name,
                        device_model=dev_model,
                    )
                )

    _LOGGER.debug(
        "Setting up %d button entities for gateway %s", len(entities), gw_name
    )
    async_add_entities(entities)
