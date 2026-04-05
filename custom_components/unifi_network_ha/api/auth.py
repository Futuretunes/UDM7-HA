"""Authentication handlers for the UniFi Network API.

Supports two authentication methods:
- API key authentication (header-based, no session required)
- Credential authentication (cookie-based with CSRF token)
"""

from __future__ import annotations

import abc
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class AuthHandler(abc.ABC):
    """Abstract base class for authentication handlers."""

    @abc.abstractmethod
    async def authenticate(
        self,
        session: aiohttp.ClientSession,
        host: str,
        is_unifi_os: bool,
    ) -> None:
        """Perform authentication against the UniFi controller.

        Args:
            session: The aiohttp client session (cookies are managed here).
            host: Base URL of the controller (e.g. "https://192.168.1.1").
            is_unifi_os: True if the target is a UniFi OS device (UDM/UDR/UCG).
        """

    @abc.abstractmethod
    def apply_headers(self, headers: dict[str, str]) -> None:
        """Inject authentication headers into an outgoing request.

        Args:
            headers: Mutable dict of HTTP headers to modify in-place.
        """

    async def logout(
        self,
        session: aiohttp.ClientSession,
        host: str,
        is_unifi_os: bool,
    ) -> None:
        """Log out of the controller. Default implementation is a no-op.

        Args:
            session: The aiohttp client session.
            host: Base URL of the controller.
            is_unifi_os: True if the target is a UniFi OS device.
        """


class ApiKeyAuth(AuthHandler):
    """Authentication via a static API key.

    The key is sent as an ``X-API-KEY`` header on every request.
    No login/logout handshake is required.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def authenticate(
        self,
        session: aiohttp.ClientSession,
        host: str,
        is_unifi_os: bool,
    ) -> None:
        """No-op — API key auth does not require a login step."""
        _LOGGER.debug("ApiKeyAuth: no login required (using static API key)")

    def apply_headers(self, headers: dict[str, str]) -> None:
        """Add the X-API-KEY header."""
        headers["X-API-KEY"] = self._api_key


class CredentialAuth(AuthHandler):
    """Cookie-based authentication using username and password.

    On login the controller sets session cookies on the ``aiohttp.ClientSession``.
    UniFi OS devices also return a CSRF token that must be sent back on
    subsequent mutating requests.
    """

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password
        self._csrf_token: str | None = None

    # ------------------------------------------------------------------
    # AuthHandler interface
    # ------------------------------------------------------------------

    async def authenticate(
        self,
        session: aiohttp.ClientSession,
        host: str,
        is_unifi_os: bool,
    ) -> None:
        """Log in and store the CSRF token (if provided)."""
        await self._login(session, host, is_unifi_os)

    def apply_headers(self, headers: dict[str, str]) -> None:
        """Inject the CSRF token header when available."""
        if self._csrf_token:
            headers["x-csrf-token"] = self._csrf_token

    async def logout(
        self,
        session: aiohttp.ClientSession,
        host: str,
        is_unifi_os: bool,
    ) -> None:
        """POST to the logout endpoint and clear the stored CSRF token."""
        path = "/api/auth/logout" if is_unifi_os else "/api/logout"
        url = f"{host}{path}"
        _LOGGER.debug("CredentialAuth: logging out via %s", url)
        try:
            async with session.post(url, ssl=False) as resp:
                resp.raise_for_status()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Logout request failed: %s", err)
        finally:
            self._csrf_token = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _login(
        self,
        session: aiohttp.ClientSession,
        host: str,
        is_unifi_os: bool,
    ) -> None:
        """Perform the login POST and extract the CSRF token."""
        path = "/api/auth/login" if is_unifi_os else "/api/login"
        url = f"{host}{path}"
        payload: dict[str, Any] = {
            "username": self._username,
            "password": self._password,
            "remember": True,
        }
        _LOGGER.debug("CredentialAuth: logging in via %s", url)

        try:
            async with session.post(url, json=payload, ssl=False) as resp:
                if resp.status == 401 or resp.status == 403:
                    from .client import UniFiAuthError

                    raise UniFiAuthError(
                        f"Login failed (HTTP {resp.status}): invalid credentials"
                    )
                resp.raise_for_status()

                # UniFi OS returns x-csrf-token (or X-CSRF-Token) in the
                # response headers.  Standalone controllers use a csrf_token
                # cookie instead — aiohttp handles cookies automatically.
                csrf = resp.headers.get("x-csrf-token") or resp.headers.get(
                    "X-CSRF-Token"
                )
                if csrf:
                    self._csrf_token = csrf
                    _LOGGER.debug("CredentialAuth: CSRF token acquired")

        except aiohttp.ClientResponseError as err:
            from .client import UniFiAuthError

            raise UniFiAuthError(
                f"Login request failed (HTTP {err.status}): {err.message}"
            ) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            from .client import UniFiConnectionError

            raise UniFiConnectionError(
                f"Unable to connect to {host}: {err}"
            ) from err
