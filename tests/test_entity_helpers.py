"""Tests for entity value extraction helpers.

These tests exercise the pure data-model logic that sensors and entities
rely on: state code mapping, device type classification, WAN interface
labelling, speed-test conversions, and storage calculations.  No Home
Assistant imports are required.
"""

import pytest

from custom_components.unifi_network_ha.api.models import (
    Device,
    DeviceStorage,
    HealthSubsystem,
    SpeedTestResult,
    WanInterface,
)
from custom_components.unifi_network_ha.const import DeviceState, UniFiDeviceType


# ---------------------------------------------------------------------------
# DeviceState.from_code
# ---------------------------------------------------------------------------


class TestDeviceStateFromCode:
    """Verify the API state-code -> enum mapping."""

    def test_connected(self):
        assert DeviceState.from_code(1) == DeviceState.CONNECTED
        assert DeviceState.from_code(1) == "connected"

    def test_disconnected(self):
        assert DeviceState.from_code(0) == DeviceState.DISCONNECTED
        assert DeviceState.from_code(0) == "disconnected"

    def test_pending(self):
        assert DeviceState.from_code(2) == DeviceState.PENDING

    def test_upgrading(self):
        assert DeviceState.from_code(4) == DeviceState.UPGRADING

    def test_adopting(self):
        assert DeviceState.from_code(5) == DeviceState.ADOPTING

    def test_unknown_code_falls_back_to_disconnected(self):
        assert DeviceState.from_code(99) == DeviceState.DISCONNECTED
        assert DeviceState.from_code(-1) == DeviceState.DISCONNECTED


# ---------------------------------------------------------------------------
# UniFiDeviceType.is_gateway
# ---------------------------------------------------------------------------


class TestUniFiDeviceTypeIsGateway:
    """Verify device type classification."""

    def test_udm_is_gateway(self):
        assert UniFiDeviceType.is_gateway("udm") is True

    def test_ugw_is_gateway(self):
        assert UniFiDeviceType.is_gateway("ugw") is True

    def test_uxg_is_gateway(self):
        assert UniFiDeviceType.is_gateway("uxg") is True

    def test_uap_is_not_gateway(self):
        assert UniFiDeviceType.is_gateway("uap") is False

    def test_usw_is_not_gateway(self):
        assert UniFiDeviceType.is_gateway("usw") is False

    def test_unknown_type_is_not_gateway(self):
        assert UniFiDeviceType.is_gateway("xxx") is False


# ---------------------------------------------------------------------------
# WAN interface label logic
# ---------------------------------------------------------------------------


class TestWanInterfaceLabel:
    """Test the labelling convention for WAN interfaces."""

    def test_wan_interface_from_dict_short_name(self):
        """Short names like 'wan1' should parse correctly."""
        wan = WanInterface.from_dict({"name": "wan1", "up": True, "ip": "1.2.3.4"})
        assert wan.name == "wan1"
        assert wan.up is True
        assert wan.ip == "1.2.3.4"
        # Label convention: short names get uppercased
        label = wan.name.upper() if len(wan.name) <= 4 else wan.name.title()
        assert label == "WAN1"

    def test_wan_interface_from_dict_long_name(self):
        """Longer names like 'primary wan' should title-case."""
        wan = WanInterface.from_dict({"name": "primary wan", "up": True})
        assert wan.name == "primary wan"
        label = wan.name.upper() if len(wan.name) <= 4 else wan.name.title()
        assert label == "Primary Wan"

    def test_wan_interface_from_ifname(self):
        """When only 'ifname' is provided, it is used as the name."""
        wan = WanInterface.from_dict({"ifname": "eth0", "up": False})
        assert wan.name == "eth0"

    def test_wan_interface_speed_and_duplex(self):
        wan = WanInterface.from_dict(
            {"name": "wan1", "speed": 1000, "full_duplex": True}
        )
        assert wan.speed == 1000
        assert wan.full_duplex is True

    def test_wan_interface_dns_parsing_string(self):
        """DNS field as a comma-separated string is split into a list."""
        wan = WanInterface.from_dict({"name": "wan1", "dns": "8.8.8.8, 8.8.4.4"})
        assert wan.dns == ["8.8.8.8", "8.8.4.4"]

    def test_wan_interface_dns_parsing_list(self):
        """DNS field as a list is kept as-is."""
        wan = WanInterface.from_dict({"name": "wan1", "dns": ["1.1.1.1", "1.0.0.1"]})
        assert wan.dns == ["1.1.1.1", "1.0.0.1"]


# ---------------------------------------------------------------------------
# Speed test conversion
# ---------------------------------------------------------------------------


class TestSpeedTestResult:
    """Test SpeedTestResult parsing."""

    def test_speedtest_download_value(self):
        """Verify download value from xput_download."""
        st = SpeedTestResult.from_dict(
            {"xput_download": 95.5, "xput_upload": 20.3, "latency": 5.2}
        )
        assert st.download == pytest.approx(95.5)
        assert st.upload == pytest.approx(20.3)
        assert st.latency == pytest.approx(5.2)

    def test_speedtest_alternative_keys(self):
        """Alternative key names (download, upload, ping) are also accepted."""
        st = SpeedTestResult.from_dict(
            {"download": 100.0, "upload": 25.0, "ping": 3.5}
        )
        assert st.download == pytest.approx(100.0)
        assert st.upload == pytest.approx(25.0)
        assert st.latency == pytest.approx(3.5)

    def test_speedtest_server_info(self):
        st = SpeedTestResult.from_dict(
            {
                "xput_download": 50.0,
                "server": {"city": "Chicago", "country": "US"},
            }
        )
        assert st.server_city == "Chicago"
        assert st.server_country == "US"

    def test_speedtest_in_progress(self):
        st = SpeedTestResult.from_dict(
            {"status_summary": "running"}
        )
        assert st.in_progress is True

    def test_speedtest_not_in_progress(self):
        st = SpeedTestResult.from_dict(
            {"status_summary": "completed", "in_progress": False}
        )
        assert st.in_progress is False

    def test_speedtest_empty_dict(self):
        st = SpeedTestResult.from_dict({})
        assert st.download == 0.0
        assert st.upload == 0.0
        assert st.latency == 0.0


# ---------------------------------------------------------------------------
# Health subsystem VPN
# ---------------------------------------------------------------------------


class TestHealthSubsystemVpn:
    """Test VPN-related health subsystem fields."""

    def test_health_subsystem_vpn_active_users(self):
        """Subsystem with remote_user_num_active=2 indicates VPN activity."""
        sub = HealthSubsystem.from_dict(
            {
                "subsystem": "vpn",
                "status": "ok",
                "remote_user_num_active": 2,
                "remote_user_num_inactive": 1,
                "site_to_site_num_active": 0,
            }
        )
        assert sub.remote_user_num_active == 2
        assert sub.remote_user_num_inactive == 1
        # VPN is "active" if any remote users or site-to-site tunnels are up
        is_active = (
            sub.remote_user_num_active > 0 or sub.site_to_site_num_active > 0
        )
        assert is_active is True

    def test_health_subsystem_vpn_no_activity(self):
        sub = HealthSubsystem.from_dict(
            {
                "subsystem": "vpn",
                "status": "ok",
                "remote_user_num_active": 0,
                "site_to_site_num_active": 0,
            }
        )
        is_active = (
            sub.remote_user_num_active > 0 or sub.site_to_site_num_active > 0
        )
        assert is_active is False

    def test_health_subsystem_wan_gateway_stats(self):
        """WAN subsystem carries embedded gateway CPU/mem stats."""
        sub = HealthSubsystem.from_dict(
            {
                "subsystem": "wan",
                "status": "ok",
                "gw_system-stats": {"cpu": 22.5, "mem": 60.1},
                "gw_name": "UDM-Pro",
            }
        )
        assert sub.gw_cpu == pytest.approx(22.5)
        assert sub.gw_mem == pytest.approx(60.1)
        assert sub.gw_name == "UDM-Pro"


# ---------------------------------------------------------------------------
# Device storage percentage
# ---------------------------------------------------------------------------


class TestDeviceStorage:
    """Test storage percentage computation."""

    def test_device_storage_percentage(self):
        """storage with size=100, used=25 -> 25%."""
        storage = DeviceStorage.from_dict(
            {"name": "microSD", "mount_point": "/data", "size": 100, "used": 25}
        )
        assert storage.size == 100
        assert storage.used == 25
        pct = (storage.used / storage.size * 100) if storage.size > 0 else 0
        assert pct == pytest.approx(25.0)

    def test_device_storage_zero_size(self):
        """Zero size avoids division by zero."""
        storage = DeviceStorage.from_dict({"name": "empty", "size": 0, "used": 0})
        pct = (storage.used / storage.size * 100) if storage.size > 0 else 0
        assert pct == 0

    def test_device_storage_full(self):
        """Fully used storage -> 100%."""
        storage = DeviceStorage.from_dict({"size": 500, "used": 500})
        pct = (storage.used / storage.size * 100) if storage.size > 0 else 0
        assert pct == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Active WAN detection
# ---------------------------------------------------------------------------


class TestActiveWanDetection:
    """Test active WAN interface detection from Device model."""

    def test_active_wan_single_up(self):
        """Device with wan1.up=True, wan2.up=False -> active_wan == 'wan1'."""
        device = Device.from_dict(
            {
                "mac": "aa:bb:cc:dd:ee:01",
                "type": "udm",
                "wan1": {"name": "wan1", "up": True, "ip": "1.2.3.4"},
                "wan2": {"name": "wan2", "up": False},
            }
        )
        assert device.active_wan == "wan1"
        assert len(device.wan_interfaces) == 2
        assert device.wan_interfaces[0].up is True
        assert device.wan_interfaces[1].up is False

    def test_active_wan_both_up_uplink_selects(self):
        """Device with both WANs up; uplink pointing to wan2 -> active_wan == 'wan2'."""
        device = Device.from_dict(
            {
                "mac": "aa:bb:cc:dd:ee:01",
                "type": "udm",
                "wan1": {"name": "wan1", "up": True, "ip": "1.2.3.4"},
                "wan2": {"name": "wan2", "up": True, "ip": "5.6.7.8"},
                "uplink": {"name": "wan2"},
            }
        )
        # The uplink dict takes priority
        assert device.active_wan == "wan2"

    def test_active_wan_none_up(self):
        """No WAN interface is up -> active_wan is empty."""
        device = Device.from_dict(
            {
                "mac": "aa:bb:cc:dd:ee:01",
                "type": "udm",
                "wan1": {"name": "wan1", "up": False},
                "wan2": {"name": "wan2", "up": False},
            }
        )
        assert device.active_wan == ""

    def test_active_wan_no_wan_interfaces(self):
        """Non-gateway device (e.g. AP) has no WAN interfaces."""
        device = Device.from_dict(
            {
                "mac": "aa:bb:cc:dd:ee:02",
                "type": "uap",
                "name": "Office AP",
            }
        )
        assert device.wan_interfaces == []
        assert device.active_wan == ""

    def test_internet_detection_explicit(self):
        """Explicit 'internet' field takes precedence."""
        device = Device.from_dict(
            {
                "mac": "aa:bb:cc:dd:ee:01",
                "type": "udm",
                "internet": True,
            }
        )
        assert device.internet is True

    def test_internet_detection_from_wan(self):
        """Internet detected from WAN interface data when no explicit field."""
        device = Device.from_dict(
            {
                "mac": "aa:bb:cc:dd:ee:01",
                "type": "udm",
                "wan1": {"name": "wan1", "up": True, "internet": True},
            }
        )
        assert device.internet is True
