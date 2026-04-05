"""Alarm data coordinator."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from ..api.models import Alarm
from .base import UniFiDataUpdateCoordinator

if TYPE_CHECKING:
    from ..hub import UniFiHub

_LOGGER = logging.getLogger(__name__)


class AlarmCoordinator(UniFiDataUpdateCoordinator):
    """Coordinator for UniFi alarm data (stat/alarm)."""

    def __init__(self, hub: UniFiHub, update_interval: int = 120) -> None:
        super().__init__(
            hub.hass,
            _LOGGER,
            name="UniFi Alarms",
            update_interval=timedelta(seconds=update_interval),
        )
        self.hub = hub
        self.alarms: list[Alarm] = []
        self.alarm_count: int = 0
        self.latest_alarm: Alarm | None = None

    async def _async_fetch_data(self) -> dict[str, Any]:
        """Fetch unarchived alarms from the API."""
        raw = await self.hub.legacy.get_alarms(archived=False)
        alarms = [Alarm.from_dict(a) for a in raw]
        # Sort by timestamp descending so latest is first
        alarms.sort(key=lambda a: a.timestamp, reverse=True)
        self.alarms = alarms
        self.alarm_count = len(alarms)
        self.latest_alarm = alarms[0] if alarms else None
        return {"alarms": alarms, "count": len(alarms)}

    def process_websocket_message(self, msg_type: str, data: list[dict]) -> None:
        """Handle alarm:add and alarm:sync WebSocket messages."""
        if not data:
            return

        updated = False
        for item in data:
            alarm = Alarm.from_dict(item)
            if not alarm.id:
                continue

            # Check if this alarm already exists
            existing_ids = {a.id for a in self.alarms}
            if alarm.id not in existing_ids:
                # Prepend new alarm
                self.alarms.insert(0, alarm)
                updated = True
            else:
                # Update existing alarm (e.g. archived state change)
                for i, existing in enumerate(self.alarms):
                    if existing.id == alarm.id:
                        self.alarms[i] = alarm
                        updated = True
                        break

        if updated:
            # Remove archived alarms from the list
            self.alarms = [a for a in self.alarms if not a.archived]
            # Re-sort by timestamp
            self.alarms.sort(key=lambda a: a.timestamp, reverse=True)
            self.alarm_count = len(self.alarms)
            self.latest_alarm = self.alarms[0] if self.alarms else None
            self.async_set_updated_data(
                {"alarms": self.alarms, "count": self.alarm_count}
            )
