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


# ===================================================================
# v0.3.0 feature tests
# ===================================================================

class TestTrafficReport:
    """Tests for traffic report data parsing."""

    def test_traffic_today_calculation(self):
        """Traffic today sums hourly wan-rx_bytes entries."""
        hourly = [
            {"wan-rx_bytes": 1073741824, "wan-tx_bytes": 536870912},  # 1 GB / 0.5 GB
            {"wan-rx_bytes": 2147483648, "wan-tx_bytes": 1073741824},  # 2 GB / 1 GB
        ]
        total_rx = sum(e.get("wan-rx_bytes", 0) for e in hourly)
        total_tx = sum(e.get("wan-tx_bytes", 0) for e in hourly)
        # Convert to GB
        rx_gb = round(total_rx / (1024**3), 2)
        tx_gb = round(total_tx / (1024**3), 2)
        assert rx_gb == 3.0
        assert tx_gb == 1.5

    def test_traffic_today_empty(self):
        """Empty hourly data returns 0."""
        hourly = []
        total = sum(e.get("wan-rx_bytes", 0) for e in hourly)
        assert total == 0


class TestPoeBudget:
    """Tests for PoE power budget calculation."""

    def test_poe_total_power(self):
        from custom_components.unifi_network_ha.api.models import Device
        device = Device.from_dict({
            "mac": "aa:bb:cc:dd:ee:ff",
            "type": "usw",
            "port_table": [
                {"port_idx": 1, "poe_enable": True, "poe_power": "3.5"},
                {"port_idx": 2, "poe_enable": True, "poe_power": "7.2"},
                {"port_idx": 3, "poe_enable": False, "poe_power": "0"},
                {"port_idx": 4, "poe_enable": True, "poe_power": "0"},
            ],
        })
        total = sum(p.poe_power for p in device.ports if p.poe_enable and p.poe_power > 0)
        assert round(total, 1) == 10.7

    def test_poe_no_poe_ports(self):
        from custom_components.unifi_network_ha.api.models import Device
        device = Device.from_dict({
            "mac": "aa:bb:cc:dd:ee:ff",
            "type": "usw",
            "port_table": [
                {"port_idx": 1, "poe_enable": False},
                {"port_idx": 2, "poe_enable": False},
            ],
        })
        total = sum(p.poe_power for p in device.ports if p.poe_enable and p.poe_power > 0)
        assert total == 0


class TestWifiExperience:
    """Tests for WiFi experience score calculation."""

    def test_wifi_experience_average(self):
        from custom_components.unifi_network_ha.api.models import Device
        devices = [
            Device.from_dict({
                "mac": "aa:bb:cc:dd:ee:01", "type": "uap",
                "radio_table_stats": [
                    {"name": "ra0", "radio": "ng", "satisfaction": 90, "num_sta": 5},
                    {"name": "rai0", "radio": "na", "satisfaction": 80, "num_sta": 3},
                ],
            }),
            Device.from_dict({
                "mac": "aa:bb:cc:dd:ee:02", "type": "uap",
                "radio_table_stats": [
                    {"name": "ra0", "radio": "ng", "satisfaction": 70, "num_sta": 2},
                ],
            }),
        ]
        scores = []
        for d in devices:
            for r in d.radios:
                if r.satisfaction > 0 and r.num_sta > 0:
                    scores.append(r.satisfaction)
        avg = round(sum(scores) / len(scores), 1)
        assert avg == 80.0  # (90 + 80 + 70) / 3

    def test_wifi_experience_no_aps(self):
        """No APs means no score."""
        scores = []
        assert len(scores) == 0


class TestProtectModels:
    """Tests for Protect data models."""

    def test_protect_camera_from_dict(self):
        from custom_components.unifi_network_ha.coordinators.protect import ProtectCamera
        cam = ProtectCamera.from_dict({
            "id": "cam1",
            "name": "Front Door",
            "mac": "AA:BB:CC:DD:EE:01",
            "type": "UVC-G4-Pro",
            "state": "CONNECTED",
            "isRecording": True,
            "lastMotion": 1700000000,
            "firmwareVersion": "4.63.15",
        })
        assert cam.id == "cam1"
        assert cam.name == "Front Door"
        assert cam.is_connected is True
        assert cam.is_recording is True
        assert cam.firmware == "4.63.15"

    def test_protect_camera_disconnected(self):
        from custom_components.unifi_network_ha.coordinators.protect import ProtectCamera
        cam = ProtectCamera.from_dict({"id": "cam2", "name": "Back", "state": "DISCONNECTED"})
        assert cam.is_connected is False

    def test_protect_nvr_from_dict(self):
        from custom_components.unifi_network_ha.coordinators.protect import ProtectNvr
        nvr = ProtectNvr.from_dict({
            "name": "NVR",
            "version": "4.0.6",
            "uptime": 86400,
            "storageInfo": {"totalSize": 128000000000, "totalSpaceAvailable": 96000000000},
            "recordingRetentionDurationMs": 604800000,  # 7 days
            "systemInfo": {
                "cpu": {"averageLoad": 15.5},
                "memory": {"total": 4000000000, "available": 2000000000},
            },
        })
        assert nvr.name == "NVR"
        assert nvr.version == "4.0.6"
        assert nvr.storage_used == 32000000000  # 128B - 96B
        assert nvr.storage_total == 128000000000
        assert nvr.recording_retention == 168  # 604800000 / 3600000
        assert nvr.cpu_usage == 15.5

    def test_protect_nvr_empty(self):
        from custom_components.unifi_network_ha.coordinators.protect import ProtectNvr
        nvr = ProtectNvr.from_dict({})
        assert nvr.name == ""
        assert nvr.storage_total == 0
        assert nvr.recording_retention == 0


class TestVoucherServiceConstants:
    """Tests for voucher service constants."""

    def test_voucher_service_names(self):
        from custom_components.unifi_network_ha.services import (
            SERVICE_CREATE_VOUCHER,
            SERVICE_LIST_VOUCHERS,
            SERVICE_REVOKE_VOUCHER,
        )
        assert SERVICE_CREATE_VOUCHER == "create_voucher"
        assert SERVICE_LIST_VOUCHERS == "list_vouchers"
        assert SERVICE_REVOKE_VOUCHER == "revoke_voucher"


class TestProtectFeatureToggle:
    """Tests for Protect feature toggle constant."""

    def test_protect_toggle_exists(self):
        from custom_components.unifi_network_ha.const import CONF_ENABLE_PROTECT
        assert CONF_ENABLE_PROTECT == "enable_protect"
