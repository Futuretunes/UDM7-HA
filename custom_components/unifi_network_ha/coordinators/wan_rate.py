"""WAN rate coordinator for real-time throughput."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from ..api.models import Device
from .base import UniFiDataUpdateCoordinator

if TYPE_CHECKING:
    from ..hub import UniFiHub

_LOGGER = logging.getLogger(__name__)


class WanRateCoordinator(UniFiDataUpdateCoordinator):
    """Fast-polling coordinator for WAN throughput rates."""

    def __init__(self, hub: UniFiHub, update_interval: int = 5) -> None:
        super().__init__(
            hub.hass,
            _LOGGER,
            name="UniFi WAN Rates",
            update_interval=timedelta(seconds=update_interval),
        )
        self.hub = hub
        self.gateway: Device | None = None

    async def _async_fetch_data(self) -> dict[str, Any]:
        """Fetch only the gateway device for WAN rate data."""
        if not self.hub.gateway_mac:
            return {"gateway": None}

        raw = await self.hub.legacy.get_device(self.hub.gateway_mac)
        if raw is None:
            return {"gateway": self.gateway}

        self.gateway = Device.from_dict(raw)
        return {"gateway": self.gateway}
