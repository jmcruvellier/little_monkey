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
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.util import dt as dt_util

from .api import (
    EQUIPMENT_DURATIONS,
    MEASURE_PERIODS,
    MEASURES,
    SAVINGS_PERIODS,
    LittleMonkeyApiClientError,
    TZ,
)
from .const import (
    CONF_USE_ANALYSIS_FEATURE,
    CONF_USE_EQUIPMENT_FEATURE,
    CONF_USE_MEASURES_FEATURE,
    DOMAIN,
    option_enabled,
)
from .entity import equipment_identifier, registry_device
from .utils import get_current_date

SERVICE_GET_SAVINGS = "get_savings"
SERVICE_GET_CONSUMPTION_ANALYSIS = "get_consumption_analysis"
SERVICE_GET_CATEGORY_HISTORY = "get_category_history"
SERVICE_GET_ACTIVATIONS = "get_activations"
SERVICE_GET_EQUIPMENTS = "get_equipments"
SERVICE_GET_MEASURES = "get_measures"
ATTR_MEASURE = "measure"
ATTR_CHECK = "check"
SERVICE_SET_EQUIPMENT_MODE = "set_equipment_mode"
ATTR_DEVICE_ID = "device_id"
ATTR_MODE = "mode"
ATTR_DURATION = "duration"
ATTR_UNTIL = "until"
EQUIPMENT_MODES = ["auto", "forced", "absence", "on", "off"]
# Duration of a forced mode without a duration, in minutes
DEFAULT_FORCED_MINUTES = 60
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
# ecojoko analyses weeks and months only: a year gives the current week
GET_CONSUMPTION_ANALYSIS_SCHEMA = GET_SAVINGS_SCHEMA.extend({
    vol.Required(ATTR_PERIOD): vol.In(["week", "month"]),
})
GET_CATEGORY_HISTORY_SCHEMA = vol.Schema({
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Required(ATTR_CATEGORY): vol.All(vol.Coerce(int), vol.Range(min=0)),
    vol.Optional(ATTR_DATE): cv.date,
})
GET_ACTIVATIONS_SCHEMA = vol.Schema({
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Optional(ATTR_PAGE, default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=365)),
})
GET_MEASURES_SCHEMA = vol.Schema({
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Required(ATTR_MEASURE): vol.In(list(MEASURES)),
    vol.Required(ATTR_PERIOD): vol.In(list(MEASURE_PERIODS)),
    vol.Optional(ATTR_DATE): cv.date,
    # Only whether the option of the measures is on
    vol.Optional(ATTR_CHECK, default=False): cv.boolean,
})
GET_EQUIPMENTS_SCHEMA = vol.Schema({
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
})
SET_EQUIPMENT_MODE_SCHEMA = vol.Schema({
    vol.Required(ATTR_DEVICE_ID): cv.string,
    vol.Required(ATTR_MODE): vol.In(EQUIPMENT_MODES),
    # Minutes of a forced mode or of an absence
    vol.Optional(ATTR_DURATION): vol.All(vol.Coerce(int), vol.Range(min=1)),
    # End of an absence
    vol.Optional(ATTR_UNTIL): cv.datetime,
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


async def _async_read(hass: HomeAssistant, call: ServiceCall, read, option=None):
    """Read data from ecojoko for a service, with the client of the entry.

    Without the option of the service, nothing is read: the answer is
    {"enabled": false}, and the card asks to turn the option on.
    """
    entry = _loaded_entry(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
    if option is not None and not option_enabled(entry, option):
        return {"enabled": False}
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
        hass, call, lambda client: client.async_get_analysis(period, day),
        CONF_USE_ANALYSIS_FEATURE)
    return {"period": period, **analysis}


async def _async_get_category_history(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Return the consumption of a category, week by week over a year."""
    category = call.data[ATTR_CATEGORY]
    day = call.data.get(ATTR_DATE) or get_current_date(TZ)
    return await _async_read(
        hass, call, lambda client: client.async_get_category_history(category, day),
        CONF_USE_ANALYSIS_FEATURE)


async def _async_get_measures(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    """Return the measures of a period holding a day, as the page « Mesures ».

    The day is today by default. The electricity of a day is its power every
    few minutes with its tariff band; of a week, 30 days or a year, the
    energy and cost of its days or months by band. The temperature and the
    humidity are inside and outside, as curves.
    """
    measure = call.data[ATTR_MEASURE]
    period = call.data[ATTR_PERIOD]
    day = call.data.get(ATTR_DATE) or get_current_date(TZ)
    if call.data.get(ATTR_CHECK):
        # Only whether the option is on, without reading ecojoko: the card
        # of the measures asks it before reading the statistics of Home
        # Assistant
        entry = _loaded_entry(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        return {"enabled": option_enabled(entry, CONF_USE_MEASURES_FEATURE)}
    measures = await _async_read(
        hass, call, lambda client: client.async_get_measures(measure, period, day),
        CONF_USE_MEASURES_FEATURE)
    return {"measure": measure, "period": period, "date": day.isoformat(), **measures}


async def _async_get_activations(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Return the activations of the appliances over 48 hours.

    Page 0 for the last 48 hours, 1 for the 48 hours before, and so on.
    """
    page = call.data[ATTR_PAGE]
    activations = await _async_read(
        hass, call, lambda client: client.async_get_activations(page),
        CONF_USE_ANALYSIS_FEATURE)
    return {"page": page, **activations}


async def _async_get_equipments(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Return the equipments of the installation, as last read.

    Every equipment has its status and its controls. A piloted one also has
    its state and its measures of today, read every two minutes and after a
    command, and the id of its Home Assistant device. Nothing is read from
    ecojoko: the answer is immediate.
    """
    entry = _loaded_entry(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
    # Without the option of the equipments, the card asks to turn it on
    if not option_enabled(entry, CONF_USE_EQUIPMENT_FEATURE):
        return {"enabled": False, "equipments": []}
    coordinator = entry.runtime_data
    piloted = coordinator.equipment.data or {}
    registry = dr.async_get(hass)
    equipments = []
    for equipment in coordinator.client.equipments:
        device = registry_device(
            registry, equipment_identifier(entry.entry_id, equipment["id"]), entry.entry_id)
        equipments.append({
            **piloted.get(equipment["id"], equipment),
            "device_id": None if device is None else device.id,
            "entities": equipment_entities(hass, entry.entry_id, equipment),
        })
    return {"enabled": True, "equipments": equipments}


def _equipment_of_device(hass: HomeAssistant, device_id: str):
    """Return the loaded entry and the ecojoko id of the equipment of a device."""
    device = dr.async_get(hass).async_get(device_id)
    if device is not None:
        for entry_id in device.config_entries:
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
                continue
            for equipment in entry.runtime_data.client.equipments:
                if equipment_identifier(entry.entry_id, equipment["id"]) in device.identifiers:
                    return entry, equipment
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="equipment_not_found")


def _mode_seconds(call: ServiceCall) -> int | None:
    """Return the seconds of a forced mode or of an absence, None otherwise."""
    mode = call.data[ATTR_MODE]
    if mode not in EQUIPMENT_DURATIONS:
        return None
    until = call.data.get(ATTR_UNTIL)
    if mode == "absence" and until is not None:
        if until.tzinfo is None:
            until = until.replace(tzinfo=dt_util.get_default_time_zone())
        # Through the timestamps, right across a change of the clocks
        seconds = int(until.timestamp() - dt_util.now().timestamp())
    elif ATTR_DURATION in call.data:
        seconds = call.data[ATTR_DURATION] * 60
    elif mode == "forced":
        seconds = DEFAULT_FORCED_MINUTES * 60
    else:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="absence_end_required")
    low, high = EQUIPMENT_DURATIONS[mode]
    if not low <= seconds <= high:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="duration_out_of_range",
            translation_placeholders={"min": str(low // 60), "max": str(high // 60)},
        )
    return seconds


async def _async_set_equipment_mode(hass: HomeAssistant, call: ServiceCall) -> None:
    """Pilot an equipment: forced, absence, back to automatic, on or off.

    A forced mode lasts the duration given, an hour by default; an absence
    lasts the duration given or until the end given.
    """
    entry, equipment = _equipment_of_device(hass, call.data[ATTR_DEVICE_ID])
    if not option_enabled(entry, CONF_USE_EQUIPMENT_FEATURE):
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="equipment_disabled")
    mode = call.data[ATTR_MODE]
    if mode not in equipment["controls"]:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="mode_not_supported",
            translation_placeholders={"mode": mode, "name": str(equipment.get("name"))},
        )
    await entry.runtime_data.equipment.async_command(
        equipment["id"], mode, _mode_seconds(call))


# Entities of an equipment, by the name of their value in the answer:
# platform and key of their unique id
EQUIPMENT_ENTITIES = {
    "mode": ("sensor", "equipment_mode"),
    "power": ("sensor", "equipment_power"),
    "energy": ("sensor", "equipment_energy"),
    "cost": ("sensor", "equipment_cost"),
    "voltage": ("sensor", "equipment_voltage"),
    "max_power": ("sensor", "equipment_max_power"),
    "control": ("select", "equipment_mode"),
    "connection": ("sensor", "equipment_connection"),
    "signal": ("sensor", "equipment_signal"),
    "wifi_signal": ("sensor", "equipment_wifi_signal"),
    "battery": ("sensor", "equipment_battery"),
}
# Sensors of the Ecojoko device that give the measures of an equipment, by type
DEVICE_MEASURES = {
    "TEMP_HUM": {"temperature": "indoor_temp", "humidity": "indoor_hum"},
    "POWER_METER": {"power": "realtime_consumption"},
}


def equipment_entities(hass: HomeAssistant, entry_id: str, equipment: dict) -> dict:
    """Return the entities of the values of an equipment, for its details.

    Its own sensors, and for a sensor or the Linky key the sensors of the
    Ecojoko device that give the same measures.
    """
    registry = er.async_get(hass)
    entities = {}
    for name, (platform, key) in EQUIPMENT_ENTITIES.items():
        entity_id = registry.async_get_entity_id(
            platform, DOMAIN, f"{entry_id}_{equipment['id']}_{key}")
        if entity_id:
            entities[name] = entity_id
    for name, key in DEVICE_MEASURES.get(equipment.get("type"), {}).items():
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{entry_id}_{key}")
        if entity_id:
            entities.setdefault(name, entity_id)
    return entities


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
        (SERVICE_GET_EQUIPMENTS, _async_get_equipments, GET_EQUIPMENTS_SCHEMA),
        (SERVICE_GET_MEASURES, _async_get_measures, GET_MEASURES_SCHEMA),
    ):
        hass.services.async_register(
            DOMAIN,
            service,
            partial(handler, hass),
            schema=schema,
            supports_response=SupportsResponse.ONLY,
        )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_EQUIPMENT_MODE,
        partial(_async_set_equipment_mode, hass),
        schema=SET_EQUIPMENT_MODE_SCHEMA,
    )
