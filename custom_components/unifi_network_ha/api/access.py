"""UniFi Access API wrapper.

Accesses the UniFi Access application for door locks, intercoms, and
access control devices. Runs under /proxy/access/ on UniFi OS devices.
"""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class AccessApi:
    """Wrapper for UniFi Access API endpoints."""

    def __init__(self, host: str, port: int, session: aiohttp.ClientSession,
                 verify_ssl: bool = False, auth=None) -> None:
        self._host = host
        self._port = port
        self._session = session
        self._ssl = False if not verify_ssl else None
        self._base_url = f"https://{host}:{port}/proxy/access/api/v2"
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
            _LOGGER.debug("Access API request failed for %s", path, exc_info=True)
            return None

    async def _post(self, path: str, json: dict | None = None) -> Any:
        url = f"{self._base_url}/{path}"
        headers = {}
        if self._auth:
            self._auth.apply_headers(headers)
        try:
            async with self._session.post(
                url, headers=headers, json=json, ssl=self._ssl,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status in (401, 403, 404):
                    return None
                if resp.status != 200:
                    return None
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError):
            _LOGGER.debug("Access API POST failed for %s", path, exc_info=True)
            return None

    async def is_available(self) -> bool:
        """Check if Access is running on this device."""
        result = await self._get("devices")
        return result is not None

    async def get_devices(self) -> list[dict]:
        """Get all Access devices (readers, hubs, locks)."""
        data = await self._get("devices")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data", data.get("devices", []))
        return []

    async def get_doors(self) -> list[dict]:
        """Get all configured doors."""
        data = await self._get("doors")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data", data.get("doors", []))
        return []

    async def unlock_door(self, door_id: str) -> bool:
        """Remotely unlock a door."""
        result = await self._post(f"doors/{door_id}/unlock")
        return result is not None

    async def lock_door(self, door_id: str) -> bool:
        """Remotely lock a door."""
        result = await self._post(f"doors/{door_id}/lock")
        return result is not None

    async def get_access_logs(self, limit: int = 25) -> list[dict]:
        """Get recent access logs (entry/exit events)."""
        data = await self._get(f"logs?limit={limit}")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data", [])
        return []
