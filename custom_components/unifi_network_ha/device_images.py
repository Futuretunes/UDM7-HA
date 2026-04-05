"""Device image URL mapping for UniFi devices.

Maps UniFi device model shortnames to product image URLs so that
Home Assistant can display product photos for each network device.

Two resolution strategies are used:

1. **Static map** -- a curated dict of model -> image URL for models
   whose CDN UUIDs have been verified.
2. **Fallback** -- for unknown models, a URL pattern on static.ui.com
   that serves device icons based on the model identifier.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Verified product image URLs
# ---------------------------------------------------------------------------
# These URLs point to official Ubiquiti product images on the CDN.
# Only entries whose UUIDs have been verified are included here.
# The model string comes from the "model" field in the UniFi API device
# response.
#
# Format: model_shortname -> (image_url, display_name)

DEVICE_IMAGE_MAP: dict[str, tuple[str, str]] = {
    # Cloud Gateways / Dream Machines
    "UDR7": (
        "https://cdn.ecomm.ui.com/products/5fd748ec-76b6-48ca-9256-9fb09d50b4b0/"
        "c57b6e85-cf5b-48c8-9e92-9f25e4dd0f39.png",
        "Dream Router 7",
    ),
    "UDR": (
        "https://cdn.ecomm.ui.com/products/60459473-c989-41db-93f2-3c0f40df84f3/"
        "b4fd2ae0-8d83-4ad0-ab4e-138d034a32f3.png",
        "Dream Router",
    ),
    "UDM": (
        "https://cdn.ecomm.ui.com/products/9585991f-2b82-411c-8f44-addb4711e4db/"
        "efe7fc7e-907c-4997-ac52-807323c8fd41.png",
        "Dream Machine",
    ),
    "UDMPRO": (
        "https://cdn.ecomm.ui.com/products/9df27ed4-c4ae-471a-8982-f5b0650da76a/"
        "2ede4300-385f-4043-8d96-e0400a22465f.png",
        "Dream Machine Pro",
    ),
    "UDMSE": (
        "https://cdn.ecomm.ui.com/products/1b6fcc08-a6b8-4496-a831-6125a47c412f/"
        "1aaaac38-597b-4125-b0de-7a2671580b21.png",
        "Dream Machine SE",
    ),
    "UDMPROMAXHD": (
        "https://cdn.ecomm.ui.com/products/401190d7-6a49-4c2e-bef1-7fe087d2b6b6/"
        "95713566-423f-45e1-8b40-6d760f048490.png",
        "Dream Machine Pro Max",
    ),
    "UCG-Ultra": (
        "https://cdn.ecomm.ui.com/products/8d2d9e4b-89f3-49a1-9c17-5d774c0067b4/"
        "2e179331-f85a-4bc9-bf3e-d00192522732.png",
        "Cloud Gateway Ultra",
    ),
    # Access Points
    "U6-Pro": (
        "https://cdn.ecomm.ui.com/products/8e88b222-7a55-4cf0-8677-ae9b6347fe84/"
        "e16aa122-b5e5-4ffb-9f1a-27ee14d9ab3d.png",
        "U6 Pro",
    ),
    "U6-Lite": (
        "https://cdn.ecomm.ui.com/products/259686b4-ae75-411c-90bc-e4040e38ca56/"
        "3dac99a9-6352-44f3-ac8b-ade89c707831.png",
        "U6 Lite",
    ),
    # Switches
    "USW-Flex": (
        "https://cdn.ecomm.ui.com/products/c9a07d37-b390-4a5b-89c5-3cdab8e011c7/"
        "4bcd3c2b-a8b1-4be1-baab-deda172291cd.png",
        "Switch Flex",
    ),
    "USW-Flex-Mini": (
        "https://cdn.ecomm.ui.com/products/5a176b22-af34-40f2-820c-958610df1825/"
        "19394e07-5146-4f8c-b72d-7fdbdf679c97.png",
        "Switch Flex Mini",
    ),
}

# ---------------------------------------------------------------------------
# Display names for models not in the verified image map
# ---------------------------------------------------------------------------
# Even when we don't have a confirmed CDN URL we can still provide a
# human-friendly display name.

DISPLAY_NAMES: dict[str, str] = {
    # Cloud Gateways / Dream Machines
    "UDR7": "Dream Router 7",
    "UDR": "Dream Router",
    "UDM": "Dream Machine",
    "UDMPRO": "Dream Machine Pro",
    "UDMSE": "Dream Machine SE",
    "UDMPROMAXHD": "Dream Machine Pro Max",
    "UCG-Ultra": "Cloud Gateway Ultra",
    "UXG-Pro": "Next-Gen Gateway Pro",
    "UXG-Enterprise": "Next-Gen Gateway Enterprise",
    "UXG-Lite": "Cloud Gateway Lite",
    # Access Points - WiFi 7
    "U7-Pro": "U7 Pro",
    "U7-Pro-Max": "U7 Pro Max",
    "U7-Outdoor": "U7 Outdoor",
    # Access Points - WiFi 6 / 6E
    "U6-Pro": "U6 Pro",
    "U6-LR": "U6 LR",
    "U6-Lite": "U6 Lite",
    "U6-Enterprise": "U6 Enterprise",
    "U6-Mesh": "U6 Mesh",
    "U6-IW": "U6 In-Wall",
    "U6-Extender": "U6 Extender",
    # Access Points - older
    "UAP-AC-Pro": "UAP AC Pro",
    "UAP-AC-LR": "UAP AC LR",
    "UAP-AC-Lite": "UAP AC Lite",
    "UAP-AC-IW": "UAP AC In-Wall",
    "UAP-AC-M": "UAP AC Mesh",
    "UAP-AC-M-Pro": "UAP AC Mesh Pro",
    "UAP-nanoHD": "UniFi nanoHD",
    "UAP-FlexHD": "UniFi FlexHD",
    # Switches
    "USW-24-PoE": "Switch 24 PoE",
    "USW-48-PoE": "Switch 48 PoE",
    "USW-Lite-8-PoE": "Switch Lite 8 PoE",
    "USW-Lite-16-PoE": "Switch Lite 16 PoE",
    "USW-Ultra": "Switch Ultra",
    "USW-Pro-24-PoE": "Switch Pro 24 PoE",
    "USW-Pro-48-PoE": "Switch Pro 48 PoE",
    "USW-Enterprise-24-PoE": "Switch Enterprise 24 PoE",
    "USW-Enterprise-48-PoE": "Switch Enterprise 48 PoE",
    "USW-Flex-Mini": "Switch Flex Mini",
    "USW-Flex": "Switch Flex",
    "USW-Aggregation": "Switch Aggregation",
    "USW-Pro-Max-24-PoE": "Switch Pro Max 24 PoE",
    "USW-Pro-Max-48-PoE": "Switch Pro Max 48 PoE",
    # Legacy
    "USG": "Security Gateway",
    "USG-Pro-4": "Security Gateway Pro",
    "USG-XG-8": "Security Gateway XG-8",
}

# ---------------------------------------------------------------------------
# Alternative model name mappings
# ---------------------------------------------------------------------------
# The API sometimes returns different variants of the same model string.

MODEL_ALIASES: dict[str, str] = {
    "UDM-Pro": "UDMPRO",
    "UDM-SE": "UDMSE",
    "UDM-Pro-Max": "UDMPROMAXHD",
    "UDM Pro": "UDMPRO",
    "UDM SE": "UDMSE",
    "UDM Pro Max": "UDMPROMAXHD",
    "UCG Ultra": "UCG-Ultra",
    "UXG Pro": "UXG-Pro",
    "UXG Enterprise": "UXG-Enterprise",
    "UXG Lite": "UXG-Lite",
    "U7 Pro": "U7-Pro",
    "U7 Pro Max": "U7-Pro-Max",
    "U7 Outdoor": "U7-Outdoor",
    "U6 Pro": "U6-Pro",
    "U6 LR": "U6-LR",
    "U6 Lite": "U6-Lite",
    "U6 Enterprise": "U6-Enterprise",
    "U6 Mesh": "U6-Mesh",
    "U6 IW": "U6-IW",
    "U6 Extender": "U6-Extender",
    # Switch variants the API may report
    "USW Flex": "USW-Flex",
    "USW Flex Mini": "USW-Flex-Mini",
    "USWFLEX": "USW-Flex",
    "USWFLEXMINI": "USW-Flex-Mini",
    "USW-Flex-2.5G-5": "USW-Flex",
}

# ---------------------------------------------------------------------------
# Fallback URL pattern
# ---------------------------------------------------------------------------
# For models not in the verified map we try the static.ui.com fingerprint
# CDN which serves device icons keyed by model identifier.

_STATIC_UI_FALLBACK = (
    "https://static.ui.com/fingerprint/ui/icons/{model_id}_128x128.png"
)


def _resolve_model(model: str) -> str:
    """Resolve *model* through aliases and return the canonical key."""
    if model in DEVICE_IMAGE_MAP or model in DISPLAY_NAMES:
        return model
    canonical = MODEL_ALIASES.get(model)
    if canonical:
        return canonical
    # Case-insensitive fallback
    normalised = model.upper().replace(" ", "-")
    for key in DEVICE_IMAGE_MAP:
        if key.upper().replace(" ", "-") == normalised:
            return key
    for key in DISPLAY_NAMES:
        if key.upper().replace(" ", "-") == normalised:
            return key
    return model


def get_device_image_url(model: str, allow_fallback: bool = True) -> str | None:
    """Return the product image URL for a UniFi device model.

    Args:
        model: The device model string from the API (e.g. ``"UDR7"``,
            ``"U6-Pro"``).
        allow_fallback: If ``True`` (default), returns a best-effort
            static.ui.com URL for unknown models. If ``False``, returns
            ``None`` for models not in the verified map.

    Returns:
        A URL string pointing to a product image, or ``None`` if the
        model is empty or unknown (when fallback is disabled).
    """
    if not model:
        return None

    canonical = _resolve_model(model)

    # 1. Verified CDN image
    entry = DEVICE_IMAGE_MAP.get(canonical)
    if entry:
        return entry[0]

    if not allow_fallback:
        return None

    # 2. Fallback to static.ui.com icon pattern
    model_id = canonical.lower().replace("-", "").replace(" ", "")
    return _STATIC_UI_FALLBACK.format(model_id=model_id)


def get_device_display_name(model: str) -> str | None:
    """Return the human-friendly display name for a UniFi device model.

    Returns ``None`` if the model is not in the known mapping.
    """
    if not model:
        return None
    canonical = _resolve_model(model)
    # Check verified map first (it carries display names too)
    entry = DEVICE_IMAGE_MAP.get(canonical)
    if entry:
        return entry[1]
    return DISPLAY_NAMES.get(canonical)
