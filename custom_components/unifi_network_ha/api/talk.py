"""UniFi Talk API wrapper.

Accesses the UniFi Talk application for intercom and phone devices.
Runs under /proxy/talk/ on UniFi OS devices.
"""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class TalkApi:
    """Wrapper for UniFi Talk API endpoints."""

    def __init__(self, host: str, port: int, session: aiohttp.ClientSession,
                 verify_ssl: bool = False, auth=None) -> None:
        self._host = host
        self._port = port
        self._session = session
        self._ssl = False if not verify_ssl else None
        self._base_url = f"https://{host}:{port}/proxy/talk/api"
        self._auth = auth

    async def _get(self, path: str) -> Any:
        url = f"{self._base_url}/{path}"
        headers = {}
        if self._auth:
            self._auth.apply_headers(headers)
        try:
            async with self._session.get(
                url, headers=headers, ssl=self._ssl,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status in (401, 403, 404):
                    return None
                if resp.status != 200:
                    return None
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError):
            _LOGGER.debug("Talk API request failed for %s", path, exc_info=True)
            return None

    async def is_available(self) -> bool:
        """Check if Talk is running on this device."""
        result = await self._get("devices")
        return result is not None

    async def get_devices(self) -> list[dict]:
        """Get all Talk devices (intercoms, phones)."""
        data = await self._get("devices")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data", data.get("devices", []))
        return []
