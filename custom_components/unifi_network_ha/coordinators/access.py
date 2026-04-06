"""UniFi Access coordinator."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from .base import UniFiDataUpdateCoordinator

if TYPE_CHECKING:
    from ..hub import UniFiHub

_LOGGER = logging.getLogger(__name__)


@dataclass
class AccessDoor:
    """A door managed by UniFi Access."""
    id: str = ""
    name: str = ""
    is_locked: bool = True
    door_type: str = ""  # "door", "gate", "garage"
    device_name: str = ""
    last_event: str = ""
    last_event_time: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> AccessDoor:
        return cls(
            id=data.get("id", data.get("_id", "")),
            name=data.get("name", data.get("full_name", "")),
            is_locked=data.get("door_lock_relay_status", "lock") == "lock",
            door_type=data.get("type", data.get("door_type", "door")),
            device_name=data.get("device_name", ""),
            last_event=data.get("last_event", {}).get("type", "") if isinstance(data.get("last_event"), dict) else "",
            last_event_time=data.get("last_event", {}).get("timestamp", 0) if isinstance(data.get("last_event"), dict) else 0,
        )


@dataclass
class AccessDevice:
    """A UniFi Access device (reader, hub, intercom)."""
    id: str = ""
    name: str = ""
    mac: str = ""
    model: str = ""
    type: str = ""  # "UAH" (hub), "UA-Reader" etc.
    is_connected: bool = False
    firmware: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> AccessDevice:
        return cls(
            id=data.get("id", data.get("_id", "")),
            name=data.get("name", data.get("alias", "")),
            mac=data.get("mac", ""),
            model=data.get("model", data.get("hw_type", "")),
            type=data.get("type", data.get("device_type", "")),
            is_connected=data.get("is_connected", data.get("connected", False)),
            firmware=data.get("firmware", data.get("fw_version", "")),
        )


class AccessCoordinator(UniFiDataUpdateCoordinator):
    """Coordinator for UniFi Access data."""

    def __init__(self, hub: UniFiHub, update_interval: int = 30) -> None:
        super().__init__(hub.hass, _LOGGER, name="UniFi Access",
                         update_interval=timedelta(seconds=update_interval))
        self.hub = hub
        self.doors: dict[str, AccessDoor] = {}
        self.devices: dict[str, AccessDevice] = {}
        self.available: bool = False

    async def _async_fetch_data(self) -> dict[str, Any]:
        if not self.hub.access:
            return {"doors": {}, "devices": {}}

        # Fetch doors
        raw_doors = await self.hub.access.get_doors()
        self.doors = {}
        for raw in raw_doors:
            door = AccessDoor.from_dict(raw)
            if door.id:
                self.doors[door.id] = door

        # Fetch devices
        raw_devices = await self.hub.access.get_devices()
        self.devices = {}
        for raw in raw_devices:
            device = AccessDevice.from_dict(raw)
            if device.id:
                self.devices[device.id] = device

        self.available = True
        return {"doors": self.doors, "devices": self.devices}
