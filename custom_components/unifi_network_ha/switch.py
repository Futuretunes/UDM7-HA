"""UniFi Network HA switch platform.

Provides toggle switches for:
- Client block/unblock (one per tracked client)
- WLAN enable/disable (one per WLAN)
- PoE port enable/disable (per PoE-capable port on switches)
- Port enable/disable (per port on switches, excluding uplinks)
- Port forward enable/disable (one per port-forward rule)
- Traffic rule enable/disable (one per traffic rule)
- Firewall policy enable/disable (one per firewall policy)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.models import Client, FirewallPolicy, PortForward, TrafficRule, Wlan
from .const import (
    CONF_ENABLE_DPI,
    CONF_TRACK_CLIENTS,
    DEFAULT_TRACK_CLIENTS,
    DOMAIN,
    MANUFACTURER,
)
from .coordinators.base import UniFiDataUpdateCoordinator
from .coordinators.client import ClientCoordinator
from .entity import UniFiEntity

if TYPE_CHECKING:
    from .hub import UniFiHub

_LOGGER = logging.getLogger(__name__)


# ===========================================================================
# Client block switch (Phase 3)
# ===========================================================================


class UniFiBlockClientSwitch(CoordinatorEntity[ClientCoordinator], SwitchEntity):
    """Switch to block / unblock a network client."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:block-helper"

    def __init__(
        self,
        coordinator: ClientCoordinator,
        hub: UniFiHub,
        client: Client,
    ) -> None:
        super().__init__(coordinator)
        self._hub = hub
        self._client_mac = client.mac
        self._attr_unique_id = f"{client.mac}_blocked"
        self._attr_name = "Blocked"

    # -- State -------------------------------------------------------------

    @property
    def is_on(self) -> bool:
        """Return True when the client is blocked."""
        client = self._hub.client_coordinator.all_known.get(self._client_mac)
        return client.blocked if client else False

    # -- Commands ----------------------------------------------------------

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Block the client."""
        _LOGGER.info("Blocking client %s", self._client_mac)
        await self._hub.legacy.block_client(self._client_mac)
        await self._hub.client_coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unblock the client."""
        _LOGGER.info("Unblocking client %s", self._client_mac)
        await self._hub.legacy.unblock_client(self._client_mac)
        await self._hub.client_coordinator.async_request_refresh()

    # -- Device registry ---------------------------------------------------

    @property
    def device_info(self) -> DeviceInfo:
        """Associate the switch with the client's HA device."""
        client = self._hub.client_coordinator.all_known.get(self._client_mac)
        name = "Unknown"
        if client:
            name = client.name or client.hostname or client.mac
        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self._client_mac)},
            name=name,
            manufacturer=client.oui if client and client.oui else None,
            default_name=self._client_mac,
        )


# ===========================================================================
# WLAN enable/disable switch (Phase 4)
# ===========================================================================


class UniFiWlanSwitch(CoordinatorEntity[UniFiDataUpdateCoordinator], SwitchEntity):
    """Switch to enable / disable a WLAN."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:wifi"

    def __init__(
        self,
        coordinator: UniFiDataUpdateCoordinator,
        hub: UniFiHub,
        wlan: Wlan,
    ) -> None:
        super().__init__(coordinator)
        self._hub = hub
        self._wlan_id = wlan.id
        safe_key = wlan.name.lower().replace(" ", "_").replace("-", "_")
        self._attr_unique_id = f"wlan_{wlan.id}_{safe_key}_enabled"
        self._attr_name = f"WLAN {wlan.name}"

    @property
    def device_info(self) -> DeviceInfo:
        """Place WLAN switches under the gateway device."""
        gw = self._hub.device_coordinator.devices.get(self._hub.gateway_mac) if self._hub.device_coordinator else None
        gw_name = gw.name if gw and gw.name else "UniFi Controller"
        gw_model = (gw.model_name or gw.model or "UniFi Gateway") if gw else "UniFi Gateway"
        return DeviceInfo(
            identifiers={(DOMAIN, self._hub.gateway_mac or "controller")},
            name=gw_name,
            manufacturer=MANUFACTURER,
            model=gw_model,
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether the WLAN is enabled."""
        cache: dict[str, Wlan] | None = getattr(self._hub, "_wlan_cache", None)
        if cache is None:
            return None
        wlan = cache.get(self._wlan_id)
        if wlan is None:
            return None
        return wlan.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the WLAN."""
        _LOGGER.info("Enabling WLAN %s", self._wlan_id)
        await self._hub.legacy.set_wlan(self._wlan_id, {"enabled": True})
        self._update_wlan_cache(enabled=True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the WLAN."""
        _LOGGER.info("Disabling WLAN %s", self._wlan_id)
        await self._hub.legacy.set_wlan(self._wlan_id, {"enabled": False})
        self._update_wlan_cache(enabled=False)
        self.async_write_ha_state()

    def _update_wlan_cache(self, enabled: bool) -> None:
        """Optimistically update the hub WLAN cache."""
        cache: dict[str, Wlan] | None = getattr(self._hub, "_wlan_cache", None)
        if cache is not None and self._wlan_id in cache:
            old = cache[self._wlan_id]
            cache[self._wlan_id] = Wlan(
                id=old.id, name=old.name, enabled=enabled,
                security=old.security, wpa_mode=old.wpa_mode,
                x_passphrase=old.x_passphrase, is_guest=old.is_guest,
                raw=old.raw,
            )


# ===========================================================================
# PoE port switch (Phase 4)
# ===========================================================================


class UniFiPoEPortSwitch(UniFiEntity, SwitchEntity):
    """Switch to toggle PoE on a switch port."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:flash"

    def __init__(
        self,
        coordinator: UniFiDataUpdateCoordinator,
        hub: UniFiHub,
        mac: str,
        device_name: str,
        device_model: str,
        port_idx: int,
        port_name: str,
        device_id: str,
    ) -> None:
        from homeassistant.helpers.entity import EntityDescription

        desc = EntityDescription(key=f"port_{port_idx}_poe")
        super().__init__(coordinator, desc, hub, mac, device_name, device_model)
        self._port_idx = port_idx
        self._device_id = device_id
        self._attr_name = f"{port_name} PoE"

    @property
    def is_on(self) -> bool | None:
        """Return whether PoE is enabled on this port."""
        if self._hub.device_coordinator is None:
            return None
        device = self._hub.device_coordinator.devices.get(self._device_mac)
        if device is None:
            return None
        for port in device.ports:
            if port.idx == self._port_idx:
                return port.poe_enable
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable PoE on this port."""
        _LOGGER.info("Enabling PoE on %s port %d", self._device_mac, self._port_idx)
        await self._hub.legacy.set_device(
            self._device_id,
            {"port_overrides": [{"port_idx": self._port_idx, "poe_mode": "auto"}]},
        )
        await self._hub.device_coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable PoE on this port."""
        _LOGGER.info("Disabling PoE on %s port %d", self._device_mac, self._port_idx)
        await self._hub.legacy.set_device(
            self._device_id,
            {"port_overrides": [{"port_idx": self._port_idx, "poe_mode": "off"}]},
        )
        await self._hub.device_coordinator.async_request_refresh()


# ===========================================================================
# Port enable switch (Phase 4)
# ===========================================================================


class UniFiPortEnableSwitch(UniFiEntity, SwitchEntity):
    """Switch to enable / disable a switch port."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:ethernet"

    def __init__(
        self,
        coordinator: UniFiDataUpdateCoordinator,
        hub: UniFiHub,
        mac: str,
        device_name: str,
        device_model: str,
        port_idx: int,
        port_name: str,
        device_id: str,
    ) -> None:
        from homeassistant.helpers.entity import EntityDescription

        desc = EntityDescription(key=f"port_{port_idx}_enabled")
        super().__init__(coordinator, desc, hub, mac, device_name, device_model)
        self._port_idx = port_idx
        self._device_id = device_id
        self._attr_name = f"{port_name} enabled"

    @property
    def is_on(self) -> bool | None:
        """Return whether the port is up (enabled)."""
        if self._hub.device_coordinator is None:
            return None
        device = self._hub.device_coordinator.devices.get(self._device_mac)
        if device is None:
            return None
        for port in device.ports:
            if port.idx == self._port_idx:
                return port.up
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the port."""
        _LOGGER.info("Enabling port %d on %s", self._port_idx, self._device_mac)
        await self._hub.legacy.set_device(
            self._device_id,
            {"port_overrides": [{"port_idx": self._port_idx, "port_security_enabled": False}]},
        )
        await self._hub.device_coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the port."""
        _LOGGER.info("Disabling port %d on %s", self._port_idx, self._device_mac)
        await self._hub.legacy.set_device(
            self._device_id,
            {"port_overrides": [{"port_idx": self._port_idx, "port_security_enabled": True}]},
        )
        await self._hub.device_coordinator.async_request_refresh()


# ===========================================================================
# DPI restriction group switch (Phase 5)
# ===========================================================================


class UniFiDpiRestrictionSwitch(CoordinatorEntity[UniFiDataUpdateCoordinator], SwitchEntity):
    """Switch to enable / disable a DPI restriction group."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:filter-variant"

    def __init__(
        self,
        coordinator: UniFiDataUpdateCoordinator,
        hub: UniFiHub,
        group_id: str,
        group_name: str,
        enabled: bool,
    ) -> None:
        super().__init__(coordinator)
        self._hub = hub
        self._group_id = group_id
        safe_key = group_name.lower().replace(" ", "_").replace("-", "_")
        self._attr_unique_id = f"dpi_group_{group_id}_{safe_key}"
        self._attr_name = f"DPI {group_name}"
        self._is_enabled = enabled

    @property
    def device_info(self) -> DeviceInfo:
        """Place DPI switches under the gateway device."""
        gw = (
            self._hub.device_coordinator.devices.get(self._hub.gateway_mac)
            if self._hub.device_coordinator
            else None
        )
        gw_name = gw.name if gw and gw.name else "UniFi Controller"
        gw_model = (
            (gw.model_name or gw.model or "UniFi Gateway") if gw else "UniFi Gateway"
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self._hub.gateway_mac or "controller")},
            name=gw_name,
            manufacturer=MANUFACTURER,
            model=gw_model,
        )

    @property
    def is_on(self) -> bool:
        """Return whether the DPI restriction group is enabled."""
        # Check the hub DPI group cache if available
        cache: dict[str, dict] | None = getattr(self._hub, "_dpi_group_cache", None)
        if cache is not None and self._group_id in cache:
            return cache[self._group_id].get("enabled", self._is_enabled)
        return self._is_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the DPI restriction group."""
        _LOGGER.info("Enabling DPI group %s", self._group_id)
        await self._hub.legacy.set_dpi_group(self._group_id, {"enabled": True})
        self._is_enabled = True
        self._update_cache(enabled=True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the DPI restriction group."""
        _LOGGER.info("Disabling DPI group %s", self._group_id)
        await self._hub.legacy.set_dpi_group(self._group_id, {"enabled": False})
        self._is_enabled = False
        self._update_cache(enabled=False)
        self.async_write_ha_state()

    def _update_cache(self, enabled: bool) -> None:
        """Optimistically update the hub DPI group cache."""
        cache: dict[str, dict] | None = getattr(self._hub, "_dpi_group_cache", None)
        if cache is not None and self._group_id in cache:
            cache[self._group_id]["enabled"] = enabled


# ===========================================================================
# Port forward switch (Phase 6)
# ===========================================================================


class UniFiPortForwardSwitch(CoordinatorEntity[UniFiDataUpdateCoordinator], SwitchEntity):
    """Switch to enable / disable a port-forwarding rule."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:arrow-decision"

    def __init__(
        self,
        coordinator: UniFiDataUpdateCoordinator,
        hub: UniFiHub,
        pf: PortForward,
    ) -> None:
        super().__init__(coordinator)
        self._hub = hub
        self._pf_id = pf.id
        self._attr_unique_id = f"portfwd_{pf.id}"
        self._attr_name = f"Port Forward {pf.name}"

    @property
    def device_info(self) -> DeviceInfo:
        """Place port-forward switches under the gateway device."""
        gw = (
            self._hub.device_coordinator.devices.get(self._hub.gateway_mac)
            if self._hub.device_coordinator
            else None
        )
        gw_name = gw.name if gw and gw.name else "UniFi Controller"
        gw_model = (
            (gw.model_name or gw.model or "UniFi Gateway") if gw else "UniFi Gateway"
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self._hub.gateway_mac or "controller")},
            name=gw_name,
            manufacturer=MANUFACTURER,
            model=gw_model,
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether the port-forward rule is enabled."""
        cache: dict[str, PortForward] | None = getattr(self._hub, "_pf_cache", None)
        if cache is None:
            return None
        pf = cache.get(self._pf_id)
        if pf is None:
            return None
        return pf.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the port-forward rule."""
        _LOGGER.info("Enabling port forward %s", self._pf_id)
        await self._hub.legacy.set_port_forward(self._pf_id, {"enabled": True})
        self._update_cache(enabled=True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the port-forward rule."""
        _LOGGER.info("Disabling port forward %s", self._pf_id)
        await self._hub.legacy.set_port_forward(self._pf_id, {"enabled": False})
        self._update_cache(enabled=False)
        self.async_write_ha_state()

    def _update_cache(self, enabled: bool) -> None:
        """Optimistically update the hub port-forward cache."""
        cache: dict[str, PortForward] | None = getattr(self._hub, "_pf_cache", None)
        if cache is not None and self._pf_id in cache:
            old = cache[self._pf_id]
            cache[self._pf_id] = PortForward(
                id=old.id, name=old.name, enabled=enabled,
                dst_port=old.dst_port, fwd_ip=old.fwd_ip,
                fwd_port=old.fwd_port, proto=old.proto,
                src=old.src, raw=old.raw,
            )


# ===========================================================================
# Traffic rule switch (Phase 6)
# ===========================================================================


class UniFiTrafficRuleSwitch(CoordinatorEntity[UniFiDataUpdateCoordinator], SwitchEntity):
    """Switch to enable / disable a traffic rule."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:traffic-light"

    def __init__(
        self,
        coordinator: UniFiDataUpdateCoordinator,
        hub: UniFiHub,
        rule: TrafficRule,
    ) -> None:
        super().__init__(coordinator)
        self._hub = hub
        self._rule_id = rule.id
        self._attr_unique_id = f"traffic_rule_{rule.id}"
        self._attr_name = f"Traffic Rule {rule.description}"

    @property
    def device_info(self) -> DeviceInfo:
        """Place traffic-rule switches under the gateway device."""
        gw = (
            self._hub.device_coordinator.devices.get(self._hub.gateway_mac)
            if self._hub.device_coordinator
            else None
        )
        gw_name = gw.name if gw and gw.name else "UniFi Controller"
        gw_model = (
            (gw.model_name or gw.model or "UniFi Gateway") if gw else "UniFi Gateway"
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self._hub.gateway_mac or "controller")},
            name=gw_name,
            manufacturer=MANUFACTURER,
            model=gw_model,
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether the traffic rule is enabled."""
        cache: dict[str, TrafficRule] | None = getattr(
            self._hub, "_traffic_rule_cache", None
        )
        if cache is None:
            return None
        rule = cache.get(self._rule_id)
        if rule is None:
            return None
        return rule.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the traffic rule."""
        _LOGGER.info("Enabling traffic rule %s", self._rule_id)
        await self._hub.v2.set_traffic_rule(self._rule_id, {"enabled": True})
        self._update_cache(enabled=True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the traffic rule."""
        _LOGGER.info("Disabling traffic rule %s", self._rule_id)
        await self._hub.v2.set_traffic_rule(self._rule_id, {"enabled": False})
        self._update_cache(enabled=False)
        self.async_write_ha_state()

    def _update_cache(self, enabled: bool) -> None:
        """Optimistically update the hub traffic-rule cache."""
        cache: dict[str, TrafficRule] | None = getattr(
            self._hub, "_traffic_rule_cache", None
        )
        if cache is not None and self._rule_id in cache:
            old = cache[self._rule_id]
            cache[self._rule_id] = TrafficRule(
                id=old.id, description=old.description, enabled=enabled,
                action=old.action, matching_target=old.matching_target,
                target_devices=old.target_devices, raw=old.raw,
            )


# ===========================================================================
# Firewall policy switch (Phase 6)
# ===========================================================================


class UniFiFirewallPolicySwitch(CoordinatorEntity[UniFiDataUpdateCoordinator], SwitchEntity):
    """Switch to enable / disable a firewall policy."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:shield-lock-outline"

    def __init__(
        self,
        coordinator: UniFiDataUpdateCoordinator,
        hub: UniFiHub,
        policy: FirewallPolicy,
    ) -> None:
        super().__init__(coordinator)
        self._hub = hub
        self._policy_id = policy.id
        self._attr_unique_id = f"fw_policy_{policy.id}"
        self._attr_name = f"Firewall Policy {policy.name}"

    @property
    def device_info(self) -> DeviceInfo:
        """Place firewall-policy switches under the gateway device."""
        gw = (
            self._hub.device_coordinator.devices.get(self._hub.gateway_mac)
            if self._hub.device_coordinator
            else None
        )
        gw_name = gw.name if gw and gw.name else "UniFi Controller"
        gw_model = (
            (gw.model_name or gw.model or "UniFi Gateway") if gw else "UniFi Gateway"
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self._hub.gateway_mac or "controller")},
            name=gw_name,
            manufacturer=MANUFACTURER,
            model=gw_model,
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether the firewall policy is enabled."""
        cache: dict[str, FirewallPolicy] | None = getattr(
            self._hub, "_fw_policy_cache", None
        )
        if cache is None:
            return None
        policy = cache.get(self._policy_id)
        if policy is None:
            return None
        return policy.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the firewall policy."""
        _LOGGER.info("Enabling firewall policy %s", self._policy_id)
        await self._hub.v2.set_firewall_policy(self._policy_id, {"enabled": True})
        self._update_cache(enabled=True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the firewall policy."""
        _LOGGER.info("Disabling firewall policy %s", self._policy_id)
        await self._hub.v2.set_firewall_policy(self._policy_id, {"enabled": False})
        self._update_cache(enabled=False)
        self.async_write_ha_state()

    def _update_cache(self, enabled: bool) -> None:
        """Optimistically update the hub firewall-policy cache."""
        cache: dict[str, FirewallPolicy] | None = getattr(
            self._hub, "_fw_policy_cache", None
        )
        if cache is not None and self._policy_id in cache:
            old = cache[self._policy_id]
            cache[self._policy_id] = FirewallPolicy(
                id=old.id, name=old.name, enabled=enabled,
                action=old.action, raw=old.raw,
            )


# ===========================================================================
# Platform setup
# ===========================================================================


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UniFi Network HA switch entities."""
    hub: UniFiHub = entry.runtime_data

    if hub.legacy is None:
        _LOGGER.debug("Legacy API not available — skipping switch setup")
        return

    entities: list[SwitchEntity] = []

    # ── WLAN switches ──────────────────────────────────────────────────
    if hub.device_coordinator is not None:
        try:
            raw_wlans = await hub.legacy.get_wlans()
            wlans: dict[str, Wlan] = {}
            for raw in raw_wlans:
                wlan = Wlan.from_dict(raw)
                if wlan.id and wlan.name:
                    wlans[wlan.id] = wlan

            # Store on hub so state lookups can find current WLAN data
            hub._wlan_cache = wlans  # noqa: SLF001

            for wlan in wlans.values():
                entities.append(
                    UniFiWlanSwitch(
                        coordinator=hub.device_coordinator,
                        hub=hub,
                        wlan=wlan,
                    )
                )
            _LOGGER.debug("Discovered %d WLAN switch(es)", len(wlans))
        except Exception:
            _LOGGER.warning("Could not fetch WLANs for switch setup", exc_info=True)

    # ── DPI restriction group switches ────────────────────────────────
    if hub.get_option(CONF_ENABLE_DPI, False) and hub.dpi_coordinator is not None:
        try:
            raw_groups = await hub.legacy.get_dpi_groups()
            dpi_groups: dict[str, dict] = {}
            for raw in raw_groups:
                group_id = raw.get("_id", raw.get("id", ""))
                group_name = raw.get("name", "")
                if group_id and group_name:
                    dpi_groups[group_id] = raw

            # Store on hub so state lookups can find current DPI group data
            hub._dpi_group_cache = dpi_groups  # noqa: SLF001

            for group_id, group_data in dpi_groups.items():
                group_name = group_data.get("name", "Unknown")
                enabled = group_data.get("enabled", True)
                entities.append(
                    UniFiDpiRestrictionSwitch(
                        coordinator=hub.dpi_coordinator,
                        hub=hub,
                        group_id=group_id,
                        group_name=group_name,
                        enabled=enabled,
                    )
                )
            _LOGGER.debug("Discovered %d DPI restriction group switch(es)", len(dpi_groups))
        except Exception:
            _LOGGER.warning("Could not fetch DPI groups for switch setup", exc_info=True)

    # ── Port forward switches ─────────────────────────────────────────
    if hub.device_coordinator is not None:
        try:
            raw_pfs = await hub.legacy.get_port_forwards()
            pf_cache: dict[str, PortForward] = {}
            for raw in raw_pfs:
                pf = PortForward.from_dict(raw)
                if pf.id and pf.name:
                    pf_cache[pf.id] = pf

            hub._pf_cache = pf_cache  # noqa: SLF001

            for pf in pf_cache.values():
                entities.append(
                    UniFiPortForwardSwitch(
                        coordinator=hub.device_coordinator,
                        hub=hub,
                        pf=pf,
                    )
                )
            _LOGGER.debug("Discovered %d port forward switch(es)", len(pf_cache))
        except Exception:
            _LOGGER.warning("Could not fetch port forwards for switch setup", exc_info=True)

    # ── Traffic rule switches ─────────────────────────────────────────
    if hub.v2 is not None and hub.device_coordinator is not None:
        try:
            raw_rules = await hub.v2.get_traffic_rules()
            rule_cache: dict[str, TrafficRule] = {}
            for raw in raw_rules:
                rule = TrafficRule.from_dict(raw)
                if rule.id and rule.description:
                    rule_cache[rule.id] = rule

            hub._traffic_rule_cache = rule_cache  # noqa: SLF001

            for rule in rule_cache.values():
                entities.append(
                    UniFiTrafficRuleSwitch(
                        coordinator=hub.device_coordinator,
                        hub=hub,
                        rule=rule,
                    )
                )
            _LOGGER.debug("Discovered %d traffic rule switch(es)", len(rule_cache))
        except Exception:
            _LOGGER.warning("Could not fetch traffic rules for switch setup", exc_info=True)

    # ── Firewall policy switches ──────────────────────────────────────
    if hub.v2 is not None and hub.device_coordinator is not None:
        try:
            raw_policies = await hub.v2.get_firewall_policies()
            policy_cache: dict[str, FirewallPolicy] = {}
            for raw in raw_policies:
                policy = FirewallPolicy.from_dict(raw)
                if policy.id and policy.name:
                    policy_cache[policy.id] = policy

            hub._fw_policy_cache = policy_cache  # noqa: SLF001

            for policy in policy_cache.values():
                entities.append(
                    UniFiFirewallPolicySwitch(
                        coordinator=hub.device_coordinator,
                        hub=hub,
                        policy=policy,
                    )
                )
            _LOGGER.debug("Discovered %d firewall policy switch(es)", len(policy_cache))
        except Exception:
            _LOGGER.warning("Could not fetch firewall policies for switch setup", exc_info=True)

    # ── Per-switch-port switches (PoE + port enable) ───────────────────
    if hub.device_coordinator is not None:
        for mac, device in hub.device_coordinator.devices.items():
            if device.type != "usw":
                continue
            dev_name = device.name or f"Switch {mac}"
            dev_model = device.model_name or device.model or "UniFi Switch"
            device_id = device.raw.get("_id", "")

            if not device_id:
                _LOGGER.debug("Switch %s missing _id — skipping port switches", mac)
                continue

            for port in device.ports:
                if port.idx <= 0:
                    continue
                port_name = port.name or f"Port {port.idx}"

                # PoE switch (only for PoE-capable ports)
                if port.poe_enable or port.poe_mode:
                    entities.append(
                        UniFiPoEPortSwitch(
                            coordinator=hub.device_coordinator,
                            hub=hub,
                            mac=mac,
                            device_name=dev_name,
                            device_model=dev_model,
                            port_idx=port.idx,
                            port_name=port_name,
                            device_id=device_id,
                        )
                    )

                # Port enable switch (skip uplink ports)
                if not port.is_uplink:
                    entities.append(
                        UniFiPortEnableSwitch(
                            coordinator=hub.device_coordinator,
                            hub=hub,
                            mac=mac,
                            device_name=dev_name,
                            device_model=dev_model,
                            port_idx=port.idx,
                            port_name=port_name,
                            device_id=device_id,
                        )
                    )

    _LOGGER.debug("Setting up %d device switch entities", len(entities))
    async_add_entities(entities)

    # ── Client block switches (dynamic — added as clients appear) ──────
    if hub.get_option(CONF_TRACK_CLIENTS, DEFAULT_TRACK_CLIENTS) and hub.client_coordinator:
        tracked_macs: set[str] = set()

        @callback
        def _async_add_new_switches() -> None:
            """Create block switches for newly discovered clients."""
            new_entities: list[UniFiBlockClientSwitch] = []
            for c_mac, client in hub.client_coordinator.all_known.items():
                if c_mac not in tracked_macs:
                    tracked_macs.add(c_mac)
                    new_entities.append(
                        UniFiBlockClientSwitch(hub.client_coordinator, hub, client)
                    )
            if new_entities:
                _LOGGER.debug(
                    "Adding %d new client block switch(es)", len(new_entities)
                )
                async_add_entities(new_entities)

        # Add switches for all known clients at startup.
        _async_add_new_switches()

        # Dynamically add switches when new clients appear.
        entry.async_on_unload(
            hub.client_coordinator.async_add_listener(_async_add_new_switches)
        )
