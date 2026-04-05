"""DPI (Deep Packet Inspection) data coordinator."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from ..api.models import DpiCategory, DpiData
from .base import UniFiDataUpdateCoordinator

if TYPE_CHECKING:
    from ..hub import UniFiHub

_LOGGER = logging.getLogger(__name__)


class DpiCoordinator(UniFiDataUpdateCoordinator):
    """Coordinator for UniFi DPI data (stat/sitedpi)."""

    def __init__(self, hub: UniFiHub, update_interval: int = 300) -> None:
        super().__init__(
            hub.hass,
            _LOGGER,
            name="UniFi DPI",
            update_interval=timedelta(seconds=update_interval),
        )
        self.hub = hub
        self.dpi_data: DpiData | None = None
        self.top_categories: list[DpiCategory] = []
        self.top_apps: list[DpiCategory] = []

    async def _async_fetch_data(self) -> dict[str, Any]:
        """Fetch DPI stats from the API."""
        raw = await self.hub.legacy.get_site_dpi()
        if raw:
            self.dpi_data = DpiData.from_dict(raw[0] if isinstance(raw, list) and raw else {})
            # Sort by total bytes (rx + tx) descending, take top 10
            self.top_categories = sorted(
                self.dpi_data.by_cat,
                key=lambda c: c.rx_bytes + c.tx_bytes,
                reverse=True,
            )[:10]
            self.top_apps = sorted(
                self.dpi_data.by_app,
                key=lambda a: a.rx_bytes + a.tx_bytes,
                reverse=True,
            )[:10]
        else:
            self.dpi_data = None
            self.top_categories = []
            self.top_apps = []
        return {"dpi": self.dpi_data}

    def process_websocket_message(self, msg_type: str, data: list[dict]) -> None:
        """Handle DPI-related WebSocket messages.

        DPI data changes infrequently so we just trigger a refresh
        rather than attempting to merge partial updates.
        """
        self.hass.async_create_task(self.async_request_refresh())
