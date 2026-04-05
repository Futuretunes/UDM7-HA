"""Tests for config flow connection validation logic.

Since the config flow class itself depends heavily on Home Assistant (ConfigFlow,
voluptuous schemas, etc.), we test the *underlying API calls* that the config
flow uses to validate connections.  This covers API key auth, credential auth,
cloud API key validation, and legacy endpoint access.

HTTP is mocked via aioresponses so the tests exercise real aiohttp I/O paths.
"""

import pytest
import aiohttp
from aioresponses import aioresponses

from custom_components.unifi_network_ha.api.client import (
    UniFiApiClient,
    UniFiAuthError,
    UniFiConnectionError,
)
from custom_components.unifi_network_ha.api.auth import ApiKeyAuth, CredentialAuth
from custom_components.unifi_network_ha.api.local_legacy import LocalLegacyApi
from custom_components.unifi_network_ha.api.cloud import (
    CloudApi,
    CloudApiAuthError,
    CloudApiConnectionError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE = "https://192.168.1.1:443"


def _make_client(
    session: aiohttp.ClientSession,
    auth=None,
    is_unifi_os: bool = True,
) -> UniFiApiClient:
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
    client._is_unifi_os = is_unifi_os
    return client


# ---------------------------------------------------------------------------
# API key connection tests
# ---------------------------------------------------------------------------


class TestApiKeyConnection:
    """Validate API key auth connection flow."""

    @pytest.mark.asyncio
    async def test_api_key_connection_success(self, mock_aiohttp, aiohttp_session):
        """Create client with ApiKeyAuth, mock successful get_sites."""
        mock_aiohttp.get(
            f"{BASE}/proxy/network/api/self/sites",
            payload={
                "meta": {"rc": "ok"},
                "data": [
                    {"name": "default", "desc": "Default"},
                    {"name": "branch", "desc": "Branch Office"},
                ],
            },
        )

        client = _make_client(aiohttp_session)
        legacy = LocalLegacyApi(client)
        sites = await legacy.get_sites()

        assert len(sites) == 2
        assert sites[0]["name"] == "default"
        assert sites[1]["name"] == "branch"

    @pytest.mark.asyncio
    async def test_api_key_connection_invalid_key(self, mock_aiohttp, aiohttp_session):
        """Mock 401 response when the API key is invalid."""
        # First 401 triggers re-auth (no-op for ApiKeyAuth), then retry also 401s.
        mock_aiohttp.get(
            f"{BASE}/proxy/network/api/self/sites",
            status=401,
        )
        mock_aiohttp.get(
            f"{BASE}/proxy/network/api/self/sites",
            status=401,
        )

        client = _make_client(aiohttp_session)
        legacy = LocalLegacyApi(client)

        with pytest.raises(UniFiAuthError):
            await legacy.get_sites()


# ---------------------------------------------------------------------------
# Credential login tests
# ---------------------------------------------------------------------------


class TestCredentialLogin:
    """Validate credential-based auth flow."""

    @pytest.mark.asyncio
    async def test_credential_login_success(self, mock_aiohttp, aiohttp_session):
        """Mock successful login with CSRF header, then get_sites."""
        auth = CredentialAuth("admin", "password")

        # Login endpoint returns 200 with CSRF token.
        mock_aiohttp.post(
            f"{BASE}/api/auth/login",
            payload={"meta": {"rc": "ok"}, "data": []},
            headers={"x-csrf-token": "csrf-abc123"},
        )

        # get_sites succeeds after login.
        mock_aiohttp.get(
            f"{BASE}/proxy/network/api/self/sites",
            payload={
                "meta": {"rc": "ok"},
                "data": [{"name": "default", "desc": "Default"}],
            },
        )

        client = _make_client(aiohttp_session, auth=auth)
        # Perform login
        await client.login()

        # Verify CSRF token was stored
        assert auth._csrf_token == "csrf-abc123"

        legacy = LocalLegacyApi(client)
        sites = await legacy.get_sites()
        assert len(sites) == 1

    @pytest.mark.asyncio
    async def test_credential_login_wrong_password(
        self, mock_aiohttp, aiohttp_session
    ):
        """Mock login returning 401 for wrong credentials."""
        auth = CredentialAuth("admin", "wrong-pass")

        mock_aiohttp.post(
            f"{BASE}/api/auth/login",
            status=401,
        )

        client = _make_client(aiohttp_session, auth=auth)

        with pytest.raises(UniFiAuthError, match="invalid credentials"):
            await client.login()


# ---------------------------------------------------------------------------
# Connection failure tests
# ---------------------------------------------------------------------------


class TestConnectionFailure:
    """Validate connection error handling."""

    @pytest.mark.asyncio
    async def test_connection_refused(self, mock_aiohttp, aiohttp_session):
        """Mock raising ConnectionError -> UniFiConnectionError."""
        mock_aiohttp.get(
            f"{BASE}/proxy/network/api/self/sites",
            exception=aiohttp.ClientError("Connection refused"),
        )

        client = _make_client(aiohttp_session)
        legacy = LocalLegacyApi(client)

        with pytest.raises(UniFiConnectionError):
            await legacy.get_sites()


# ---------------------------------------------------------------------------
# Cloud API tests
# ---------------------------------------------------------------------------


class TestCloudApi:
    """Validate Cloud API (api.ui.com) connection logic."""

    @pytest.mark.asyncio
    async def test_cloud_api_key_valid(self, mock_aiohttp, aiohttp_session):
        """Create CloudApi, mock GET /ea/hosts returning hosts.

        ``get_hosts`` uses ``_get_paginated`` which appends offset/limit
        query params, so we mock with the exact URL.
        """
        import re

        mock_aiohttp.get(
            re.compile(r"^https://api\.ui\.com/ea/hosts"),
            payload=[
                {
                    "id": "host1",
                    "name": "UDM-Pro",
                    "type": "udm-pro",
                    "ipAddress": "203.0.113.5",
                    "isOnline": True,
                }
            ],
        )

        cloud = CloudApi("valid-cloud-key", aiohttp_session)
        hosts = await cloud.get_hosts()

        assert len(hosts) == 1
        assert hosts[0]["name"] == "UDM-Pro"
        assert hosts[0]["isOnline"] is True

    @pytest.mark.asyncio
    async def test_cloud_api_key_invalid(self, mock_aiohttp, aiohttp_session):
        """Mock 401 for invalid cloud API key."""
        import re

        mock_aiohttp.get(
            re.compile(r"^https://api\.ui\.com/ea/hosts"),
            status=401,
        )

        cloud = CloudApi("bad-cloud-key", aiohttp_session)

        with pytest.raises(CloudApiAuthError):
            await cloud.get_hosts()

    @pytest.mark.asyncio
    async def test_cloud_api_connection_error(
        self, mock_aiohttp, aiohttp_session
    ):
        """Network failure for cloud API raises CloudApiConnectionError."""
        mock_aiohttp.get(
            "https://api.ui.com/ea/hosts",
            exception=aiohttp.ClientError("DNS resolution failed"),
        )

        cloud = CloudApi("some-key", aiohttp_session)

        with pytest.raises(CloudApiConnectionError):
            await cloud.get_hosts()


# ---------------------------------------------------------------------------
# Legacy API endpoint tests
# ---------------------------------------------------------------------------


class TestLegacyApiEndpoints:
    """Test individual LocalLegacyApi endpoint calls."""

    @pytest.mark.asyncio
    async def test_get_sites_response(self, mock_aiohttp, aiohttp_session):
        """Mock get_sites returning multiple sites."""
        mock_aiohttp.get(
            f"{BASE}/proxy/network/api/self/sites",
            payload={
                "meta": {"rc": "ok"},
                "data": [
                    {"name": "default", "desc": "Default", "_id": "site1"},
                    {"name": "branch", "desc": "Branch Office", "_id": "site2"},
                    {"name": "remote", "desc": "Remote Site", "_id": "site3"},
                ],
            },
        )

        client = _make_client(aiohttp_session)
        legacy = LocalLegacyApi(client)
        sites = await legacy.get_sites()

        assert len(sites) == 3
        assert sites[0]["name"] == "default"
        assert sites[1]["desc"] == "Branch Office"
        assert sites[2]["_id"] == "site3"

    @pytest.mark.asyncio
    async def test_get_devices_finds_gateway(self, mock_aiohttp, aiohttp_session):
        """Mock get_devices returning a UDM device -- can detect gateway."""
        mock_aiohttp.get(
            f"{BASE}/proxy/network/api/s/default/stat/device",
            payload={
                "meta": {"rc": "ok"},
                "data": [
                    {
                        "mac": "aa:bb:cc:dd:ee:ff",
                        "type": "udm",
                        "name": "Dream Machine",
                        "model": "UDM-Pro",
                        "state": 1,
                    },
                    {
                        "mac": "aa:bb:cc:dd:ee:aa",
                        "type": "uap",
                        "name": "Office AP",
                        "model": "U6-LR",
                        "state": 1,
                    },
                ],
            },
        )

        client = _make_client(aiohttp_session)
        legacy = LocalLegacyApi(client)
        devices = await legacy.get_devices()

        assert len(devices) == 2
        assert devices[0]["mac"] == "aa:bb:cc:dd:ee:ff"
        assert devices[0]["type"] == "udm"

        # Verify we can identify the gateway
        from custom_components.unifi_network_ha.const import UniFiDeviceType

        gateways = [d for d in devices if UniFiDeviceType.is_gateway(d["type"])]
        assert len(gateways) == 1
        assert gateways[0]["name"] == "Dream Machine"

    @pytest.mark.asyncio
    async def test_get_clients(self, mock_aiohttp, aiohttp_session):
        """Mock get_clients returning active clients."""
        mock_aiohttp.get(
            f"{BASE}/proxy/network/api/s/default/stat/sta",
            payload={
                "meta": {"rc": "ok"},
                "data": [
                    {
                        "mac": "11:22:33:44:55:66",
                        "hostname": "my-laptop",
                        "ip": "192.168.1.100",
                        "is_wired": True,
                    }
                ],
            },
        )

        client = _make_client(aiohttp_session)
        legacy = LocalLegacyApi(client)
        clients = await legacy.get_clients()

        assert len(clients) == 1
        assert clients[0]["hostname"] == "my-laptop"

    @pytest.mark.asyncio
    async def test_get_health(self, mock_aiohttp, aiohttp_session):
        """Mock get_health returning subsystem data."""
        mock_aiohttp.get(
            f"{BASE}/proxy/network/api/s/default/stat/health",
            payload={
                "meta": {"rc": "ok"},
                "data": [
                    {"subsystem": "wan", "status": "ok", "wan_ip": "1.2.3.4"},
                    {"subsystem": "lan", "status": "ok"},
                ],
            },
        )

        client = _make_client(aiohttp_session)
        legacy = LocalLegacyApi(client)
        health = await legacy.get_health()

        assert len(health) == 2
        assert health[0]["subsystem"] == "wan"
        assert health[0]["wan_ip"] == "1.2.3.4"

    @pytest.mark.asyncio
    async def test_get_alarms(self, mock_aiohttp, aiohttp_session):
        """Mock get_alarms returning alarm data."""
        mock_aiohttp.get(
            f"{BASE}/proxy/network/api/s/default/stat/alarm",
            payload={
                "meta": {"rc": "ok"},
                "data": [
                    {"_id": "a1", "key": "EVT_IPS_Alert", "archived": False},
                    {"_id": "a2", "key": "EVT_GW_Restart", "archived": True},
                    {"_id": "a3", "key": "EVT_AP_Lost", "archived": False},
                ],
            },
        )

        client = _make_client(aiohttp_session)
        legacy = LocalLegacyApi(client)

        # Default: unarchived only
        alarms = await legacy.get_alarms(archived=False)
        assert len(alarms) == 2
        assert all(not a.get("archived") for a in alarms)

    @pytest.mark.asyncio
    async def test_standalone_controller_paths(
        self, mock_aiohttp, aiohttp_session
    ):
        """On a standalone controller, paths are NOT prefixed with /proxy/network."""
        mock_aiohttp.get(
            f"{BASE}/api/s/default/stat/device",
            payload={"meta": {"rc": "ok"}, "data": [{"mac": "ff:ff:ff:ff:ff:ff"}]},
        )

        client = _make_client(aiohttp_session, is_unifi_os=False)
        legacy = LocalLegacyApi(client)
        devices = await legacy.get_devices()

        assert len(devices) == 1
        assert devices[0]["mac"] == "ff:ff:ff:ff:ff:ff"
