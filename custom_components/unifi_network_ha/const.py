"""Constants for the UniFi Network HA integration."""
from __future__ import annotations

from enum import StrEnum
from typing import Final

DOMAIN: Final = "unifi_network_ha"
MANUFACTURER: Final = "Ubiquiti Inc."

# Config entry keys
CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_SITE: Final = "site"
CONF_AUTH_METHOD: Final = "auth_method"
CONF_API_KEY: Final = "api_key"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_CLOUD_API_KEY: Final = "cloud_api_key"
CONF_CLOUD_ENABLED: Final = "cloud_enabled"

# Options keys
CONF_UPDATE_INTERVAL_DEVICES: Final = "update_interval_devices"
CONF_UPDATE_INTERVAL_CLIENTS: Final = "update_interval_clients"
CONF_UPDATE_INTERVAL_HEALTH: Final = "update_interval_health"
CONF_UPDATE_INTERVAL_WAN_RATE: Final = "update_interval_wan_rate"
CONF_UPDATE_INTERVAL_ALARMS: Final = "update_interval_alarms"
CONF_UPDATE_INTERVAL_DPI: Final = "update_interval_dpi"
CONF_UPDATE_INTERVAL_CLOUD: Final = "update_interval_cloud"
CONF_UPDATE_INTERVAL_TRAFFIC: Final = "update_interval_traffic"

CONF_TRACK_CLIENTS: Final = "track_clients"
CONF_TRACK_WIRED: Final = "track_wired"
CONF_TRACK_WIRELESS: Final = "track_wireless"
CONF_SSID_FILTER: Final = "ssid_filter"
CONF_CLIENT_HEARTBEAT: Final = "client_heartbeat"

CONF_ENABLE_WAN_MONITORING: Final = "enable_wan_monitoring"
CONF_ENABLE_DPI: Final = "enable_dpi"
CONF_ENABLE_ALARMS: Final = "enable_alarms"
CONF_ENABLE_VPN: Final = "enable_vpn"
CONF_ENABLE_CLOUD: Final = "enable_cloud"
CONF_ENABLE_PROTECT: Final = "enable_protect"

# Feature group toggles
CONF_ENABLE_DEVICE_SENSORS: Final = "enable_device_sensors"
CONF_ENABLE_PER_CLIENT_SENSORS: Final = "enable_per_client_sensors"
CONF_ENABLE_CLIENT_CONTROLS: Final = "enable_client_controls"
CONF_ENABLE_DEVICE_CONTROLS: Final = "enable_device_controls"

# Default values
DEFAULT_PORT: Final = 443
DEFAULT_SITE: Final = "default"
DEFAULT_VERIFY_SSL: Final = False

DEFAULT_UPDATE_INTERVAL_DEVICES: Final = 30      # seconds
DEFAULT_UPDATE_INTERVAL_CLIENTS: Final = 30
DEFAULT_UPDATE_INTERVAL_HEALTH: Final = 60
DEFAULT_UPDATE_INTERVAL_WAN_RATE: Final = 5
DEFAULT_UPDATE_INTERVAL_ALARMS: Final = 120
DEFAULT_UPDATE_INTERVAL_DPI: Final = 300
DEFAULT_UPDATE_INTERVAL_CLOUD: Final = 900
DEFAULT_UPDATE_INTERVAL_TRAFFIC: Final = 300     # 5 minutes

DEFAULT_CLIENT_HEARTBEAT: Final = 300  # 5 minutes
DEFAULT_TRACK_CLIENTS: Final = True
DEFAULT_TRACK_WIRED: Final = True
DEFAULT_TRACK_WIRELESS: Final = True


class AuthMethod(StrEnum):
    """Authentication methods."""
    API_KEY = "api_key"
    CREDENTIALS = "credentials"


class UniFiDeviceType(StrEnum):
    """UniFi device types from the API."""
    GATEWAY = "ugw"
    ACCESS_POINT = "uap"
    SWITCH = "usw"
    DREAM_MACHINE = "udm"
    NEXT_GEN_GATEWAY = "uxg"

    @classmethod
    def is_gateway(cls, device_type: str) -> bool:
        """Check if device type is a gateway."""
        return device_type in (cls.GATEWAY, cls.DREAM_MACHINE, cls.NEXT_GEN_GATEWAY)


class DeviceState(StrEnum):
    """Device states."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    PENDING = "pending"
    UPGRADING = "upgrading"
    ADOPTING = "adopting"

    @classmethod
    def from_code(cls, code: int) -> DeviceState:
        """Convert API state code to enum."""
        mapping = {
            0: cls.DISCONNECTED,
            1: cls.CONNECTED,
            2: cls.PENDING,
            4: cls.UPGRADING,
            5: cls.ADOPTING,
        }
        return mapping.get(code, cls.DISCONNECTED)


# Entity platforms to load
PLATFORMS: Final = [
    "binary_sensor",
    "button",
    "device_tracker",
    "event",
    "image",
    "light",
    "sensor",
    "switch",
    "update",
]

# Known gateway device models for detection
GATEWAY_MODELS: Final = {
    "UDR7", "UDR", "UDM", "UDM-Pro", "UDM-SE", "UDM-Pro-Max",
    "UXG-Pro", "UXG-Enterprise", "UXG-Lite", "USG", "USG-Pro-4",
    "UCG-Ultra", "EFG",
}
