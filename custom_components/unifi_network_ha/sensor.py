"""UniFi Network HA sensor platform.

Provides sensors for gateway system stats, WAN interfaces, speed-test
results, and site-health metrics.  Dynamic sensors (temperatures, storage,
per-WAN-interface) are discovered at setup time based on the data reported
by the gateway device.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    PERCENTAGE,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.models import DevicePort
from .const import (
    CONF_ENABLE_ALARMS,
    CONF_ENABLE_CLOUD,
    CONF_ENABLE_DEVICE_SENSORS,
    CONF_ENABLE_DPI,
    CONF_ENABLE_PER_CLIENT_SENSORS,
    CONF_ENABLE_VPN,
    DeviceState,
)
from .coordinators.base import UniFiDataUpdateCoordinator
from .entity import UniFiEntity
from .hub import UniFiHub

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo

# Type alias used in __init__.py — import so the platform signature matches.
from . import UniFiConfigEntry

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sensor description
# ---------------------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class UniFiSensorDescription(SensorEntityDescription):
    """Extended sensor description with a value-extraction callback.

    Attributes
    ----------
    value_fn:
        Called with the ``UniFiHub`` instance; must return the native sensor
        value (or ``None`` when unavailable).
    coordinator_key:
        Selects which coordinator the entity subscribes to for updates.
        One of ``"device"``, ``"health"``, or ``"wan_rate"``.
    """

    value_fn: Callable[[UniFiHub], Any]
    coordinator_key: str = "device"


# ---------------------------------------------------------------------------
# Coordinator lookup helper
# ---------------------------------------------------------------------------

def _get_coordinator(hub: UniFiHub, key: str) -> UniFiDataUpdateCoordinator:
    """Return the coordinator that matches *key*."""
    mapping: dict[str, UniFiDataUpdateCoordinator | None] = {
        "device": hub.device_coordinator,
        "health": hub.health_coordinator,
        "wan_rate": hub.wan_rate_coordinator,
        "alarm": hub.alarm_coordinator,
        "dpi": hub.dpi_coordinator,
        "cloud": hub.cloud_coordinator,
        "client": hub.client_coordinator,
    }
    coordinator = mapping.get(key)
    if coordinator is None:
        raise ValueError(f"Unknown or uninitialised coordinator key: {key!r}")
    return coordinator


# ---------------------------------------------------------------------------
# Static gateway sensors  (coordinator_key="device" unless noted)
# ---------------------------------------------------------------------------

GATEWAY_SENSORS: tuple[UniFiSensorDescription, ...] = (
    # ── System ──────────────────────────────────────────────────────────
    UniFiSensorDescription(
        key="cpu_usage",
        translation_key="cpu_usage",
        name="CPU usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:cpu-64-bit",
        value_fn=lambda hub: _gw(hub, "cpu_usage"),
    ),
    UniFiSensorDescription(
        key="memory_usage",
        translation_key="memory_usage",
        name="Memory usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:memory",
        value_fn=lambda hub: _gw(hub, "mem_usage"),
    ),
    UniFiSensorDescription(
        key="uptime",
        translation_key="uptime",
        name="Uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:clock-outline",
        value_fn=lambda hub: _gw(hub, "uptime"),
    ),
    UniFiSensorDescription(
        key="load_avg_1m",
        translation_key="load_avg_1m",
        name="Load average (1 min)",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:gauge",
        value_fn=lambda hub: _gw(hub, "loadavg_1"),
    ),
    UniFiSensorDescription(
        key="load_avg_5m",
        translation_key="load_avg_5m",
        name="Load average (5 min)",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:gauge",
        value_fn=lambda hub: _gw(hub, "loadavg_5"),
    ),
    UniFiSensorDescription(
        key="load_avg_15m",
        translation_key="load_avg_15m",
        name="Load average (15 min)",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:gauge",
        value_fn=lambda hub: _gw(hub, "loadavg_15"),
    ),
    UniFiSensorDescription(
        key="connected_clients",
        translation_key="connected_clients",
        name="Connected clients",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:account-multiple",
        value_fn=lambda hub: _gw(hub, "num_sta"),
    ),
    UniFiSensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        name="Firmware version",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:package-up",
        value_fn=lambda hub: _gw(hub, "version"),
    ),
    UniFiSensorDescription(
        key="device_state",
        translation_key="device_state",
        name="Device state",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:information-outline",
        value_fn=lambda hub: _gw_state(hub),
    ),
    # ── Active WAN ──────────────────────────────────────────────────────
    UniFiSensorDescription(
        key="active_wan",
        translation_key="active_wan",
        name="Active WAN",
        icon="mdi:wan",
        value_fn=lambda hub: _gw(hub, "active_wan"),
    ),
    # ── Speedtest ───────────────────────────────────────────────────────
    UniFiSensorDescription(
        key="speedtest_download",
        translation_key="speedtest_download",
        name="Speedtest download",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:download-network",
        value_fn=lambda hub: _speedtest(hub, "download"),
    ),
    UniFiSensorDescription(
        key="speedtest_upload",
        translation_key="speedtest_upload",
        name="Speedtest upload",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:upload-network",
        value_fn=lambda hub: _speedtest(hub, "upload"),
    ),
    UniFiSensorDescription(
        key="speedtest_ping",
        translation_key="speedtest_ping",
        name="Speedtest ping",
        native_unit_of_measurement="ms",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:timer-outline",
        value_fn=lambda hub: _speedtest(hub, "latency"),
    ),
    UniFiSensorDescription(
        key="speedtest_last_run",
        translation_key="speedtest_last_run",
        name="Speedtest last run",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-check-outline",
        value_fn=lambda hub: _speedtest_run_date(hub),
    ),
    UniFiSensorDescription(
        key="speedtest_server",
        translation_key="speedtest_server",
        name="Speedtest server",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:server-network",
        value_fn=lambda hub: _speedtest(hub, "server_city"),
    ),
    # ── Health / WAN (from health coordinator) ──────────────────────────
    UniFiSensorDescription(
        key="isp_name",
        translation_key="isp_name",
        name="ISP name",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:web",
        value_fn=lambda hub: _health_wan(hub, "isp_name"),
        coordinator_key="health",
    ),
    UniFiSensorDescription(
        key="wan_latency",
        translation_key="wan_latency",
        name="WAN latency",
        native_unit_of_measurement="ms",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:timer-outline",
        value_fn=lambda hub: _health_wan(hub, "latency"),
        coordinator_key="health",
    ),
    # ── Fan / Memory ───────────────────────────────────────────────────
    UniFiSensorDescription(
        key="fan_level",
        translation_key="fan_level",
        name="Fan level",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda hub: _gw(hub, "fan_level"),
    ),
    UniFiSensorDescription(
        key="memory_total",
        translation_key="memory_total",
        name="Memory total",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda hub: _gw(hub, "mem_total"),
    ),
    UniFiSensorDescription(
        key="memory_used",
        translation_key="memory_used",
        name="Memory used",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda hub: _gw(hub, "mem_used"),
    ),
)


# ---------------------------------------------------------------------------
# Health subsystem sensors (coordinator_key="health")
# ---------------------------------------------------------------------------

HEALTH_SUBSYSTEM_SENSORS: tuple[UniFiSensorDescription, ...] = (
    # ── WLAN subsystem ─────────────────────────────────────────────────
    UniFiSensorDescription(
        key="wlan_clients",
        translation_key="wlan_clients",
        name="WLAN clients",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:wifi",
        value_fn=lambda hub: _health_sub(hub, "wlan", "num_user"),
        coordinator_key="health",
    ),
    UniFiSensorDescription(
        key="wlan_guests",
        translation_key="wlan_guests",
        name="WLAN guests",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:account-group-outline",
        value_fn=lambda hub: _health_sub(hub, "wlan", "num_guest"),
        coordinator_key="health",
    ),
    UniFiSensorDescription(
        key="wlan_iot_devices",
        translation_key="wlan_iot_devices",
        name="WLAN IoT devices",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:devices",
        value_fn=lambda hub: _health_sub(hub, "wlan", "num_iot"),
        coordinator_key="health",
    ),
    UniFiSensorDescription(
        key="wlan_throughput_rx",
        translation_key="wlan_throughput_rx",
        name="WLAN throughput RX",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:download-network",
        value_fn=lambda hub: _health_sub(hub, "wlan", "rx_bytes_r"),
        coordinator_key="health",
    ),
    UniFiSensorDescription(
        key="wlan_throughput_tx",
        translation_key="wlan_throughput_tx",
        name="WLAN throughput TX",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:upload-network",
        value_fn=lambda hub: _health_sub(hub, "wlan", "tx_bytes_r"),
        coordinator_key="health",
    ),
    UniFiSensorDescription(
        key="ap_count",
        translation_key="ap_count",
        name="Access point count",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:access-point",
        value_fn=lambda hub: _health_sub(hub, "wlan", "num_ap"),
        coordinator_key="health",
    ),
    # ── LAN subsystem ──────────────────────────────────────────────────
    UniFiSensorDescription(
        key="lan_clients",
        translation_key="lan_clients",
        name="LAN clients",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:ethernet",
        value_fn=lambda hub: _health_sub(hub, "lan", "num_user"),
        coordinator_key="health",
    ),
    UniFiSensorDescription(
        key="lan_guests",
        translation_key="lan_guests",
        name="LAN guests",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:account-group-outline",
        value_fn=lambda hub: _health_sub(hub, "lan", "num_guest"),
        coordinator_key="health",
    ),
    UniFiSensorDescription(
        key="switch_count",
        translation_key="switch_count",
        name="Switch count",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:switch",
        value_fn=lambda hub: _health_sub(hub, "lan", "num_sw"),
        coordinator_key="health",
    ),
    UniFiSensorDescription(
        key="lan_throughput_rx",
        translation_key="lan_throughput_rx",
        name="LAN throughput RX",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:download-network",
        value_fn=lambda hub: _health_sub(hub, "lan", "rx_bytes_r"),
        coordinator_key="health",
    ),
    UniFiSensorDescription(
        key="lan_throughput_tx",
        translation_key="lan_throughput_tx",
        name="LAN throughput TX",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:upload-network",
        value_fn=lambda hub: _health_sub(hub, "lan", "tx_bytes_r"),
        coordinator_key="health",
    ),
    # ── Device adoption counts (from WAN subsystem) ────────────────────
    UniFiSensorDescription(
        key="adopted_devices",
        name="Adopted devices",
        icon="mdi:devices",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda hub: _health_sub(hub, "wan", "num_adopted"),
        coordinator_key="health",
    ),
    UniFiSensorDescription(
        key="pending_devices",
        name="Pending devices",
        icon="mdi:clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda hub: _health_sub(hub, "wan", "num_pending"),
        coordinator_key="health",
    ),
    UniFiSensorDescription(
        key="disconnected_devices",
        name="Disconnected devices",
        icon="mdi:lan-disconnect",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda hub: _health_sub(hub, "wan", "num_disconnected"),
        coordinator_key="health",
    ),
)


# ---------------------------------------------------------------------------
# VPN sensors (coordinator_key="health", conditional on CONF_ENABLE_VPN)
# ---------------------------------------------------------------------------

VPN_SENSORS: tuple[UniFiSensorDescription, ...] = (
    UniFiSensorDescription(
        key="vpn_remote_users_active",
        translation_key="vpn_remote_users_active",
        name="VPN remote users active",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:vpn",
        value_fn=lambda hub: _health_sub(hub, "vpn", "remote_user_num_active"),
        coordinator_key="health",
    ),
    UniFiSensorDescription(
        key="vpn_remote_users_inactive",
        translation_key="vpn_remote_users_inactive",
        name="VPN remote users inactive",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:vpn",
        value_fn=lambda hub: _health_sub(hub, "vpn", "remote_user_num_inactive"),
        coordinator_key="health",
    ),
    UniFiSensorDescription(
        key="vpn_s2s_active",
        translation_key="vpn_s2s_active",
        name="VPN site-to-site active",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:vpn",
        value_fn=lambda hub: _health_sub(hub, "vpn", "site_to_site_num_active"),
        coordinator_key="health",
    ),
    UniFiSensorDescription(
        key="vpn_s2s_inactive",
        translation_key="vpn_s2s_inactive",
        name="VPN site-to-site inactive",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:vpn",
        value_fn=lambda hub: _health_sub(hub, "vpn", "site_to_site_num_inactive"),
        coordinator_key="health",
    ),
)


# ---------------------------------------------------------------------------
# Alarm sensors (coordinator_key="alarm", conditional on CONF_ENABLE_ALARMS)
# ---------------------------------------------------------------------------

ALARM_SENSORS: tuple[UniFiSensorDescription, ...] = (
    UniFiSensorDescription(
        key="alarm_count",
        translation_key="alarm_count",
        name="Alarm count",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:alert-circle",
        value_fn=lambda hub: (
            hub.alarm_coordinator.alarm_count
            if hub.alarm_coordinator else None
        ),
        coordinator_key="alarm",
    ),
    UniFiSensorDescription(
        key="latest_alarm",
        translation_key="latest_alarm",
        name="Latest alarm",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alert",
        value_fn=lambda hub: (
            hub.alarm_coordinator.latest_alarm.msg
            if hub.alarm_coordinator and hub.alarm_coordinator.latest_alarm
            else None
        ),
        coordinator_key="alarm",
    ),
)


# ---------------------------------------------------------------------------
# DPI sensors (coordinator_key="dpi", conditional on CONF_ENABLE_DPI)
# ---------------------------------------------------------------------------

DPI_SENSORS: tuple[UniFiSensorDescription, ...] = (
    UniFiSensorDescription(
        key="dpi_top_category",
        translation_key="dpi_top_category",
        name="DPI top category",
        icon="mdi:chart-bar",
        value_fn=lambda hub: (
            hub.dpi_coordinator.top_categories[0].cat
            if hub.dpi_coordinator and hub.dpi_coordinator.top_categories
            else None
        ),
        coordinator_key="dpi",
    ),
    UniFiSensorDescription(
        key="dpi_top_app",
        translation_key="dpi_top_app",
        name="DPI top app",
        icon="mdi:application",
        value_fn=lambda hub: (
            hub.dpi_coordinator.top_apps[0].app
            if hub.dpi_coordinator and hub.dpi_coordinator.top_apps
            else None
        ),
        coordinator_key="dpi",
    ),
    UniFiSensorDescription(
        key="dpi_total_rx",
        translation_key="dpi_total_rx",
        name="DPI total RX",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement="B",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        icon="mdi:download",
        value_fn=lambda hub: _dpi_total(hub, "rx_bytes"),
        coordinator_key="dpi",
    ),
    UniFiSensorDescription(
        key="dpi_total_tx",
        translation_key="dpi_total_tx",
        name="DPI total TX",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement="B",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        icon="mdi:upload",
        value_fn=lambda hub: _dpi_total(hub, "tx_bytes"),
        coordinator_key="dpi",
    ),
)


# ---------------------------------------------------------------------------
# ISP metrics sensors (coordinator_key="cloud", conditional on cloud)
# ---------------------------------------------------------------------------

ISP_METRICS_SENSORS: tuple[UniFiSensorDescription, ...] = (
    UniFiSensorDescription(
        key="isp_avg_latency",
        translation_key="isp_avg_latency",
        name="ISP average latency",
        native_unit_of_measurement="ms",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:timer-outline",
        value_fn=lambda hub: _isp_metric(hub, "avg_latency"),
        coordinator_key="cloud",
    ),
    UniFiSensorDescription(
        key="isp_max_latency",
        translation_key="isp_max_latency",
        name="ISP max latency",
        native_unit_of_measurement="ms",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:timer-alert-outline",
        value_fn=lambda hub: _isp_metric(hub, "max_latency"),
        coordinator_key="cloud",
    ),
    UniFiSensorDescription(
        key="isp_packet_loss",
        translation_key="isp_packet_loss",
        name="ISP packet loss",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:packet-loss",
        value_fn=lambda hub: _isp_metric(hub, "packet_loss"),
        coordinator_key="cloud",
    ),
    UniFiSensorDescription(
        key="isp_download",
        translation_key="isp_download",
        name="ISP download",
        native_unit_of_measurement="kbps",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:download-network",
        value_fn=lambda hub: _isp_metric(hub, "download_kbps"),
        coordinator_key="cloud",
    ),
    UniFiSensorDescription(
        key="isp_upload",
        translation_key="isp_upload",
        name="ISP upload",
        native_unit_of_measurement="kbps",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:upload-network",
        value_fn=lambda hub: _isp_metric(hub, "upload_kbps"),
        coordinator_key="cloud",
    ),
    UniFiSensorDescription(
        key="isp_uptime",
        translation_key="isp_uptime",
        name="ISP uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:clock-check-outline",
        value_fn=lambda hub: _isp_metric(hub, "uptime"),
        coordinator_key="cloud",
    ),
    UniFiSensorDescription(
        key="isp_downtime",
        translation_key="isp_downtime",
        name="ISP downtime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:clock-alert-outline",
        value_fn=lambda hub: _isp_metric(hub, "downtime"),
        coordinator_key="cloud",
    ),
)


# ---------------------------------------------------------------------------
# Value-extraction helpers
# ---------------------------------------------------------------------------

def _isp_metric(hub: UniFiHub, attr: str):
    """Read *attr* from the most recent ISP metrics entry."""
    if hub.cloud_coordinator is None:
        return None
    latest = hub.cloud_coordinator.latest_isp_metrics
    if latest is None:
        return None
    value = getattr(latest, attr, None)
    if value is None:
        return None
    return value

def _health_sub(hub: UniFiHub, subsystem: str, attr: str):
    """Read *attr* from a health subsystem."""
    if hub.health_coordinator is None:
        return None
    sub = hub.health_coordinator.subsystems.get(subsystem)
    if sub is None:
        return None
    value = getattr(sub, attr, None)
    if isinstance(value, str) and not value:
        return None
    return value


def _dpi_total(hub: UniFiHub, byte_attr: str):
    """Sum a byte attribute across all DPI categories."""
    if hub.dpi_coordinator is None or hub.dpi_coordinator.dpi_data is None:
        return None
    return sum(
        getattr(cat, byte_attr, 0)
        for cat in hub.dpi_coordinator.dpi_data.by_cat
    )


def _gateway_device(hub: UniFiHub):
    """Return the gateway ``Device`` from the device coordinator, or *None*."""
    if hub.device_coordinator is None:
        return None
    return hub.device_coordinator.devices.get(hub.gateway_mac)


def _gateway_device_wan_rate(hub: UniFiHub):
    """Return the gateway ``Device`` from the WAN-rate coordinator, or *None*."""
    if hub.wan_rate_coordinator is None:
        return None
    return hub.wan_rate_coordinator.gateway


def _gw(hub: UniFiHub, attr: str):
    """Safely read *attr* from the gateway device."""
    gw = _gateway_device(hub)
    if gw is None:
        return None
    return getattr(gw, attr, None)


def _gw_state(hub: UniFiHub):
    """Return the human-readable device state."""
    gw = _gateway_device(hub)
    if gw is None:
        return None
    return DeviceState.from_code(gw.state).value


def _speedtest(hub: UniFiHub, attr: str):
    """Read a speedtest attribute, converting bandwidth to Mbps when needed."""
    gw = _gateway_device(hub)
    if gw is None or gw.speedtest is None:
        return None
    value = getattr(gw.speedtest, attr, None)
    if value is None:
        return None
    # download/upload values come from the API in bits/s — convert to Mbps
    if attr in ("download", "upload") and isinstance(value, (int, float)):
        return round(value / 1_000_000, 2) if value > 1000 else value
    return value


def _speedtest_run_date(hub: UniFiHub):
    """Return the speedtest run date as a timezone-aware datetime."""
    gw = _gateway_device(hub)
    if gw is None or gw.speedtest is None:
        return None
    ts = gw.speedtest.run_date
    if not ts or ts <= 0:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=UTC)
    except (OSError, ValueError, OverflowError):
        return None


def _health_wan(hub: UniFiHub, attr: str):
    """Read an attribute from the ``wan`` health subsystem."""
    if hub.health_coordinator is None:
        return None
    wan = hub.health_coordinator.subsystems.get("wan")
    if wan is None:
        return None
    value = getattr(wan, attr, None)
    # Return None for empty strings so the sensor shows "unknown"
    if isinstance(value, str) and not value:
        return None
    return value


def _wan_iface_device(hub: UniFiHub, wan_name: str):
    """Return the WAN interface with *wan_name* from the device coordinator."""
    gw = _gateway_device(hub)
    if gw is None:
        return None
    for wi in gw.wan_interfaces:
        if wi.name == wan_name:
            return wi
    return None


def _wan_iface_rate(hub: UniFiHub, wan_name: str):
    """Return the WAN interface with *wan_name* from the WAN-rate coordinator."""
    gw = _gateway_device_wan_rate(hub)
    if gw is None:
        return None
    for wi in gw.wan_interfaces:
        if wi.name == wan_name:
            return wi
    return None


# ---------------------------------------------------------------------------
# Dynamic sensor factories (temperatures, storage, per-WAN interface)
# ---------------------------------------------------------------------------

def _make_temperature_sensor(temp_name: str) -> UniFiSensorDescription:
    """Create a sensor description for a specific temperature reading."""
    safe_key = temp_name.lower().replace(" ", "_").replace("-", "_")
    return UniFiSensorDescription(
        key=f"temperature_{safe_key}",
        name=f"Temperature {temp_name}",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda hub, _tn=temp_name: _temp_value(hub, _tn),
    )


def _temp_value(hub: UniFiHub, temp_name: str):
    """Return the value for a named temperature sensor."""
    gw = _gateway_device(hub)
    if gw is None:
        return None
    for t in gw.temperatures:
        if t.name == temp_name:
            return t.value
    return None


def _make_storage_sensor(storage_name: str) -> UniFiSensorDescription:
    """Create a sensor description for a storage device's usage percentage."""
    safe_key = storage_name.lower().replace(" ", "_").replace("/", "_").replace("-", "_")
    return UniFiSensorDescription(
        key=f"storage_{safe_key}_usage",
        name=f"Storage {storage_name} usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:harddisk",
        value_fn=lambda hub, _sn=storage_name: _storage_value(hub, _sn),
    )


def _storage_value(hub: UniFiHub, storage_name: str):
    """Return usage percentage for a named storage device."""
    gw = _gateway_device(hub)
    if gw is None:
        return None
    for s in gw.storage:
        if s.name == storage_name:
            if s.size > 0:
                return round((s.used / s.size) * 100, 1)
            return 0.0
    return None


def _make_wan_sensors(wan_name: str) -> list[UniFiSensorDescription]:
    """Create sensor descriptions for a single WAN interface."""
    safe_key = wan_name.lower().replace(" ", "_").replace("-", "_")
    label = wan_name.upper() if len(wan_name) <= 4 else wan_name.title()

    return [
        # IP address
        UniFiSensorDescription(
            key=f"{safe_key}_ip",
            name=f"{label} IP address",
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:ip-network",
            value_fn=lambda hub, _wn=wan_name: _wan_attr(hub, _wn, "ip"),
        ),
        # IPv6 address
        UniFiSensorDescription(
            key=f"{safe_key}_ip6",
            name=f"{label} IPv6 address",
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:ip-network",
            value_fn=lambda hub, _wn=wan_name: _wan_attr(hub, _wn, "ip6"),
        ),
        # Download rate (fast-poll from wan_rate coordinator)
        UniFiSensorDescription(
            key=f"{safe_key}_download_rate",
            name=f"{label} download rate",
            device_class=SensorDeviceClass.DATA_RATE,
            native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
            icon="mdi:download-network",
            value_fn=lambda hub, _wn=wan_name: _wan_rate_attr(hub, _wn, "rx_bytes_r"),
            coordinator_key="wan_rate",
        ),
        # Upload rate (fast-poll from wan_rate coordinator)
        UniFiSensorDescription(
            key=f"{safe_key}_upload_rate",
            name=f"{label} upload rate",
            device_class=SensorDeviceClass.DATA_RATE,
            native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
            icon="mdi:upload-network",
            value_fn=lambda hub, _wn=wan_name: _wan_rate_attr(hub, _wn, "tx_bytes_r"),
            coordinator_key="wan_rate",
        ),
        # Link speed
        UniFiSensorDescription(
            key=f"{safe_key}_link_speed",
            name=f"{label} link speed",
            device_class=SensorDeviceClass.DATA_RATE,
            native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:speedometer",
            value_fn=lambda hub, _wn=wan_name: _wan_attr(hub, _wn, "speed"),
        ),
        # Type (e.g. "ethernet", "sfp+")
        UniFiSensorDescription(
            key=f"{safe_key}_type",
            name=f"{label} type",
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:ethernet",
            value_fn=lambda hub, _wn=wan_name: _wan_attr(hub, _wn, "type"),
        ),
        # Latency
        UniFiSensorDescription(
            key=f"{safe_key}_latency",
            name=f"{label} latency",
            native_unit_of_measurement="ms",
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
            icon="mdi:timer-outline",
            value_fn=lambda hub, _wn=wan_name: _wan_attr(hub, _wn, "latency"),
        ),
        # Gateway IP
        UniFiSensorDescription(
            key=f"{safe_key}_gateway",
            name=f"{label} gateway",
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:router-network",
            value_fn=lambda hub, _wn=wan_name: _wan_attr(hub, _wn, "gateway"),
        ),
    ]


def _wan_attr(hub: UniFiHub, wan_name: str, attr: str):
    """Read *attr* from a WAN interface on the device coordinator gateway."""
    wi = _wan_iface_device(hub, wan_name)
    if wi is None:
        return None
    value = getattr(wi, attr, None)
    if isinstance(value, str) and not value:
        return None
    return value


def _wan_rate_attr(hub: UniFiHub, wan_name: str, attr: str):
    """Read *attr* from a WAN interface on the WAN-rate coordinator gateway."""
    wi = _wan_iface_rate(hub, wan_name)
    if wi is None:
        return None
    return getattr(wi, attr, None)


# ---------------------------------------------------------------------------
# VRRP / Shadow Mode sensor (conditional — only created when gateway has VRRP)
# ---------------------------------------------------------------------------

VRRP_SENSOR = UniFiSensorDescription(
    key="vrrp_state",
    name="VRRP state",
    icon="mdi:shield-sync",
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=lambda hub: _gw(hub, "vrrp_state") or None,
    coordinator_key="device",
)


# ---------------------------------------------------------------------------
# Per-client sensor helpers and factory
# ---------------------------------------------------------------------------

def _client_attr(hub: UniFiHub, mac: str, attr: str):
    """Read an attribute from a client."""
    if hub.client_coordinator is None:
        return None
    client = hub.client_coordinator.clients.get(mac)
    if client is None:
        return None
    value = getattr(client, attr, None)
    if value == 0 and attr in ("signal", "satisfaction"):
        return None  # 0 means not available for these
    return value


def _make_client_sensors(client_mac: str, client_name: str) -> list[UniFiSensorDescription]:
    """Create sensor descriptions for a single network client."""
    safe_mac = client_mac.replace(":", "_")

    return [
        UniFiSensorDescription(
            key=f"client_{safe_mac}_signal",
            name=f"{client_name} signal strength",
            native_unit_of_measurement="dBm",
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
            icon="mdi:wifi",
            value_fn=lambda hub, _m=client_mac: _client_attr(hub, _m, "signal"),
            coordinator_key="client",
        ),
        UniFiSensorDescription(
            key=f"client_{safe_mac}_rx_rate",
            name=f"{client_name} RX rate",
            native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
            device_class=SensorDeviceClass.DATA_RATE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
            value_fn=lambda hub, _m=client_mac: _client_attr(hub, _m, "rx_rate"),
            coordinator_key="client",
        ),
        UniFiSensorDescription(
            key=f"client_{safe_mac}_tx_rate",
            name=f"{client_name} TX rate",
            native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
            device_class=SensorDeviceClass.DATA_RATE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
            value_fn=lambda hub, _m=client_mac: _client_attr(hub, _m, "tx_rate"),
            coordinator_key="client",
        ),
        UniFiSensorDescription(
            key=f"client_{safe_mac}_rx_bandwidth",
            name=f"{client_name} download bandwidth",
            native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
            device_class=SensorDeviceClass.DATA_RATE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
            icon="mdi:download",
            value_fn=lambda hub, _m=client_mac: _client_attr(hub, _m, "rx_bytes_r"),
            coordinator_key="client",
        ),
        UniFiSensorDescription(
            key=f"client_{safe_mac}_tx_bandwidth",
            name=f"{client_name} upload bandwidth",
            native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
            device_class=SensorDeviceClass.DATA_RATE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
            icon="mdi:upload",
            value_fn=lambda hub, _m=client_mac: _client_attr(hub, _m, "tx_bytes_r"),
            coordinator_key="client",
        ),
        UniFiSensorDescription(
            key=f"client_{safe_mac}_satisfaction",
            name=f"{client_name} satisfaction",
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
            icon="mdi:emoticon-happy-outline",
            value_fn=lambda hub, _m=client_mac: _client_attr(hub, _m, "satisfaction"),
            coordinator_key="client",
        ),
        UniFiSensorDescription(
            key=f"client_{safe_mac}_uptime",
            name=f"{client_name} uptime",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            entity_registry_enabled_default=False,
            value_fn=lambda hub, _m=client_mac: _client_attr(hub, _m, "uptime"),
            coordinator_key="client",
        ),
    ]


# ---------------------------------------------------------------------------
# Per-AP radio sensor factories
# ---------------------------------------------------------------------------

def _get_device_radio(hub: UniFiHub, mac: str, radio_name: str):
    """Return the radio with *radio_name* on the device with *mac*."""
    if hub.device_coordinator is None:
        return None
    device = hub.device_coordinator.devices.get(mac)
    if device is None:
        return None
    for radio in device.radios:
        if radio.radio == radio_name:
            return radio
    return None


def _make_ap_radio_sensors(
    mac: str, radio_name: str
) -> list[UniFiSensorDescription]:
    """Create sensor descriptions for a single radio on an AP."""
    label = radio_name.upper().replace("NG", "2.4 GHz").replace("NA", "5 GHz").replace("6E", "6 GHz")
    prefix = f"radio_{radio_name}"

    return [
        UniFiSensorDescription(
            key=f"{prefix}_channel",
            translation_key="radio_channel",
            name=f"{label} channel",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:access-point",
            value_fn=lambda hub, _m=mac, _r=radio_name: (
                getattr(_get_device_radio(hub, _m, _r), "channel", None)
            ),
        ),
        UniFiSensorDescription(
            key=f"{prefix}_clients",
            translation_key="radio_clients",
            name=f"{label} clients",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:account-multiple-outline",
            value_fn=lambda hub, _m=mac, _r=radio_name: (
                getattr(_get_device_radio(hub, _m, _r), "num_sta", None)
            ),
        ),
        UniFiSensorDescription(
            key=f"{prefix}_channel_utilization",
            translation_key="radio_channel_utilization",
            name=f"{label} channel utilization",
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:chart-bar",
            value_fn=lambda hub, _m=mac, _r=radio_name: (
                getattr(_get_device_radio(hub, _m, _r), "cu_total", None)
            ),
        ),
        UniFiSensorDescription(
            key=f"{prefix}_tx_retries",
            translation_key="radio_tx_retries",
            name=f"{label} TX retries",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:refresh",
            value_fn=lambda hub, _m=mac, _r=radio_name: (
                getattr(_get_device_radio(hub, _m, _r), "tx_retries", None)
            ),
        ),
        UniFiSensorDescription(
            key=f"{prefix}_satisfaction",
            translation_key="radio_satisfaction",
            name=f"{label} satisfaction",
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:emoticon-happy-outline",
            value_fn=lambda hub, _m=mac, _r=radio_name: (
                getattr(_get_device_radio(hub, _m, _r), "satisfaction", None)
            ),
        ),
        UniFiSensorDescription(
            key=f"{prefix}_tx_power",
            translation_key="radio_tx_power",
            name=f"{label} TX power",
            native_unit_of_measurement="dBm",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:signal-variant",
            value_fn=lambda hub, _m=mac, _r=radio_name: (
                getattr(_get_device_radio(hub, _m, _r), "tx_power", None)
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Per-switch-port sensor factories
# ---------------------------------------------------------------------------

def _get_device_port(hub: UniFiHub, mac: str, port_idx: int):
    """Return the port with *port_idx* on the device with *mac*."""
    if hub.device_coordinator is None:
        return None
    device = hub.device_coordinator.devices.get(mac)
    if device is None:
        return None
    for port in device.ports:
        if port.idx == port_idx:
            return port
    return None


def _make_switch_port_sensors(
    mac: str, port: "DevicePort"
) -> list[UniFiSensorDescription]:
    """Create sensor descriptions for a single port on a switch."""
    idx = port.idx
    port_label = port.name or f"Port {idx}"
    prefix = f"port_{idx}"

    sensors: list[UniFiSensorDescription] = [
        UniFiSensorDescription(
            key=f"{prefix}_rx_rate",
            translation_key="port_rx_rate",
            name=f"{port_label} RX rate",
            device_class=SensorDeviceClass.DATA_RATE,
            native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
            icon="mdi:download-network",
            value_fn=lambda hub, _m=mac, _i=idx: (
                getattr(_get_device_port(hub, _m, _i), "rx_bytes_r", None)
            ),
        ),
        UniFiSensorDescription(
            key=f"{prefix}_tx_rate",
            translation_key="port_tx_rate",
            name=f"{port_label} TX rate",
            device_class=SensorDeviceClass.DATA_RATE,
            native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
            icon="mdi:upload-network",
            value_fn=lambda hub, _m=mac, _i=idx: (
                getattr(_get_device_port(hub, _m, _i), "tx_bytes_r", None)
            ),
        ),
        UniFiSensorDescription(
            key=f"{prefix}_speed",
            translation_key="port_speed",
            name=f"{port_label} speed",
            device_class=SensorDeviceClass.DATA_RATE,
            native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:speedometer",
            value_fn=lambda hub, _m=mac, _i=idx: (
                getattr(_get_device_port(hub, _m, _i), "speed", None)
            ),
        ),
    ]

    # PoE power sensor — only if the port is PoE-capable.
    if port.poe_enable or port.poe_mode:
        sensors.append(
            UniFiSensorDescription(
                key=f"{prefix}_poe_power",
                translation_key="port_poe_power",
                name=f"{port_label} PoE power",
                device_class=SensorDeviceClass.POWER,
                native_unit_of_measurement="W",
                state_class=SensorStateClass.MEASUREMENT,
                suggested_display_precision=1,
                icon="mdi:flash",
                value_fn=lambda hub, _m=mac, _i=idx: (
                    getattr(_get_device_port(hub, _m, _i), "poe_power", None)
                ),
            )
        )

    # STP state — diagnostic string sensor.
    sensors.append(
        UniFiSensorDescription(
            key=f"{prefix}_stp_state",
            translation_key="port_stp_state",
            name=f"{port_label} STP state",
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:transit-connection-variant",
            value_fn=lambda hub, _m=mac, _i=idx: (
                getattr(_get_device_port(hub, _m, _i), "stp_state", None) or None
            ),
        )
    )

    # SFP temperature — only if port has an SFP module inserted.
    if port.sfp_found:
        sensors.append(
            UniFiSensorDescription(
                key=f"{prefix}_sfp_temperature",
                translation_key="port_sfp_temperature",
                name=f"{port_label} SFP temperature",
                device_class=SensorDeviceClass.TEMPERATURE,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                state_class=SensorStateClass.MEASUREMENT,
                suggested_display_precision=1,
                icon="mdi:thermometer",
                value_fn=lambda hub, _m=mac, _i=idx: (
                    getattr(_get_device_port(hub, _m, _i), "sfp_temperature", None)
                ),
            )
        )

    return sensors


# ---------------------------------------------------------------------------
# Sensor entity
# ---------------------------------------------------------------------------

class UniFiSensorEntity(UniFiEntity, SensorEntity):
    """Sensor entity for UniFi Network HA."""

    entity_description: UniFiSensorDescription

    @property
    def native_value(self) -> Any:
        """Return the current sensor value."""
        try:
            return self.entity_description.value_fn(self._hub)
        except Exception:  # noqa: BLE001 — never let a bad value crash HA
            _LOGGER.debug(
                "Error reading value for sensor %s",
                self.entity_description.key,
                exc_info=True,
            )
            return None


class UniFiClientSensorEntity(UniFiSensorEntity):
    """Sensor entity that belongs to a client device (uses CONNECTION_NETWORK_MAC)."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info using CONNECTION_NETWORK_MAC to match the device_tracker device."""
        client = None
        if self._hub.client_coordinator:
            client = self._hub.client_coordinator.all_known.get(self._device_mac)
        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self._device_mac)},
            name=self._device_name,
            manufacturer=client.oui if client else None,
        )


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    entry: UniFiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UniFi Network HA sensor entities."""
    hub: UniFiHub = entry.runtime_data
    entities: list[UniFiSensorEntity] = []

    # We need a gateway to create any sensors in this phase.
    if not hub.gateway_mac or hub.device_coordinator is None:
        _LOGGER.debug("No gateway or device coordinator — skipping sensor setup")
        return

    gateway = hub.device_coordinator.devices.get(hub.gateway_mac)
    if gateway is None:
        _LOGGER.debug("Gateway MAC %s not found in devices", hub.gateway_mac)
        return

    gw_name = gateway.name or "Gateway"
    gw_model = gateway.model_name or gateway.model or "UniFi Gateway"

    # ── Static gateway sensors ──────────────────────────────────────────
    for desc in GATEWAY_SENSORS:
        coordinator = _get_coordinator(hub, desc.coordinator_key)
        entities.append(
            UniFiSensorEntity(
                coordinator=coordinator,
                description=desc,
                hub=hub,
                mac=hub.gateway_mac,
                device_name=gw_name,
                device_model=gw_model,
            )
        )

    # ── Dynamic temperature sensors ─────────────────────────────────────
    for temp in gateway.temperatures:
        if not temp.name:
            continue
        desc = _make_temperature_sensor(temp.name)
        entities.append(
            UniFiSensorEntity(
                coordinator=hub.device_coordinator,
                description=desc,
                hub=hub,
                mac=hub.gateway_mac,
                device_name=gw_name,
                device_model=gw_model,
            )
        )

    # ── Dynamic storage sensors ─────────────────────────────────────────
    for storage in gateway.storage:
        if not storage.name:
            continue
        desc = _make_storage_sensor(storage.name)
        entities.append(
            UniFiSensorEntity(
                coordinator=hub.device_coordinator,
                description=desc,
                hub=hub,
                mac=hub.gateway_mac,
                device_name=gw_name,
                device_model=gw_model,
            )
        )

    # ── Dynamic per-WAN-interface sensors ───────────────────────────────
    for wan in gateway.wan_interfaces:
        if not wan.name:
            continue
        for desc in _make_wan_sensors(wan.name):
            coordinator = _get_coordinator(hub, desc.coordinator_key)
            entities.append(
                UniFiSensorEntity(
                    coordinator=coordinator,
                    description=desc,
                    hub=hub,
                    mac=hub.gateway_mac,
                    device_name=gw_name,
                    device_model=gw_model,
                )
            )

    # ── Health subsystem sensors ───────────────────────────────────────
    if hub.health_coordinator is not None:
        for desc in HEALTH_SUBSYSTEM_SENSORS:
            coordinator = _get_coordinator(hub, desc.coordinator_key)
            entities.append(
                UniFiSensorEntity(
                    coordinator=coordinator,
                    description=desc,
                    hub=hub,
                    mac=hub.gateway_mac,
                    device_name=gw_name,
                    device_model=gw_model,
                )
            )

    # ── VPN sensors ────────────────────────────────────────────────────
    if hub.get_option(CONF_ENABLE_VPN, True) and hub.health_coordinator is not None:
        for desc in VPN_SENSORS:
            coordinator = _get_coordinator(hub, desc.coordinator_key)
            entities.append(
                UniFiSensorEntity(
                    coordinator=coordinator,
                    description=desc,
                    hub=hub,
                    mac=hub.gateway_mac,
                    device_name=gw_name,
                    device_model=gw_model,
                )
            )

    # ── Alarm sensors ──────────────────────────────────────────────────
    if hub.get_option(CONF_ENABLE_ALARMS, True) and hub.alarm_coordinator is not None:
        for desc in ALARM_SENSORS:
            coordinator = _get_coordinator(hub, desc.coordinator_key)
            entities.append(
                UniFiSensorEntity(
                    coordinator=coordinator,
                    description=desc,
                    hub=hub,
                    mac=hub.gateway_mac,
                    device_name=gw_name,
                    device_model=gw_model,
                )
            )

    # ── DPI sensors ────────────────────────────────────────────────────
    if hub.get_option(CONF_ENABLE_DPI, False) and hub.dpi_coordinator is not None:
        for desc in DPI_SENSORS:
            coordinator = _get_coordinator(hub, desc.coordinator_key)
            entities.append(
                UniFiSensorEntity(
                    coordinator=coordinator,
                    description=desc,
                    hub=hub,
                    mac=hub.gateway_mac,
                    device_name=gw_name,
                    device_model=gw_model,
                )
            )

    # ── ISP metrics sensors (cloud) ───────────────────────────────────
    if hub.cloud_coordinator is not None and hub.get_option(CONF_ENABLE_CLOUD, True):
        for desc in ISP_METRICS_SENSORS:
            coordinator = _get_coordinator(hub, desc.coordinator_key)
            entities.append(
                UniFiSensorEntity(
                    coordinator=coordinator,
                    description=desc,
                    hub=hub,
                    mac=hub.gateway_mac,
                    device_name=gw_name,
                    device_model=gw_model,
                )
            )

    # ── VRRP state sensor (conditional on gateway having VRRP) ────────
    if gateway.vrrp_enabled or gateway.vrrp_state:
        coordinator = _get_coordinator(hub, VRRP_SENSOR.coordinator_key)
        entities.append(
            UniFiSensorEntity(
                coordinator=coordinator,
                description=VRRP_SENSOR,
                hub=hub,
                mac=hub.gateway_mac,
                device_name=gw_name,
                device_model=gw_model,
            )
        )

    # ── Per-client sensors (gated behind CONF_ENABLE_PER_CLIENT_SENSORS) ──
    if hub.get_option(CONF_ENABLE_PER_CLIENT_SENSORS, False) and hub.client_coordinator:
        for mac, client in hub.client_coordinator.clients.items():
            client_name = client.name or client.hostname or mac
            for desc in _make_client_sensors(mac, client_name):
                coordinator = _get_coordinator(hub, desc.coordinator_key)
                if coordinator is None:
                    continue
                entities.append(
                    UniFiClientSensorEntity(
                        coordinator=coordinator,
                        description=desc,
                        hub=hub,
                        mac=mac,
                        device_name=client_name,
                        device_model=client.oui or "Network Client",
                    )
                )

    # ── Per-AP radio sensors ──────────────────────────────────────────
    if hub.get_option(CONF_ENABLE_DEVICE_SENSORS, True):
        for mac, device in hub.device_coordinator.devices.items():
            if device.type != "uap":
                continue
            dev_name = device.name or f"AP {mac}"
            dev_model = device.model_name or device.model or "UniFi AP"
            for radio in device.radios:
                if not radio.radio:
                    continue
                for desc in _make_ap_radio_sensors(mac, radio.radio):
                    entities.append(
                        UniFiSensorEntity(
                            coordinator=hub.device_coordinator,
                            description=desc,
                            hub=hub,
                            mac=mac,
                            device_name=dev_name,
                            device_model=dev_model,
                        )
                    )

    # ── Per-switch-port sensors ────────────────────────────────────────
    if hub.get_option(CONF_ENABLE_DEVICE_SENSORS, True):
        for mac, device in hub.device_coordinator.devices.items():
            if device.type != "usw":
                continue
            dev_name = device.name or f"Switch {mac}"
            dev_model = device.model_name or device.model or "UniFi Switch"
            for port in device.ports:
                if port.idx <= 0:
                    continue
                for desc in _make_switch_port_sensors(mac, port):
                    entities.append(
                        UniFiSensorEntity(
                            coordinator=hub.device_coordinator,
                            description=desc,
                            hub=hub,
                            mac=mac,
                            device_name=dev_name,
                            device_model=dev_model,
                        )
                    )

    _LOGGER.debug(
        "Setting up %d sensor entities for gateway %s", len(entities), gw_name
    )
    async_add_entities(entities)
