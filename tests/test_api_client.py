"""Tests for the UniFi API client (api/client.py) and auth handlers (api/auth.py).

These are pure unit tests -- no Home Assistant modules are imported.
HTTP is mocked via aioresponses so the tests exercise real aiohttp I/O paths.
"""

import pytest
import aiohttp
from aioresponses import aioresponses

from custom_components.unifi_network_ha.api.client import (
    UniFiApiClient,
    UniFiAuthError,
    UniFiConnectionError,
    UniFiApiError,
    UniFiResponseError,
)
from custom_components.unifi_network_ha.api.auth import ApiKeyAuth, CredentialAuth


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE = "https://192.168.1.1:443"


def _make_client(session: aiohttp.ClientSession, auth=None) -> UniFiApiClient:
    """Create a client with sensible test defaults."""
    if auth is None:
        auth = ApiKeyAuth("test-key")
    client = UniFiApiClient(
        host="192.168.1.1",
        port=443,
        site="default",
        auth=auth,
        verify_ssl=False,
        session=session,
    )
    # Skip auto-detection for most tests.
    client._is_unifi_os = False
    return client


# ---------------------------------------------------------------------------
# UniFi OS detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detect_unifi_os_true(mock_aiohttp, aiohttp_session):
    """x-csrf-token header in the root page response means UniFi OS."""
    mock_aiohttp.get(
        f"{BASE}/",
        headers={"x-csrf-token": "abc123"},
        body="<html></html>",
    )

    client = _make_client(aiohttp_session)
    client._is_unifi_os = None  # reset so detection runs

    result = await client.detect_unifi_os()
    assert result is True
    assert client.is_unifi_os is True


@pytest.mark.asyncio
async def test_detect_unifi_os_false(mock_aiohttp, aiohttp_session):
    """Normal HTML without markers means standalone controller."""
    mock_aiohttp.get(
        f"{BASE}/",
        body="<html><title>UniFi Controller</title></html>",
    )

    client = _make_client(aiohttp_session)
    client._is_unifi_os = None

    result = await client.detect_unifi_os()
    assert result is False
    assert client.is_unifi_os is False


@pytest.mark.asyncio
async def test_detect_unifi_os_body_marker(mock_aiohttp, aiohttp_session):
    """'UniFi OS' text in the body (without the header) still counts."""
    mock_aiohttp.get(
        f"{BASE}/",
        body="<html><title>UniFi OS Console</title></html>",
    )

    client = _make_client(aiohttp_session)
    client._is_unifi_os = None

    result = await client.detect_unifi_os()
    assert result is True
    assert client.is_unifi_os is True


# ---------------------------------------------------------------------------
# URL building
# ---------------------------------------------------------------------------


def test_build_url_unifi_os(aiohttp_session):
    """On UniFi OS, API paths are prefixed with /proxy/network."""
    client = _make_client(aiohttp_session)
    client._is_unifi_os = True

    url = client._build_url("/api/s/default/stat/device")
    assert url == f"{BASE}/proxy/network/api/s/default/stat/device"


def test_build_url_standalone(aiohttp_session):
    """On a standalone controller, paths are used as-is."""
    client = _make_client(aiohttp_session)
    client._is_unifi_os = False

    url = client._build_url("/api/s/default/stat/device")
    assert url == f"{BASE}/api/s/default/stat/device"


def test_build_url_no_proxy_for_auth(aiohttp_session):
    """/api/auth/login is NOT prefixed even on UniFi OS."""
    client = _make_client(aiohttp_session)
    client._is_unifi_os = True

    url = client._build_url("/api/auth/login")
    assert url == f"{BASE}/api/auth/login"


def test_build_url_no_proxy_for_proxy_paths(aiohttp_session):
    """Paths already starting with /proxy/ are NOT double-prefixed."""
    client = _make_client(aiohttp_session)
    client._is_unifi_os = True

    url = client._build_url("/proxy/network/v2/api/site/default/traffic-rules")
    assert url == f"{BASE}/proxy/network/v2/api/site/default/traffic-rules"


# ---------------------------------------------------------------------------
# Response handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_unwraps_envelope(mock_aiohttp, aiohttp_session):
    """Standard UniFi envelope is unwrapped: returns the 'data' list."""
    mock_aiohttp.get(
        f"{BASE}/api/s/default/stat/device",
        payload={"meta": {"rc": "ok"}, "data": [{"foo": 1}]},
    )

    client = _make_client(aiohttp_session)
    result = await client.get("/api/s/default/stat/device")
    assert result == [{"foo": 1}]


@pytest.mark.asyncio
async def test_get_returns_raw_on_no_envelope(mock_aiohttp, aiohttp_session):
    """When there is no standard envelope, the full body is returned."""
    mock_aiohttp.get(
        f"{BASE}/api/s/default/some/endpoint",
        payload={"items": [1, 2]},
    )

    client = _make_client(aiohttp_session)
    result = await client.get("/api/s/default/some/endpoint")
    assert result == {"items": [1, 2]}


@pytest.mark.asyncio
async def test_api_error_raised(mock_aiohttp, aiohttp_session):
    """An envelope with rc='error' raises UniFiApiError."""
    mock_aiohttp.get(
        f"{BASE}/api/s/default/stat/device",
        payload={"meta": {"rc": "error", "msg": "api.err.Invalid"}},
    )

    client = _make_client(aiohttp_session)
    with pytest.raises(UniFiApiError, match="api.err.Invalid"):
        await client.get("/api/s/default/stat/device")


@pytest.mark.asyncio
async def test_auth_error_on_401(mock_aiohttp, aiohttp_session):
    """HTTP 401 raises UniFiAuthError (after the single retry also 401s)."""
    # First call returns 401, triggering re-auth.
    mock_aiohttp.get(
        f"{BASE}/api/s/default/stat/device",
        status=401,
    )
    # The re-auth (ApiKeyAuth.authenticate) is a no-op, so the retry fires.
    mock_aiohttp.get(
        f"{BASE}/api/s/default/stat/device",
        status=401,
    )

    client = _make_client(aiohttp_session)
    with pytest.raises(UniFiAuthError):
        await client.get("/api/s/default/stat/device")


@pytest.mark.asyncio
async def test_retry_on_401(mock_aiohttp, aiohttp_session):
    """First 401 triggers re-auth; if retry succeeds, data is returned."""
    auth = CredentialAuth("admin", "password")

    client = _make_client(aiohttp_session, auth=auth)
    client._is_unifi_os = False

    # First request returns 401.
    mock_aiohttp.get(
        f"{BASE}/api/s/default/stat/device",
        status=401,
    )
    # Re-auth: CredentialAuth POSTs to /api/login (standalone).
    mock_aiohttp.post(
        f"{BASE}/api/login",
        payload={"meta": {"rc": "ok"}, "data": []},
    )
    # Retry succeeds.
    mock_aiohttp.get(
        f"{BASE}/api/s/default/stat/device",
        payload={"meta": {"rc": "ok"}, "data": [{"name": "gw"}]},
    )

    result = await client.get("/api/s/default/stat/device")
    assert result == [{"name": "gw"}]


@pytest.mark.asyncio
async def test_connection_error(mock_aiohttp, aiohttp_session):
    """Network-level failures are wrapped in UniFiConnectionError."""
    mock_aiohttp.get(
        f"{BASE}/api/s/default/stat/device",
        exception=aiohttp.ClientError("connection refused"),
    )

    client = _make_client(aiohttp_session)
    with pytest.raises(UniFiConnectionError):
        await client.get("/api/s/default/stat/device")


# ---------------------------------------------------------------------------
# Auth handlers
# ---------------------------------------------------------------------------


def test_api_key_auth_headers():
    """ApiKeyAuth injects X-API-KEY into the headers dict."""
    auth = ApiKeyAuth("my-secret-key")
    headers: dict[str, str] = {}
    auth.apply_headers(headers)
    assert headers == {"X-API-KEY": "my-secret-key"}


def test_credential_auth_applies_csrf():
    """CredentialAuth injects x-csrf-token when one has been stored."""
    auth = CredentialAuth("admin", "password")
    # Simulate a login that stored a CSRF token.
    auth._csrf_token = "tok-12345"

    headers: dict[str, str] = {}
    auth.apply_headers(headers)
    assert headers == {"x-csrf-token": "tok-12345"}


def test_credential_auth_no_csrf_when_none():
    """CredentialAuth does not add a header when no CSRF token is stored."""
    auth = CredentialAuth("admin", "password")

    headers: dict[str, str] = {}
    auth.apply_headers(headers)
    assert headers == {}
