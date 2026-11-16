"""Services of little_monkey."""
from __future__ import annotations

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
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_PERIOD = "period"
ATTR_DATE = "date"

GET_SAVINGS_SCHEMA = vol.Schema({
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Required(ATTR_PERIOD): vol.In(list(SAVINGS_PERIODS)),
    vol.Optional(ATTR_DATE): cv.date,
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


async def _async_get_savings(call: ServiceCall) -> ServiceResponse:
    """Return the savings of the week, month or year holding a day.

    The day is today by default. The answer holds the savings of the period
    and its bars: the days of a week, the weeks of a month or the months of
    a year, as in the attributes of the savings sensors.
    """
    entry = _loaded_entry(call.hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
    period = call.data[ATTR_PERIOD]
    day = call.data.get(ATTR_DATE) or get_current_date(TZ)
    try:
        savings = await entry.runtime_data.client.async_get_savings_period(period, day)
    except LittleMonkeyApiClientError as exception:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="savings_not_read",
            translation_placeholders={"error": str(exception)},
        ) from exception
    return {"period": period, "date": day.isoformat(), **savings}


def async_register_services(hass: HomeAssistant) -> None:
    """Register the services of the integration, once for all its entries."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_SAVINGS,
        _async_get_savings,
        schema=GET_SAVINGS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
