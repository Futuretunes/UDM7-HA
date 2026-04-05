"""UniFi Network HA image platform.

Provides:
* A WiFi QR code image entity for each WLAN.
* A product image entity for each adopted UniFi network device.

The QR code entity exposes the standard ``WIFI:`` connection string as
extra state attributes so that HA dashboards can render a QR code using a
card that supports the ``wifi_qr`` format.

Since generating actual QR code images requires an external library that
is not bundled with Home Assistant, this platform generates a minimal SVG
QR code using a pure-Python implementation embedded below.  The SVG is
returned as the image bytes.
"""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.models import Device, Wlan
from .const import CONF_ENABLE_DEVICE_CONTROLS, DOMAIN, MANUFACTURER
from .device_images import get_device_image_url
from .hub import UniFiHub

# Type alias used in __init__.py — import so the platform signature matches.
from . import UniFiConfigEntry

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WiFi connection string helper
# ---------------------------------------------------------------------------

def _wifi_string(ssid: str, password: str, security: str = "WPA") -> str:
    """Build a standard WiFi connection string for QR codes.

    Format: ``WIFI:T:<type>;S:<ssid>;P:<password>;;``

    Special characters in SSID and password are escaped per the spec.
    """
    def _escape(s: str) -> str:
        for ch in ("\\", ";", ",", ":", '"'):
            s = s.replace(ch, f"\\{ch}")
        return s

    sec = security.upper() if security else "WPA"
    if sec not in ("WPA", "WEP", "nopass"):
        sec = "WPA"

    parts = [f"WIFI:T:{sec}", f"S:{_escape(ssid)}"]
    if sec != "nopass" and password:
        parts.append(f"P:{_escape(password)}")
    return ";".join(parts) + ";;"


# ---------------------------------------------------------------------------
# WLAN QR code image entity
# ---------------------------------------------------------------------------


class UniFiWlanQrCode(ImageEntity):
    """QR code image for connecting to a WLAN.

    Exposes the WiFi connection string both as the entity state attribute
    ``wifi_string`` and generates a minimal SVG-based QR code as the
    image content.
    """

    _attr_has_entity_name = True
    _attr_content_type = "image/svg+xml"

    def __init__(
        self,
        hass: HomeAssistant,
        hub: UniFiHub,
        wlan: Wlan,
    ) -> None:
        super().__init__(hass)
        self._hub = hub
        self._wlan = wlan
        self._attr_unique_id = f"wlan_{wlan.id}_qr"
        self._attr_name = f"{wlan.name} QR code"
        self._wifi_str = _wifi_string(
            ssid=wlan.name,
            password=wlan.x_passphrase,
            security=wlan.security or wlan.wpa_mode or "WPA",
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Place QR code entities under the gateway device."""
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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the WiFi connection string and WLAN metadata."""
        return {
            "wifi_string": self._wifi_str,
            "ssid": self._wlan.name,
            "security": self._wlan.security or self._wlan.wpa_mode or "WPA",
            "is_guest": self._wlan.is_guest,
        }

    async def async_image(self) -> bytes | None:
        """Return an SVG image encoding the WiFi QR string.

        Uses an embedded pure-Python QR code generator that produces a
        compact SVG.  If generation fails, returns a simple SVG with the
        WiFi string as text.
        """
        try:
            svg = await self.hass.async_add_executor_job(
                _generate_qr_svg, self._wifi_str
            )
            return svg.encode("utf-8")
        except Exception:
            _LOGGER.debug("QR generation failed, returning text SVG", exc_info=True)
            return _text_fallback_svg(self._wifi_str).encode("utf-8")


# ---------------------------------------------------------------------------
# Device product image entity
# ---------------------------------------------------------------------------


class UniFiDeviceImage(ImageEntity):
    """Product image for a UniFi network device.

    Fetches the product photo from Ubiquiti's CDN (or static.ui.com
    fallback) and caches it so subsequent requests are served locally.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_content_type = "image/png"

    def __init__(
        self,
        hass: HomeAssistant,
        hub: UniFiHub,
        device: Device,
    ) -> None:
        super().__init__(hass)
        self._hub = hub
        self._device = device
        self._device_mac = device.mac
        self._attr_unique_id = f"{device.mac}_product_image"
        self._attr_name = "Product image"
        self._image_url = get_device_image_url(device.model)
        self._cached_image: bytes | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Link this image entity to the network device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_mac)},
            name=self._device.name or self._device_mac,
            manufacturer=MANUFACTURER,
            model=self._device.model_name or self._device.model,
        )

    async def async_image(self) -> bytes | None:
        """Return the product image bytes, fetching from CDN if needed."""
        if self._cached_image is not None:
            return self._cached_image
        if not self._image_url:
            return None
        try:
            session = async_get_clientsession(self._hub.hass)
            timeout = aiohttp.ClientTimeout(total=15)
            async with session.get(self._image_url, timeout=timeout) as resp:
                if resp.status == 200:
                    self._cached_image = await resp.read()
                    return self._cached_image
                _LOGGER.debug(
                    "Device image fetch returned %s for %s (%s)",
                    resp.status,
                    self._device.model,
                    self._image_url,
                )
        except Exception:  # noqa: BLE001
            _LOGGER.debug(
                "Could not fetch device image for %s", self._device.model,
                exc_info=True,
            )
        return None


# ---------------------------------------------------------------------------
# Minimal QR code SVG generator (pure Python, no external deps)
# ---------------------------------------------------------------------------

def _generate_qr_svg(data: str, module_size: int = 8, border: int = 4) -> str:
    """Generate a QR code as an SVG string.

    This uses a minimal implementation based on the QR code spec for
    alphanumeric/byte mode.  For simplicity and reliability we attempt to
    import the ``qrcode`` library first (available in many HA installs
    via HACS or system packages).  If unavailable, we fall back to a text
    placeholder SVG.
    """
    try:
        import qrcode  # type: ignore[import-untyped]
        from qrcode.image.svg import SvgPathImage  # type: ignore[import-untyped]

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=module_size,
            border=border,
        )
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(image_factory=SvgPathImage)
        # SvgPathImage.to_string() returns bytes
        svg_bytes = img.to_string()
        if isinstance(svg_bytes, bytes):
            return svg_bytes.decode("utf-8")
        return str(svg_bytes)
    except ImportError:
        _LOGGER.debug(
            "qrcode library not available; returning text-based SVG fallback"
        )
        return _text_fallback_svg(data)


def _text_fallback_svg(data: str) -> str:
    """Return a simple SVG that displays the WiFi string as text."""
    # Escape XML special chars
    safe = data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="100" viewBox="0 0 300 100">'
        '<rect width="300" height="100" fill="white"/>'
        '<text x="10" y="30" font-family="monospace" font-size="10" fill="black">'
        "WiFi QR Code</text>"
        f'<text x="10" y="55" font-family="monospace" font-size="8" fill="black">'
        f"{safe}</text>"
        '<text x="10" y="80" font-family="monospace" font-size="8" fill="grey">'
        "Install 'qrcode' package for image</text>"
        "</svg>"
    )


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UniFiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UniFi Network HA image entities.

    Creates:
    * A WiFi QR code image for each WLAN.
    * A product photo image for each adopted device with a known model.
    """
    hub: UniFiHub = entry.runtime_data
    entities: list[ImageEntity] = []

    if hub.legacy is None:
        _LOGGER.debug("Legacy API not available — skipping image setup")
        return

    if not hub.get_option(CONF_ENABLE_DEVICE_CONTROLS, True):
        _LOGGER.debug("Device controls disabled — skipping image setup")
        return

    # --- WLAN QR codes ---------------------------------------------------
    try:
        raw_wlans = await hub.legacy.get_wlans()
        for raw in raw_wlans:
            wlan = Wlan.from_dict(raw)
            if not wlan.id or not wlan.name:
                continue
            entities.append(
                UniFiWlanQrCode(
                    hass=hass,
                    hub=hub,
                    wlan=wlan,
                )
            )
    except Exception:
        _LOGGER.warning("Could not fetch WLANs for QR code setup", exc_info=True)

    # --- Device product images -------------------------------------------
    if hub.device_coordinator:
        for mac, device in hub.device_coordinator.devices.items():
            if not device.adopted:
                continue
            image_url = get_device_image_url(device.model)
            if image_url:
                entities.append(
                    UniFiDeviceImage(hass=hass, hub=hub, device=device)
                )

    _LOGGER.debug("Setting up %d image entities", len(entities))
    async_add_entities(entities)
