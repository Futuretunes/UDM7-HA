"""Traffic statistics coordinator."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from .base import UniFiDataUpdateCoordinator

if TYPE_CHECKING:
    from ..hub import UniFiHub

_LOGGER = logging.getLogger(__name__)


class TrafficCoordinator(UniFiDataUpdateCoordinator):
    """Coordinator for traffic reports (stat/report)."""

    def __init__(self, hub: UniFiHub, update_interval: int = 300) -> None:
        super().__init__(
            hub.hass,
            _LOGGER,
            name="UniFi Traffic",
            update_interval=timedelta(seconds=update_interval),
        )
        self.hub = hub
        self.hourly: list[dict] = []
        self.daily: list[dict] = []

    async def _async_fetch_data(self) -> dict[str, Any]:
        try:
            self.hourly = await self.hub.legacy.get_traffic_report("hourly")
            self.daily = await self.hub.legacy.get_traffic_report("daily")
        except Exception:
            _LOGGER.debug("Traffic report fetch failed", exc_info=True)
        return {"hourly": self.hourly, "daily": self.daily}
