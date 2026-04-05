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

SERVICE_RECONNECT_SCHEMA = vol.Schema({
    vol.Required("mac"): cv.string,
})

SERVICE_BLOCK_SCHEMA = vol.Schema({
    vol.Required("mac"): cv.string,
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


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services."""
    hass.services.async_remove(DOMAIN, SERVICE_RECONNECT_CLIENT)
    hass.services.async_remove(DOMAIN, SERVICE_REMOVE_CLIENTS)
    hass.services.async_remove(DOMAIN, SERVICE_BLOCK_CLIENT)
    hass.services.async_remove(DOMAIN, SERVICE_UNBLOCK_CLIENT)
