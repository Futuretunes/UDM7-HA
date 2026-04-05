"""Wrapper for the UniFi Integration API v1 endpoints.

These endpoints live under ``/proxy/network/integration/v1/...`` and provide
a cleaner, officially supported interface for third-party integrations.
Because the path already starts with ``/proxy/``, the base client will
**not** add an additional ``/proxy/network`` prefix on UniFi OS.

The Integration API returns paginated responses.  List methods handle
pagination automatically by following ``offset``/``limit`` parameters until
all items have been retrieved.
"""

from __future__ import annotations

import logging
from typing import Any

from .client import UniFiApiClient

_LOGGER = logging.getLogger(__name__)

_BASE = "/proxy/network/integration/v1"
_PAGE_LIMIT = 200


class LocalIntegrationApi:
    """UniFi Integration API v1 wrapper."""

    def __init__(self, client: UniFiApiClient) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # Pagination helper
    # ------------------------------------------------------------------

    async def _get_paginated(self, path: str) -> list[dict]:
        """Retrieve all pages from a paginated list endpoint.

        The Integration API returns objects like::

            {"data": [...], "offset": 0, "limit": 200, "count": 350}

        This method loops until all items are fetched.
        """
        results: list[dict] = []
        offset = 0

        while True:
            params = {"offset": str(offset), "limit": str(_PAGE_LIMIT)}
            body = await self._client.get(path, params=params)

            # The body may already be unwrapped to a list by the base client
            # (if the envelope matches), or it may be a dict with a "data" key.
            if isinstance(body, list):
                page = body
                # If we got a raw list, there's no pagination metadata — just
                # return what we have.
                results.extend(page)
                break

            if isinstance(body, dict):
                page = body.get("data", [])
                if not isinstance(page, list):
                    page = []
                results.extend(page)

                total = body.get("count", body.get("totalCount", 0))
                offset += len(page)

                # Stop if we've collected everything or got an empty page.
                if not page or offset >= total:
                    break
            else:
                break

        return results

    @staticmethod
    def _single(body: Any) -> dict:
        """Extract a single resource from the response.

        Some Integration API endpoints return ``{"data": {…}}`` or just the
        dict directly.
        """
        if isinstance(body, dict):
            inner = body.get("data")
            if isinstance(inner, dict):
                return inner
            return body
        if isinstance(body, list) and body:
            return body[0]
        return {}

    # ==================================================================
    # Sites
    # ==================================================================

    async def get_sites(self) -> list[dict]:
        """Return all sites visible to the current user.

        ``GET /proxy/network/integration/v1/sites``
        """
        return await self._get_paginated(f"{_BASE}/sites")

    # ==================================================================
    # Devices
    # ==================================================================

    async def get_devices(self, site_id: str) -> list[dict]:
        """Return all devices for a site.

        ``GET /proxy/network/integration/v1/sites/{id}/devices``
        """
        return await self._get_paginated(f"{_BASE}/sites/{site_id}/devices")

    async def get_device(self, site_id: str, device_id: str) -> dict:
        """Return a single device.

        ``GET /proxy/network/integration/v1/sites/{id}/devices/{did}``
        """
        body = await self._client.get(
            f"{_BASE}/sites/{site_id}/devices/{device_id}"
        )
        return self._single(body)

    async def get_device_statistics(
        self, site_id: str, device_id: str
    ) -> dict:
        """Return the latest statistics for a device.

        ``GET /proxy/network/integration/v1/sites/{id}/devices/{did}/statistics/latest``
        """
        body = await self._client.get(
            f"{_BASE}/sites/{site_id}/devices/{device_id}/statistics/latest"
        )
        return self._single(body)

    # ==================================================================
    # Clients
    # ==================================================================

    async def get_clients(self, site_id: str) -> list[dict]:
        """Return all clients for a site.

        ``GET /proxy/network/integration/v1/sites/{id}/clients``
        """
        return await self._get_paginated(f"{_BASE}/sites/{site_id}/clients")

    async def get_client(self, site_id: str, client_id: str) -> dict:
        """Return a single client.

        ``GET /proxy/network/integration/v1/sites/{id}/clients/{cid}``
        """
        body = await self._client.get(
            f"{_BASE}/sites/{site_id}/clients/{client_id}"
        )
        return self._single(body)

    # ==================================================================
    # Actions
    # ==================================================================

    async def device_action(
        self, site_id: str, device_id: str, action: str
    ) -> dict:
        """Execute an action on a device (e.g. restart, locate).

        ``POST /proxy/network/integration/v1/sites/{id}/devices/{did}/actions``

        Args:
            site_id: The site identifier.
            device_id: The device identifier.
            action: Action name (e.g. ``"restart"``, ``"locate"``).
        """
        body = await self._client.post(
            f"{_BASE}/sites/{site_id}/devices/{device_id}/actions",
            json={"action": action},
        )
        return body if isinstance(body, dict) else {}

    async def client_action(
        self, site_id: str, client_id: str, action: str
    ) -> dict:
        """Execute an action on a client (e.g. block, reconnect).

        ``POST /proxy/network/integration/v1/sites/{id}/clients/{cid}/actions``

        Args:
            site_id: The site identifier.
            client_id: The client identifier.
            action: Action name (e.g. ``"block"``, ``"reconnect"``).
        """
        body = await self._client.post(
            f"{_BASE}/sites/{site_id}/clients/{client_id}/actions",
            json={"action": action},
        )
        return body if isinstance(body, dict) else {}
