"""Base coordinator for UniFi Network HA."""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class UniFiDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Base coordinator that polls an API endpoint and merges WebSocket updates.

    Subclasses must implement:
    - _async_fetch_data() -> dict[str, Any] — fetch data from the API

    Optionally override:
    - _process_websocket_message(msg_type, data) — handle real-time updates
    """

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        name: str,
        update_interval: timedelta,
    ) -> None:
        super().__init__(hass, logger, name=name, update_interval=update_interval)
        self._ws_unsubscribe: Callable[[], None] | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        """Poll data from the API."""
        try:
            return await self._async_fetch_data()
        except Exception as err:
            raise UpdateFailed(f"Error fetching {self.name} data: {err}") from err

    async def _async_fetch_data(self) -> dict[str, Any]:
        """Fetch data from the API. Must be implemented by subclasses."""
        raise NotImplementedError

    def process_websocket_message(self, msg_type: str, data: list[dict]) -> None:
        """Handle a WebSocket message and merge into coordinator data.

        Called synchronously from the WebSocket handler.
        Override in subclasses for specific merge logic.
        Updates self.data in-place and calls async_set_updated_data().
        """

    def set_websocket_unsubscribe(self, unsub: Callable[[], None]) -> None:
        """Store the WebSocket unsubscribe callback for cleanup."""
        self._ws_unsubscribe = unsub

    async def async_shutdown(self) -> None:
        """Clean up resources."""
        if self._ws_unsubscribe:
            self._ws_unsubscribe()
            self._ws_unsubscribe = None
        await super().async_shutdown()
