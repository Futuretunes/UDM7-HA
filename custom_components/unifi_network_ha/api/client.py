"""Core HTTP client for the UniFi Network API.

All higher-level API modules (devices, clients, stats, etc.) build on top of
:class:`UniFiApiClient` which handles URL construction, authentication,
response envelope unwrapping, and retry-on-401.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .auth import AuthHandler

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)

# Paths that should *never* be prefixed with /proxy/network on UniFi OS.
_NO_PROXY_PREFIXES = ("/api/auth/", "/api/auth", "/proxy/")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class UniFiAuthError(Exception):
    """Authentication with the UniFi controller failed."""


class UniFiConnectionError(Exception):
    """Could not connect to the UniFi controller."""


class UniFiApiError(Exception):
    """The UniFi API returned a logical error (rc != ok)."""


class UniFiResponseError(Exception):
    """The response body was not in the expected format."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class UniFiApiClient:
    """Low-level async HTTP client for a single UniFi controller.

    Args:
        host: Hostname or IP address of the controller (no scheme or port).
        port: HTTPS port (typically 443 for UniFi OS, 8443 for standalone).
        site: UniFi site name (usually ``"default"``).
        auth: An :class:`~.auth.AuthHandler` instance.
        verify_ssl: Whether to verify the server's TLS certificate.
        session: An :class:`aiohttp.ClientSession` — normally obtained from
            Home Assistant via ``async_get_clientsession``.
    """

    def __init__(
        self,
        host: str,
        port: int,
        site: str,
        auth: AuthHandler,
        verify_ssl: bool,
        session: aiohttp.ClientSession,
    ) -> None:
        self._host = host
        self._port = port
        self._site = site
        self._auth = auth
        self._verify_ssl = verify_ssl
        self._session = session

        self._is_unifi_os: bool | None = None  # None = not yet detected
        self._base_url = f"https://{host}:{port}"

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def is_unifi_os(self) -> bool:
        """Whether the controller is a UniFi OS device.

        Raises ``RuntimeError`` if called before :meth:`detect_unifi_os`.
        """
        if self._is_unifi_os is None:
            raise RuntimeError(
                "UniFi OS detection has not been performed yet; "
                "call detect_unifi_os() first"
            )
        return self._is_unifi_os

    @property
    def base_url(self) -> str:
        """Full base URL including scheme and port (e.g. ``https://192.168.1.1:443``)."""
        return self._base_url

    @property
    def site(self) -> str:
        """The active UniFi site name."""
        return self._site

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def detect_unifi_os(self) -> bool:
        """Probe the controller to determine if it is running UniFi OS.

        UniFi OS devices serve a web application at ``/`` whose response
        includes the ``x-csrf-token`` header or a ``UniFi OS`` marker in
        the body.  Standalone controllers typically redirect to
        ``/manage/account/login``.

        Returns:
            ``True`` if the device is UniFi OS, ``False`` otherwise.
        """
        url = f"{self._base_url}/"
        ssl_ctx = self._ssl_context
        _LOGGER.debug("Probing %s for UniFi OS", url)

        try:
            async with self._session.get(
                url, ssl=ssl_ctx, timeout=REQUEST_TIMEOUT, allow_redirects=False
            ) as resp:
                # UniFi OS returns x-csrf-token on the root page.
                if "x-csrf-token" in resp.headers:
                    _LOGGER.debug("Detected UniFi OS (x-csrf-token header present)")
                    self._is_unifi_os = True
                    return True

                # Fallback: read a small chunk and look for "UniFi OS" text.
                body = await resp.text(encoding="utf-8", errors="replace")
                if "UniFi OS" in body or "ubnt-device" in body:
                    _LOGGER.debug("Detected UniFi OS (body marker)")
                    self._is_unifi_os = True
                    return True

        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.warning("UniFi OS probe failed: %s", err)
            # If we cannot tell, assume standalone — the caller can override.

        _LOGGER.debug("UniFi OS not detected; assuming standalone controller")
        self._is_unifi_os = False
        return False

    async def login(self) -> None:
        """Authenticate with the controller via the configured auth handler."""
        if self._is_unifi_os is None:
            await self.detect_unifi_os()
        await self._auth.authenticate(self._session, self._base_url, self.is_unifi_os)
        _LOGGER.debug("Authenticated with %s", self._base_url)

    async def logout(self) -> None:
        """End the session with the controller."""
        if self._is_unifi_os is None:
            # Never logged in — nothing to do.
            return
        await self._auth.logout(self._session, self._base_url, self.is_unifi_os)
        _LOGGER.debug("Logged out from %s", self._base_url)

    # ------------------------------------------------------------------
    # HTTP verbs (convenience wrappers)
    # ------------------------------------------------------------------

    async def get(
        self,
        path: str,
        params: dict[str, str] | None = None,
    ) -> Any:
        """Send a GET request and return the unwrapped response data."""
        return await self.request("GET", path, params=params)

    async def post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Send a POST request and return the unwrapped response data."""
        return await self.request("POST", path, json=json)

    async def put(
        self,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Send a PUT request and return the unwrapped response data."""
        return await self.request("PUT", path, json=json)

    # ------------------------------------------------------------------
    # Core request method
    # ------------------------------------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        """Execute an HTTP request against the controller.

        This method:
        1. Builds the full URL (prepending ``/proxy/network`` on UniFi OS
           where appropriate).
        2. Applies authentication headers.
        3. Unwraps the standard UniFi ``{"meta": …, "data": …}`` envelope.
        4. On HTTP 401, re-authenticates once and retries.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, …).
            path: API path (e.g. ``/api/s/default/stat/device``).
            json: Optional JSON body for POST/PUT.
            params: Optional query parameters.

        Returns:
            The ``data`` list from the response envelope, or the full parsed
            JSON when the response does not use the envelope format.

        Raises:
            UniFiAuthError: If authentication fails after retry.
            UniFiConnectionError: If the controller is unreachable.
            UniFiApiError: If the API returns a logical error.
            UniFiResponseError: If the response cannot be parsed.
        """
        if self._is_unifi_os is None:
            await self.detect_unifi_os()

        url = self._build_url(path)
        headers: dict[str, str] = {}
        self._auth.apply_headers(headers)

        try:
            result = await self._do_request(method, url, headers, json, params)
        except UniFiAuthError:
            # Re-authenticate once and retry.
            _LOGGER.debug("Got 401 — re-authenticating and retrying %s %s", method, url)
            await self._auth.authenticate(
                self._session, self._base_url, self.is_unifi_os
            )
            headers = {}
            self._auth.apply_headers(headers)
            result = await self._do_request(method, url, headers, json, params)

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _ssl_context(self) -> bool:
        """Return the ``ssl`` parameter for aiohttp requests.

        ``False`` disables certificate verification (common for self-signed
        certs on local UniFi controllers).  ``None`` (the default) uses the
        default SSL context.
        """
        if not self._verify_ssl:
            return False
        return True  # use default SSL verification

    def _build_url(self, path: str) -> str:
        """Construct the full request URL.

        On UniFi OS, legacy API paths need a ``/proxy/network`` prefix.
        Paths that already start with ``/proxy/`` or ``/api/auth`` are left
        as-is.
        """
        if self._is_unifi_os and not any(
            path.startswith(prefix) for prefix in _NO_PROXY_PREFIXES
        ):
            path = f"/proxy/network{path}"
        return f"{self._base_url}{path}"

    async def _do_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        json: dict[str, Any] | None,
        params: dict[str, str] | None,
    ) -> Any:
        """Perform the actual HTTP call, returning parsed response data."""
        ssl_ctx = self._ssl_context
        _LOGGER.debug("%s %s", method, url)

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                json=json,
                params=params,
                ssl=ssl_ctx,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                # Handle auth failures — caller may retry.
                if resp.status in (401, 403):
                    raise UniFiAuthError(
                        f"{method} {url} returned HTTP {resp.status}"
                    )

                if resp.status != 200:
                    text = await resp.text()
                    raise UniFiApiError(
                        f"{method} {url} returned HTTP {resp.status}: {text}"
                    )

                # Some endpoints return empty bodies (e.g. DELETE, some POSTs).
                if resp.content_length == 0:
                    return None

                return self._unwrap_response(await resp.json(content_type=None))

        except UniFiAuthError:
            raise
        except UniFiApiError:
            raise
        except UniFiResponseError:
            raise
        except aiohttp.ContentTypeError as err:
            raise UniFiResponseError(
                f"Unexpected content type from {url}: {err}"
            ) from err
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UniFiConnectionError(
                f"Connection to {url} failed: {err}"
            ) from err

    @staticmethod
    def _unwrap_response(body: Any) -> Any:
        """Extract the ``data`` payload from the standard UniFi envelope.

        The envelope looks like::

            {"meta": {"rc": "ok"}, "data": [...]}

        If the response does not match this shape (e.g. auth endpoints,
        Integration API v1), the full body is returned as-is.
        """
        if not isinstance(body, dict):
            return body

        meta = body.get("meta")
        if isinstance(meta, dict):
            rc = meta.get("rc")
            if rc == "error":
                msg = meta.get("msg", "Unknown API error")
                raise UniFiApiError(f"UniFi API error: {msg}")
            if rc == "ok" and "data" in body:
                return body["data"]

        # Not the standard envelope — return the full body.
        return body
