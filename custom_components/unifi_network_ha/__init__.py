"""The UniFi Network HA integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .hub import UniFiHub
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

# Type alias for config entry with our runtime data
type UniFiConfigEntry = ConfigEntry[UniFiHub]


async def async_setup_entry(hass: HomeAssistant, entry: UniFiConfigEntry) -> bool:
    """Set up UniFi Network HA from a config entry."""
    hub = UniFiHub(hass, entry)

    if not await hub.async_setup():
        return False

    # Store hub as runtime_data on the config entry (HA 2024.x+ pattern)
    entry.runtime_data = hub

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Set up custom services (idempotent — safe to call multiple times)
    await async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: UniFiConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hub: UniFiHub = entry.runtime_data
        await hub.async_teardown()

    # Only unload services if this is the last config entry being removed
    if not hass.config_entries.async_entries(DOMAIN):
        await async_unload_services(hass)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: UniFiConfigEntry) -> None:
    """Handle options update by reloading the entry."""
    await hass.config_entries.async_reload(entry.entry_id)
