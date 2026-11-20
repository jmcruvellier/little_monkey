"""Adds config flow for Ecojoko."""
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME, UnitOfTime
from homeassistant.helpers import selector
from homeassistant.helpers.selector import NumberSelectorMode
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.translation import async_get_translations

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
    CONF_USE_TEMPHUM_FEATURE,
    CONF_USE_PROD_FEATURE,
    CONF_REMOVED_BANDS,
    CONF_TARIFF_BANDS,
    LOGGER,
    SENSOR_GROUP_OPTIONS,
)
from .tariff import (
    KNOWN_BANDS,
    NO_CATEGORY,
    OFF_PEAK,
    PEAK,
    has_sensor,
    new_band,
)
from .utils import account_unique_id

if TYPE_CHECKING:
    # Only for the annotations: this type exists since Home Assistant 2024.4
    from homeassistant.config_entries import ConfigFlowResult

PASSWORD_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)
CATEGORY_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[OFF_PEAK, PEAK, NO_CATEGORY],
        translation_key="category",
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)
# Settings of the last screen
SETTINGS_KEYS = (
    CONF_USE_PROD_FEATURE, CONF_USE_TEMPHUM_FEATURE, *SENSOR_GROUP_OPTIONS, POLL_INTERVAL)
# Suffix of the field of the category of a band
CATEGORY_SUFFIX = " – HC/HP"


def _account_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    """Return the schema of the first screen: the ecojoko account."""
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): cv.string,
            vol.Required(
                CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Required(
                CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")
            ): PASSWORD_SELECTOR,
        }
    )


def _settings_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    """Return the schema of the last screen: the other sensors and the poll."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_USE_PROD_FEATURE,
                default=defaults.get(CONF_USE_PROD_FEATURE, False),
            ): cv.boolean,
            vol.Optional(
                CONF_USE_TEMPHUM_FEATURE,
                default=defaults.get(CONF_USE_TEMPHUM_FEATURE, False),
            ): cv.boolean,
            # The groups of sensors of 2.0.0, off by default, after the
            # options of the earlier versions
            **{
                vol.Optional(option, default=defaults.get(option, False)): cv.boolean
                for option in SENSOR_GROUP_OPTIONS
            },
            vol.Required(
                POLL_INTERVAL,
                default=defaults.get(POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement=UnitOfTime.SECONDS,
                    min=3,
                    max=60,
                ),
            ),
        }
    )


def _account_of_another_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry, username: str
) -> bool:
    """Tell whether an ecojoko account is already the one of another entry."""
    account = account_unique_id(username)
    return any(
        other.entry_id != entry.entry_id
        and account_unique_id(other.data.get(CONF_USERNAME, "")) == account
        for other in hass.config_entries.async_entries(DOMAIN)
    )


def _name_errors(user_input: Mapping[str, Any]) -> dict[str, str]:
    """Return the form errors of the name, which names the device."""
    if not str(user_input.get(CONF_NAME) or "").strip():
        return {CONF_NAME: "name_required"}
    return {}


async def _async_validate(
    hass: HomeAssistant,
    data: Mapping[str, Any],
    check_gateway: bool = False,
    discover: bool = False,
) -> tuple[dict[str, str], dict | None, dict, bool]:
    """Log in to ecojoko and, if asked, read the contract and its bands.

    Return the form errors (empty if it worked), the active contract, its
    tariff bands {id: label}, and whether these bands are complete: the
    contract and every week of its statistics were read.
    """
    # A session used for this check only, released as soon as it is done
    session = async_create_clientsession(hass, auto_cleanup=False)
    client = LittleMonkeyApiClient(
        username=data.get(CONF_USERNAME, ""),
        password=data.get(CONF_PASSWORD, ""),
        poll_interval=data.get(POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        use_hchp=False,
        use_temphum=False,
        use_prod=False,
        session=session,
    )
    contract, bands = None, {}
    try:
        await client.async_get_cookiesdata()
        if check_gateway or discover:
            await client.async_get_gatewaydata()
        if discover:
            contract, bands = await client.async_get_tariff_setup()
    except LittleMonkeyApiClientAuthenticationError as exception:
        LOGGER.warning(exception)
        return {"base": "auth"}, None, {}, False
    except LittleMonkeyApiClientCommunicationError as exception:
        LOGGER.error(exception)
        return {"base": "connection"}, None, {}, False
    except LittleMonkeyApiClientError as exception:
        LOGGER.exception(exception)
        return {"base": "unknown"}, None, {}, False
    finally:
        session.detach()
    complete = contract is not None and not client.tariff_weeks_missed
    return {}, contract, bands, complete


def merge_bands(configured: list, found: dict, complete: bool, removed=()) -> list:
    """Return the bands to show: the ones found, with their saved settings.

    A band configured before keeps its key, name and category. A band no
    longer found (previous contract) is dropped, unless the bands found are
    not complete: the contract or a week of its statistics was not read,
    and a band missing from them may still be in the contract. A band
    removed by the user is not shown, even when it is found.
    """
    saved = {band["id"]: band for band in configured}
    bands = []
    for band_id, label in found.items():
        if band_id in removed:
            continue
        band = dict(saved.get(band_id) or new_band(band_id, label))
        band["label"] = label
        bands.append(band)
    if not complete:
        bands += [band for band_id, band in saved.items() if band_id not in found]
    return bands


def _band_fields(bands: list) -> list:
    """Return the fields of each band: (band, name field, category field).

    The fields are named after the label of the band, shown as it is: the
    bands depend on the contract and have no translation.
    """
    fields, used = [], set()
    for band in bands:
        label = band.get("label") or f"#{band['id']}"
        if label in used:
            label = f"{label} (#{band['id']})"
        used.add(label)
        name_field = label if has_sensor(band) else None
        fields.append((band, name_field, label + CATEGORY_SUFFIX))
    return fields


async def _async_default_names(hass: HomeAssistant, bands: list) -> dict:
    """Return the name shown by default for the sensor of each band.

    A known sensor keeps its translated name, another band takes its label.
    """
    translations = await async_get_translations(
        hass, hass.config.language, "entity", [DOMAIN])
    names = {}
    for band in bands:
        translated = translations.get(
            f"component.{DOMAIN}.entity.sensor.{band['key']}.name")
        names[band["id"]] = translated or band.get("label")
    return names


class _BandsSteps:
    """Screens shared by the setup and the options: bands, then settings."""

    _contract: dict | None = None
    _bands: list = []
    _removed: dict = {}
    _kept_removed: list = []
    _default_names: dict = {}

    def _init_bands(
        self, configured: list, contract, found: dict, complete: bool, removed=()
    ) -> None:
        """Keep the contract, the bands to show and the removed ones still found.

        A band removed but no longer found is forgotten: if ecojoko gives
        it again, it is reported as missing like any new band. When the
        bands found are not complete, it is kept removed instead.
        """
        self._contract = contract
        self._bands = merge_bands(configured, found, complete, removed)
        self._removed = {
            band_id: label for band_id, label in found.items() if band_id in removed}
        self._kept_removed = [] if complete else [
            band_id for band_id in removed if band_id not in found]

    def _removable(self) -> dict:
        """Return the bands that can be removed {id as text: label}."""
        labels = {band["id"]: band.get("label") or f"#{band['id']}" for band in self._bands}
        labels.update(self._removed)
        return {str(band_id): label for band_id, label in sorted(labels.items())}

    def _contract_text(self) -> str:
        """Return the contract as shown to the user."""
        contract = self._contract or {}
        parts = [contract.get("supplier_name"), contract.get("offer_name")]
        return " – ".join(str(part) for part in parts if part) or "?"

    async def _async_bands_form(self, step_id: str, use_hchp: bool):
        """Show the bands found, with a name and a category for each."""
        self._default_names = await _async_default_names(self.hass, self._bands)
        schema = {
            vol.Optional(CONF_USE_HCHP_FEATURE, default=use_hchp): cv.boolean,
        }
        for band, name_field, category_field in _band_fields(self._bands):
            if name_field is not None:
                schema[vol.Optional(
                    name_field,
                    default=band.get("name") or self._default_names[band["id"]],
                )] = cv.string
            schema[vol.Required(
                category_field, default=band.get("category") or NO_CATEGORY
            )] = CATEGORY_SELECTOR
        # Bands to remove: those of a previous contract that ecojoko still
        # gives, for instance. The ones removed before stay checked
        removable = self._removable()
        if removable:
            schema[vol.Optional(
                CONF_REMOVED_BANDS,
                default=[str(band_id) for band_id in self._removed],
            )] = selector.SelectSelector(selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value=value, label=label)
                    for value, label in removable.items()],
                multiple=True,
                mode=selector.SelectSelectorMode.LIST,
            ))
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(schema),
            description_placeholders={"contract": self._contract_text()},
        )

    def _read_bands(self, user_input: Mapping[str, Any]) -> tuple[list, list]:
        """Return the bands with the names and categories chosen, and the removed ids."""
        removed = sorted(
            int(value) for value in user_input.get(CONF_REMOVED_BANDS) or []
            if value in self._removable())
        bands = []
        for band, name_field, category_field in _band_fields(self._bands):
            if band["id"] in removed:
                continue
            chosen = {key: band[key] for key in ("id", "label", "key")}
            name = None
            if name_field is not None:
                name = str(user_input.get(name_field) or "").strip()
                default = self._default_names.get(band["id"])
                if not name:
                    name = default
                # The translated name of a known sensor is not saved: it
                # keeps following the language of Home Assistant. Another
                # band keeps its name if ecojoko renames it
                if band["id"] in KNOWN_BANDS and name == default:
                    name = None
            chosen["name"] = name
            category = user_input.get(category_field)
            chosen["category"] = category if category in (OFF_PEAK, PEAK) else None
            bands.append(chosen)
        # A band removed before and no longer checked comes back with its
        # default settings
        bands += [
            new_band(band_id, label) for band_id, label in self._removed.items()
            if band_id not in removed]
        return bands, removed

    def _save_bands(self, user_input: Mapping[str, Any]) -> None:
        """Keep the HC/HP option, the bands and the removed ones chosen."""
        self._data[CONF_USE_HCHP_FEATURE] = (
            user_input.get(CONF_USE_HCHP_FEATURE) is True)
        self._data[CONF_TARIFF_BANDS], removed = self._read_bands(user_input)
        removed = sorted({*removed, *self._kept_removed})
        # Saved only when there are some: most entries never remove a band
        if removed:
            self._data[CONF_REMOVED_BANDS] = removed
        else:
            self._data.pop(CONF_REMOVED_BANDS, None)


class EcojokoFlowHandler(_BandsSteps, config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Ecojoko: account, tariff bands, then settings."""

    # Version 2: unique ids based on the config entry (see async_migrate_entry)
    # Version 3: tariff bands instead of the Tempo option
    # Version 3.2: poll interval of at least 30 s. A minor version: an
    # earlier 2.0.0 version still loads the entry
    VERSION = 3
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Init EcojokoFlowHandler."""
        self._reauth_entry: config_entries.ConfigEntry | None = None
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> ConfigFlowResult:
        """Ask for the ecojoko account, then read its contract."""
        _errors = {}
        if user_input is not None:
            # The same ecojoko account cannot be added twice
            await self.async_set_unique_id(
                account_unique_id(user_input[CONF_USERNAME])
            )
            self._abort_if_unique_id_configured()
            _errors = _name_errors(user_input)
            if not _errors:
                _errors, contract, found, complete = await _async_validate(
                    self.hass, user_input, discover=True
                )
            if not _errors:
                self._data = dict(user_input)
                self._init_bands([], contract, found, complete)
                return await self.async_step_bands()

        return self.async_show_form(
            step_id="user",
            # Keep what the user typed when the form is shown again
            data_schema=self.add_suggested_values_to_schema(
                _account_schema({}), user_input
            ),
            errors=_errors,
        )

    async def async_step_bands(
        self,
        user_input: dict | None = None,
    ) -> ConfigFlowResult:
        """Show the tariff bands of the contract."""
        if user_input is not None:
            self._save_bands(user_input)
            return await self.async_step_settings()
        return await self._async_bands_form("bands", use_hchp=True)

    async def async_step_settings(
        self,
        user_input: dict | None = None,
    ) -> ConfigFlowResult:
        """Ask for the other sensors and the poll interval."""
        if user_input is not None:
            self._data.update(
                {key: user_input.get(key, False) for key in SETTINGS_KEYS})
            return self.async_create_entry(
                title=self._data[CONF_USERNAME],
                data=self._data,
            )
        return self.async_show_form(
            step_id="settings",
            data_schema=_settings_schema({}),
        )

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],
    ) -> ConfigFlowResult:
        """Handle a flow started because ecojoko rejected the credentials."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict | None = None,
    ) -> ConfigFlowResult:
        """Ask for the new password and check it."""
        entry = self._reauth_entry
        _errors = {}
        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            _errors, _contract, _found, _complete = await _async_validate(self.hass, data)
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
                {vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR}
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


class EcojokoOptionsFlowHandler(_BandsSteps, config_entries.OptionsFlow):
    """Options flow for Ecojoko: the same screens as the setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the Ecojoko OptionsFlow."""
        self._config_entry = config_entry
        self._data: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the ecojoko account, then read its contract again."""
        _errors = {}
        if user_input is not None:
            _errors = _name_errors(user_input)
            if not _errors and _account_of_another_entry(
                self.hass, self._config_entry, user_input[CONF_USERNAME]
            ):
                # As the setup, which refuses the same account twice
                _errors = {"base": "already_configured"}
            if not _errors:
                _errors, contract, found, complete = await _async_validate(
                    self.hass, user_input, discover=True
                )
            if not _errors:
                self._data = {**self._config_entry.data, **user_input}
                self._init_bands(
                    self._config_entry.data.get(CONF_TARIFF_BANDS) or [],
                    contract,
                    found,
                    complete,
                    self._config_entry.data.get(CONF_REMOVED_BANDS) or [],
                )
                return await self.async_step_bands()

        return self.async_show_form(
            step_id="init",
            # Keep what the user typed when the form is shown again
            data_schema=self.add_suggested_values_to_schema(
                _account_schema(self._config_entry.data), user_input
            ),
            errors=_errors,
        )

    async def async_step_bands(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the tariff bands of the contract."""
        if user_input is not None:
            self._save_bands(user_input)
            return await self.async_step_settings()
        return await self._async_bands_form(
            "bands",
            use_hchp=self._config_entry.data.get(CONF_USE_HCHP_FEATURE) is True,
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the other sensors and the poll interval, then save."""
        if user_input is not None:
            self._data.update(
                {key: user_input.get(key, False) for key in SETTINGS_KEYS})
            # The title of the entry is the username it was created with: it
            # follows a new username, unless the user gave it another title.
            # The entities are identified by the entry: they do not change
            title = self._config_entry.title
            if title == self._config_entry.data.get(CONF_USERNAME):
                title = self._data[CONF_USERNAME]
            # All the settings are kept in the entry data. Data and options
            # are saved together: the entry is reloaded once, and
            # async_create_entry below changes nothing more
            self.hass.config_entries.async_update_entry(
                entry=self._config_entry,
                data=self._data,
                options={},
                title=title,
            )
            return self.async_create_entry(
                title=title,
                data={}
            )
        return self.async_show_form(
            step_id="settings",
            data_schema=_settings_schema(self._config_entry.data),
        )
