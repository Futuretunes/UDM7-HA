"""UniFi Protect API wrapper.

Accesses the UniFi Protect application on gateways that include NVR
functionality (UDR7, UDM-Pro, UDM-SE, etc.). Runs under /proxy/protect/
on UniFi OS devices.
"""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .auth import AuthHandler

_LOGGER = logging.getLogger(__name__)


class ProtectApi:
    """Wrapper for UniFi Protect API endpoints."""

    def __init__(
        self,
        host: str,
        port: int,
        session: aiohttp.ClientSession,
        verify_ssl: bool = False,
        auth: AuthHandler | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._session = session
        self._ssl = False if not verify_ssl else None
        self._base_url = f"https://{host}:{port}/proxy/protect/api"
        self._auth = auth

    async def _get(self, path: str) -> Any:
        """Make a GET request to the Protect API."""
        url = f"{self._base_url}/{path}"
        headers: dict[str, str] = {}
        if self._auth:
            self._auth.apply_headers(headers)
        try:
            async with self._session.get(
                url,
                headers=headers,
                ssl=self._ssl,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status in (401, 403):
                    _LOGGER.debug("Protect API auth failed: %s", resp.status)
                    return None
                if resp.status == 404:
                    _LOGGER.debug("Protect API not available (404)")
                    return None
                if resp.status != 200:
                    _LOGGER.debug(
                        "Protect API unexpected status: %s", resp.status
                    )
                    return None
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError):
            _LOGGER.debug("Protect API connection failed", exc_info=True)
            return None

    async def is_available(self) -> bool:
        """Check if Protect is running on this device."""
        result = await self._get("bootstrap")
        return result is not None

    async def get_bootstrap(self) -> dict | None:
        """Get Protect bootstrap data (cameras, NVR info, etc.)."""
        return await self._get("bootstrap")

    async def get_cameras(self) -> list[dict]:
        """Get all cameras."""
        data = await self._get("cameras")
        return data if isinstance(data, list) else []

    async def get_nvr(self) -> dict | None:
        """Get NVR system info."""
        bootstrap = await self._get("bootstrap")
        if isinstance(bootstrap, dict):
            return bootstrap.get("nvr")
        return None
