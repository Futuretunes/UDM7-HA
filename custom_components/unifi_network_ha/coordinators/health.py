"""Site health coordinator."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from ..api.models import HealthSubsystem
from .base import UniFiDataUpdateCoordinator

if TYPE_CHECKING:
    from ..hub import UniFiHub

_LOGGER = logging.getLogger(__name__)


class HealthCoordinator(UniFiDataUpdateCoordinator):
    """Coordinator for UniFi site health (stat/health)."""

    def __init__(self, hub: UniFiHub, update_interval: int = 60) -> None:
        super().__init__(
            hub.hass,
            _LOGGER,
            name="UniFi Health",
            update_interval=timedelta(seconds=update_interval),
        )
        self.hub = hub
        # Parsed subsystems keyed by name ("wan", "www", "wlan", "lan", "vpn")
        self.subsystems: dict[str, HealthSubsystem] = {}

    async def _async_fetch_data(self) -> dict[str, Any]:
        """Fetch site health from the API."""
        raw_health = await self.hub.legacy.get_health()
        subsystems: dict[str, HealthSubsystem] = {}
        for raw in raw_health:
            sub = HealthSubsystem.from_dict(raw)
            if sub.subsystem:
                subsystems[sub.subsystem] = sub
        self.subsystems = subsystems
        return {"subsystems": subsystems, "raw": raw_health}
