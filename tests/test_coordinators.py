"""Tests for coordinator data processing.

Since the actual coordinators require a full Home Assistant installation
(DataUpdateCoordinator, hass instance, etc.), we test the *data processing
logic* they rely on -- model parsing via ``from_dict`` and the merge /
dispatch patterns used in ``process_websocket_message``.

Each helper function below mirrors the corresponding coordinator method so
the business logic is exercised without HA dependencies.
"""

import pytest

from custom_components.unifi_network_ha.api.models import (
    Alarm,
    Client,
    Device,
    DpiCategory,
    DpiData,
    HealthSubsystem,
)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_DEVICES_RAW = [
    {
        "mac": "aa:bb:cc:dd:ee:01",
        "name": "Gateway",
        "type": "udm",
        "state": 1,
        "system-stats": {"cpu": 10.0, "mem": 40.0},
    },
    {
        "mac": "aa:bb:cc:dd:ee:02",
        "name": "Office AP",
        "type": "uap",
        "state": 1,
        "num_sta": 5,
    },
    {
        "mac": "aa:bb:cc:dd:ee:03",
        "name": "Switch 24",
        "type": "usw",
        "state": 1,
    },
]

SAMPLE_CLIENTS_RAW = [
    {
        "mac": "11:22:33:44:55:01",
        "hostname": "laptop",
        "ip": "192.168.1.100",
        "is_wired": False,
        "essid": "HomeNet",
        "signal": -55,
    },
    {
        "mac": "11:22:33:44:55:02",
        "hostname": "desktop",
        "ip": "192.168.1.101",
        "is_wired": True,
    },
    {
        "mac": "11:22:33:44:55:03",
        "hostname": "phone",
        "ip": "192.168.1.102",
        "is_wired": False,
        "essid": "HomeNet",
        "signal": -70,
        "_is_guest_by_uap": True,
    },
]

SAMPLE_HEALTH_RAW = [
    {
        "subsystem": "wan",
        "status": "ok",
        "wan_ip": "203.0.113.5",
        "isp_name": "Comcast",
        "latency": 8.5,
        "gw_system-stats": {"cpu": 15.0, "mem": 55.0},
        "gw_name": "Gateway",
    },
    {
        "subsystem": "wlan",
        "status": "ok",
        "num_user": 20,
        "num_guest": 3,
        "num_iot": 5,
        "num_ap": 2,
    },
    {
        "subsystem": "lan",
        "status": "ok",
        "num_user": 8,
        "num_sw": 3,
    },
    {
        "subsystem": "vpn",
        "status": "ok",
        "remote_user_num_active": 1,
        "site_to_site_num_active": 0,
    },
]

SAMPLE_ALARMS_RAW = [
    {
        "_id": "alarm1",
        "key": "EVT_IPS_Alert",
        "msg": "Threat detected",
        "time": 1700000000,
        "src_ip": "198.51.100.5",
        "dest_ip": "192.168.1.100",
        "dest_port": 22,
        "proto": "tcp",
        "inner_alert_severity": 2,
        "inner_alert_signature": "ET SCAN SSH",
    },
    {
        "_id": "alarm2",
        "key": "EVT_GW_WANTransition",
        "msg": "WAN failover",
        "time": 1699999000,
    },
]

SAMPLE_DPI_RAW = {
    "by_cat": [
        {"cat": 1, "app": 0, "rx_bytes": 500_000, "tx_bytes": 100_000},
        {"cat": 2, "app": 0, "rx_bytes": 200_000, "tx_bytes": 50_000},
        {"cat": 3, "app": 0, "rx_bytes": 800_000, "tx_bytes": 300_000},
    ],
    "by_app": [
        {"cat": 1, "app": 10, "rx_bytes": 300_000, "tx_bytes": 80_000},
        {"cat": 1, "app": 20, "rx_bytes": 100_000, "tx_bytes": 10_000},
        {"cat": 3, "app": 30, "rx_bytes": 700_000, "tx_bytes": 200_000},
    ],
}


# ---------------------------------------------------------------------------
# Helpers — mirror coordinator logic without HA dependencies
# ---------------------------------------------------------------------------


def parse_devices(raw_list: list[dict]) -> dict[str, Device]:
    """Mirror DeviceCoordinator._async_fetch_data logic."""
    devices: dict[str, Device] = {}
    for raw in raw_list:
        device = Device.from_dict(raw)
        if device.mac:
            devices[device.mac] = device
    return devices


def merge_device_ws(
    devices: dict[str, Device], ws_data: list[dict]
) -> dict[str, Device]:
    """Mirror DeviceCoordinator.process_websocket_message logic."""
    for item in ws_data:
        mac = item.get("mac", "")
        if mac:
            devices[mac] = Device.from_dict(item)
    return devices


def parse_clients(raw_list: list[dict]) -> dict[str, Client]:
    """Mirror ClientCoordinator._async_fetch_data logic."""
    clients: dict[str, Client] = {}
    for raw in raw_list:
        client = Client.from_dict(raw)
        if client.mac:
            clients[client.mac] = client
    return clients


def merge_client_ws(
    clients: dict[str, Client],
    all_known: dict[str, Client],
    msg_type: str,
    ws_data: list[dict],
) -> tuple[dict[str, Client], dict[str, Client]]:
    """Mirror ClientCoordinator.process_websocket_message logic."""
    for item in ws_data:
        mac = item.get("mac", "")
        if not mac:
            continue
        if msg_type == "user:delete":
            clients.pop(mac, None)
        else:
            client = Client.from_dict(item)
            clients[mac] = client
            all_known[mac] = client
    return clients, all_known


def parse_health(raw_list: list[dict]) -> dict[str, HealthSubsystem]:
    """Mirror HealthCoordinator._async_fetch_data logic."""
    subsystems: dict[str, HealthSubsystem] = {}
    for raw in raw_list:
        sub = HealthSubsystem.from_dict(raw)
        if sub.subsystem:
            subsystems[sub.subsystem] = sub
    return subsystems


def parse_alarms(raw_list: list[dict]) -> list[Alarm]:
    """Mirror AlarmCoordinator._async_fetch_data logic."""
    alarms = [Alarm.from_dict(a) for a in raw_list]
    alarms.sort(key=lambda a: a.timestamp, reverse=True)
    return alarms


def merge_alarm_ws(
    alarms: list[Alarm], ws_data: list[dict]
) -> list[Alarm]:
    """Mirror AlarmCoordinator.process_websocket_message logic."""
    existing_ids = {a.id for a in alarms}
    for item in ws_data:
        alarm = Alarm.from_dict(item)
        if not alarm.id:
            continue
        if alarm.id not in existing_ids:
            alarms.insert(0, alarm)
        else:
            for i, existing in enumerate(alarms):
                if existing.id == alarm.id:
                    alarms[i] = alarm
                    break
    # Remove archived, re-sort
    alarms = [a for a in alarms if not a.archived]
    alarms.sort(key=lambda a: a.timestamp, reverse=True)
    return alarms


def parse_dpi(raw: dict) -> DpiData:
    """Mirror DpiCoordinator._async_fetch_data logic."""
    return DpiData.from_dict(raw)


# ---------------------------------------------------------------------------
# Tests — Device coordinator
# ---------------------------------------------------------------------------


class TestDeviceCoordinatorParsing:
    """Verify device data parsing."""

    def test_device_coordinator_data_parsing(self):
        """Given a list of raw device dicts, parse them into Device objects."""
        devices = parse_devices(SAMPLE_DEVICES_RAW)

        assert len(devices) == 3
        assert "aa:bb:cc:dd:ee:01" in devices
        assert "aa:bb:cc:dd:ee:02" in devices
        assert "aa:bb:cc:dd:ee:03" in devices

        gw = devices["aa:bb:cc:dd:ee:01"]
        assert gw.name == "Gateway"
        assert gw.type == "udm"
        assert gw.state == 1
        assert gw.cpu_usage == pytest.approx(10.0)
        assert gw.mem_usage == pytest.approx(40.0)

        ap = devices["aa:bb:cc:dd:ee:02"]
        assert ap.name == "Office AP"
        assert ap.type == "uap"
        assert ap.num_sta == 5

        sw = devices["aa:bb:cc:dd:ee:03"]
        assert sw.name == "Switch 24"
        assert sw.type == "usw"

    def test_device_coordinator_data_parsing_empty(self):
        """Empty input yields an empty dict."""
        devices = parse_devices([])
        assert devices == {}

    def test_device_coordinator_data_parsing_missing_mac(self):
        """A device dict without a mac key is skipped."""
        devices = parse_devices([{"name": "no-mac-device", "type": "uap"}])
        assert len(devices) == 0


class TestDeviceCoordinatorWebSocket:
    """Verify WebSocket merge behaviour for devices."""

    def test_device_coordinator_ws_merge(self):
        """A device:sync message that changes one device's CPU is reflected."""
        devices = parse_devices(SAMPLE_DEVICES_RAW)
        assert devices["aa:bb:cc:dd:ee:01"].cpu_usage == pytest.approx(10.0)

        # Simulate a ws update — gateway CPU goes to 75
        ws_data = [
            {
                "mac": "aa:bb:cc:dd:ee:01",
                "name": "Gateway",
                "type": "udm",
                "state": 1,
                "system-stats": {"cpu": 75.0, "mem": 42.0},
            }
        ]
        devices = merge_device_ws(devices, ws_data)

        assert len(devices) == 3  # total count unchanged
        assert devices["aa:bb:cc:dd:ee:01"].cpu_usage == pytest.approx(75.0)
        assert devices["aa:bb:cc:dd:ee:01"].mem_usage == pytest.approx(42.0)

    def test_device_coordinator_ws_merge_new_device(self):
        """A device:sync for a new MAC adds it to the collection."""
        devices = parse_devices(SAMPLE_DEVICES_RAW)
        assert len(devices) == 3

        ws_data = [
            {
                "mac": "aa:bb:cc:dd:ee:04",
                "name": "New AP",
                "type": "uap",
                "state": 1,
            }
        ]
        devices = merge_device_ws(devices, ws_data)
        assert len(devices) == 4
        assert devices["aa:bb:cc:dd:ee:04"].name == "New AP"


# ---------------------------------------------------------------------------
# Tests — Client coordinator
# ---------------------------------------------------------------------------


class TestClientCoordinatorParsing:
    """Verify client data parsing."""

    def test_client_coordinator_data_parsing(self):
        """Given raw client dicts, parse into Client objects keyed by MAC."""
        clients = parse_clients(SAMPLE_CLIENTS_RAW)

        assert len(clients) == 3
        assert "11:22:33:44:55:01" in clients
        assert "11:22:33:44:55:02" in clients
        assert "11:22:33:44:55:03" in clients

        laptop = clients["11:22:33:44:55:01"]
        assert laptop.hostname == "laptop"
        assert laptop.ip == "192.168.1.100"
        assert laptop.is_wired is False
        assert laptop.essid == "HomeNet"
        assert laptop.signal == -55

        desktop = clients["11:22:33:44:55:02"]
        assert desktop.hostname == "desktop"
        assert desktop.is_wired is True

        phone = clients["11:22:33:44:55:03"]
        assert phone.hostname == "phone"
        assert phone.is_guest is True

    def test_client_coordinator_data_parsing_empty(self):
        """Empty input yields an empty dict."""
        clients = parse_clients([])
        assert clients == {}


class TestClientCoordinatorWebSocket:
    """Verify WebSocket merge/delete behaviour for clients."""

    def test_client_coordinator_ws_merge_update(self):
        """sta:sync update for an existing client updates the data."""
        clients = parse_clients(SAMPLE_CLIENTS_RAW)
        all_known = dict(clients)

        ws_data = [
            {
                "mac": "11:22:33:44:55:01",
                "hostname": "laptop",
                "ip": "192.168.1.200",  # IP changed
                "is_wired": False,
                "essid": "HomeNet",
                "signal": -45,  # signal improved
            }
        ]
        clients, all_known = merge_client_ws(
            clients, all_known, "sta:sync", ws_data
        )

        assert len(clients) == 3
        assert clients["11:22:33:44:55:01"].ip == "192.168.1.200"
        assert clients["11:22:33:44:55:01"].signal == -45

    def test_client_coordinator_ws_merge_new_client(self):
        """sta:sync for a brand-new MAC adds the client."""
        clients = parse_clients(SAMPLE_CLIENTS_RAW)
        all_known = dict(clients)

        ws_data = [
            {
                "mac": "11:22:33:44:55:99",
                "hostname": "tablet",
                "ip": "192.168.1.200",
                "is_wired": False,
                "essid": "GuestNet",
            }
        ]
        clients, all_known = merge_client_ws(
            clients, all_known, "sta:sync", ws_data
        )

        assert len(clients) == 4
        assert "11:22:33:44:55:99" in clients
        assert clients["11:22:33:44:55:99"].hostname == "tablet"
        # Also added to all_known
        assert "11:22:33:44:55:99" in all_known

    def test_client_coordinator_ws_delete(self):
        """user:delete removes a client from the active set."""
        clients = parse_clients(SAMPLE_CLIENTS_RAW)
        all_known = dict(clients)

        ws_data = [{"mac": "11:22:33:44:55:02"}]
        clients, all_known = merge_client_ws(
            clients, all_known, "user:delete", ws_data
        )

        # Active set no longer has the deleted client
        assert len(clients) == 2
        assert "11:22:33:44:55:02" not in clients
        # all_known still has it (user:delete does not touch all_known)
        assert "11:22:33:44:55:02" in all_known

    def test_client_coordinator_ws_delete_nonexistent(self):
        """Deleting a MAC that is not in the active set is a no-op."""
        clients = parse_clients(SAMPLE_CLIENTS_RAW)
        all_known = dict(clients)

        ws_data = [{"mac": "ff:ff:ff:ff:ff:ff"}]
        clients, all_known = merge_client_ws(
            clients, all_known, "user:delete", ws_data
        )

        assert len(clients) == 3  # unchanged


# ---------------------------------------------------------------------------
# Tests — Health coordinator
# ---------------------------------------------------------------------------


class TestHealthCoordinatorParsing:
    """Verify health subsystem parsing."""

    def test_health_coordinator_parsing(self):
        """Given raw health data, parse correctly keyed by subsystem name."""
        subsystems = parse_health(SAMPLE_HEALTH_RAW)

        assert len(subsystems) == 4
        assert set(subsystems.keys()) == {"wan", "wlan", "lan", "vpn"}

        wan = subsystems["wan"]
        assert wan.status == "ok"
        assert wan.wan_ip == "203.0.113.5"
        assert wan.isp_name == "Comcast"
        assert wan.latency == pytest.approx(8.5)
        assert wan.gw_cpu == pytest.approx(15.0)
        assert wan.gw_mem == pytest.approx(55.0)
        assert wan.gw_name == "Gateway"

        wlan = subsystems["wlan"]
        assert wlan.num_user == 20
        assert wlan.num_guest == 3
        assert wlan.num_iot == 5
        assert wlan.num_ap == 2

        lan = subsystems["lan"]
        assert lan.num_user == 8
        assert lan.num_sw == 3

        vpn = subsystems["vpn"]
        assert vpn.remote_user_num_active == 1
        assert vpn.site_to_site_num_active == 0

    def test_health_coordinator_parsing_empty(self):
        """Empty list yields empty dict."""
        subsystems = parse_health([])
        assert subsystems == {}

    def test_health_coordinator_parsing_missing_subsystem(self):
        """A dict without 'subsystem' key is skipped."""
        subsystems = parse_health([{"status": "ok"}])
        assert len(subsystems) == 0


# ---------------------------------------------------------------------------
# Tests — Alarm coordinator
# ---------------------------------------------------------------------------


class TestAlarmCoordinatorParsing:
    """Verify alarm parsing."""

    def test_alarm_coordinator_parsing(self):
        """Given raw alarm list, parse into Alarm objects with correct count."""
        alarms = parse_alarms(SAMPLE_ALARMS_RAW)

        assert len(alarms) == 2

        # Sorted by timestamp descending — alarm1 (1700000000) first
        assert alarms[0].id == "alarm1"
        assert alarms[0].key == "EVT_IPS_Alert"
        assert alarms[0].msg == "Threat detected"
        assert alarms[0].timestamp == 1700000000
        assert alarms[0].src_ip == "198.51.100.5"
        assert alarms[0].dest_ip == "192.168.1.100"
        assert alarms[0].dest_port == 22
        assert alarms[0].proto == "tcp"
        assert alarms[0].inner_alert_severity == 2
        assert alarms[0].inner_alert_signature == "ET SCAN SSH"

        assert alarms[1].id == "alarm2"
        assert alarms[1].key == "EVT_GW_WANTransition"
        assert alarms[1].timestamp == 1699999000

    def test_alarm_coordinator_parsing_empty(self):
        """Empty input yields empty list."""
        alarms = parse_alarms([])
        assert alarms == []


class TestAlarmCoordinatorWebSocket:
    """Verify alarm WebSocket add/update behaviour."""

    def test_alarm_coordinator_ws_add(self):
        """alarm:add prepends a new alarm."""
        alarms = parse_alarms(SAMPLE_ALARMS_RAW)
        assert len(alarms) == 2

        ws_data = [
            {
                "_id": "alarm3",
                "key": "EVT_IPS_Alert",
                "msg": "New threat",
                "time": 1700001000,
            }
        ]
        alarms = merge_alarm_ws(alarms, ws_data)

        assert len(alarms) == 3
        # alarm3 has the highest timestamp, so it should be first
        assert alarms[0].id == "alarm3"
        assert alarms[0].timestamp == 1700001000

    def test_alarm_coordinator_ws_update_existing(self):
        """alarm:sync updating an existing alarm replaces it."""
        alarms = parse_alarms(SAMPLE_ALARMS_RAW)

        ws_data = [
            {
                "_id": "alarm1",
                "key": "EVT_IPS_Alert",
                "msg": "Updated threat info",
                "time": 1700000000,
            }
        ]
        alarms = merge_alarm_ws(alarms, ws_data)

        assert len(alarms) == 2
        # Find alarm1 and check the updated message
        alarm1 = next(a for a in alarms if a.id == "alarm1")
        assert alarm1.msg == "Updated threat info"

    def test_alarm_coordinator_ws_archive_removes(self):
        """When an alarm update marks it archived, it is removed."""
        alarms = parse_alarms(SAMPLE_ALARMS_RAW)
        assert len(alarms) == 2

        ws_data = [
            {
                "_id": "alarm1",
                "key": "EVT_IPS_Alert",
                "msg": "Threat detected",
                "time": 1700000000,
                "archived": True,
            }
        ]
        alarms = merge_alarm_ws(alarms, ws_data)

        assert len(alarms) == 1
        assert alarms[0].id == "alarm2"


# ---------------------------------------------------------------------------
# Tests — DPI coordinator
# ---------------------------------------------------------------------------


class TestDpiCoordinatorParsing:
    """Verify DPI data parsing and sorting."""

    def test_dpi_coordinator_parsing(self):
        """Given raw DPI response, parse into DpiData with categories and apps."""
        dpi = parse_dpi(SAMPLE_DPI_RAW)

        assert len(dpi.by_cat) == 3
        assert len(dpi.by_app) == 3

        # Verify individual category data
        cat1 = dpi.by_cat[0]
        assert cat1.cat == 1
        assert cat1.rx_bytes == 500_000
        assert cat1.tx_bytes == 100_000

    def test_dpi_coordinator_top_categories_sorted(self):
        """Top categories are sorted by total bytes (rx + tx) descending."""
        dpi = parse_dpi(SAMPLE_DPI_RAW)

        # Sort same way the coordinator does
        top_categories = sorted(
            dpi.by_cat,
            key=lambda c: c.rx_bytes + c.tx_bytes,
            reverse=True,
        )[:10]

        # cat 3 (800k+300k=1.1M) > cat 1 (500k+100k=600k) > cat 2 (200k+50k=250k)
        assert top_categories[0].cat == 3
        assert top_categories[1].cat == 1
        assert top_categories[2].cat == 2

    def test_dpi_coordinator_top_apps_sorted(self):
        """Top apps are sorted by total bytes (rx + tx) descending."""
        dpi = parse_dpi(SAMPLE_DPI_RAW)

        top_apps = sorted(
            dpi.by_app,
            key=lambda a: a.rx_bytes + a.tx_bytes,
            reverse=True,
        )[:10]

        # app 30 (700k+200k=900k) > app 10 (300k+80k=380k) > app 20 (100k+10k=110k)
        assert top_apps[0].app == 30
        assert top_apps[1].app == 10
        assert top_apps[2].app == 20

    def test_dpi_coordinator_parsing_empty(self):
        """Empty DPI data yields empty lists."""
        dpi = parse_dpi({})
        assert dpi.by_cat == []
        assert dpi.by_app == []
