"""Wrapper for the UniFi Site Manager Cloud API.

This module communicates with the Ubiquiti cloud service at
``https://api.ui.com`` and provides access to the Early Access (EA)
endpoints for hosts, sites, devices, ISP metrics, and SD-WAN
configuration.

Authentication is handled via an API key passed in the ``X-API-KEY``
header.  Rate limit: 100 requests per minute on EA endpoints.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

_CLOUD_BASE_URL = "https://api.ui.com"
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
_PAGE_LIMIT = 200
_DEFAULT_PAGE_LIMIT = 25  # Cloud API default; we override with _PAGE_LIMIT


class CloudApiError(Exception):
    """The cloud API returned an unexpected status."""


class CloudApiAuthError(CloudApiError):
    """The API key was rejected."""


class CloudApiConnectionError(CloudApiError):
    """Could not reach the cloud API."""


class CloudApi:
    """UniFi Site Manager Cloud API wrapper."""

    def __init__(self, api_key: str, session: aiohttp.ClientSession) -> None:
        self._api_key = api_key
        self._session = session
        self._base_url = _CLOUD_BASE_URL

    # ------------------------------------------------------------------
    # Core request method
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Make a cloud API request with ``X-API-KEY`` header.

        Args:
            method: HTTP method.
            path: API path (e.g. ``/ea/hosts``).
            params: Optional query parameters.
            json: Optional JSON body.

        Returns:
            Parsed JSON response body.

        Raises:
            CloudApiAuthError: On HTTP 401/403.
            CloudApiError: On non-200 responses.
            CloudApiConnectionError: On network failures.
        """
        url = f"{self._base_url}{path}"
        headers = {"X-API-KEY": self._api_key}

        _LOGGER.debug("%s %s", method, url)

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                timeout=_REQUEST_TIMEOUT,
            ) as resp:
                if resp.status in (401, 403):
                    raise CloudApiAuthError(
                        f"{method} {url} returned HTTP {resp.status}"
                    )

                if resp.status != 200:
                    text = await resp.text()
                    raise CloudApiError(
                        f"{method} {url} returned HTTP {resp.status}: {text}"
                    )

                if resp.content_length == 0:
                    return None

                return await resp.json(content_type=None)

        except (CloudApiAuthError, CloudApiError):
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CloudApiConnectionError(
                f"Connection to {url} failed: {err}"
            ) from err

    # ------------------------------------------------------------------
    # Pagination helper
    # ------------------------------------------------------------------

    async def _get_paginated(self, path: str) -> list[dict]:
        """Retrieve all pages from a paginated cloud endpoint.

        The cloud API uses ``offset`` / ``limit`` query parameters and
        returns list payloads directly or in a ``data`` wrapper.
        """
        results: list[dict] = []
        offset = 0

        while True:
            params = {"offset": str(offset), "limit": str(_PAGE_LIMIT)}
            body = await self._request("GET", path, params=params)

            if isinstance(body, list):
                page = body
            elif isinstance(body, dict):
                # Some endpoints return {"data": [...], "count": N}
                page = body.get("data", [])
                if not isinstance(page, list):
                    page = []
            else:
                break

            results.extend(page)

            # Stop if we got fewer items than the limit (last page).
            if len(page) < _PAGE_LIMIT:
                break

            offset += len(page)

        return results

    # ==================================================================
    # Hosts
    # ==================================================================

    async def get_hosts(self) -> list[dict]:
        """Return all UniFi OS hosts (consoles).

        ``GET /ea/hosts``
        """
        return await self._get_paginated("/ea/hosts")

    async def get_host(self, host_id: str) -> dict:
        """Return a single host by identifier.

        ``GET /ea/hosts/{id}``
        """
        body = await self._request("GET", f"/ea/hosts/{host_id}")
        if isinstance(body, dict):
            return body
        return {}

    # ==================================================================
    # Sites
    # ==================================================================

    async def get_sites(self) -> list[dict]:
        """Return all sites across all hosts.

        ``GET /ea/sites``
        """
        return await self._get_paginated("/ea/sites")

    # ==================================================================
    # Devices
    # ==================================================================

    async def get_devices(self) -> list[dict]:
        """Return all devices across all sites.

        ``GET /ea/devices``
        """
        return await self._get_paginated("/ea/devices")

    # ==================================================================
    # ISP metrics
    # ==================================================================

    async def get_isp_metrics(
        self,
        duration: str = "5m",
        begin_ts: int | None = None,
        end_ts: int | None = None,
    ) -> list[dict]:
        """Return ISP metrics (latency, packet loss, bandwidth).

        ``GET /ea/isp-metrics/{duration}``

        Args:
            duration: Aggregation window — ``"5m"`` or ``"1h"``.
            begin_ts: Optional start timestamp (epoch milliseconds).
            end_ts: Optional end timestamp (epoch milliseconds).
        """
        params: dict[str, str] = {}
        if begin_ts is not None:
            params["beginTimestamp"] = str(begin_ts)
        if end_ts is not None:
            params["endTimestamp"] = str(end_ts)

        body = await self._request(
            "GET", f"/ea/isp-metrics/{duration}", params=params or None
        )

        if isinstance(body, list):
            return body
        if isinstance(body, dict):
            data = body.get("data", [])
            return data if isinstance(data, list) else []
        return []

    # ==================================================================
    # SD-WAN
    # ==================================================================

    async def get_sdwan_configs(self) -> list[dict]:
        """Return all SD-WAN configurations.

        ``GET /ea/sd-wan-configs``
        """
        return await self._get_paginated("/ea/sd-wan-configs")

    async def get_sdwan_status(self, config_id: str) -> dict:
        """Return the status of an SD-WAN configuration.

        ``GET /ea/sd-wan-configs/{id}/status``
        """
        body = await self._request(
            "GET", f"/ea/sd-wan-configs/{config_id}/status"
        )
        if isinstance(body, dict):
            return body
        return {}
