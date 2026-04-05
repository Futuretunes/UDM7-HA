"""Tests for the UniFi API data models (api/models.py).

These are pure unit tests -- no Home Assistant modules are imported.
Each model's ``from_dict`` classmethod is exercised with both empty and
realistic payloads to confirm safe parsing and correct field mapping.
"""

import pytest

from custom_components.unifi_network_ha.api.models import (
    Device,
    Client,
    WanInterface,
    SpeedTestResult,
    HealthSubsystem,
    Alarm,
    DpiData,
    DpiCategory,
    Wlan,
    DeviceTemperature,
    DevicePort,
    DeviceRadio,
    DeviceStorage,
    CloudIspMetrics,
)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_DEVICE = {
    "mac": "aa:bb:cc:dd:ee:ff",
    "ip": "192.168.1.1",
    "name": "Dream Router 7",
    "model": "UDR7",
    "model_name": "Dream Router 7",
    "type": "udm",
    "version": "4.0.6",
    "upgradable": True,
    "upgrade_to_firmware": "4.0.7",
    "adopted": True,
    "state": 1,
    "uptime": 86400,
    "system-stats": {"cpu": 12.5, "mem": 45.2},
    "sys_stats": {
        "loadavg_1": 0.5,
        "loadavg_5": 0.3,
        "loadavg_15": 0.2,
        "mem_total": 3145728,
        "mem_used": 1572864,
    },
    "num_sta": 25,
    "wan1": {
        "name": "wan1",
        "up": True,
        "ip": "203.0.113.5",
        "speed": 1000,
        "type": "dhcp",
        "rx_bytes-r": 125000.0,
        "tx_bytes-r": 50000.0,
        "gateway": "203.0.113.1",
        "dns": ["8.8.8.8", "8.8.4.4"],
    },
    "wan2": {
        "name": "wan2",
        "up": False,
        "ip": "198.51.100.10",
        "speed": 100,
    },
    "uplink": {"name": "wan1", "type": "wire"},
    "internet": True,
    "speedtest-status": {
        "xput_download": 500000000,
        "xput_upload": 100000000,
        "latency": 5.2,
        "rundate": 1700000000,
        "status_summary": "Success",
        "server": {"city": "New York", "country": "US"},
    },
    "temperatures": [
        {"name": "CPU", "value": 55.0, "type": "cpu"},
        {"name": "Board", "value": 42.0, "type": "board"},
    ],
    "port_table": [
        {
            "port_idx": 1,
            "name": "Port 1",
            "up": True,
            "speed": 1000,
            "poe_enable": True,
            "poe_power": "3.2",
        },
    ],
    "radio_table_stats": [
        {
            "name": "ra0",
            "radio": "ng",
            "channel": 6,
            "num_sta": 10,
            "cu_total": 35,
            "satisfaction": 85,
        },
    ],
    "storage": [
        {
            "name": "microSD",
            "mount_point": "/mnt/data",
            "size": 128000000000,
            "used": 32000000000,
        },
    ],
    "led_override": "on",
}


SAMPLE_CLIENT = {
    "mac": "11:22:33:44:55:66",
    "ip": "192.168.1.42",
    "hostname": "laptop",
    "name": "Work Laptop",
    "oui": "Apple",
    "is_wired": False,
    "essid": "MyNetwork",
    "bssid": "aa:bb:cc:dd:ee:f0",
    "ap_mac": "aa:bb:cc:dd:ee:ff",
    "signal": -55,
    "rssi": 40,
    "noise": -95,
    "channel": 36,
    "radio": "na",
    "radio_proto": "ax",
    "satisfaction": 98,
    "rx_bytes": 1000000,
    "tx_bytes": 500000,
    "rx_bytes-r": 12500.0,
    "tx_bytes-r": 6250.0,
    "rx_rate": 866000,
    "tx_rate": 866000,
    "uptime": 3600,
    "last_seen": 1700000000,
    "first_seen": 1699900000,
    "network": "LAN",
    "vlan": 1,
}


# ---------------------------------------------------------------------------
# Device tests
# ---------------------------------------------------------------------------


class TestDevice:
    """Tests for Device.from_dict."""

    def test_device_from_empty_dict(self):
        """An empty dict should produce a Device with all defaults -- no exception."""
        dev = Device.from_dict({})
        assert dev.mac == ""
        assert dev.ip == ""
        assert dev.name == ""
        assert dev.cpu_usage == 0.0
        assert dev.mem_usage == 0.0
        assert dev.wan_interfaces == []
        assert dev.speedtest is None
        assert dev.temperatures == []
        assert dev.ports == []
        assert dev.radios == []
        assert dev.storage == []
        assert dev.led_enabled is True  # default when led_override absent
        assert dev.raw == {}

    def test_device_from_full_dict(self):
        """A realistic device dict is fully parsed."""
        dev = Device.from_dict(SAMPLE_DEVICE)

        # Identity
        assert dev.mac == "aa:bb:cc:dd:ee:ff"
        assert dev.ip == "192.168.1.1"
        assert dev.name == "Dream Router 7"
        assert dev.model == "UDR7"
        assert dev.model_name == "Dream Router 7"
        assert dev.type == "udm"
        assert dev.version == "4.0.6"
        assert dev.upgradable is True
        assert dev.upgrade_to_firmware == "4.0.7"
        assert dev.adopted is True
        assert dev.state == 1
        assert dev.uptime == 86400

        # System stats (from "system-stats" hyphenated key)
        assert dev.cpu_usage == 12.5
        assert dev.mem_usage == 45.2

        # sys_stats (underscore key)
        assert dev.loadavg_1 == 0.5
        assert dev.loadavg_5 == 0.3
        assert dev.loadavg_15 == 0.2
        assert dev.mem_total == 3145728
        assert dev.mem_used == 1572864

        # Client count
        assert dev.num_sta == 25

        # WAN interfaces
        assert len(dev.wan_interfaces) == 2
        assert dev.wan_interfaces[0].name == "wan1"
        assert dev.wan_interfaces[0].up is True
        assert dev.wan_interfaces[0].ip == "203.0.113.5"
        assert dev.wan_interfaces[0].speed == 1000
        assert dev.wan_interfaces[0].rx_bytes_r == 125000.0
        assert dev.wan_interfaces[0].tx_bytes_r == 50000.0
        assert dev.wan_interfaces[0].gateway == "203.0.113.1"
        assert dev.wan_interfaces[0].dns == ["8.8.8.8", "8.8.4.4"]
        assert dev.wan_interfaces[1].name == "wan2"
        assert dev.wan_interfaces[1].up is False

        # Active WAN (from uplink)
        assert dev.active_wan == "wan1"
        assert dev.internet is True

        # Speed test
        assert dev.speedtest is not None
        assert dev.speedtest.download == 500000000
        assert dev.speedtest.upload == 100000000
        assert dev.speedtest.latency == 5.2
        assert dev.speedtest.run_date == 1700000000
        assert dev.speedtest.status_summary == "Success"
        assert dev.speedtest.server_city == "New York"
        assert dev.speedtest.server_country == "US"

        # Temperatures
        assert len(dev.temperatures) == 2
        assert dev.temperatures[0].name == "CPU"
        assert dev.temperatures[0].value == 55.0
        assert dev.temperatures[0].type == "cpu"
        assert dev.temperatures[1].name == "Board"
        assert dev.temperatures[1].value == 42.0

        # Ports
        assert len(dev.ports) == 1
        assert dev.ports[0].idx == 1
        assert dev.ports[0].name == "Port 1"
        assert dev.ports[0].up is True
        assert dev.ports[0].speed == 1000
        assert dev.ports[0].poe_enable is True
        assert dev.ports[0].poe_power == 3.2

        # Radios
        assert len(dev.radios) == 1
        assert dev.radios[0].name == "ra0"
        assert dev.radios[0].radio == "ng"
        assert dev.radios[0].channel == 6
        assert dev.radios[0].num_sta == 10
        assert dev.radios[0].cu_total == 35
        assert dev.radios[0].satisfaction == 85

        # Storage
        assert len(dev.storage) == 1
        assert dev.storage[0].name == "microSD"
        assert dev.storage[0].mount_point == "/mnt/data"
        assert dev.storage[0].size == 128000000000
        assert dev.storage[0].used == 32000000000

        # LED
        assert dev.led_enabled is True  # "on" != "off"

        # Uplink
        assert dev.uplink_type == "wire"

        # Raw data preserved
        assert dev.raw is SAMPLE_DEVICE

    def test_device_wan_extraction(self):
        """wan1 and wan2 dicts produce two WanInterface entries."""
        data = {
            "wan1": {"name": "wan1", "up": True, "ip": "1.1.1.1"},
            "wan2": {"name": "wan2", "up": False, "ip": "2.2.2.2"},
        }
        dev = Device.from_dict(data)
        assert len(dev.wan_interfaces) == 2
        assert dev.wan_interfaces[0].name == "wan1"
        assert dev.wan_interfaces[0].up is True
        assert dev.wan_interfaces[1].name == "wan2"
        assert dev.wan_interfaces[1].up is False

    def test_device_active_wan_from_uplink(self):
        """uplink.name = 'wan2' sets active_wan to 'wan2'."""
        data = {
            "wan1": {"name": "wan1", "up": True},
            "wan2": {"name": "wan2", "up": True},
            "uplink": {"name": "wan2", "type": "wire"},
        }
        dev = Device.from_dict(data)
        assert dev.active_wan == "wan2"

    def test_device_speedtest_parsing(self):
        """speedtest-status dict is parsed into a SpeedTestResult."""
        data = {
            "speedtest-status": {
                "xput_download": 250000000,
                "xput_upload": 50000000,
                "latency": 8.5,
                "rundate": 1700000000,
                "status_summary": "Success",
                "server": {"city": "London", "country": "GB"},
            },
        }
        dev = Device.from_dict(data)
        assert dev.speedtest is not None
        assert dev.speedtest.download == 250000000
        assert dev.speedtest.upload == 50000000
        assert dev.speedtest.latency == 8.5
        assert dev.speedtest.server_city == "London"
        assert dev.speedtest.server_country == "GB"

    def test_device_temperatures(self):
        """temperatures list is parsed into DeviceTemperature objects."""
        data = {
            "temperatures": [
                {"name": "CPU", "value": 60.0, "type": "cpu"},
                {"name": "PHY", "value": 48.5, "type": "phy"},
            ],
        }
        dev = Device.from_dict(data)
        assert len(dev.temperatures) == 2
        assert dev.temperatures[0].name == "CPU"
        assert dev.temperatures[0].value == 60.0
        assert dev.temperatures[0].type == "cpu"
        assert dev.temperatures[1].name == "PHY"
        assert dev.temperatures[1].value == 48.5
        assert dev.temperatures[1].type == "phy"


# ---------------------------------------------------------------------------
# Client tests
# ---------------------------------------------------------------------------


class TestClient:
    """Tests for Client.from_dict."""

    def test_client_from_dict(self):
        """A realistic client dict is fully parsed."""
        c = Client.from_dict(SAMPLE_CLIENT)
        assert c.mac == "11:22:33:44:55:66"
        assert c.ip == "192.168.1.42"
        assert c.hostname == "laptop"
        assert c.name == "Work Laptop"
        assert c.oui == "Apple"
        assert c.is_wired is False
        assert c.essid == "MyNetwork"
        assert c.bssid == "aa:bb:cc:dd:ee:f0"
        assert c.ap_mac == "aa:bb:cc:dd:ee:ff"
        assert c.signal == -55
        assert c.rssi == 40
        assert c.noise == -95
        assert c.channel == 36
        assert c.radio == "na"
        assert c.radio_proto == "ax"
        assert c.satisfaction == 98
        assert c.rx_bytes == 1000000
        assert c.tx_bytes == 500000
        assert c.rx_bytes_r == 12500.0
        assert c.tx_bytes_r == 6250.0
        assert c.rx_rate == 866000
        assert c.tx_rate == 866000
        assert c.uptime == 3600
        assert c.last_seen == 1700000000
        assert c.first_seen == 1699900000
        assert c.network == "LAN"
        assert c.vlan == 1
        assert c.raw is SAMPLE_CLIENT

    def test_client_from_empty_dict(self):
        """An empty dict should produce a Client with all defaults."""
        c = Client.from_dict({})
        assert c.mac == ""
        assert c.ip == ""
        assert c.hostname == ""
        assert c.is_wired is False
        assert c.is_guest is False
        assert c.signal == 0
        assert c.rx_bytes_r == 0.0
        assert c.raw == {}

    def test_client_guest_detection(self):
        """_is_guest_by_uap: true should set is_guest to True."""
        data = {
            "mac": "aa:bb:cc:dd:ee:ff",
            "_is_guest_by_uap": True,
        }
        c = Client.from_dict(data)
        assert c.is_guest is True

    def test_client_guest_detection_ugw(self):
        """_is_guest_by_ugw: true should also set is_guest to True."""
        data = {
            "mac": "aa:bb:cc:dd:ee:ff",
            "_is_guest_by_ugw": True,
        }
        c = Client.from_dict(data)
        assert c.is_guest is True


# ---------------------------------------------------------------------------
# WanInterface tests
# ---------------------------------------------------------------------------


class TestWanInterface:
    """Tests for WanInterface.from_dict."""

    def test_wan_interface_from_dict(self):
        """Hyphenated keys like 'rx_bytes-r' are handled correctly."""
        data = {
            "name": "wan1",
            "up": True,
            "ip": "1.2.3.4",
            "speed": 1000,
            "type": "dhcp",
            "rx_bytes-r": 99000.5,
            "tx_bytes-r": 33000.1,
            "gateway": "1.2.3.1",
            "dns": ["8.8.8.8"],
        }
        w = WanInterface.from_dict(data)
        assert w.name == "wan1"
        assert w.up is True
        assert w.ip == "1.2.3.4"
        assert w.speed == 1000
        assert w.type == "dhcp"
        assert w.rx_bytes_r == 99000.5
        assert w.tx_bytes_r == 33000.1
        assert w.gateway == "1.2.3.1"
        assert w.dns == ["8.8.8.8"]

    def test_wan_interface_empty(self):
        """An empty dict produces defaults without raising."""
        w = WanInterface.from_dict({})
        assert w.name == ""
        assert w.up is False
        assert w.rx_bytes_r == 0.0

    def test_wan_interface_dns_as_string(self):
        """DNS provided as comma-separated string is split into a list."""
        data = {"dns": "8.8.8.8, 1.1.1.1"}
        w = WanInterface.from_dict(data)
        assert w.dns == ["8.8.8.8", "1.1.1.1"]


# ---------------------------------------------------------------------------
# HealthSubsystem tests
# ---------------------------------------------------------------------------


class TestHealthSubsystem:
    """Tests for HealthSubsystem.from_dict."""

    def test_health_subsystem_from_dict(self):
        """Basic subsystem fields are parsed."""
        data = {
            "subsystem": "wan",
            "status": "ok",
            "wan_ip": "203.0.113.5",
            "isp_name": "ExampleISP",
            "num_user": 10,
            "num_guest": 2,
            "latency": 5.5,
        }
        h = HealthSubsystem.from_dict(data)
        assert h.subsystem == "wan"
        assert h.status == "ok"
        assert h.wan_ip == "203.0.113.5"
        assert h.isp_name == "ExampleISP"
        assert h.num_user == 10
        assert h.num_guest == 2
        assert h.latency == 5.5

    def test_health_gw_system_stats(self):
        """gw_system-stats (hyphenated key) is parsed into gw_cpu and gw_mem."""
        data = {
            "subsystem": "wan",
            "status": "ok",
            "gw_system-stats": {"cpu": 25.5, "mem": 60.0},
            "gw_version": "4.0.6",
        }
        h = HealthSubsystem.from_dict(data)
        assert h.gw_cpu == 25.5
        assert h.gw_mem == 60.0
        assert h.gw_version == "4.0.6"

    def test_health_empty_dict(self):
        """An empty dict produces defaults."""
        h = HealthSubsystem.from_dict({})
        assert h.subsystem == ""
        assert h.status == ""
        assert h.gw_cpu == 0.0
        assert h.gw_mem == 0.0


# ---------------------------------------------------------------------------
# Alarm tests
# ---------------------------------------------------------------------------


class TestAlarm:
    """Tests for Alarm.from_dict."""

    def test_alarm_from_dict(self):
        """All alarm fields including IPS-specific ones are parsed."""
        data = {
            "_id": "abc123",
            "key": "EVT_IPS_Alert",
            "msg": "Suspicious traffic detected",
            "datetime": "2024-01-15T10:30:00Z",
            "time": 1705312200,
            "archived": False,
            "catname": "Intrusion",
            "src_ip": "10.0.0.5",
            "src_port": 54321,
            "dest_ip": "192.168.1.100",
            "dest_port": 443,
            "proto": "tcp",
            "inner_alert_action": "blocked",
            "inner_alert_severity": 3,
            "inner_alert_signature": "ET TROJAN Something",
        }
        a = Alarm.from_dict(data)
        assert a.id == "abc123"
        assert a.key == "EVT_IPS_Alert"
        assert a.msg == "Suspicious traffic detected"
        assert a.datetime == "2024-01-15T10:30:00Z"
        assert a.timestamp == 1705312200
        assert a.archived is False
        assert a.catname == "Intrusion"
        assert a.src_ip == "10.0.0.5"
        assert a.src_port == 54321
        assert a.dest_ip == "192.168.1.100"
        assert a.dest_port == 443
        assert a.proto == "tcp"
        assert a.inner_alert_action == "blocked"
        assert a.inner_alert_severity == 3
        assert a.inner_alert_signature == "ET TROJAN Something"
        assert a.raw is data

    def test_alarm_empty_dict(self):
        """An empty dict produces defaults."""
        a = Alarm.from_dict({})
        assert a.id == ""
        assert a.key == ""
        assert a.src_ip == ""
        assert a.dest_ip == ""


# ---------------------------------------------------------------------------
# DPI tests
# ---------------------------------------------------------------------------


class TestDpiData:
    """Tests for DpiData.from_dict."""

    def test_dpi_data_from_dict(self):
        """by_cat and by_app lists are parsed into DpiCategory objects."""
        data = {
            "by_cat": [
                {"cat": 3, "rx_bytes": 100000, "tx_bytes": 50000, "rx_packets": 100, "tx_packets": 50},
                {"cat": 5, "rx_bytes": 200000, "tx_bytes": 100000, "rx_packets": 200, "tx_packets": 100},
            ],
            "by_app": [
                {"cat": 3, "app": 42, "rx_bytes": 80000, "tx_bytes": 40000},
            ],
        }
        dpi = DpiData.from_dict(data)
        assert len(dpi.by_cat) == 2
        assert dpi.by_cat[0].cat == 3
        assert dpi.by_cat[0].rx_bytes == 100000
        assert dpi.by_cat[0].tx_bytes == 50000
        assert dpi.by_cat[1].cat == 5
        assert dpi.by_cat[1].rx_bytes == 200000
        assert len(dpi.by_app) == 1
        assert dpi.by_app[0].cat == 3
        assert dpi.by_app[0].app == 42
        assert dpi.by_app[0].rx_bytes == 80000

    def test_dpi_data_empty(self):
        """An empty dict produces empty lists."""
        dpi = DpiData.from_dict({})
        assert dpi.by_cat == []
        assert dpi.by_app == []

    def test_dpi_category_from_dict(self):
        """Individual DpiCategory parsing."""
        data = {"cat": 7, "app": 99, "rx_bytes": 1234, "tx_bytes": 5678, "rx_packets": 10, "tx_packets": 20}
        cat = DpiCategory.from_dict(data)
        assert cat.cat == 7
        assert cat.app == 99
        assert cat.rx_bytes == 1234
        assert cat.tx_bytes == 5678
        assert cat.rx_packets == 10
        assert cat.tx_packets == 20


# ---------------------------------------------------------------------------
# CloudIspMetrics tests
# ---------------------------------------------------------------------------


class TestCloudIspMetrics:
    """Tests for CloudIspMetrics.from_dict."""

    def test_cloud_isp_metrics(self):
        """camelCase fields from the cloud API are mapped to snake_case attrs."""
        data = {
            "periodStart": "2024-01-01T00:00:00Z",
            "periodEnd": "2024-01-02T00:00:00Z",
            "wanName": "wan1",
            "ispName": "Comcast",
            "ispAsn": 7922,
            "avgLatency": 12.5,
            "maxLatency": 45.0,
            "packetLoss": 0.01,
            "downloadKbps": 500000.0,
            "uploadKbps": 50000.0,
            "uptime": 99.95,
            "downtime": 0.05,
        }
        m = CloudIspMetrics.from_dict(data)
        assert m.period_start == "2024-01-01T00:00:00Z"
        assert m.period_end == "2024-01-02T00:00:00Z"
        assert m.wan_name == "wan1"
        assert m.isp_name == "Comcast"
        assert m.isp_asn == 7922
        assert m.avg_latency == 12.5
        assert m.max_latency == 45.0
        assert m.packet_loss == 0.01
        assert m.download_kbps == 500000.0
        assert m.upload_kbps == 50000.0
        assert m.uptime == 99.95
        assert m.downtime == 0.05

    def test_cloud_isp_metrics_snake_case(self):
        """snake_case fields are also accepted (dual-key support)."""
        data = {
            "period_start": "2024-06-01",
            "period_end": "2024-06-02",
            "wan_name": "wan2",
            "isp_name": "AT&T",
            "isp_asn": 7018,
            "avg_latency": 20.0,
            "max_latency": 50.0,
            "packet_loss": 0.5,
            "download_kbps": 100000.0,
            "upload_kbps": 10000.0,
        }
        m = CloudIspMetrics.from_dict(data)
        assert m.period_start == "2024-06-01"
        assert m.wan_name == "wan2"
        assert m.isp_name == "AT&T"
        assert m.avg_latency == 20.0

    def test_cloud_isp_metrics_empty(self):
        """An empty dict produces defaults."""
        m = CloudIspMetrics.from_dict({})
        assert m.period_start == ""
        assert m.isp_name == ""
        assert m.avg_latency == 0.0
        assert m.download_kbps == 0.0


# ---------------------------------------------------------------------------
# SpeedTestResult tests
# ---------------------------------------------------------------------------


class TestSpeedTestResult:
    """Tests for SpeedTestResult.from_dict."""

    def test_speedtest_from_dict(self):
        """Full speed test dict with server sub-dict is parsed."""
        data = {
            "xput_download": 500000000,
            "xput_upload": 100000000,
            "latency": 5.2,
            "rundate": 1700000000,
            "status_summary": "Success",
            "server": {"city": "New York", "country": "US"},
        }
        st = SpeedTestResult.from_dict(data)
        assert st.download == 500000000
        assert st.upload == 100000000
        assert st.latency == 5.2
        assert st.run_date == 1700000000
        assert st.status_summary == "Success"
        assert st.server_city == "New York"
        assert st.server_country == "US"

    def test_speedtest_empty(self):
        """Empty dict produces defaults."""
        st = SpeedTestResult.from_dict({})
        assert st.download == 0.0
        assert st.upload == 0.0
        assert st.latency == 0.0


# ---------------------------------------------------------------------------
# Wlan tests
# ---------------------------------------------------------------------------


class TestWlan:
    """Tests for Wlan.from_dict."""

    def test_wlan_from_dict(self):
        """WLAN configuration dict is parsed correctly."""
        data = {
            "_id": "wlan001",
            "name": "MyNetwork",
            "enabled": True,
            "security": "wpapsk",
            "wpa_mode": "wpa2",
            "x_passphrase": "secret123",
            "is_guest": False,
        }
        w = Wlan.from_dict(data)
        assert w.id == "wlan001"
        assert w.name == "MyNetwork"
        assert w.enabled is True
        assert w.security == "wpapsk"
        assert w.wpa_mode == "wpa2"
        assert w.x_passphrase == "secret123"
        assert w.is_guest is False


# ---------------------------------------------------------------------------
# Hardware detail model tests
# ---------------------------------------------------------------------------


class TestHardwareModels:
    """Tests for DeviceTemperature, DevicePort, DeviceRadio, DeviceStorage."""

    def test_device_temperature_from_dict(self):
        data = {"name": "CPU", "value": 72.3, "type": "cpu"}
        t = DeviceTemperature.from_dict(data)
        assert t.name == "CPU"
        assert t.value == 72.3
        assert t.type == "cpu"

    def test_device_port_from_dict(self):
        data = {
            "port_idx": 3,
            "name": "LAN 3",
            "up": True,
            "speed": 2500,
            "poe_enable": True,
            "poe_power": "7.5",
            "rx_bytes-r": 50000.0,
            "tx_bytes-r": 30000.0,
        }
        p = DevicePort.from_dict(data)
        assert p.idx == 3
        assert p.name == "LAN 3"
        assert p.up is True
        assert p.speed == 2500
        assert p.poe_enable is True
        assert p.poe_power == 7.5
        assert p.rx_bytes_r == 50000.0
        assert p.tx_bytes_r == 30000.0

    def test_device_radio_from_dict(self):
        data = {
            "name": "ra0",
            "radio": "ng",
            "channel": 6,
            "num_sta": 15,
            "cu_total": 42,
            "satisfaction": 90,
            "tx_power": 23,
        }
        r = DeviceRadio.from_dict(data)
        assert r.name == "ra0"
        assert r.radio == "ng"
        assert r.channel == 6
        assert r.num_sta == 15
        assert r.cu_total == 42
        assert r.satisfaction == 90
        assert r.tx_power == 23

    def test_device_storage_from_dict(self):
        data = {
            "name": "SSD",
            "mount_point": "/mnt/ssd",
            "size": 256000000000,
            "used": 64000000000,
            "type": "ssd",
        }
        s = DeviceStorage.from_dict(data)
        assert s.name == "SSD"
        assert s.mount_point == "/mnt/ssd"
        assert s.size == 256000000000
        assert s.used == 64000000000
        assert s.type == "ssd"
