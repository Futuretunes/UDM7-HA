"""Device data coordinator."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from ..api.models import Device
from .base import UniFiDataUpdateCoordinator

if TYPE_CHECKING:
    from ..hub import UniFiHub

_LOGGER = logging.getLogger(__name__)


class DeviceCoordinator(UniFiDataUpdateCoordinator):
    """Coordinator for UniFi device data (stat/device)."""

    def __init__(self, hub: UniFiHub, update_interval: int = 30) -> None:
        super().__init__(
            hub.hass,
            _LOGGER,
            name="UniFi Devices",
            update_interval=timedelta(seconds=update_interval),
        )
        self.hub = hub
        # Parsed Device objects keyed by MAC
        self.devices: dict[str, Device] = {}

    async def _async_fetch_data(self) -> dict[str, Any]:
        """Fetch all devices from the API."""
        raw_devices = await self.hub.legacy.get_devices()
        devices: dict[str, Device] = {}
        for raw in raw_devices:
            device = Device.from_dict(raw)
            if device.mac:
                devices[device.mac] = device
        self.devices = devices
        return {"devices": devices, "raw": raw_devices}

    def process_websocket_message(self, msg_type: str, data: list[dict]) -> None:
        """Handle device:sync WebSocket messages."""
        if not self.data:
            return
        updated = False
        for item in data:
            mac = item.get("mac", "")
            if mac:
                device = Device.from_dict(item)
                self.devices[mac] = device
                updated = True
        if updated:
            self.async_set_updated_data({"devices": self.devices, "raw": data})
