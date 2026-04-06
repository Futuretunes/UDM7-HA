"""The UniFi Network HA integration."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .hub import UniFiHub
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

# Path to the custom Lovelace card served under /unifi_network_ha/
CARD_DIR = Path(__file__).parent / "www"
CARD_URL_BASE = f"/{DOMAIN}"

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

    # Register the custom Lovelace card (idempotent)
    await _async_register_card(hass)

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


async def _async_register_card(hass: HomeAssistant) -> None:
    """Register the custom Lovelace card static path and frontend resource.

    This is idempotent — safe to call on every config-entry setup.
    The card JS is served at ``/unifi_network_ha/unifi-network-card.js``
    and automatically added to Lovelace resources so users do not need
    to add it manually.
    """
    card_file = CARD_DIR / "unifi-network-card.js"
    if not card_file.is_file():
        _LOGGER.debug("Custom card file not found at %s", card_file)
        return

    card_url = f"{CARD_URL_BASE}/unifi-network-card.js"

    # Register static path — API changed in recent HA versions
    try:
        from homeassistant.components.http import StaticPathConfig  # HA 2025.7+

        await hass.http.async_register_static_paths(
            [StaticPathConfig(card_url, str(card_file), cache_headers=False)]
        )
    except (ImportError, AttributeError):
        try:
            hass.http.register_static_path(card_url, str(card_file), cache_headers=False)
        except AttributeError:
            _LOGGER.debug("Could not register static path for custom card")
            return

    # Add the resource to Lovelace so the card is available without manual config
    try:
        from homeassistant.components.frontend import add_extra_js_url

        add_extra_js_url(hass, card_url)
        _LOGGER.debug("Registered custom card resource: %s", card_url)
    except (ImportError, AttributeError):
        _LOGGER.info(
            "Add %s as a Lovelace resource manually (Settings > Dashboards > Resources)",
            card_url,
        )
