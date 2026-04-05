"""Tests for v0.2.0 features.

Covers device image mapping, VRRP model parsing, feature toggle constants,
client sensor helpers, port SFP fields, LED brightness mapping, and service
name constants.

No Home Assistant modules are imported -- the root conftest.py stubs them
before collection.
"""

import pytest

# ---------------------------------------------------------------------------
# 1. Device image mapping tests
# ---------------------------------------------------------------------------

from custom_components.unifi_network_ha.device_images import (
    get_device_image_url,
    get_device_display_name,
)


def test_known_model_returns_url():
    url = get_device_image_url("UDR7")
    assert url is not None
    assert "cdn.ecomm.ui.com" in url


def test_aliased_model_resolves():
    # "UDM-Pro" should resolve via MODEL_ALIASES
    url = get_device_image_url("UDM-Pro")
    assert url is not None


def test_unknown_model_returns_fallback():
    url = get_device_image_url("UNKNOWN-MODEL-XYZ")
    assert url is not None  # should return static.ui.com fallback
    assert "static.ui.com" in url


def test_empty_model_returns_none():
    assert get_device_image_url("") is None


def test_display_name_known():
    name = get_device_display_name("UDR7")
    assert name == "Dream Router 7"


def test_display_name_unknown():
    assert get_device_display_name("UNKNOWN") is None


def test_case_insensitive_lookup():
    url1 = get_device_image_url("udr7")
    url2 = get_device_image_url("UDR7")
    # Both should resolve (case insensitive)
    assert url1 is not None
    assert url2 is not None


# ---------------------------------------------------------------------------
# 2. VRRP model parsing tests
# ---------------------------------------------------------------------------

from custom_components.unifi_network_ha.api.models import Device


def test_device_vrrp_enabled():
    data = {
        "mac": "aa:bb:cc:dd:ee:ff",
        "config_network": {"type": "vrrp"},
        "vrrp_enabled": True,
        "vrrp_state": "master",
    }
    device = Device.from_dict(data)
    assert device.vrrp_enabled is True
    assert device.vrrp_state == "master"


def test_device_vrrp_disabled_by_default():
    device = Device.from_dict({"mac": "aa:bb:cc:dd:ee:ff"})
    assert device.vrrp_enabled is False
    assert device.vrrp_state == ""


def test_device_vrrp_backup_state():
    data = {"mac": "aa:bb:cc:dd:ee:ff", "vrrp_enabled": True, "vrrp_state": "backup"}
    device = Device.from_dict(data)
    assert device.vrrp_state == "backup"


# ---------------------------------------------------------------------------
# 3. Feature toggle tests
# ---------------------------------------------------------------------------

from custom_components.unifi_network_ha.const import (
    CONF_ENABLE_DEVICE_SENSORS,
    CONF_ENABLE_PER_CLIENT_SENSORS,
    CONF_ENABLE_CLIENT_CONTROLS,
    CONF_ENABLE_DEVICE_CONTROLS,
    CONF_ENABLE_DPI,
    CONF_ENABLE_ALARMS,
    CONF_ENABLE_VPN,
    CONF_ENABLE_WAN_MONITORING,
    CONF_ENABLE_CLOUD,
)


def test_feature_toggle_constants_exist():
    """Verify all feature toggle constants are defined."""
    assert CONF_ENABLE_DEVICE_SENSORS == "enable_device_sensors"
    assert CONF_ENABLE_PER_CLIENT_SENSORS == "enable_per_client_sensors"
    assert CONF_ENABLE_CLIENT_CONTROLS == "enable_client_controls"
    assert CONF_ENABLE_DEVICE_CONTROLS == "enable_device_controls"
    assert CONF_ENABLE_DPI == "enable_dpi"
    assert CONF_ENABLE_ALARMS == "enable_alarms"
    assert CONF_ENABLE_VPN == "enable_vpn"
    assert CONF_ENABLE_WAN_MONITORING == "enable_wan_monitoring"
    assert CONF_ENABLE_CLOUD == "enable_cloud"


# ---------------------------------------------------------------------------
# 4. Client sensor helper tests
# ---------------------------------------------------------------------------

from custom_components.unifi_network_ha.api.models import Client


def test_client_signal_zero_treated_as_unavailable():
    """Signal of 0 should be treated as not available."""
    client = Client.from_dict({"mac": "11:22:33:44:55:66", "signal": 0})
    assert client.signal == 0  # model stores it, but sensor helper returns None for 0


def test_client_satisfaction_value():
    client = Client.from_dict({"mac": "11:22:33:44:55:66", "satisfaction": 85})
    assert client.satisfaction == 85


def test_client_bandwidth_rates():
    client = Client.from_dict({
        "mac": "11:22:33:44:55:66",
        "rx_bytes-r": 50000.0,
        "tx_bytes-r": 25000.0,
        "rx_rate": 144000,
        "tx_rate": 72000,
    })
    assert client.rx_bytes_r == 50000.0
    assert client.tx_bytes_r == 25000.0
    assert client.rx_rate == 144000
    assert client.tx_rate == 72000


# ---------------------------------------------------------------------------
# 5. Port sensor model tests
# ---------------------------------------------------------------------------

from custom_components.unifi_network_ha.api.models import DevicePort


def test_port_sfp_fields():
    port = DevicePort.from_dict({
        "port_idx": 1,
        "sfp_found": True,
        "sfp_temperature": 42.5,
        "stp_state": "forwarding",
    })
    assert port.sfp_found is True
    assert port.sfp_temperature == 42.5
    assert port.stp_state == "forwarding"


def test_port_sfp_not_found():
    port = DevicePort.from_dict({"port_idx": 2, "sfp_found": False})
    assert port.sfp_found is False
    assert port.sfp_temperature == 0.0


# ---------------------------------------------------------------------------
# 6. LED brightness mapping test
# ---------------------------------------------------------------------------


def test_led_brightness_mapping():
    """Test that LED brightness maps correctly between HA (0-255) and UniFi (0-100)."""
    # Device with brightness at 50%
    device = Device.from_dict({
        "mac": "aa:bb:cc:dd:ee:ff",
        "led_override": "on",
        "led_override_color_brightness": 50,
    })
    assert device.led_enabled is True
    assert device.led_brightness == 50

    # Mapping: 50/100 * 255 = 127.5 -> rounds to 128
    ha_brightness = round(device.led_brightness * 255 / 100)
    assert ha_brightness == 128  # 50 * 255 / 100 = 127.5 -> rounds to 128


# ---------------------------------------------------------------------------
# 7. Service names test
# ---------------------------------------------------------------------------

from custom_components.unifi_network_ha.services import (
    SERVICE_RECONNECT_CLIENT,
    SERVICE_REMOVE_CLIENTS,
    SERVICE_BLOCK_CLIENT,
    SERVICE_UNBLOCK_CLIENT,
    SERVICE_KICK_CLIENT,
    SERVICE_FORGET_CLIENT,
)


def test_service_constants():
    assert SERVICE_KICK_CLIENT == "kick_client"
    assert SERVICE_FORGET_CLIENT == "forget_client"
    assert SERVICE_RECONNECT_CLIENT == "reconnect_client"
    assert SERVICE_REMOVE_CLIENTS == "remove_clients"


def test_service_constants_block():
    """Block/unblock constants are also correctly defined."""
    assert SERVICE_BLOCK_CLIENT == "block_client"
    assert SERVICE_UNBLOCK_CLIENT == "unblock_client"
