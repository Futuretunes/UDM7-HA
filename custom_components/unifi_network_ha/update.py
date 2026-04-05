"""UniFi Network HA update platform.

Provides firmware update entities for all adopted UniFi devices.  Each entity
reports the installed firmware version and, when an upgrade is available,
the target version.  The ``install`` action triggers the upgrade via the
controller's device-management command endpoint.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
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
# Update entity
# ---------------------------------------------------------------------------


class UniFiUpdateEntity(UniFiEntity, UpdateEntity):
    """Firmware update entity for a UniFi network device."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
    )
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: UniFiDataUpdateCoordinator,
        hub: UniFiHub,
        mac: str,
        device_name: str,
        device_model: str,
    ) -> None:
        desc = EntityDescription(key="firmware_update")
        super().__init__(coordinator, desc, hub, mac, device_name, device_model)
        self._attr_name = "Firmware"
        self._attr_title = f"{device_name} firmware"

    @property
    def installed_version(self) -> str | None:
        """Return the currently installed firmware version."""
        if self._hub.device_coordinator is None:
            return None
        device = self._hub.device_coordinator.devices.get(self._device_mac)
        if device is None:
            return None
        return device.version or None

    @property
    def latest_version(self) -> str | None:
        """Return the latest available firmware version.

        When no upgrade is available the installed version is returned so
        that Home Assistant considers the device up-to-date.
        """
        if self._hub.device_coordinator is None:
            return None
        device = self._hub.device_coordinator.devices.get(self._device_mac)
        if device is None:
            return None
        if device.upgradable:
            return device.upgrade_to_firmware or "available"
        # Same as installed → no update available
        return device.version or None

    async def async_install(
        self,
        version: str | None = None,
        backup: bool = False,
        **kwargs: Any,
    ) -> None:
        """Trigger the firmware upgrade on the device."""
        _LOGGER.info(
            "Triggering firmware upgrade for %s (%s)",
            self._device_name,
            self._device_mac,
        )
        await self._hub.legacy.upgrade_device(self._device_mac)
        await self._hub.device_coordinator.async_request_refresh()


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UniFiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UniFi Network HA firmware update entities."""
    hub: UniFiHub = entry.runtime_data
    entities: list[UniFiUpdateEntity] = []

    if hub.device_coordinator is None or hub.legacy is None:
        _LOGGER.debug("Device coordinator or legacy API not available — skipping update setup")
        return

    for mac, device in hub.device_coordinator.devices.items():
        if not device.adopted:
            continue

        dev_name = device.name or f"Device {mac}"
        dev_model = device.model_name or device.model or "UniFi Device"

        entities.append(
            UniFiUpdateEntity(
                coordinator=hub.device_coordinator,
                hub=hub,
                mac=mac,
                device_name=dev_name,
                device_model=dev_model,
            )
        )

    _LOGGER.debug("Setting up %d firmware update entities", len(entities))
    async_add_entities(entities)
