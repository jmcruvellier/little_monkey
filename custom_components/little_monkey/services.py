"""Services of little_monkey."""
from __future__ import annotations

from functools import partial

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api import SAVINGS_PERIODS, LittleMonkeyApiClientError, TZ
from .const import DOMAIN
from .utils import get_current_date

SERVICE_GET_SAVINGS = "get_savings"
SERVICE_GET_CONSUMPTION_ANALYSIS = "get_consumption_analysis"
SERVICE_GET_CATEGORY_HISTORY = "get_category_history"
SERVICE_GET_ACTIVATIONS = "get_activations"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_PERIOD = "period"
ATTR_DATE = "date"
ATTR_CATEGORY = "category"
ATTR_PAGE = "page"

GET_SAVINGS_SCHEMA = vol.Schema({
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Required(ATTR_PERIOD): vol.In(list(SAVINGS_PERIODS)),
    vol.Optional(ATTR_DATE): cv.date,
})
GET_CONSUMPTION_ANALYSIS_SCHEMA = GET_SAVINGS_SCHEMA
GET_CATEGORY_HISTORY_SCHEMA = vol.Schema({
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Required(ATTR_CATEGORY): vol.All(vol.Coerce(int), vol.Range(min=0)),
    vol.Optional(ATTR_DATE): cv.date,
})
GET_ACTIVATIONS_SCHEMA = vol.Schema({
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Optional(ATTR_PAGE, default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=365)),
})


def _loaded_entry(hass: HomeAssistant, entry_id: str | None):
    """Return the loaded entry asked for, or the only one."""
    entries = [
        entry for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    if entry_id is not None:
        entries = [entry for entry in entries if entry.entry_id == entry_id]
    if len(entries) == 1:
        return entries[0]
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="entry_not_found" if not entries else "entry_required",
    )


async def _async_read(hass: HomeAssistant, call: ServiceCall, read):
    """Read data from ecojoko for a service, with the client of the entry."""
    entry = _loaded_entry(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
    try:
        return await read(entry.runtime_data.client)
    except LittleMonkeyApiClientError as exception:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="data_not_read",
            translation_placeholders={"error": str(exception)},
        ) from exception


async def _async_get_savings(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    """Return the savings of the week, month or year holding a day.

    The day is today by default. The answer holds the savings of the period
    and its bars: the days of a week, the weeks of a month or the months of
    a year, as in the attributes of the savings sensors.
    """
    period = call.data[ATTR_PERIOD]
    day = call.data.get(ATTR_DATE) or get_current_date(TZ)
    savings = await _async_read(
        hass, call, lambda client: client.async_get_savings_period(period, day))
    return {"period": period, "date": day.isoformat(), **savings}


async def _async_get_consumption_analysis(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Return the analysis of the consumption of a week, month or year.

    Without a date, the last period analysed by ecojoko. The answer holds
    the categories (standby, lighting...), or available false and the
    message of ecojoko when the period is not analysed yet.
    """
    period = call.data[ATTR_PERIOD]
    day = call.data.get(ATTR_DATE)
    analysis = await _async_read(
        hass, call, lambda client: client.async_get_analysis(period, day))
    return {"period": period, **analysis}


async def _async_get_category_history(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Return the consumption of a category, week by week over a year."""
    category = call.data[ATTR_CATEGORY]
    day = call.data.get(ATTR_DATE) or get_current_date(TZ)
    return await _async_read(
        hass, call, lambda client: client.async_get_category_history(category, day))


async def _async_get_activations(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Return the activations of the appliances over 48 hours.

    Page 0 for the last 48 hours, 1 for the 48 hours before, and so on.
    """
    page = call.data[ATTR_PAGE]
    activations = await _async_read(
        hass, call, lambda client: client.async_get_activations(page))
    return {"page": page, **activations}


def async_register_services(hass: HomeAssistant) -> None:
    """Register the services of the integration, once for all its entries."""
    # ServiceCall.hass appeared after Home Assistant 2024.7
    for service, handler, schema in (
        (SERVICE_GET_SAVINGS, _async_get_savings, GET_SAVINGS_SCHEMA),
        (SERVICE_GET_CONSUMPTION_ANALYSIS, _async_get_consumption_analysis,
         GET_CONSUMPTION_ANALYSIS_SCHEMA),
        (SERVICE_GET_CATEGORY_HISTORY, _async_get_category_history,
         GET_CATEGORY_HISTORY_SCHEMA),
        (SERVICE_GET_ACTIVATIONS, _async_get_activations, GET_ACTIVATIONS_SCHEMA),
    ):
        hass.services.async_register(
            DOMAIN,
            service,
            partial(handler, hass),
            schema=schema,
            supports_response=SupportsResponse.ONLY,
        )
