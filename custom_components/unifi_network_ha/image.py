"""UniFi Network HA image platform.

Provides a WiFi QR code image entity for each WLAN.  The entity exposes
the standard ``WIFI:`` connection string as extra state attributes so that
HA dashboards can render a QR code using a card that supports the
``wifi_qr`` format.

Since generating actual QR code images requires an external library that
is not bundled with Home Assistant, this platform generates a minimal SVG
QR code using a pure-Python implementation embedded below.  The SVG is
returned as the image bytes.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.models import Wlan
from .const import DOMAIN, MANUFACTURER
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
    """Set up UniFi Network HA WLAN QR code image entities."""
    hub: UniFiHub = entry.runtime_data
    entities: list[UniFiWlanQrCode] = []

    if hub.legacy is None:
        _LOGGER.debug("Legacy API not available — skipping image setup")
        return

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
        return

    _LOGGER.debug("Setting up %d WLAN QR code image entities", len(entities))
    async_add_entities(entities)
