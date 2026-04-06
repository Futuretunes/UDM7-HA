"""UniFi Network Advanced lock platform.

Provides lock entities for doors managed by UniFi Access.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENABLE_ACCESS, DOMAIN, MANUFACTURER
from .hub import UniFiHub

from . import UniFiConfigEntry

_LOGGER = logging.getLogger(__name__)


class UniFiAccessLock(CoordinatorEntity, LockEntity):
    """Lock entity for a UniFi Access door."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, hub, door_id, door_name):
        super().__init__(coordinator)
        self._hub = hub
        self._door_id = door_id
        self._attr_unique_id = f"access_door_{door_id}"
        self._attr_name = door_name

    @property
    def is_locked(self) -> bool | None:
        if not self._hub.access_coordinator:
            return None
        door = self._hub.access_coordinator.doors.get(self._door_id)
        return door.is_locked if door else None

    async def async_lock(self, **kwargs: Any) -> None:
        await self._hub.access.lock_door(self._door_id)
        await self._hub.access_coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs: Any) -> None:
        await self._hub.access.unlock_door(self._door_id)
        await self._hub.access_coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        door = self._hub.access_coordinator.doors.get(self._door_id) if self._hub.access_coordinator else None
        if not door:
            return {}
        attrs = {}
        if door.door_type:
            attrs["door_type"] = door.door_type
        if door.last_event:
            attrs["last_event"] = door.last_event
        if door.device_name:
            attrs["device"] = door.device_name
        return attrs

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"access_{self._door_id}")},
            name=self._attr_name,
            manufacturer=MANUFACTURER,
            model="UniFi Access Door",
            via_device=(DOMAIN, self._hub.gateway_mac),
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UniFiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub: UniFiHub = entry.runtime_data

    if not hub.get_option(CONF_ENABLE_ACCESS, False):
        return

    if not hub.access_coordinator or not hub.access_coordinator.available:
        return

    entities = []
    for door_id, door in hub.access_coordinator.doors.items():
        entities.append(
            UniFiAccessLock(
                coordinator=hub.access_coordinator,
                hub=hub,
                door_id=door_id,
                door_name=door.name or f"Door {door_id[:8]}",
            )
        )

    if entities:
        _LOGGER.debug("Setting up %d access lock entities", len(entities))
        async_add_entities(entities)
