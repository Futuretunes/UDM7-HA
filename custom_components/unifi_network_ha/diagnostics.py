"""Diagnostics for UniFi Network HA."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_API_KEY, CONF_PASSWORD, CONF_CLOUD_API_KEY, CONF_USERNAME

REDACT_KEYS = {CONF_API_KEY, CONF_PASSWORD, CONF_CLOUD_API_KEY, CONF_USERNAME, "x_passphrase"}
REDACT_MAC = True


def _redact_mac(data: Any) -> Any:
    """Redact MAC addresses from diagnostic data."""
    if isinstance(data, str) and len(data) == 17 and data.count(":") == 5:
        return f"{data[:8]}:XX:XX:XX"
    if isinstance(data, dict):
        return {k: _redact_mac(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_redact_mac(v) for v in data]
    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hub = entry.runtime_data

    data: dict[str, Any] = {
        "config": async_redact_data(dict(entry.data), REDACT_KEYS),
        "options": async_redact_data(dict(entry.options), REDACT_KEYS),
    }

    # Gateway info
    if hub.device_coordinator and hub.device_coordinator.devices:
        gw = hub.device_coordinator.devices.get(hub.gateway_mac)
        if gw:
            data["gateway"] = {
                "model": gw.model,
                "model_name": gw.model_name,
                "version": gw.version,
                "uptime": gw.uptime,
                "cpu": gw.cpu_usage,
                "mem": gw.mem_usage,
                "wan_count": len(gw.wan_interfaces),
                "active_wan": gw.active_wan,
                "internet": gw.internet,
            }

    # Coordinator states
    data["coordinators"] = {}
    for name, coord in [
        ("devices", hub.device_coordinator),
        ("clients", hub.client_coordinator),
        ("health", hub.health_coordinator),
        ("wan_rate", hub.wan_rate_coordinator),
        ("alarms", hub.alarm_coordinator),
        ("dpi", hub.dpi_coordinator),
        ("cloud", hub.cloud_coordinator),
    ]:
        if coord:
            data["coordinators"][name] = {
                "last_update": str(coord.last_update_success_time),
                "update_interval": str(coord.update_interval),
                "data_available": coord.data is not None,
            }

    # Device counts
    if hub.device_coordinator:
        data["device_count"] = len(hub.device_coordinator.devices)
    if hub.client_coordinator:
        data["client_count"] = len(hub.client_coordinator.clients)

    # WebSocket state
    if hub.websocket:
        data["websocket"] = {
            "state": hub.websocket.state.value if hub.websocket.state else "unknown",
        }

    return _redact_mac(data) if REDACT_MAC else data
