"""Custom services for UniFi Network HA."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_RECONNECT_CLIENT = "reconnect_client"
SERVICE_REMOVE_CLIENTS = "remove_clients"
SERVICE_BLOCK_CLIENT = "block_client"
SERVICE_UNBLOCK_CLIENT = "unblock_client"
SERVICE_KICK_CLIENT = "kick_client"
SERVICE_FORGET_CLIENT = "forget_client"
SERVICE_CREATE_VOUCHER = "create_voucher"
SERVICE_LIST_VOUCHERS = "list_vouchers"
SERVICE_REVOKE_VOUCHER = "revoke_voucher"

SERVICE_RECONNECT_SCHEMA = vol.Schema({
    vol.Required("mac"): cv.string,
})

SERVICE_BLOCK_SCHEMA = vol.Schema({
    vol.Required("mac"): cv.string,
})

SERVICE_KICK_SCHEMA = vol.Schema({
    vol.Required("mac"): cv.string,
})

SERVICE_FORGET_SCHEMA = vol.Schema({
    vol.Required("mac"): cv.string,
})

SERVICE_CREATE_VOUCHER_SCHEMA = vol.Schema({
    vol.Optional("count", default=1): vol.All(int, vol.Range(min=1, max=100)),
    vol.Optional("quota", default=1): vol.All(int, vol.Range(min=0, max=100)),  # 0 = unlimited
    vol.Optional("expire", default=1440): vol.All(int, vol.Range(min=1)),  # minutes
    vol.Optional("up_bandwidth"): vol.All(int, vol.Range(min=1)),  # kbps
    vol.Optional("down_bandwidth"): vol.All(int, vol.Range(min=1)),  # kbps
    vol.Optional("byte_quota"): vol.All(int, vol.Range(min=1)),  # megabytes
    vol.Optional("note", default=""): cv.string,
})

SERVICE_REVOKE_VOUCHER_SCHEMA = vol.Schema({
    vol.Required("voucher_id"): cv.string,
})


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for UniFi Network HA."""

    async def _reconnect_client(call: ServiceCall) -> None:
        """Force a client to reconnect to the network."""
        mac = call.data["mac"].lower()
        for entry in hass.config_entries.async_entries(DOMAIN):
            hub = entry.runtime_data
            if hub.legacy is None:
                continue
            await hub.legacy.kick_client(mac)
            _LOGGER.info("Reconnected client %s", mac)

    async def _remove_clients(call: ServiceCall) -> None:
        """Remove offline clients from the controller."""
        for entry in hass.config_entries.async_entries(DOMAIN):
            hub = entry.runtime_data
            if hub.legacy is None:
                continue
            # Get all known clients, find offline ones
            all_users = await hub.legacy.get_all_users()
            active: set[str] = set()
            if hub.client_coordinator:
                active = set(hub.client_coordinator.clients.keys())
            offline_macs = [
                u["mac"]
                for u in all_users
                if u.get("mac") and u["mac"] not in active
            ]
            if offline_macs:
                await hub.legacy.forget_client(offline_macs)
                _LOGGER.info("Removed %d offline clients", len(offline_macs))

    async def _block_client(call: ServiceCall) -> None:
        """Block a client from the network."""
        mac = call.data["mac"].lower()
        for entry in hass.config_entries.async_entries(DOMAIN):
            hub = entry.runtime_data
            if hub.legacy is None:
                continue
            await hub.legacy.block_client(mac)
            _LOGGER.info("Blocked client %s", mac)

    async def _unblock_client(call: ServiceCall) -> None:
        """Unblock a client on the network."""
        mac = call.data["mac"].lower()
        for entry in hass.config_entries.async_entries(DOMAIN):
            hub = entry.runtime_data
            if hub.legacy is None:
                continue
            await hub.legacy.unblock_client(mac)
            _LOGGER.info("Unblocked client %s", mac)

    async def _kick_client(call: ServiceCall) -> None:
        """Disconnect a client from the network (they can reconnect)."""
        mac = call.data["mac"].lower()
        for entry in hass.config_entries.async_entries(DOMAIN):
            hub = entry.runtime_data
            if hub.legacy is None:
                continue
            await hub.legacy.kick_client(mac)
            _LOGGER.info("Kicked client %s", mac)

    async def _forget_client(call: ServiceCall) -> None:
        """Remove a client from the known clients list on the controller."""
        mac = call.data["mac"].lower()
        for entry in hass.config_entries.async_entries(DOMAIN):
            hub = entry.runtime_data
            if hub.legacy is None:
                continue
            await hub.legacy.forget_client([mac])
            _LOGGER.info("Forgot client %s", mac)

    async def _create_voucher(call: ServiceCall) -> None:
        """Create guest portal vouchers."""
        for entry in hass.config_entries.async_entries(DOMAIN):
            hub = entry.runtime_data
            if hub.legacy is None:
                continue
            result = await hub.legacy.create_voucher(
                count=call.data.get("count", 1),
                quota=call.data.get("quota", 1),
                expire=call.data.get("expire", 1440),
                up_bandwidth=call.data.get("up_bandwidth"),
                down_bandwidth=call.data.get("down_bandwidth"),
                byte_quota=call.data.get("byte_quota"),
                note=call.data.get("note", ""),
            )
            if result:
                # Fire an event with the created voucher codes
                codes = [v.get("code", "") for v in result if v.get("code")]
                hass.bus.async_fire(f"{DOMAIN}_voucher_created", {
                    "codes": codes,
                    "count": len(codes),
                    "expire_minutes": call.data.get("expire", 1440),
                })
                _LOGGER.info("Created %d voucher(s)", len(codes))
            break  # only use first config entry

    async def _list_vouchers(call: ServiceCall) -> None:
        """List active vouchers -- fires an event with the voucher data."""
        for entry in hass.config_entries.async_entries(DOMAIN):
            hub = entry.runtime_data
            if hub.legacy is None:
                continue
            vouchers = await hub.legacy.get_vouchers()
            hass.bus.async_fire(f"{DOMAIN}_voucher_list", {
                "vouchers": [
                    {
                        "code": v.get("code", ""),
                        "note": v.get("note", ""),
                        "quota": v.get("quota", 0),
                        "used": v.get("used", 0),
                        "duration": v.get("duration", 0),
                        "status": v.get("status", ""),
                        "create_time": v.get("create_time", 0),
                    }
                    for v in vouchers
                ],
                "count": len(vouchers),
            })
            break  # only use first config entry

    async def _revoke_voucher(call: ServiceCall) -> None:
        """Revoke a guest voucher."""
        voucher_id = call.data["voucher_id"]
        for entry in hass.config_entries.async_entries(DOMAIN):
            hub = entry.runtime_data
            if hub.legacy is None:
                continue
            await hub.legacy.revoke_voucher(voucher_id)
            _LOGGER.info("Revoked voucher %s", voucher_id)
            break  # only use first config entry

    hass.services.async_register(
        DOMAIN, SERVICE_RECONNECT_CLIENT, _reconnect_client,
        schema=SERVICE_RECONNECT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_CLIENTS, _remove_clients,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_BLOCK_CLIENT, _block_client,
        schema=SERVICE_BLOCK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_UNBLOCK_CLIENT, _unblock_client,
        schema=SERVICE_BLOCK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_KICK_CLIENT, _kick_client,
        schema=SERVICE_KICK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_FORGET_CLIENT, _forget_client,
        schema=SERVICE_FORGET_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CREATE_VOUCHER, _create_voucher,
        schema=SERVICE_CREATE_VOUCHER_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_LIST_VOUCHERS, _list_vouchers,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REVOKE_VOUCHER, _revoke_voucher,
        schema=SERVICE_REVOKE_VOUCHER_SCHEMA,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services."""
    hass.services.async_remove(DOMAIN, SERVICE_RECONNECT_CLIENT)
    hass.services.async_remove(DOMAIN, SERVICE_REMOVE_CLIENTS)
    hass.services.async_remove(DOMAIN, SERVICE_BLOCK_CLIENT)
    hass.services.async_remove(DOMAIN, SERVICE_UNBLOCK_CLIENT)
    hass.services.async_remove(DOMAIN, SERVICE_KICK_CLIENT)
    hass.services.async_remove(DOMAIN, SERVICE_FORGET_CLIENT)
    hass.services.async_remove(DOMAIN, SERVICE_CREATE_VOUCHER)
    hass.services.async_remove(DOMAIN, SERVICE_LIST_VOUCHERS)
    hass.services.async_remove(DOMAIN, SERVICE_REVOKE_VOUCHER)
