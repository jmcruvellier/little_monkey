"""Adds config flow for Ecojoko."""
from __future__ import annotations

from typing import Any
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.core import callback
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
    CONF_LANG,
    DEFAULT_LANG,
    LANG_CODES,
    LOGGER
)

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
                vol.Required(
                    CONF_LANG, default=DEFAULT_LANG
                    ): selector.LanguageSelector(
                    selector.LanguageSelectorConfig(
                        languages=LANG_CODES,
                        native_name=True,
                        no_sort=True
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
            vol.Required(
                CONF_LANG, default=config_entry.options.get(CONF_LANG, DEFAULT_LANG)
                ): selector.LanguageSelector(
                selector.LanguageSelectorConfig(
                    languages=LANG_CODES,
                    native_name=True,
                    no_sort=True
                ),
            ),
        }
    )

class EcojokoFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Ecojoko."""

    VERSION = 1

    def __init__(self) -> None:
        """Init EcojokoFlowHandler."""
        self._errors: dict[str, Any] = {}

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.FlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            try:
                await self._get_cookies(
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                    poll_interval=user_input[POLL_INTERVAL],
                    use_hchp=user_input[CONF_USE_HCHP_FEATURE],
                    use_tempo=user_input[CONF_USE_TEMPO_FEATURE],
                    use_temphum=user_input[CONF_USE_TEMPHUM_FEATURE],
                    use_prod=user_input[CONF_USE_PROD_FEATURE]
                )
            except LittleMonkeyApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            except LittleMonkeyApiClientCommunicationError as exception:
                LOGGER.error(exception)
                _errors["base"] = "connection"
            except LittleMonkeyApiClientError as exception:
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                    options={ CONF_LANG: DEFAULT_LANG }
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_get_data_schema(),
            errors=_errors,
        )

    async def _get_cookies(self, username: str,
                           password: str,
                           poll_interval: int,
                           use_hchp: bool,
                           use_temphum: bool,
                           use_tempo: bool,
                           use_prod: bool) -> None:
        client = LittleMonkeyApiClient(
            username=username,
            password=password,
            poll_interval=poll_interval,
            use_hchp=use_hchp,
            use_tempo=use_tempo,
            use_temphum=use_temphum,
            use_prod=use_prod,
            session=async_create_clientsession(self.hass),
        )
        await client.async_get_cookiesdata()


    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for Met."""
        return EcojokoOptionsFlowHandler(config_entry)

class EcojokoOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for Ecojoko component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the Ecojoko OptionsFlow."""
        self._config_entry = config_entry
        self._errors: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure options for Ecojoko."""

        if user_input is not None:
            # Update config entry with data from user input
            self.hass.config_entries.async_update_entry(
                entry=self._config_entry,
                data=user_input,
                # options={ CONF_LANG: DEFAULT_LANG }
            )

            client = await self._get_cookies(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                poll_interval=user_input[POLL_INTERVAL],
                use_hchp=user_input[CONF_USE_HCHP_FEATURE],
                use_tempo=user_input[CONF_USE_TEMPO_FEATURE],
                use_temphum=user_input[CONF_USE_TEMPHUM_FEATURE],
                use_prod=user_input[CONF_USE_PROD_FEATURE],
            )

            await self._get_gateway(client)

            # TEST ONLY
            # await self._get_realtime_conso(client)
            # await self._get_kwhstat(client)

            return self.async_create_entry(
                title=self._config_entry.title,
                data=user_input
            )

        return self.async_show_form(
            step_id="init",
            data_schema=_get_data_schema(config_entry=self._config_entry),
            errors=self._errors,
        )

    async def _get_cookies(self, username: str,
                           password: str,
                           poll_interval: int,
                           use_hchp: bool,
                           use_tempo: bool,
                           use_temphum: bool,
                           use_prod: bool) -> LittleMonkeyApiClient:
        client = LittleMonkeyApiClient(
            username=username,
            password=password,
            poll_interval=poll_interval,
            use_hchp=use_hchp,
            use_tempo=use_tempo,
            use_temphum=use_temphum,
            use_prod=use_prod,
            session=async_create_clientsession(self.hass),
        )
        await client.async_get_cookiesdata()
        return client

    async def _get_gateway(self, client: LittleMonkeyApiClient) -> None:
        await client.async_get_gatewaydata()

    async def _get_realtime_conso(self, client: LittleMonkeyApiClient) -> None:
        await client.async_get_realtime_conso()

    async def _get_kwhstat(self, client: LittleMonkeyApiClient) -> None:
        await client.async_get_kwhstat()
