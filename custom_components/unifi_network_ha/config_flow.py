"""Config flow for the UniFi Network HA integration."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api.auth import ApiKeyAuth, CredentialAuth
from .api.client import UniFiApiClient, UniFiAuthError, UniFiConnectionError
from .api.cloud import CloudApi, CloudApiAuthError, CloudApiConnectionError
from .api.local_legacy import LocalLegacyApi
from .const import (
    CONF_API_KEY,
    CONF_AUTH_METHOD,
    CONF_CLIENT_HEARTBEAT,
    CONF_CLOUD_API_KEY,
    CONF_CLOUD_ENABLED,
    CONF_ENABLE_ALARMS,
    CONF_ENABLE_CLIENT_CONTROLS,
    CONF_ENABLE_CLOUD,
    CONF_ENABLE_DEVICE_CONTROLS,
    CONF_ENABLE_DEVICE_SENSORS,
    CONF_ENABLE_DPI,
    CONF_ENABLE_PER_CLIENT_SENSORS,
    CONF_ENABLE_PROTECT,
    CONF_ENABLE_VPN,
    CONF_ENABLE_WAN_MONITORING,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SITE,
    CONF_SSID_FILTER,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_WIRED,
    CONF_TRACK_WIRELESS,
    CONF_UPDATE_INTERVAL_ALARMS,
    CONF_UPDATE_INTERVAL_CLIENTS,
    CONF_UPDATE_INTERVAL_CLOUD,
    CONF_UPDATE_INTERVAL_DEVICES,
    CONF_UPDATE_INTERVAL_DPI,
    CONF_UPDATE_INTERVAL_HEALTH,
    CONF_UPDATE_INTERVAL_WAN_RATE,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DEFAULT_CLIENT_HEARTBEAT,
    DEFAULT_PORT,
    DEFAULT_SITE,
    DEFAULT_TRACK_CLIENTS,
    DEFAULT_TRACK_WIRED,
    DEFAULT_TRACK_WIRELESS,
    DEFAULT_UPDATE_INTERVAL_ALARMS,
    DEFAULT_UPDATE_INTERVAL_CLIENTS,
    DEFAULT_UPDATE_INTERVAL_CLOUD,
    DEFAULT_UPDATE_INTERVAL_DEVICES,
    DEFAULT_UPDATE_INTERVAL_DPI,
    DEFAULT_UPDATE_INTERVAL_HEALTH,
    DEFAULT_UPDATE_INTERVAL_WAN_RATE,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    AuthMethod,
)

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Form schemas
# ---------------------------------------------------------------------------

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=65535,
                step=1,
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Required(CONF_SITE, default=DEFAULT_SITE): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_AUTH_METHOD, default=AuthMethod.API_KEY): SelectSelector(
            SelectSelectorConfig(
                options=[
                    {"value": AuthMethod.API_KEY, "label": "API Key"},
                    {"value": AuthMethod.CREDENTIALS, "label": "Username & Password"},
                ],
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): BooleanSelector(),
    }
)

STEP_API_KEY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

STEP_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

STEP_CLOUD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLOUD_ENABLED, default=False): BooleanSelector(),
        vol.Optional(CONF_CLOUD_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

STEP_FEATURES_SCHEMA = vol.Schema(
    {
        # Group 1 — Network Monitoring
        vol.Required(
            CONF_ENABLE_WAN_MONITORING, default=True
        ): BooleanSelector(),
        vol.Required(
            CONF_TRACK_CLIENTS, default=DEFAULT_TRACK_CLIENTS
        ): BooleanSelector(),
        vol.Required(
            CONF_ENABLE_DEVICE_SENSORS, default=True
        ): BooleanSelector(),
        # Group 2 — Security & Analysis
        vol.Required(CONF_ENABLE_ALARMS, default=True): BooleanSelector(),
        vol.Required(CONF_ENABLE_DPI, default=False): BooleanSelector(),
        vol.Required(CONF_ENABLE_VPN, default=True): BooleanSelector(),
        # Group 3 — Protect / NVR
        vol.Required(CONF_ENABLE_PROTECT, default=False): BooleanSelector(),
        # Group 4 — Advanced
        vol.Required(CONF_ENABLE_PER_CLIENT_SENSORS, default=False): BooleanSelector(),
        vol.Required(CONF_ENABLE_CLIENT_CONTROLS, default=True): BooleanSelector(),
        vol.Required(CONF_ENABLE_DEVICE_CONTROLS, default=True): BooleanSelector(),
    }
)


# ---------------------------------------------------------------------------
# Config flow
# ---------------------------------------------------------------------------


class UniFiNetworkHAConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UniFi Network HA."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the config flow."""
        self._data: dict[str, Any] = {}
        self._sites: list[dict] = []

    # ------------------------------------------------------------------
    # Step 1 — Connection details
    # ------------------------------------------------------------------

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial user step (host, port, site, auth method)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Normalise port to int (NumberSelector returns float)
            user_input[CONF_PORT] = int(user_input[CONF_PORT])

            self._data.update(user_input)

            if user_input[CONF_AUTH_METHOD] == AuthMethod.API_KEY:
                return await self.async_step_api_key()
            return await self.async_step_credentials()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 2a — API key authentication
    # ------------------------------------------------------------------

    async def async_step_api_key(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle API key entry and validation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)

            err, sites = await self._test_connection(self._data)
            if err is not None:
                errors.update(err)
            else:
                self._sites = sites
                # Skip cloud step — it can be enabled later in options
                self._data[CONF_CLOUD_ENABLED] = False
                return await self.async_step_site()

        return self.async_show_form(
            step_id="api_key",
            data_schema=STEP_API_KEY_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 2b — Credential authentication
    # ------------------------------------------------------------------

    async def async_step_credentials(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle username/password entry and validation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)

            err, sites = await self._test_connection(self._data)
            if err is not None:
                errors.update(err)
            else:
                self._sites = sites
                # Skip cloud step — it can be enabled later in options
                self._data[CONF_CLOUD_ENABLED] = False
                return await self.async_step_site()

        return self.async_show_form(
            step_id="credentials",
            data_schema=STEP_CREDENTIALS_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 3 — Cloud API (optional)
    # ------------------------------------------------------------------

    async def async_step_cloud(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle optional cloud API configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            cloud_enabled = user_input.get(CONF_CLOUD_ENABLED, False)
            cloud_key = user_input.get(CONF_CLOUD_API_KEY, "")

            if cloud_enabled and cloud_key:
                # Validate the cloud API key
                err = await self._test_cloud_connection(cloud_key)
                if err is not None:
                    errors.update(err)

            if not errors:
                self._data[CONF_CLOUD_ENABLED] = cloud_enabled
                if cloud_enabled and cloud_key:
                    self._data[CONF_CLOUD_API_KEY] = cloud_key
                else:
                    self._data[CONF_CLOUD_ENABLED] = False
                    self._data.pop(CONF_CLOUD_API_KEY, None)

                return await self.async_step_site()

        return self.async_show_form(
            step_id="cloud",
            data_schema=STEP_CLOUD_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 4 — Site selection
    # ------------------------------------------------------------------

    async def async_step_site(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle site selection from discovered sites."""
        errors: dict[str, str] = {}

        if not self._sites:
            # No sites found — use the site from step 1 and move on
            return await self.async_step_features()

        # Build a mapping of site name -> description for the selector
        site_options: list[dict[str, str]] = []
        for site in self._sites:
            name = site.get("name", "default")
            desc = site.get("desc", name)
            site_options.append({"value": name, "label": desc})

        # Auto-select if only one site
        if len(site_options) == 1:
            self._data[CONF_SITE] = site_options[0]["value"]
            return await self.async_step_features()

        if user_input is not None:
            self._data[CONF_SITE] = user_input[CONF_SITE]
            return await self.async_step_features()

        site_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SITE,
                    default=self._data.get(CONF_SITE, DEFAULT_SITE),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=site_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="site",
            data_schema=site_schema,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 5 — Feature toggles
    # ------------------------------------------------------------------

    async def async_step_features(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle feature toggle selection and create the config entry."""
        if user_input is not None:
            self._data.update(user_input)

            # Also store the cloud feature flag based on earlier cloud step
            self._data[CONF_ENABLE_CLOUD] = self._data.get(
                CONF_CLOUD_ENABLED, False
            )

            # Set unique ID and check for duplicates
            unique_id = (
                f"{self._data[CONF_HOST]}:"
                f"{self._data[CONF_PORT]}:"
                f"{self._data[CONF_SITE]}"
            )
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            title = (
                f"UniFi ({self._data[CONF_HOST]}:{self._data[CONF_PORT]})"
            )

            return self.async_create_entry(title=title, data=self._data)

        return self.async_show_form(
            step_id="features",
            data_schema=STEP_FEATURES_SCHEMA,
        )

    # ------------------------------------------------------------------
    # Reauth flow
    # ------------------------------------------------------------------

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],
    ) -> ConfigFlowResult:
        """Handle reauth when credentials expire."""
        self._data = dict(entry_data)
        auth_method = self._data.get(CONF_AUTH_METHOD, AuthMethod.CREDENTIALS)

        if auth_method == AuthMethod.API_KEY:
            return await self.async_step_reauth_api_key()
        return await self.async_step_reauth_credentials()

    async def async_step_reauth_api_key(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle re-authentication for API key auth."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data[CONF_API_KEY] = user_input[CONF_API_KEY]

            err, _ = await self._test_connection(self._data)
            if err is not None:
                errors.update(err)
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )

        return self.async_show_form(
            step_id="reauth_api_key",
            data_schema=STEP_API_KEY_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth_credentials(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle re-authentication for credential auth."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data[CONF_USERNAME] = user_input[CONF_USERNAME]
            self._data[CONF_PASSWORD] = user_input[CONF_PASSWORD]

            err, _ = await self._test_connection(self._data)
            if err is not None:
                errors.update(err)
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="reauth_credentials",
            data_schema=STEP_CREDENTIALS_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    async def _test_connection(
        self,
        data: dict[str, Any],
    ) -> tuple[dict[str, str] | None, list[dict]]:
        """Test connection and return (errors, sites).

        Creates a temporary connection using the HA-managed aiohttp session,
        authenticates, and attempts to fetch the list of sites.

        Returns:
            A tuple of ``(None, sites_list)`` on success, or
            ``({"base": "error_key"}, [])`` on failure.
        """
        session = aiohttp_client.async_get_clientsession(self.hass)

        auth_method = data.get(CONF_AUTH_METHOD, AuthMethod.CREDENTIALS)
        if auth_method == AuthMethod.API_KEY:
            api_key = data.get(CONF_API_KEY, "")
            if not api_key:
                return {"base": "invalid_api_key"}, []
            auth = ApiKeyAuth(api_key)
        else:
            username = data.get(CONF_USERNAME, "")
            password = data.get(CONF_PASSWORD, "")
            if not username or not password:
                return {"base": "invalid_auth"}, []
            auth = CredentialAuth(username, password)

        client = UniFiApiClient(
            host=data[CONF_HOST],
            port=data[CONF_PORT],
            site=data.get(CONF_SITE, DEFAULT_SITE),
            auth=auth,
            verify_ssl=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            session=session,
        )

        try:
            # For credential auth we need an explicit login step.
            if auth_method == AuthMethod.CREDENTIALS:
                await client.login()

            legacy = LocalLegacyApi(client)
            sites = await legacy.get_sites()
            return None, sites

        except UniFiAuthError:
            _LOGGER.debug("Authentication failed during config flow validation")
            error_key = (
                "invalid_api_key"
                if auth_method == AuthMethod.API_KEY
                else "invalid_auth"
            )
            return {"base": error_key}, []
        except UniFiConnectionError:
            _LOGGER.debug("Connection failed during config flow validation")
            return {"base": "cannot_connect"}, []
        except Exception:
            _LOGGER.exception("Unexpected error during config flow validation")
            return {"base": "unknown"}, []

    async def _test_cloud_connection(
        self,
        cloud_api_key: str,
    ) -> dict[str, str] | None:
        """Validate a cloud API key by fetching hosts.

        Returns:
            ``None`` on success, or ``{"base": "error_key"}`` on failure.
        """
        session = aiohttp_client.async_get_clientsession(self.hass)
        cloud = CloudApi(api_key=cloud_api_key, session=session)

        try:
            await cloud.get_hosts()
            return None
        except CloudApiAuthError:
            _LOGGER.debug("Cloud API key validation failed")
            return {"base": "invalid_api_key"}
        except CloudApiConnectionError:
            _LOGGER.debug("Cloud API connection failed")
            return {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected error validating cloud API key")
            return {"base": "unknown"}

    # ------------------------------------------------------------------
    # Options flow registration
    # ------------------------------------------------------------------

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> UniFiNetworkHAOptionsFlow:
        """Return the options flow handler."""
        return UniFiNetworkHAOptionsFlow(config_entry)


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------


class UniFiNetworkHAOptionsFlow(OptionsFlow):
    """Handle options for UniFi Network HA."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialise the options flow."""
        self._config_entry = config_entry
        self._options: dict[str, Any] = dict(config_entry.options)

    # ------------------------------------------------------------------
    # Step 1 — Feature toggles
    # ------------------------------------------------------------------

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """First options step — feature toggles."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_intervals()

        current = self._options
        schema = vol.Schema(
            {
                # ── Group 1 — Network Monitoring (default: on) ────────
                vol.Required(
                    CONF_ENABLE_WAN_MONITORING,
                    default=current.get(CONF_ENABLE_WAN_MONITORING, True),
                ): BooleanSelector(),
                vol.Required(
                    CONF_TRACK_CLIENTS,
                    default=current.get(CONF_TRACK_CLIENTS, DEFAULT_TRACK_CLIENTS),
                ): BooleanSelector(),
                vol.Required(
                    CONF_ENABLE_DEVICE_SENSORS,
                    default=current.get(CONF_ENABLE_DEVICE_SENSORS, True),
                ): BooleanSelector(),
                # ── Group 2 — Security & Analysis ─────────────────────
                vol.Required(
                    CONF_ENABLE_ALARMS,
                    default=current.get(CONF_ENABLE_ALARMS, True),
                ): BooleanSelector(),
                vol.Required(
                    CONF_ENABLE_DPI,
                    default=current.get(CONF_ENABLE_DPI, False),
                ): BooleanSelector(),
                vol.Required(
                    CONF_ENABLE_VPN,
                    default=current.get(CONF_ENABLE_VPN, True),
                ): BooleanSelector(),
                # ── Group 3 — Protect / NVR ──────────────────────────
                vol.Required(
                    CONF_ENABLE_PROTECT,
                    default=current.get(CONF_ENABLE_PROTECT, False),
                ): BooleanSelector(),
                # ── Group 4 — Advanced ────────────────────────────────
                vol.Required(
                    CONF_ENABLE_PER_CLIENT_SENSORS,
                    default=current.get(CONF_ENABLE_PER_CLIENT_SENSORS, False),
                ): BooleanSelector(),
                vol.Required(
                    CONF_ENABLE_CLIENT_CONTROLS,
                    default=current.get(CONF_ENABLE_CLIENT_CONTROLS, True),
                ): BooleanSelector(),
                vol.Required(
                    CONF_ENABLE_DEVICE_CONTROLS,
                    default=current.get(CONF_ENABLE_DEVICE_CONTROLS, True),
                ): BooleanSelector(),
                vol.Required(
                    CONF_ENABLE_CLOUD,
                    default=current.get(CONF_ENABLE_CLOUD, False),
                ): BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )

    # ------------------------------------------------------------------
    # Step 2 — Update intervals
    # ------------------------------------------------------------------

    async def async_step_intervals(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Second options step — polling intervals."""
        if user_input is not None:
            # Normalise to int (NumberSelector returns float)
            for key, value in user_input.items():
                user_input[key] = int(value)
            self._options.update(user_input)
            return await self.async_step_client_tracking()

        current = self._options

        interval_fields: dict[vol.Required, NumberSelector] = {}
        interval_defs: list[tuple[str, int]] = [
            (CONF_UPDATE_INTERVAL_DEVICES, DEFAULT_UPDATE_INTERVAL_DEVICES),
            (CONF_UPDATE_INTERVAL_CLIENTS, DEFAULT_UPDATE_INTERVAL_CLIENTS),
            (CONF_UPDATE_INTERVAL_HEALTH, DEFAULT_UPDATE_INTERVAL_HEALTH),
            (CONF_UPDATE_INTERVAL_WAN_RATE, DEFAULT_UPDATE_INTERVAL_WAN_RATE),
            (CONF_UPDATE_INTERVAL_ALARMS, DEFAULT_UPDATE_INTERVAL_ALARMS),
            (CONF_UPDATE_INTERVAL_DPI, DEFAULT_UPDATE_INTERVAL_DPI),
            (CONF_UPDATE_INTERVAL_CLOUD, DEFAULT_UPDATE_INTERVAL_CLOUD),
        ]

        for conf_key, default_val in interval_defs:
            interval_fields[
                vol.Required(conf_key, default=current.get(conf_key, default_val))
            ] = NumberSelector(
                NumberSelectorConfig(
                    min=5,
                    max=3600,
                    step=1,
                    unit_of_measurement="seconds",
                    mode=NumberSelectorMode.BOX,
                )
            )

        return self.async_show_form(
            step_id="intervals",
            data_schema=vol.Schema(interval_fields),
        )

    # ------------------------------------------------------------------
    # Step 3 — Client tracking options
    # ------------------------------------------------------------------

    async def async_step_client_tracking(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Third options step — client tracking configuration."""
        if user_input is not None:
            # Normalise heartbeat to int
            if CONF_CLIENT_HEARTBEAT in user_input:
                user_input[CONF_CLIENT_HEARTBEAT] = int(
                    user_input[CONF_CLIENT_HEARTBEAT]
                )

            # Handle SSID filter: split comma-separated string into a list,
            # strip whitespace, and drop empty entries.
            raw_ssids = user_input.get(CONF_SSID_FILTER, "")
            if isinstance(raw_ssids, str) and raw_ssids.strip():
                user_input[CONF_SSID_FILTER] = [
                    s.strip() for s in raw_ssids.split(",") if s.strip()
                ]
            else:
                user_input[CONF_SSID_FILTER] = []

            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        current = self._options

        # Convert stored SSID list back to comma-separated string for display
        ssid_list = current.get(CONF_SSID_FILTER, [])
        ssid_default = ", ".join(ssid_list) if isinstance(ssid_list, list) else ""

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TRACK_WIRED,
                    default=current.get(CONF_TRACK_WIRED, DEFAULT_TRACK_WIRED),
                ): BooleanSelector(),
                vol.Required(
                    CONF_TRACK_WIRELESS,
                    default=current.get(CONF_TRACK_WIRELESS, DEFAULT_TRACK_WIRELESS),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_SSID_FILTER,
                    description={"suggested_value": ssid_default},
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Required(
                    CONF_CLIENT_HEARTBEAT,
                    default=current.get(
                        CONF_CLIENT_HEARTBEAT, DEFAULT_CLIENT_HEARTBEAT
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=60,
                        max=3600,
                        step=1,
                        unit_of_measurement="seconds",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="client_tracking",
            data_schema=schema,
        )
