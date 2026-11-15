"""Adds config flow for Ecojoko."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME, UnitOfTime
from homeassistant.helpers import selector
from homeassistant.helpers.selector import NumberSelectorMode
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import (
    LittleMonkeyApiClient,
    LittleMonkeyApiClientAuthenticationError,
    LittleMonkeyApiClientCommunicationError,
    LittleMonkeyApiClientError,
)
from .const import (
    DOMAIN,
    POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    CONF_USE_HCHP_FEATURE,
    CONF_USE_TEMPO_FEATURE,
    CONF_USE_TEMPHUM_FEATURE,
    CONF_USE_PROD_FEATURE,
    LOGGER
)
from .utils import account_unique_id

def _get_data_schema(config_entry: config_entries.ConfigEntry | None = None) -> vol.Schema:
    """Get a schema with default values."""
    if config_entry is None:
        return vol.Schema(
            {
                vol.Required(CONF_NAME, default=""): cv.string,
                vol.Required(CONF_USERNAME, default=""): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT
                        ),
                    ),
                vol.Required(CONF_PASSWORD, default=""): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        ),
                    ),
                vol.Optional(
                    CONF_USE_HCHP_FEATURE, default=False,
                ): cv.boolean,
                vol.Optional(
                    CONF_USE_TEMPO_FEATURE, default=False,
                ): cv.boolean,
                vol.Optional(
                    CONF_USE_PROD_FEATURE, default=False,
                ): cv.boolean,
                vol.Optional(
                    CONF_USE_TEMPHUM_FEATURE, default=False,
                ): cv.boolean,
                vol.Required(POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement=UnitOfTime.SECONDS,
                            min=3,
                            max=60
                        ),
                    ),
            }
        )
    # Default values come from config entry
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=config_entry.data.get(CONF_NAME)): cv.string,
            vol.Required(
                CONF_USERNAME, default=config_entry.data.get(CONF_USERNAME)
                ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT
                        ),
                    ),
            vol.Required(
                CONF_PASSWORD, default=config_entry.data.get(CONF_PASSWORD)
                ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        ),
                    ),
            vol.Optional(
                CONF_USE_HCHP_FEATURE, default=config_entry.data.get(CONF_USE_HCHP_FEATURE),
            ): cv.boolean,
            vol.Optional(
                CONF_USE_TEMPO_FEATURE, default=config_entry.data.get(CONF_USE_TEMPO_FEATURE),
            ): cv.boolean,
            vol.Optional(
                CONF_USE_PROD_FEATURE, default=config_entry.data.get(CONF_USE_PROD_FEATURE),
            ): cv.boolean,
            vol.Optional(
                CONF_USE_TEMPHUM_FEATURE, default=config_entry.data.get(CONF_USE_TEMPHUM_FEATURE),
            ): cv.boolean,
            vol.Required(
                POLL_INTERVAL, default=config_entry.data.get(POLL_INTERVAL)
                ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement=UnitOfTime.SECONDS,
                            min=3,
                            max=60
                        ),
                    ),
        }
    )

async def _async_validate(
    hass: HomeAssistant,
    data: Mapping[str, Any],
    check_gateway: bool = False,
) -> dict[str, str]:
    """Try to log in to ecojoko and return the form errors, empty if it worked."""
    client = LittleMonkeyApiClient(
        username=data.get(CONF_USERNAME, ""),
        password=data.get(CONF_PASSWORD, ""),
        poll_interval=data.get(POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        use_hchp=data.get(CONF_USE_HCHP_FEATURE, False),
        use_tempo=data.get(CONF_USE_TEMPO_FEATURE, False),
        use_temphum=data.get(CONF_USE_TEMPHUM_FEATURE, False),
        use_prod=data.get(CONF_USE_PROD_FEATURE, False),
        session=async_create_clientsession(hass),
    )
    try:
        await client.async_get_cookiesdata()
        if check_gateway:
            await client.async_get_gatewaydata()
    except LittleMonkeyApiClientAuthenticationError as exception:
        LOGGER.warning(exception)
        return {"base": "auth"}
    except LittleMonkeyApiClientCommunicationError as exception:
        LOGGER.error(exception)
        return {"base": "connection"}
    except LittleMonkeyApiClientError as exception:
        LOGGER.exception(exception)
        return {"base": "unknown"}
    return {}


class EcojokoFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Ecojoko."""

    # Version 2: unique ids based on the config entry (see async_migrate_entry)
    VERSION = 2

    def __init__(self) -> None:
        """Init EcojokoFlowHandler."""
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.FlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            # The same ecojoko account cannot be added twice
            await self.async_set_unique_id(
                account_unique_id(user_input[CONF_USERNAME])
            )
            self._abort_if_unique_id_configured()
            _errors = await _async_validate(self.hass, user_input)
            if not _errors:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input
                )

        return self.async_show_form(
            step_id="user",
            # Keep what the user typed when the form is shown again
            data_schema=self.add_suggested_values_to_schema(
                _get_data_schema(), user_input
            ),
            errors=_errors,
        )

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],
    ) -> config_entries.FlowResult:
        """Handle a flow started because ecojoko rejected the credentials."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict | None = None,
    ) -> config_entries.FlowResult:
        """Ask for the new password and check it."""
        entry = self._reauth_entry
        _errors = {}
        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            _errors = await _async_validate(self.hass, data)
            if not _errors:
                self.hass.config_entries.async_update_entry(entry, data=data)
                # A loaded entry is reloaded by its update listener
                if entry.state is not config_entries.ConfigEntryState.LOADED:
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(entry.entry_id)
                    )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        ),
                    ),
                }
            ),
            description_placeholders={
                "username": entry.data.get(CONF_USERNAME, "")
            },
            errors=_errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for Ecojoko."""
        return EcojokoOptionsFlowHandler(config_entry)

class EcojokoOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for Ecojoko component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the Ecojoko OptionsFlow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure options for Ecojoko."""
        _errors = {}
        if user_input is not None:
            # Nothing is saved until ecojoko has accepted the new settings
            _errors = await _async_validate(
                self.hass, user_input, check_gateway=True
            )
            if not _errors:
                # All the settings are kept in the entry data. Data and options
                # are saved together: the entry is reloaded once, and
                # async_create_entry below changes nothing more
                self.hass.config_entries.async_update_entry(
                    entry=self._config_entry,
                    data=user_input,
                    options={},
                )
                return self.async_create_entry(
                    title=self._config_entry.title,
                    data={}
                )

        return self.async_show_form(
            step_id="init",
            # Keep what the user typed when the form is shown again
            data_schema=self.add_suggested_values_to_schema(
                _get_data_schema(config_entry=self._config_entry), user_input
            ),
            errors=_errors,
        )
