"""Client data coordinator.

Fetches the list of active clients (stat/sta) from the UniFi controller and
maintains both an *active* set and an *all-known* set.  The active set is
replaced on every poll; the all-known set is append-only (clients are never
removed once seen).

WebSocket messages for ``sta:sync``, ``user:sync``, and ``user:delete`` are
merged in real time so the data stays fresh between poll intervals.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from ..api.models import Client
from .base import UniFiDataUpdateCoordinator

if TYPE_CHECKING:
    from ..hub import UniFiHub

_LOGGER = logging.getLogger(__name__)


class ClientCoordinator(UniFiDataUpdateCoordinator):
    """Coordinator for UniFi client data (stat/sta)."""

    def __init__(self, hub: UniFiHub, update_interval: int = 30) -> None:
        super().__init__(
            hub.hass,
            _LOGGER,
            name="UniFi Clients",
            update_interval=timedelta(seconds=update_interval),
        )
        self.hub = hub
        self.clients: dict[str, Client] = {}  # MAC -> Client (active)
        self.all_known: dict[str, Client] = {}  # MAC -> Client (all ever seen)

    async def _async_fetch_data(self) -> dict[str, Any]:
        """Poll the controller for the current list of active clients."""
        raw_clients = await self.hub.legacy.get_clients()
        clients: dict[str, Client] = {}
        for raw in raw_clients:
            client = Client.from_dict(raw)
            if client.mac:
                clients[client.mac] = client
                self.all_known[client.mac] = client
        self.clients = clients
        return {"clients": clients}

    def process_websocket_message(self, msg_type: str, data: list[dict]) -> None:
        """Merge a real-time WebSocket update into the coordinator data.

        Handles ``sta:sync`` / ``user:sync`` (upsert) and ``user:delete``
        (removal from the active set).
        """
        if not self.data:
            return

        updated = False
        for item in data:
            mac = item.get("mac", "")
            if not mac:
                continue

            if msg_type in ("user:delete",):
                self.clients.pop(mac, None)
                updated = True
            else:
                client = Client.from_dict(item)
                self.clients[mac] = client
                self.all_known[mac] = client
                updated = True

        if updated:
            self.async_set_updated_data({"clients": self.clients})
