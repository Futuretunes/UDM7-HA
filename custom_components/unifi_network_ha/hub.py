"""Central hub for UniFi Network HA integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SITE,
    CONF_AUTH_METHOD,
    CONF_API_KEY,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_VERIFY_SSL,
    CONF_CLOUD_API_KEY,
    CONF_CLOUD_ENABLED,
    CONF_UPDATE_INTERVAL_DEVICES,
    CONF_UPDATE_INTERVAL_CLIENTS,
    CONF_UPDATE_INTERVAL_HEALTH,
    CONF_UPDATE_INTERVAL_WAN_RATE,
    CONF_UPDATE_INTERVAL_ALARMS,
    CONF_UPDATE_INTERVAL_DPI,
    CONF_UPDATE_INTERVAL_CLOUD,
    CONF_ENABLE_DPI,
    CONF_ENABLE_ALARMS,
    CONF_ENABLE_CLOUD,
    DEFAULT_UPDATE_INTERVAL_DEVICES,
    DEFAULT_UPDATE_INTERVAL_CLIENTS,
    DEFAULT_UPDATE_INTERVAL_HEALTH,
    DEFAULT_UPDATE_INTERVAL_WAN_RATE,
    DEFAULT_UPDATE_INTERVAL_ALARMS,
    DEFAULT_UPDATE_INTERVAL_DPI,
    DEFAULT_UPDATE_INTERVAL_CLOUD,
    AuthMethod,
)
from .api.client import UniFiApiClient
from .api.auth import ApiKeyAuth, CredentialAuth
from .api.local_legacy import LocalLegacyApi
from .api.local_v2 import LocalV2Api
from .api.local_integration import LocalIntegrationApi
from .api.cloud import CloudApi
from .api.websocket import UniFiWebSocket, WebSocketMessageType

if TYPE_CHECKING:
    from .coordinators.alarm import AlarmCoordinator
    from .coordinators.client import ClientCoordinator
    from .coordinators.cloud import CloudCoordinator
    from .coordinators.device import DeviceCoordinator
    from .coordinators.dpi import DpiCoordinator
    from .coordinators.health import HealthCoordinator
    from .coordinators.wan_rate import WanRateCoordinator

_LOGGER = logging.getLogger(__name__)


class UniFiHub:
    """Central hub managing all UniFi connections and coordinators."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        # Config
        self._host: str = entry.data[CONF_HOST]
        self._port: int = entry.data[CONF_PORT]
        self._site: str = entry.data.get(CONF_SITE, "default")
        self._verify_ssl: bool = entry.data.get(CONF_VERIFY_SSL, False)

        # API clients (initialized in async_setup)
        self.api: UniFiApiClient | None = None
        self.legacy: LocalLegacyApi | None = None
        self.v2: LocalV2Api | None = None
        self.integration: LocalIntegrationApi | None = None
        self.cloud: CloudApi | None = None
        self.websocket: UniFiWebSocket | None = None

        # Coordinators (initialized in _setup_coordinators)
        self.device_coordinator: DeviceCoordinator | None = None
        self.client_coordinator: ClientCoordinator | None = None
        self.health_coordinator: HealthCoordinator | None = None
        self.wan_rate_coordinator: WanRateCoordinator | None = None
        self.alarm_coordinator: AlarmCoordinator | None = None
        self.dpi_coordinator: DpiCoordinator | None = None
        self.cloud_coordinator: CloudCoordinator | None = None

        # Gateway info (detected during setup)
        self.gateway_mac: str = ""
        self.gateway_device: dict = {}  # raw device dict for gateway

    @property
    def host(self) -> str:
        return self._host

    @property
    def site(self) -> str:
        return self._site

    @property
    def available(self) -> bool:
        """Return True if the hub is available."""
        return self.api is not None

    async def async_setup(self) -> bool:
        """Set up the hub: create API clients, connect, detect gateway, start WebSocket."""
        try:
            # 1. Create the API client
            session = async_get_clientsession(self.hass, verify_ssl=self._verify_ssl)
            auth = self._create_auth()

            self.api = UniFiApiClient(
                host=self._host,
                port=self._port,
                site=self._site,
                auth=auth,
                verify_ssl=self._verify_ssl,
                session=session,
            )

            # 2. Detect UniFi OS and login
            await self.api.detect_unifi_os()
            await self.api.login()

            # 3. Create API wrappers
            self.legacy = LocalLegacyApi(self.api)
            self.v2 = LocalV2Api(self.api)
            self.integration = LocalIntegrationApi(self.api)

            # 4. Set up cloud API if enabled
            if self.entry.data.get(CONF_CLOUD_ENABLED) and self.entry.data.get(
                CONF_CLOUD_API_KEY
            ):
                cloud_session = async_get_clientsession(self.hass)
                self.cloud = CloudApi(
                    api_key=self.entry.data[CONF_CLOUD_API_KEY],
                    session=cloud_session,
                )

            # 5. Detect gateway device
            await self._detect_gateway()

            # 6. Start WebSocket (only with credential auth — API key may not support WS)
            if self.entry.data.get(CONF_AUTH_METHOD) == AuthMethod.CREDENTIALS:
                await self._start_websocket()
            else:
                _LOGGER.info("Using API key auth — WebSocket disabled (polling only)")

            # 7. Set up coordinators
            await self._setup_coordinators()

            _LOGGER.info(
                "UniFi hub connected to %s:%s (site: %s, gateway: %s)",
                self._host,
                self._port,
                self._site,
                self.gateway_mac or "not found",
            )
            return True

        except Exception:
            _LOGGER.exception("Failed to set up UniFi hub")
            return False

    async def async_teardown(self) -> None:
        """Tear down the hub: shut down coordinators, stop WebSocket, log out."""
        for coordinator in [
            self.device_coordinator,
            self.client_coordinator,
            self.health_coordinator,
            self.wan_rate_coordinator,
            self.alarm_coordinator,
            self.dpi_coordinator,
            self.cloud_coordinator,
        ]:
            if coordinator:
                await coordinator.async_shutdown()

        if self.websocket:
            await self.websocket.stop()

        if self.api:
            await self.api.logout()

        _LOGGER.debug("UniFi hub torn down")

    def _create_auth(self):
        """Create the appropriate auth handler from config."""
        auth_method = self.entry.data.get(CONF_AUTH_METHOD, AuthMethod.API_KEY)
        if auth_method == AuthMethod.API_KEY:
            return ApiKeyAuth(api_key=self.entry.data[CONF_API_KEY])
        return CredentialAuth(
            username=self.entry.data[CONF_USERNAME],
            password=self.entry.data[CONF_PASSWORD],
        )

    async def _detect_gateway(self) -> None:
        """Find the gateway device in the network."""
        try:
            devices = await self.legacy.get_devices()
            for device in devices:
                device_type = device.get("type", "")
                # Gateway types: ugw, udm, uxg
                if device_type in ("ugw", "udm", "uxg"):
                    self.gateway_mac = device.get("mac", "")
                    self.gateway_device = device
                    _LOGGER.debug(
                        "Found gateway: %s (%s)",
                        device.get("name", ""),
                        self.gateway_mac,
                    )
                    return
            _LOGGER.warning("No gateway device found in site %s", self._site)
        except Exception:
            _LOGGER.warning("Could not detect gateway device", exc_info=True)

    async def _start_websocket(self) -> None:
        """Start the WebSocket connection."""
        try:
            session = async_get_clientsession(self.hass, verify_ssl=self._verify_ssl)
            self.websocket = UniFiWebSocket(
                host=self._host,
                port=self._port,
                site=self._site,
                session=session,
                is_unifi_os=self.api.is_unifi_os,
                verify_ssl=self._verify_ssl,
            )
            await self.websocket.start()
        except Exception:
            _LOGGER.warning("Could not start WebSocket connection", exc_info=True)

    async def _setup_coordinators(self) -> None:
        """Set up data update coordinators."""
        from .coordinators.alarm import AlarmCoordinator
        from .coordinators.client import ClientCoordinator
        from .coordinators.cloud import CloudCoordinator
        from .coordinators.device import DeviceCoordinator
        from .coordinators.dpi import DpiCoordinator
        from .coordinators.health import HealthCoordinator
        from .coordinators.wan_rate import WanRateCoordinator

        # Create coordinators with configurable intervals
        device_interval = self.get_option(
            CONF_UPDATE_INTERVAL_DEVICES, DEFAULT_UPDATE_INTERVAL_DEVICES
        )
        client_interval = self.get_option(
            CONF_UPDATE_INTERVAL_CLIENTS, DEFAULT_UPDATE_INTERVAL_CLIENTS
        )
        health_interval = self.get_option(
            CONF_UPDATE_INTERVAL_HEALTH, DEFAULT_UPDATE_INTERVAL_HEALTH
        )
        wan_rate_interval = self.get_option(
            CONF_UPDATE_INTERVAL_WAN_RATE, DEFAULT_UPDATE_INTERVAL_WAN_RATE
        )

        self.device_coordinator = DeviceCoordinator(self, device_interval)
        self.client_coordinator = ClientCoordinator(self, client_interval)
        self.health_coordinator = HealthCoordinator(self, health_interval)
        self.wan_rate_coordinator = WanRateCoordinator(self, wan_rate_interval)

        # Initial data fetch
        await self.device_coordinator.async_config_entry_first_refresh()
        await self.client_coordinator.async_config_entry_first_refresh()
        await self.health_coordinator.async_config_entry_first_refresh()
        await self.wan_rate_coordinator.async_config_entry_first_refresh()

        # Wire up WebSocket subscriptions
        if self.websocket:
            unsub_devices = self.websocket.subscribe(
                self.device_coordinator.process_websocket_message,
                [
                    WebSocketMessageType.DEVICE_SYNC,
                    WebSocketMessageType.SPEED_TEST_UPDATE,
                ],
            )
            self.device_coordinator.set_websocket_unsubscribe(unsub_devices)

            unsub_clients = self.websocket.subscribe(
                self.client_coordinator.process_websocket_message,
                [
                    WebSocketMessageType.STA_SYNC,
                    WebSocketMessageType.USER_SYNC,
                    WebSocketMessageType.USER_DELETE,
                ],
            )
            self.client_coordinator.set_websocket_unsubscribe(unsub_clients)

        # Alarm coordinator (optional, enabled by default)
        if self.get_option(CONF_ENABLE_ALARMS, True):
            alarm_interval = self.get_option(
                CONF_UPDATE_INTERVAL_ALARMS, DEFAULT_UPDATE_INTERVAL_ALARMS
            )
            self.alarm_coordinator = AlarmCoordinator(self, alarm_interval)
            await self.alarm_coordinator.async_config_entry_first_refresh()

            if self.websocket:
                unsub_alarms = self.websocket.subscribe(
                    self.alarm_coordinator.process_websocket_message,
                    [
                        WebSocketMessageType.ALARM_ADD,
                        WebSocketMessageType.ALARM_SYNC,
                    ],
                )
                self.alarm_coordinator.set_websocket_unsubscribe(unsub_alarms)

        # DPI coordinator (optional, disabled by default)
        if self.get_option(CONF_ENABLE_DPI, False):
            dpi_interval = self.get_option(
                CONF_UPDATE_INTERVAL_DPI, DEFAULT_UPDATE_INTERVAL_DPI
            )
            self.dpi_coordinator = DpiCoordinator(self, dpi_interval)
            await self.dpi_coordinator.async_config_entry_first_refresh()

            if self.websocket:
                unsub_dpi = self.websocket.subscribe(
                    self.dpi_coordinator.process_websocket_message,
                    [
                        WebSocketMessageType.DPI_APP_SYNC,
                        WebSocketMessageType.DPI_GROUP_SYNC,
                    ],
                )
                self.dpi_coordinator.set_websocket_unsubscribe(unsub_dpi)

        # Cloud coordinator (optional, requires cloud API to be configured)
        if self.cloud is not None and self.get_option(CONF_ENABLE_CLOUD, True):
            cloud_interval = self.get_option(
                CONF_UPDATE_INTERVAL_CLOUD, DEFAULT_UPDATE_INTERVAL_CLOUD
            )
            self.cloud_coordinator = CloudCoordinator(self, cloud_interval)
            await self.cloud_coordinator.async_config_entry_first_refresh()

    def get_option(self, key: str, default: Any = None) -> Any:
        """Get a value from options, falling back to data, then default."""
        return self.entry.options.get(key, self.entry.data.get(key, default))
