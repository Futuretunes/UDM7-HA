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
    "U6-LR": (
        "https://cdn.ecomm.ui.com/products/d8fee47d-b53e-4a86-a5cb-cf2f6ab1c5ef/"
        "4f1f5856-05c2-4989-970e-6751e6af7eb9.png",
        "U6 LR",
    ),
    "U6-Enterprise": (
        "https://cdn.ecomm.ui.com/products/f9118c0f-060b-4fd7-99ce-ace671c7a1fe/"
        "6f2a87a4-193d-43e0-b253-aa0ea0795694.png",
        "U6 Enterprise",
    ),
    "U6-Mesh": (
        "https://cdn.ecomm.ui.com/products/7b8f8da5-d684-4170-be1f-71b53af8d7f9/"
        "fdce5345-80e9-4edd-bf5b-93cf9141649e.png",
        "U6 Mesh",
    ),
    "U7-Pro": (
        "https://cdn.ecomm.ui.com/products/fa8dd4e4-36c8-4c79-a928-22c7bff2ce29/"
        "ab5bc8a4-6135-402e-a695-e3ea5e16d3e6.png",
        "U7 Pro",
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
    "USW-Lite-8-PoE": (
        "https://cdn.ecomm.ui.com/products/75c44878-4e73-446e-8e86-f207db6b2b7c/"
        "53b8b06b-69c7-424f-bb81-2f8405356c65.png",
        "Switch Lite 8 PoE",
    ),
    "USW-Lite-16-PoE": (
        "https://cdn.ecomm.ui.com/products/e726eace-a772-4f12-bfad-c68baf20e51f/"
        "9ecfc657-5e31-4135-89b5-46b3537b35fc.png",
        "Switch Lite 16 PoE",
    ),
    "USW-Pro-24-PoE": (
        "https://cdn.ecomm.ui.com/products/5b69cdb5-e7ea-44e6-ae16-8714339038fb/"
        "18d39964-78e7-45f9-874d-e331f1408730.png",
        "Switch Pro 24 PoE",
    ),
    "USW-24-PoE": (
        "https://cdn.ecomm.ui.com/products/467359c4-e5c3-487b-ae00-f6b7de29c6fc/"
        "1fd41f67-8fd9-4689-989e-c03b43217e3a.png",
        "Switch 24 PoE",
    ),
    "USW-Ultra": (
        "https://cdn.ecomm.ui.com/products/d4e5408e-e2b4-4b32-b9d6-efdde2bbaaf3/"
        "69808d5d-ba9c-4198-b3e9-749bbb02582c.png",
        "Switch Ultra",
    ),
    "USW-Enterprise-24-PoE": (
        "https://cdn.ecomm.ui.com/products/9f693a84-9dcb-452f-889a-faba29ac4b73/"
        "5fe1f270-b8f9-4076-8cf3-805bea605720.png",
        "Switch Enterprise 24 PoE",
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
    # ── API model codes (so raw codes also get display names) ────
    "USF5P": "Switch Flex",
    "USMINI": "Switch Flex Mini",
    "USMINI2": "Switch Flex Mini",
    "USM8P": "Switch Ultra",
    "USL8LP": "Switch Lite 8 PoE",
    "USL16LP": "Switch Lite 16 PoE",
    "UAP6MP": "U6 Pro",
    "UAL6": "U6 Lite",
    "UALR6": "U6 LR",
    "U6ENT": "U6 Enterprise",
    "U7PRO": "U7 Pro",
    "UGW3": "Security Gateway",
    "UGW4": "Security Gateway Pro",
    "UDRULT": "Cloud Gateway Ultra",
    "UXGPRO": "Next-Gen Gateway Pro",
    "UDMPROSE": "Dream Machine SE",
}

# ---------------------------------------------------------------------------
# Alternative model name mappings
# ---------------------------------------------------------------------------
# The API sometimes returns different variants of the same model string.

MODEL_ALIASES: dict[str, str] = {
    # ── Gateways (API model code → our canonical key) ────────────
    "UDMPROSE": "UDMSE",               # API code for Dream Machine SE
    "UDM-Pro": "UDMPRO",
    "UDM-SE": "UDMSE",
    "UDM-Pro-Max": "UDMPROMAXHD",
    "UDM Pro": "UDMPRO",
    "UDM SE": "UDMSE",
    "UDM Pro Max": "UDMPROMAXHD",
    "UDMENT": "UDMPROMAXHD",            # Enterprise Fortress Gateway
    "UCG Ultra": "UCG-Ultra",
    "UDRULT": "UCG-Ultra",              # API code for Cloud Gateway Ultra
    "UXG Pro": "UXG-Pro",
    "UXGPRO": "UXG-Pro",               # API code
    "UXG": "UXG-Lite",                  # API code for Next-Gen Gateway Lite
    "UXGB": "UXG-Enterprise",           # API code
    "UXG Enterprise": "UXG-Enterprise",
    "UXG Lite": "UXG-Lite",
    "UGW3": "USG",                      # API code for Security Gateway
    "UGW4": "USG-Pro-4",               # API code for Security Gateway Pro
    # ── Access Points (API model code → our canonical key) ───────
    "UAP6MP": "U6-Pro",                 # API code for U6 Pro
    "UAL6": "U6-Lite",                  # API code for U6 Lite
    "UALR6": "U6-LR",                  # API code for U6 LR
    "UALR6v2": "U6-LR",
    "UALR6v3": "U6-LR",
    "U6ENT": "U6-Enterprise",           # API code
    "U6IW": "U6-IW",                    # API code
    "UAE6": "U6-Extender",              # API code
    "U6EXT": "U6-Extender",
    "UAM6": "U6-Mesh",                  # API code
    "U6M": "U6-Mesh",
    "UAIW6": "U6-IW",
    "U7PRO": "U7-Pro",                  # API code
    "U7ENT": "U7-Enterprise",
    "G7LR": "U7-LR",
    "U7P": "U7-Pro",
    "U7PG2": "UAP-AC-Pro",             # Legacy AP (AC Pro Gen2)
    "U7HD": "UAP-nanoHD",
    "U7NHD": "UAP-nanoHD",
    "U7LR": "UAP-AC-LR",
    "U7LT": "UAP-AC-Lite",
    "U7E": "UAP-AC-LR",
    "U7Ev2": "UAP-AC-LR",
    "UFLHD": "UAP-FlexHD",
    "U7IW": "UAP-AC-IW",
    "U7IWP": "UAP-AC-IW",
    "U7MSH": "UAP-AC-M",
    "U7MP": "UAP-AC-M-Pro",
    # Pretty name variants
    "U6 Pro": "U6-Pro",
    "U6 LR": "U6-LR",
    "U6 Lite": "U6-Lite",
    "U6 Enterprise": "U6-Enterprise",
    "U6 Mesh": "U6-Mesh",
    "U6 IW": "U6-IW",
    "U6 Extender": "U6-Extender",
    "U7 Pro": "U7-Pro",
    "U7 Pro Max": "U7-Pro-Max",
    "U7 Outdoor": "U7-Outdoor",
    # ── Switches (API model code → our canonical key) ────────────
    "USF5P": "USW-Flex",                # API code for Switch Flex
    "USMINI": "USW-Flex-Mini",          # API code for Switch Flex Mini
    "USMINI2": "USW-Flex-Mini",         # Gen2
    "USM8P": "USW-Ultra",               # API code for Switch Ultra
    "USM8P60": "USW-Ultra",
    "USM8P210": "USW-Ultra",
    "USL8LP": "USW-Lite-8-PoE",         # API code
    "USL8LPB": "USW-Lite-8-PoE",
    "USL16LP": "USW-Lite-16-PoE",       # API code
    "USL16LPB": "USW-Lite-16-PoE",
    "USL24P": "USW-24-PoE",             # API code
    "USL24PB": "USW-24-PoE",
    "USL48P": "USW-48-PoE",             # API code
    "USL48PB": "USW-48-PoE",
    "US24PRO": "USW-Pro-24-PoE",        # API code
    "US48PRO": "USW-Pro-48-PoE",        # API code
    "US624P": "USW-Enterprise-24-PoE",  # API code
    "US648P": "USW-Enterprise-48-PoE",  # API code
    "USL8A": "USW-Aggregation",         # API code
    "USAGGPRO": "USW-Aggregation",
    "USPM24P": "USW-Pro-Max-24-PoE",    # API code
    "USPM48P": "USW-Pro-Max-48-PoE",    # API code
    "USFXG": "USW-Flex-XG",
    # Pretty name variants
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
    # 1. Direct match in image map (highest priority)
    if model in DEVICE_IMAGE_MAP:
        return model
    # 2. Check aliases BEFORE display names (aliases point to image map keys)
    canonical = MODEL_ALIASES.get(model)
    if canonical:
        return canonical
    # 3. Direct match in display names
    if model in DISPLAY_NAMES:
        return model
    # 4. Case-insensitive fallback
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
