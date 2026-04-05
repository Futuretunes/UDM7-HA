"""UniFi Network HA light platform.

Provides a light entity for each adopted UniFi device that has an LED.
Turning the light on/off controls the ``led_override`` setting on the
device via the controller's REST API.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinators.base import UniFiDataUpdateCoordinator
from .entity import UniFiEntity
from .hub import UniFiHub

# Type alias used in __init__.py — import so the platform signature matches.
from . import UniFiConfigEntry

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LED light entity
# ---------------------------------------------------------------------------


class UniFiLedLight(UniFiEntity, LightEntity):
    """Light entity controlling the LED on a UniFi device."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: UniFiDataUpdateCoordinator,
        hub: UniFiHub,
        mac: str,
        device_name: str,
        device_model: str,
        device_id: str,
    ) -> None:
        desc = EntityDescription(key="led")
        super().__init__(coordinator, desc, hub, mac, device_name, device_model)
        self._device_id = device_id
        self._attr_name = "Status LED"

    @property
    def is_on(self) -> bool | None:
        """Return whether the device LED is on."""
        if self._hub.device_coordinator is None:
            return None
        device = self._hub.device_coordinator.devices.get(self._device_mac)
        if device is None:
            return None
        return device.led_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device LED on."""
        _LOGGER.info("Turning LED on for %s (%s)", self._device_name, self._device_mac)
        await self._hub.legacy.set_device(
            self._device_id, {"led_override": "on"}
        )
        await self._hub.device_coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device LED off."""
        _LOGGER.info("Turning LED off for %s (%s)", self._device_name, self._device_mac)
        await self._hub.legacy.set_device(
            self._device_id, {"led_override": "off"}
        )
        await self._hub.device_coordinator.async_request_refresh()


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UniFiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UniFi Network HA LED light entities."""
    hub: UniFiHub = entry.runtime_data
    entities: list[UniFiLedLight] = []

    if hub.device_coordinator is None or hub.legacy is None:
        _LOGGER.debug("Device coordinator or legacy API not available — skipping light setup")
        return

    for mac, device in hub.device_coordinator.devices.items():
        if not device.adopted:
            continue

        dev_name = device.name or f"Device {mac}"
        dev_model = device.model_name or device.model or "UniFi Device"
        device_id = device.raw.get("_id", "")

        if not device_id:
            _LOGGER.debug("Device %s missing _id — skipping LED light", mac)
            continue

        entities.append(
            UniFiLedLight(
                coordinator=hub.device_coordinator,
                hub=hub,
                mac=mac,
                device_name=dev_name,
                device_model=dev_model,
                device_id=device_id,
            )
        )

    _LOGGER.debug("Setting up %d LED light entities", len(entities))
    async_add_entities(entities)
