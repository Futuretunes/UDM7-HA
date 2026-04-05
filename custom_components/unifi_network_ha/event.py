"""UniFi Network HA event platform.

Provides event entities that fire on:
- WAN failover / recovery (active WAN interface changes)
- IPS/IDS alerts (new alarm events from the alarm coordinator)
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from homeassistant.components.event import EventDeviceClass, EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENABLE_ALARMS, DOMAIN, MANUFACTURER
from .coordinators.alarm import AlarmCoordinator
from .entity import UniFiEntity
from .hub import UniFiHub

# Type alias used in __init__.py — import so the platform signature matches.
from . import UniFiConfigEntry

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WAN Failover event entity
# ---------------------------------------------------------------------------

class WanFailoverEvent(UniFiEntity, EventEntity):
    """Event entity that fires when the active WAN interface changes."""

    _attr_event_types = ["failover", "recovery", "wan_change"]
    _attr_device_class = EventDeviceClass.BUTTON  # closest available

    def __init__(self, coordinator, hub, mac, device_name, device_model):
        desc = EventEntityDescription(key="wan_failover", name="WAN Failover")
        super().__init__(coordinator, desc, hub, mac, device_name, device_model)
        self._previous_wan: str | None = None

    def _handle_coordinator_update(self) -> None:
        """Check for WAN failover on each coordinator update."""
        super()._handle_coordinator_update()

        gw = self._hub.device_coordinator.devices.get(self._device_mac)
        if not gw:
            return

        current_wan = gw.active_wan
        if current_wan is None:
            return

        if self._previous_wan is not None and current_wan != self._previous_wan:
            # Determine event type
            if self._previous_wan == "wan" and current_wan != "wan":
                event_type = "failover"
            elif current_wan == "wan":
                event_type = "recovery"
            else:
                event_type = "wan_change"

            self._trigger_event(
                event_type,
                {
                    "previous_wan": self._previous_wan,
                    "new_wan": current_wan,
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                },
            )
            _LOGGER.info(
                "WAN %s detected: %s -> %s",
                event_type,
                self._previous_wan,
                current_wan,
            )

        self._previous_wan = current_wan


# ---------------------------------------------------------------------------
# IPS Alert event entity
# ---------------------------------------------------------------------------

class IpsAlertEvent(CoordinatorEntity[AlarmCoordinator], EventEntity):
    """Event entity that fires on new IPS/IDS alerts."""

    _attr_event_types = ["ips_alert", "threat_detected", "intrusion_attempt"]
    _attr_has_entity_name = True
    _attr_icon = "mdi:shield-alert"

    def __init__(
        self,
        coordinator: AlarmCoordinator,
        hub: UniFiHub,
        mac: str,
        device_name: str,
        device_model: str,
    ) -> None:
        super().__init__(coordinator)
        self._hub = hub
        self._device_mac = mac
        self._device_name = device_name
        self._device_model = device_model
        self._attr_unique_id = f"{mac}_ips_alerts"
        self._attr_name = "IPS Alert"
        self._last_alarm_id: str | None = None

    def _handle_coordinator_update(self) -> None:
        """Check for new IPS alerts on each coordinator update."""
        super()._handle_coordinator_update()

        coordinator = self._hub.alarm_coordinator
        if not coordinator or not coordinator.latest_alarm:
            return

        alarm = coordinator.latest_alarm
        if alarm.id == self._last_alarm_id:
            return

        self._last_alarm_id = alarm.id

        # Determine event type based on alarm key and message
        if alarm.key.startswith("EVT_IPS"):
            event_type = "ips_alert"
        elif "threat" in alarm.msg.lower():
            event_type = "threat_detected"
        else:
            event_type = "intrusion_attempt"

        self._trigger_event(
            event_type,
            {
                "message": alarm.msg,
                "category": alarm.catname,
                "source_ip": alarm.src_ip,
                "source_port": alarm.src_port,
                "dest_ip": alarm.dest_ip,
                "dest_port": alarm.dest_port,
                "protocol": alarm.proto,
                "action": alarm.inner_alert_action,
                "severity": alarm.inner_alert_severity,
                "signature": alarm.inner_alert_signature,
            },
        )

        _LOGGER.info(
            "IPS alert event fired: %s (type=%s, src=%s:%s -> dst=%s:%s)",
            alarm.msg,
            event_type,
            alarm.src_ip,
            alarm.src_port,
            alarm.dest_ip,
            alarm.dest_port,
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_mac)},
            name=self._device_name,
            manufacturer=MANUFACTURER,
            model=self._device_model,
        )


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    entry: UniFiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UniFi Network HA event entities."""
    hub: UniFiHub = entry.runtime_data
    entities: list[EventEntity] = []

    # We need a gateway and the device coordinator.
    if not hub.gateway_mac or hub.device_coordinator is None:
        _LOGGER.debug("No gateway or device coordinator — skipping event setup")
        return

    gateway = hub.device_coordinator.devices.get(hub.gateway_mac)
    if gateway is None:
        _LOGGER.debug("Gateway MAC %s not found in devices", hub.gateway_mac)
        return

    gw_name = gateway.name or "Gateway"
    gw_model = gateway.model_name or gateway.model or "UniFi Gateway"

    # Only add the failover event if the gateway reports an active WAN.
    if gateway.active_wan is not None:
        entities.append(
            WanFailoverEvent(
                coordinator=hub.device_coordinator,
                hub=hub,
                mac=hub.gateway_mac,
                device_name=gw_name,
                device_model=gw_model,
            )
        )

    # IPS alert event (conditional on alarm coordinator being enabled)
    if hub.get_option(CONF_ENABLE_ALARMS, True) and hub.alarm_coordinator is not None:
        entities.append(
            IpsAlertEvent(
                coordinator=hub.alarm_coordinator,
                hub=hub,
                mac=hub.gateway_mac,
                device_name=gw_name,
                device_model=gw_model,
            )
        )

    _LOGGER.debug(
        "Setting up %d event entities for gateway %s", len(entities), gw_name
    )
    async_add_entities(entities)
