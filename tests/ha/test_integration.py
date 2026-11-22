"""Tests of the integration inside a Home Assistant core.

They cover what needs the registries, the config entries and the flows:
migration from 1.2.7, entity names, availability, setup, reauthentication,
the setup form and the options.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import types

import voluptuous as vol
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import State
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import pytest
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

from custom_components.little_monkey import (
    api as lm_api,
    async_remove_config_entry_device,
    config_flow,
    coordinator as lm_coordinator,
    repairs,
    select as lm_select,
    services as lm_services,
)
from custom_components.little_monkey.entity import device_entry_ids, registry_device
from custom_components.little_monkey.diagnostics import (
    async_get_config_entry_diagnostics,
)

DOMAIN = "little_monkey"
# Data of an entry of version 2 (1.2.8): HC/HP and Tempo options
DATA_V2 = {
    "name": "Ecojoko",
    "username": "User@Example.com",
    "password": "pw",
    "use_hchp_feature": True,
    "use_tempo_feature": False,
    "use_temphum_feature": True,
    "use_prod_feature": False,
    "poll_interval": 5,
}
HCHP_BANDS = [
    {"id": 2, "label": "Heures Pleines", "key": "hp_grid_consumption",
     "name": None, "category": "hp"},
    {"id": 3, "label": "Heures Creuses", "key": "hc_grid_consumption",
     "name": None, "category": "hc"},
]
# The groups of sensors of 2.0.0, all on in the entry of the tests
GROUPS = {
    "use_activity_feature": True,
    "use_savings_feature": True,
    "use_contract_feature": True,
    "use_equipment_feature": True,
    "use_analysis_feature": True,
    "use_measures_feature": True,
}
# Data of an entry of the current version: tariff bands
DATA = {
    "name": "Ecojoko",
    "username": "User@Example.com",
    "password": "pw",
    "use_hchp_feature": True,
    "use_temphum_feature": True,
    "use_prod_feature": False,
    **GROUPS,
    "poll_interval": 5,
    "tariff_bands": HCHP_BANDS,
}
# First screen of the setup and of the options
ACCOUNT = {"name": "Ecojoko", "username": "User@Example.com", "password": "pw"}
# Second screen with the bands of an HP/HC contract, and last screen
HCHP_SCREEN = {
    "use_hchp_feature": True,
    "Heures Pleines – HC/HP": "hp",
    "Heures Creuses – HC/HP": "hc",
}
SETTINGS = {"use_prod_feature": False, "use_temphum_feature": True, **GROUPS, "poll_interval": 5}
# Sensors created with the options of DATA by 1.2.7
ENABLED = [
    "realtime_consumption",
    "grid_consumption",
    "hc_grid_consumption",
    "hp_grid_consumption",
    "indoor_temp",
    "outdoor_temp",
    "indoor_hum",
    "outdoor_hum",
]
# Sensors of the activity of the account, created for every entry
ACTIVITY_KEYS = [
    "savings_7_days",
    "consumption_7_days",
    "cost_7_days",
    "total_savings",
    "max_power_month",
    "max_power_year",
    "max_power_alltime",
]
# Sensors of the savings of the account, created for every entry
SAVINGS_KEYS = [
    "consumption_cost_12_months",
    "reference_cost_12_months",
    "savings_12_months",
    "savings_week",
    "savings_month",
    "savings_year",
]
# A water heater piloted by ecojoko, as the patched client reports it
WATER_HEATER = {
    "id": "630220", "type": "LULO", "model": "LULO", "name": "Chauffe-eau",
    "firmware": "1.01.11", "connected": True, "status": "Connecté",
    "signal": 29, "battery": None, "battery_voltage": None, "install_state": None,
    "wifi_signal": 30,
    "controls": ["forced", "absence", "auto"], "measures": True, "switches": True,
    "state": {
        "power": 2784, "on": True, "forced": True, "mode": "forced",
        "switch_state": "Mode forcé jusqu'à 21:00",
        "since": "2026-11-18T20:00:00+01:00", "until": "2026-11-18T21:00:00+01:00",
        "source": "command", "voltage": 232.5, "max_power": 3131,
    },
}
# An equipment that is not piloted
TEMP_HUM_EQUIPMENT = {
    "id": "3", "type": "TEMP_HUM", "model": None, "name": "Sonde",
    "firmware": None, "connected": True, "status": "Connecté",
    "signal": 66, "battery": 80, "battery_voltage": 5.09, "install_state": "Bien placé",
    "wifi_signal": None,
    "controls": [], "measures": False, "switches": False,
    "state": {"power": None, "on": None, "forced": None, "mode": None, "switch_state": None,
              "since": None, "until": None, "source": None, "voltage": None,
              "max_power": None},
}

REALTIME = "sensor.ecojoko_real_time_consumption"
GRID = "sensor.ecojoko_grid_consumption"
FORM = data_entry_flow.FlowResultType.FORM
ABORT = data_entry_flow.FlowResultType.ABORT
CREATE_ENTRY = data_entry_flow.FlowResultType.CREATE_ENTRY


def add_entry(hass, **kwargs):
    """Add a config entry of the current version to Home Assistant."""
    entry = MockConfigEntry(
        **{"domain": DOMAIN, "title": "user", "version": 3, "minor_version": 3, "data": DATA,
           **kwargs}
    )
    entry.add_to_hass(hass)
    return entry


async def setup_entry(hass, entry):
    """Set up a config entry and return whether it succeeded.

    The first reading of the activity, in the background, is waited for.
    """
    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return result


def add_1_2_7_install(hass):
    """Create what a 1.2.7 installation left in the registries.

    Return the config entry, the device and the entity ids by sensor key.
    """
    entry = add_entry(
        hass,
        version=1,
        minor_version=1,
        data={**DATA_V2, "lang": "fr-FR"},
        options={"lang": "fr-FR"},
    )
    entity_registry, device_registry = er.async_get(hass), dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        name="Ecojoko",
        identifiers={(DOMAIN, "little_monkey_Ecojoko")},
    )
    entity_ids = {
        "main": entity_registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "little_monkey_Ecojoko",
            config_entry=entry,
            device_id=device.id,
            suggested_object_id="ecojoko",
        ).entity_id
    }
    # production_surplus: sensor of an option that was enabled in the past
    for key in [*ENABLED, "production_surplus"]:
        entity_ids[key] = entity_registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"little_monkey_Ecojoko_{key}",
            config_entry=entry,
            device_id=device.id,
            suggested_object_id=f"ecojoko_{key}",
            original_name=f"Ecojoko - {key}",
        ).entity_id
    # Entity left behind by a renaming done with an older version
    entity_ids["orphan"] = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "little_monkey_Ancien_realtime_consumption",
        config_entry=entry,
        suggested_object_id="ancien_realtime_consumption",
    ).entity_id
    return entry, device, entity_ids


# --- Migration


async def test_migration_from_1_2_7(hass, fake_api):
    """Unique ids are rewritten; entity ids, device and settings are kept."""
    entry, device, entity_ids = add_1_2_7_install(hass)
    entity_registry, device_registry = er.async_get(hass), dr.async_get(hass)
    # Customisations made by the user, which must survive
    entity_registry.async_update_entity(
        entity_ids["grid_consumption"], name="Ma conso"
    )
    device_registry.async_update_device(device.id, name_by_user="Compteur")
    count_before = len(
        er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    )

    assert await setup_entry(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 3
    assert entry.minor_version == 3
    assert entry.data["poll_interval"] == 30
    assert "lang" not in entry.data
    assert "use_tempo_feature" not in entry.data
    assert entry.data["tariff_bands"] == HCHP_BANDS
    assert entry.options == {}
    assert entry.data["password"] == "pw"
    assert entry.data["name"] == "Ecojoko"
    assert entry.unique_id == "user@example.com"

    # Same entity ids, new unique ids, nothing duplicated; only the current
    # tariff period is created: the groups of sensors of 2.0.0 are off
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == count_before + 1
    assert not [e.entity_id for e in entities if e.entity_id.endswith("_2")]
    assert entity_registry.async_get(entity_ids["main"]).unique_id == entry.entry_id
    for key in [*ENABLED, "production_surplus"]:
        migrated = entity_registry.async_get(entity_ids[key])
        assert migrated.unique_id == f"{entry.entry_id}_{key}", key
    orphan = entity_registry.async_get(entity_ids["orphan"])
    assert orphan.unique_id == "little_monkey_Ancien_realtime_consumption"
    assert entity_registry.async_get(entity_ids["grid_consumption"]).name == "Ma conso"

    # Same device, new identifier, customisation kept, no second device
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert [d.id for d in devices] == [device.id]
    assert devices[0].identifiers == {(DOMAIN, entry.entry_id)}
    assert devices[0].name_by_user == "Compteur"

    # The migrated entities are the live ones
    assert hass.states.get(entity_ids["realtime_consumption"]).state == "512"
    grid = hass.states.get(entity_ids["grid_consumption"])
    assert grid.state == "4.2"
    assert grid.attributes["friendly_name"].endswith("Ma conso")
    temperature = hass.states.get(entity_ids["outdoor_temp"])
    assert temperature.attributes["unit_of_measurement"] == "°C"
    assert hass.states.get(entity_ids["main"]).state == "1.9"

    # A second start does not migrate again
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == count_before + 1
    assert hass.states.get(entity_ids["realtime_consumption"]).state == "512"


@pytest.mark.parametrize(
    ("configured", "migrated"), [(5, 30), (3, 30), (None, None), (30, 30), (45, 45)]
)
async def test_migration_raises_the_poll_interval(hass, fake_api, configured, migrated):
    """Intervals under 30 s of 2.0.0b1 are raised to 30 s, longer ones kept."""
    data = {key: value for key, value in DATA.items() if key != "poll_interval"}
    if configured is not None:
        data["poll_interval"] = configured
    entry = add_entry(hass, minor_version=1, data=data)

    assert await setup_entry(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert (entry.version, entry.minor_version) == (3, 3)
    assert entry.data.get("poll_interval") == migrated
    assert entry.data["tariff_bands"] == HCHP_BANDS


@pytest.mark.parametrize(
    ("configured", "migrated"), [(3, 5), (4, 5), (5, 5), (10, 10), (None, None), (30, 30)]
)
async def test_migration_raises_the_poll_interval_to_the_minimum(
    hass, fake_api, configured, migrated
):
    """Intervals under 5 s chosen since 2.0.0b2 are raised to the new minimum."""
    data = {key: value for key, value in DATA.items() if key != "poll_interval"}
    if configured is not None:
        data["poll_interval"] = configured
    entry = add_entry(hass, minor_version=2, data=data)

    assert await setup_entry(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert (entry.version, entry.minor_version) == (3, 3)
    assert entry.data.get("poll_interval") == migrated


async def test_device_left_by_a_renaming_can_be_removed(hass, fake_api):
    """A device left behind by an old renaming can be removed, not the live one."""
    entry, _device, entity_ids = add_1_2_7_install(hass)
    entity_registry, device_registry = er.async_get(hass), dr.async_get(hass)
    # What a renaming done with an older version left: a device and its entity
    stale = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        name="Ancien",
        identifiers={(DOMAIN, "little_monkey_Ancien")},
    )
    entity_registry.async_update_entity(entity_ids["orphan"], device_id=stale.id)
    assert await setup_entry(hass, entry)

    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert len(devices) == 2
    live = next(d for d in devices if d.id != stale.id)
    stale = device_registry.async_get(stale.id)

    assert await async_remove_config_entry_device(hass, entry, stale) is True
    assert await async_remove_config_entry_device(hass, entry, live) is False

    # What Home Assistant does once the removal is allowed
    device_registry.async_remove_device(stale.id)
    await hass.async_block_till_done()
    assert device_registry.async_get(stale.id) is None
    assert entity_registry.async_get(entity_ids["orphan"]) is None
    remaining = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert [d.id for d in remaining] == [live.id]
    assert hass.states.get(entity_ids["realtime_consumption"]).state == "512"


# --- Entities


async def test_new_install_entities(hass, fake_api):
    """A new entry creates the sensors of its options, named by translation."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    keys = [*ENABLED, "current_tariff_period", "contract", *ACTIVITY_KEYS, *SAVINGS_KEYS]
    expected = [entry.entry_id, *[f"{entry.entry_id}_{key}" for key in keys]]
    assert sorted(e.unique_id for e in entities) == sorted(expected)

    # The test instance is in English; the name is prefixed by the device name
    state = hass.states.get(REALTIME)
    assert state.attributes["friendly_name"] == "Ecojoko Real-Time Consumption"
    assert state.state == "512"
    assert state.attributes["unit_of_measurement"] == "W"
    assert state.attributes["device_class"] == "power"
    assert state.attributes["state_class"] == "measurement"


async def test_renaming_keeps_entities(hass, fake_api):
    """Changing the name renames the device and keeps every entity."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    entity_registry, device_registry = er.async_get(hass), dr.async_get(hass)
    entity_ids = sorted(
        e.entity_id
        for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    )
    device_ids = [
        d.id
        for d in dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    ]

    # The update listener reloads the entry
    hass.config_entries.async_update_entry(entry, data={**DATA, "name": "Compteur"})
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    renamed = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert sorted(e.entity_id for e in renamed) == entity_ids
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert [d.id for d in devices] == device_ids
    assert devices[0].name == "Compteur"
    state = hass.states.get(REALTIME)
    assert state.attributes["friendly_name"] == "Compteur Real-Time Consumption"


async def test_unavailable_when_api_fails_then_recovers(hass, fake_api):
    """Entities are unavailable when the API fails for long, then come back."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    coordinator = entry.runtime_data
    clock = {"now": 1000.0}

    # Only the clock of the coordinator: the event loop keeps the real one
    fake_time = types.SimpleNamespace(monotonic=lambda: clock["now"])
    with patch.object(lm_coordinator, "time", fake_time):
        # A brief failure keeps the last values
        fake_api.data_error = lm_api.LittleMonkeyApiClientCommunicationError("down")
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(REALTIME).state == "512"
        assert coordinator.last_update_success

        clock["now"] += 119
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(REALTIME).state == "512"

        # After two minutes the sensors become unavailable
        clock["now"] += 1
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(REALTIME).state == "unavailable"

        fake_api.data_error = None
        fake_api.values["_realtime_conso"] = 640
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(REALTIME).state == "640"

        # The delay starts again with the next failure
        clock["now"] += 3600
        fake_api.data_error = lm_api.LittleMonkeyApiClientCommunicationError("down")
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(REALTIME).state == "640"


async def test_unexpected_answer_is_not_a_brief_failure(hass, fake_api):
    """Only communication failures keep the last values."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    coordinator = entry.runtime_data

    fake_api.data_error = lm_api.LittleMonkeyApiClientError("unexpected data")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(REALTIME).state == "unavailable"


# --- Energy totals never decrease during a day


async def refresh(hass, entry):
    """Poll ecojoko once."""
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_energy_is_held_when_ecojoko_lowers_it(hass, fake_api):
    """A correction downwards is hidden until the total catches up."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    assert hass.states.get(GRID).state == "4.2"
    assert hass.states.get(GRID).attributes["state_class"] == "total_increasing"

    # Small and large corrections, then the total catches up
    for received, published in ((3.9, "4.2"), (3.0, "4.2"), (4.1, "4.2"), (4.5, "4.5")):
        fake_api.values["_kwh"] = received
        await refresh(hass, entry)
        assert hass.states.get(GRID).state == published, received


async def test_energy_moved_from_hc_to_hp_is_counted_once(hass, fake_api):
    """HC + HP never exceeds the grid consumption when ecojoko moves energy."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    hc, hp = "sensor.ecojoko_hc_grid_consumption", "sensor.ecojoko_hp_grid_consumption"
    assert (hass.states.get(hc).state, hass.states.get(hp).state) == ("1.5", "2.5")

    # ecojoko moves 1 kWh from HC to HP: HP only gains the 0.2 kWh left up
    # to the grid consumption; then the consumption grows in HC
    for values, published in (
        ({"_kwh_hc_ns": 0.5, "_kwh_hp_ns": 3.5}, ("1.5", "2.7")),
        ({"_kwh": 4.6, "_kwh_hc_ns": 0.9, "_kwh_hp_ns": 3.5}, ("1.9", "2.7")),
    ):
        fake_api.values.update(values)
        await refresh(hass, entry)
        assert (hass.states.get(hc).state, hass.states.get(hp).state) == published


async def test_power_follows_ecojoko_both_ways(hass, fake_api):
    """Sensors that are not totals are not held."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    fake_api.values["_realtime_conso"] = 100
    fake_api.values["_indoor_temp"] = 18
    await refresh(hass, entry)
    assert hass.states.get(REALTIME).state == "100"
    assert hass.states.get("sensor.ecojoko_indoor_temperature").state == "18"


async def test_energy_restarts_on_a_new_day(hass, fake_api):
    """The drop of a new day is published."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    assert hass.states.get(GRID).state == "4.2"

    fake_api.stat_date += dt.timedelta(days=1)
    fake_api.values["_kwh"] = 0.1
    await refresh(hass, entry)
    assert hass.states.get(GRID).state == "0.1"


def restore_grid_state(hass, value, last_updated=None):
    """Make Home Assistant restore a state of the grid consumption sensor."""
    state = State(
        GRID, str(value), last_updated=last_updated or dt_util.utcnow()
    )
    extra_data = {"native_value": value, "native_unit_of_measurement": "kWh"}
    mock_restore_cache_with_extra_data(hass, ((state, extra_data),))


async def test_held_value_survives_a_restart_the_same_day(hass, fake_api):
    """After a restart the total does not go below the one published before."""
    restore_grid_state(hass, 7.32)
    fake_api.values["_kwh"] = 7.05
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    assert hass.states.get(GRID).state == "7.32"

    fake_api.values["_kwh"] = 7.5
    await refresh(hass, entry)
    assert hass.states.get(GRID).state == "7.5"


async def test_restart_on_a_new_day_drops_the_old_value(hass, fake_api):
    """After a restart on another day the new total is published."""
    restore_grid_state(hass, 7.32, dt_util.utcnow() - dt.timedelta(days=2))
    fake_api.values["_kwh"] = 0.3
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    assert hass.states.get(GRID).state == "0.3"


# --- HTTP session


async def test_entry_has_its_own_http_session(hass, fake_api):
    """Each entry uses a session of its own, released when it is unloaded."""
    first = add_entry(hass)
    second = add_entry(hass, data={**DATA, "name": "Autre", "username": "other"})
    # Setting up the integration loads all its entries
    assert await setup_entry(hass, first)
    assert second.state is ConfigEntryState.LOADED

    sessions = [
        entry.runtime_data.client._session for entry in (first, second)
    ]
    assert sessions[0] is not sessions[1]
    assert async_get_clientsession(hass) not in sessions
    assert sessions[0].cookie_jar is not sessions[1].cookie_jar
    assert not sessions[0].closed

    assert await hass.config_entries.async_unload(first.entry_id)
    await hass.async_block_till_done()
    assert sessions[0].closed
    assert not sessions[1].closed
    assert not async_get_clientsession(hass).closed


async def test_form_validation_releases_its_session(hass, fake_api):
    """The session created to check the credentials is released at once."""
    created = []
    real = config_flow.async_create_clientsession

    def spy(*args, **kwargs):
        created.append(real(*args, **kwargs))
        return created[-1]

    with patch.object(config_flow, "async_create_clientsession", spy):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        fake_api.login_error = lm_api.LittleMonkeyApiClientAuthenticationError("x")
        await hass.config_entries.flow.async_configure(
            result["flow_id"], dict(ACCOUNT))

    assert len(created) == 1
    assert created[0].closed


# --- Setup


async def test_setup_retries_when_api_is_down(hass, fake_api):
    """Home Assistant retries the setup when ecojoko cannot be reached."""
    fake_api.data_error = lm_api.LittleMonkeyApiClientCommunicationError("down")
    entry = add_entry(hass)
    assert not await setup_entry(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_reauthentication(hass, fake_api):
    """A rejected password starts a reauthentication that fixes the entry."""
    fake_api.data_error = lm_api.LittleMonkeyApiClientAuthenticationError("401")
    entry = add_entry(hass)
    assert not await setup_entry(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == config_entries.SOURCE_REAUTH
    assert flows[0]["step_id"] == "reauth_confirm"
    flow_id = flows[0]["flow_id"]

    # Wrong new password: the form is shown again, nothing is saved
    fake_api.login_error = lm_api.LittleMonkeyApiClientAuthenticationError("401")
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"password": "bad"}
    )
    assert result["type"] == FORM
    assert result["errors"] == {"base": "auth"}
    assert entry.data["password"] == "pw"

    # Right password: saved, the entry is reloaded and works
    fake_api.login_error = None
    fake_api.data_error = None
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"password": "new"}
    )
    await hass.async_block_till_done()
    assert result["type"] == ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["password"] == "new"
    assert entry.data["name"] == "Ecojoko"
    assert entry.state is ConfigEntryState.LOADED


# --- Diagnostics


async def test_diagnostics_are_redacted(hass, fake_api):
    """Diagnostics give the state of the entry without the credentials."""
    entry = add_entry(
        hass, title="User@Example.com", data={**DATA, "name": "Chez Dupont"}
    )
    assert await setup_entry(hass, entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    text = json.dumps(diagnostics, default=str)
    assert "pw" not in json.dumps(diagnostics["entry"]["data"])
    for secret in ("User@Example.com", "user@example.com", "Dupont"):
        assert secret not in text
    assert diagnostics["entry"]["data"]["name"] == "**REDACTED**"
    assert diagnostics["entry"]["data"]["password"] == "**REDACTED**"
    assert diagnostics["entry"]["data"]["username"] == "**REDACTED**"
    assert diagnostics["entry"]["title"] == "**REDACTED**"
    assert diagnostics["entry"]["unique_id"] == "**REDACTED**"
    assert diagnostics["entry"]["data"]["poll_interval"] == 5
    assert diagnostics["coordinator"]["last_update_success"] is True
    assert diagnostics["coordinator"]["update_interval_seconds"] == 5
    assert diagnostics["data"]["realtime_consumption"] == 512
    assert set(diagnostics["client"]) >= {"logged_in", "failing_apis"}
    # The contract, without the price of its subscription
    assert diagnostics["data"]["contract"]["supplier_name"] == "EDF"
    assert "subscription_price" not in diagnostics["data"]["contract"]
    assert "24.77" not in text


async def test_diagnostics_when_setup_failed(hass, fake_api):
    """Diagnostics are still available when the entry could not be set up."""
    fake_api.data_error = lm_api.LittleMonkeyApiClientCommunicationError("down")
    entry = add_entry(hass)
    assert not await setup_entry(hass, entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["data"]["password"] == "**REDACTED**"
    assert "coordinator" not in diagnostics


# --- Flows


async def test_user_flow(hass, fake_api):
    """The setup form reports each kind of error, then creates the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FORM
    assert result["step_id"] == "user"
    assert "lang" not in [str(key) for key in result["data_schema"].schema]

    for error, key in (
        (lm_api.LittleMonkeyApiClientAuthenticationError("x"), "auth"),
        (lm_api.LittleMonkeyApiClientCommunicationError("x"), "connection"),
        (lm_api.LittleMonkeyApiClientError("x"), "unknown"),
    ):
        fake_api.login_error = error
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], dict(ACCOUNT)
        )
        assert result["type"] == FORM, key
        assert result["errors"] == {"base": key}

    fake_api.login_error = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(ACCOUNT)
    )
    assert result["type"] == FORM
    assert result["step_id"] == "bands"
    assert result["description_placeholders"] == {
        "contract": "EDF – Zen Fixe - Option HP/HC"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(HCHP_SCREEN)
    )
    assert result["type"] == FORM
    assert result["step_id"] == "settings"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(SETTINGS)
    )
    await hass.async_block_till_done()
    assert result["type"] == CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.version == 3
    assert entry.data == {**DATA, "username": "User@Example.com"}
    assert entry.unique_id == "user@example.com"
    assert entry.options == {}
    assert entry.state is ConfigEntryState.LOADED


async def test_user_flow_requires_a_name(hass, fake_api):
    """A blank name is refused before ecojoko is contacted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    for name in ("", "   "):
        fake_api.login_error = AssertionError("ecojoko must not be contacted")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**ACCOUNT, "name": name}
        )
        assert result["type"] == FORM
        assert result["errors"] == {"name": "name_required"}

    fake_api.login_error = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(ACCOUNT)
    )
    assert result["step_id"] == "bands"


async def test_options_flow_requires_a_name(hass, fake_api):
    """A blank name is refused in the options and nothing is saved."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**ACCOUNT, "name": " "}
    )
    assert result["type"] == FORM
    assert result["errors"] == {"name": "name_required"}
    assert entry.data["name"] == "Ecojoko"


async def test_options_flow_follows_a_new_username(hass, fake_api):
    """A new username keeps the entities and renames the entry named after it."""
    entry = add_entry(hass, title="User@Example.com")
    assert await setup_entry(hass, entry)
    before = {
        entity.entity_id: entity.unique_id
        for entity in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**ACCOUNT, "username": "new@example.com"})
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], dict(HCHP_SCREEN))
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], dict(SETTINGS))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] == CREATE_ENTRY
    assert entry.data["username"] == "new@example.com"
    assert entry.title == "new@example.com"
    assert entry.unique_id == "new@example.com"
    after = {
        entity.entity_id: entity.unique_id
        for entity in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}
    assert after == before


async def test_options_flow_keeps_a_title_chosen_by_the_user(hass, fake_api):
    """A title that is not the username is not changed with the username."""
    entry = add_entry(hass, title="Maison")
    assert await setup_entry(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**ACCOUNT, "username": "new@example.com"})
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], dict(HCHP_SCREEN))
    await hass.config_entries.options.async_configure(result["flow_id"], dict(SETTINGS))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.data["username"] == "new@example.com"
    assert entry.title == "Maison"


async def test_options_flow_refuses_the_account_of_another_entry(hass, fake_api):
    """The account of another entry, written differently, is refused."""
    entry = add_entry(hass)
    other = add_entry(hass, data={**DATA, "username": "other@example.com"})
    assert await setup_entry(hass, entry)
    assert other.entry_id != entry.entry_id

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**ACCOUNT, "username": " Other@Example.COM "})
    assert result["type"] == FORM
    assert result["errors"] == {"base": "already_configured"}
    assert entry.data["username"] == "User@Example.com"

    # Its own account, written differently, is accepted
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**ACCOUNT, "username": "user@example.com"})
    assert result["step_id"] == "bands"


async def test_user_flow_refuses_an_account_twice(hass, fake_api):
    """The same ecojoko account, written differently, cannot be added again."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**ACCOUNT, "username": " user@example.COM "}
    )
    assert result["type"] == ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_validates_before_saving(hass, fake_api):
    """Options are saved only when ecojoko accepts them, with one reload."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    calls_before = fake_api.data_calls

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FORM
    assert result["step_id"] == "init"

    # Rejected: nothing saved, no reload
    fake_api.login_error = lm_api.LittleMonkeyApiClientAuthenticationError("x")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**ACCOUNT, "password": "wrong"}
    )
    await hass.async_block_till_done()
    assert result["type"] == FORM
    assert result["errors"] == {"base": "auth"}
    assert entry.data["password"] == "pw"
    assert entry.data["poll_interval"] == 5
    assert fake_api.data_calls == calls_before

    # Accepted: saved, reloaded exactly once
    fake_api.login_error = None
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**ACCOUNT, "password": "good"}
    )
    assert result["step_id"] == "bands"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], dict(HCHP_SCREEN)
    )
    assert result["step_id"] == "settings"
    # Nothing saved before the last screen
    assert entry.data["password"] == "pw"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**SETTINGS, "poll_interval": 10}
    )
    await hass.async_block_till_done()
    assert result["type"] == CREATE_ENTRY
    assert entry.data["password"] == "good"
    assert entry.data["poll_interval"] == 10
    assert entry.options == {}
    assert entry.state is ConfigEntryState.LOADED
    assert fake_api.data_calls == calls_before + 1


def apparent_power_entity(hass, entry):
    """Return the entity id of the apparent power sensor of an entry, if any."""
    return er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_realtime_apparent_power")


async def test_apparent_power_sensor_needs_the_value(hass, fake_api):
    """The apparent power sensor is not created when ecojoko does not give it."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    assert apparent_power_entity(hass, entry) is None


async def test_apparent_power_sensor(hass, fake_api):
    """The apparent power sensor is created when ecojoko gives the value."""
    fake_api.values["_realtime_va"] = -640
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)

    state = hass.states.get(apparent_power_entity(hass, entry))
    assert state.state == "-640"
    assert state.attributes["unit_of_measurement"] == "VA"
    assert state.attributes["device_class"] == "apparent_power"


async def test_apparent_power_sensor_of_a_patched_1_2_7_is_kept(hass, fake_api):
    """The sensor added by hand to a 1.2.7 installation keeps its entity."""
    fake_api.values["_realtime_va"] = 640
    entry, device, _entity_ids = add_1_2_7_install(hass)
    patched = er.async_get(hass).async_get_or_create(
        "sensor",
        DOMAIN,
        "little_monkey_Ecojoko_realtime_apparent_power",
        config_entry=entry,
        device_id=device.id,
        suggested_object_id="ecojoko_puissance_apparente_linky",
    ).entity_id

    assert await setup_entry(hass, entry)

    assert apparent_power_entity(hass, entry) == patched
    assert hass.states.get(patched).state == "640"


# --- Tariff bands

TEMPO_KEYS = [
    "blue_hp_grid_consumption", "blue_hc_grid_consumption",
    "white_hp_grid_consumption", "white_hc_grid_consumption",
    "red_hp_grid_consumption", "red_hc_grid_consumption",
]
TEMPO_FOUND = {
    18: "HP Bleu", 19: "HC Bleu", 20: "HP Blanc",
    21: "HC Blanc", 22: "HP Rouge", 23: "HC Rouge",
}


async def test_migration_of_a_tempo_entry_keeps_its_sensors(hass, fake_api):
    """The Tempo option becomes six bands keeping the entities of the sensors."""
    entry = add_entry(
        hass, version=2, minor_version=1,
        data={**DATA_V2, "use_tempo_feature": True})
    entity_registry = er.async_get(hass)
    entity_ids = {
        key: entity_registry.async_get_or_create(
            "sensor", DOMAIN, f"{entry.entry_id}_{key}", config_entry=entry,
            suggested_object_id=f"ecojoko_{key}",
        ).entity_id
        for key in TEMPO_KEYS
    }
    fake_api.values["_band_values"] = {"blue_hc_grid_consumption": 1.25}

    assert await setup_entry(hass, entry)

    assert entry.version == 3
    assert "use_tempo_feature" not in entry.data
    bands = entry.data["tariff_bands"]
    assert [band["id"] for band in bands] == [2, 3, 18, 19, 20, 21, 22, 23]
    for key, entity_id in entity_ids.items():
        assert entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{key}") == entity_id
    assert not [
        e.entity_id
        for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if e.entity_id.endswith("_2")
    ]
    state = hass.states.get(entity_ids["blue_hc_grid_consumption"])
    assert state.state == "1.25"
    assert state.attributes["friendly_name"] == "Ecojoko HC Blue Grid Consumption"


async def start_setup(hass, fake_api, found, contract=None):
    """Fill the first screen of the setup and return the bands screen."""
    fake_api.bands = found
    if contract is not None:
        fake_api.contract = contract
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(ACCOUNT)
    )


def schema_defaults(result):
    """Return the fields of a form and their default values."""
    return {
        str(key): key.default() if callable(key.default) else None
        for key in result["data_schema"].schema
    }


async def test_setup_of_a_weekend_contract(hass, fake_api):
    """Each band gets a named sensor and the category chosen by the user."""
    found = {8: "HP Semaine", 9: "HC Semaine", 13: "Heures Weekend"}
    result = await start_setup(hass, fake_api, found, contract={
        "supplier_name": "EDF", "offer_name": "Vert Week-End - Option HC",
        "offer_type": "HC SEM ET WE"})
    assert result["step_id"] == "bands"
    assert schema_defaults(result) == {
        "use_hchp_feature": True,
        "use_contract_prices": False,
        "HP Semaine": "HP Semaine",
        "HP Semaine – HC/HP": "hp",
        "HC Semaine": "HC Semaine",
        "HC Semaine – HC/HP": "hc",
        "Heures Weekend": "Heures Weekend",
        "Heures Weekend – HC/HP": "none",
        "removed_bands": [],
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {
        "use_hchp_feature": True,
        "HP Semaine": "HP Semaine",
        "HP Semaine – HC/HP": "hp",
        "HC Semaine": "HC Semaine",
        "HC Semaine – HC/HP": "hc",
        "Heures Weekend": " Week-end ",
        "Heures Weekend – HC/HP": "hc",
    })
    fake_api.values["_band_values"] = {
        "band_8": 0, "band_9": 0, "band_13": 26.19}
    fake_api.values["_kwh"] = 26.19
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(SETTINGS))
    await hass.async_block_till_done()
    assert result["type"] == CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data["tariff_bands"] == [
        {"id": 8, "label": "HP Semaine", "key": "band_8",
         "name": "HP Semaine", "category": "hp"},
        {"id": 9, "label": "HC Semaine", "key": "band_9",
         "name": "HC Semaine", "category": "hc"},
        {"id": 13, "label": "Heures Weekend", "key": "band_13",
         "name": "Week-end", "category": "hc"},
    ]
    entity_registry = er.async_get(hass)
    weekend = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_band_13")
    state = hass.states.get(weekend)
    assert state.state == "26.19"
    assert state.attributes["friendly_name"] == "Ecojoko Week-end"
    assert state.attributes["device_class"] == "energy"
    assert state.attributes["state_class"] == "total_increasing"


async def test_setup_of_a_tempo_contract_keeps_the_known_names(hass, fake_api):
    """A known sensor shows its translated name and does not save it."""
    result = await start_setup(hass, fake_api, dict(TEMPO_FOUND))
    defaults = schema_defaults(result)
    assert defaults["HC Bleu"] == "HC Blue Grid Consumption"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], defaults)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(SETTINGS))
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    bands = entry.data["tariff_bands"]
    assert [band["key"] for band in bands] == TEMPO_KEYS
    assert all(band["name"] is None for band in bands)
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    unique_ids = {e.unique_id for e in entities}
    assert {f"{entry.entry_id}_{key}" for key in TEMPO_KEYS} <= unique_ids


async def options_bands_screen(hass, entry, fake_api, found, contract="same"):
    """Fill the first screen of the options and return the bands screen."""
    fake_api.bands = found
    if contract is None:
        fake_api.contract = None
    result = await hass.config_entries.options.async_init(entry.entry_id)
    return await hass.config_entries.options.async_configure(
        result["flow_id"], dict(ACCOUNT)
    )


async def test_options_follow_a_new_contract(hass, fake_api):
    """The bands of the previous contract are dropped, saved settings kept."""
    data = {**DATA, "tariff_bands": [
        *HCHP_BANDS,
        {"id": 13, "label": "Heures Weekend", "key": "band_13",
         "name": "Week-end", "category": "hc"},
        {"id": 19, "label": "HC Bleu", "key": "blue_hc_grid_consumption",
         "name": None, "category": "hc"},
    ]}
    entry = add_entry(hass, data=data)
    assert await setup_entry(hass, entry)

    # ecojoko renamed band 13; band 19 is no longer in the contract
    renamed = "Week-end et jours fériés"
    result = await options_bands_screen(
        hass, entry, fake_api,
        {2: "Heures Pleines", 3: "Heures Creuses", 13: renamed})
    defaults = schema_defaults(result)
    assert defaults[renamed] == "Week-end"
    assert defaults[renamed + " – HC/HP"] == "hc"
    assert not [key for key in defaults if "Bleu" in key]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], defaults)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], dict(SETTINGS))
    await hass.async_block_till_done()
    bands = entry.data["tariff_bands"]
    assert [(b["id"], b["key"], b["name"]) for b in bands] == [
        (2, "hp_grid_consumption", None),
        (3, "hc_grid_consumption", None),
        (13, "band_13", "Week-end"),
    ]


async def test_options_keep_the_bands_when_the_contract_is_unknown(hass, fake_api):
    """Without the contract, the configured bands are all kept."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    result = await options_bands_screen(hass, entry, fake_api, {}, contract=None)
    assert result["description_placeholders"] == {"contract": "?"}
    assert "Heures Creuses – HC/HP" in schema_defaults(result)


async def test_options_keep_the_bands_when_statistics_are_missing(hass, fake_api):
    """A week of statistics not read: a band missing from the others is kept."""
    weekend = {"id": 13, "label": "Heures Weekend", "key": "band_13",
               "name": "Week-end", "category": "hc"}
    entry = add_entry(hass, data={**DATA, "tariff_bands": [*HCHP_BANDS, weekend]})
    assert await setup_entry(hass, entry)
    fake_api.weeks_missed = 1
    result = await options_bands_screen(
        hass, entry, fake_api, {2: "Heures Pleines", 3: "Heures Creuses"})
    defaults = schema_defaults(result)
    assert defaults["Heures Weekend"] == "Week-end"
    assert defaults["Heures Weekend – HC/HP"] == "hc"


async def test_options_remove_the_bands_of_a_previous_contract(hass, fake_api):
    """Bands removed lose their sensor and stay removed while ecojoko gives them."""
    winter = [
        {"id": 28, "label": "HC Hiver", "key": "band_28", "name": None, "category": "hc"},
        {"id": 29, "label": "HP Hiver", "key": "band_29", "name": None, "category": "hp"},
    ]
    entry = add_entry(hass, data={**DATA, "tariff_bands": [*HCHP_BANDS, *winter]})
    assert await setup_entry(hass, entry)
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_band_28")
    found = {2: "Heures Pleines", 3: "Heures Creuses", 28: "HC Hiver", 29: "HP Hiver"}

    result = await options_bands_screen(hass, entry, fake_api, found)
    defaults = schema_defaults(result)
    assert defaults["removed_bands"] == []
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**defaults, "removed_bands": ["28", "29"]})
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], dict(SETTINGS))
    await hass.async_block_till_done()
    assert entry.data["tariff_bands"] == HCHP_BANDS
    assert entry.data["removed_bands"] == [28, 29]
    for key in ("band_28", "band_29"):
        assert registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{key}") is None

    # Still found, they are not proposed again but stay checked; unchecking
    # one adds it back
    result = await options_bands_screen(hass, entry, fake_api, found)
    defaults = schema_defaults(result)
    assert "HC Hiver" not in defaults
    assert defaults["removed_bands"] == ["28", "29"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**defaults, "removed_bands": ["28"]})
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], dict(SETTINGS))
    await hass.async_block_till_done()
    assert [band["id"] for band in entry.data["tariff_bands"]] == [2, 3, 29]
    assert entry.data["removed_bands"] == [28]

    # Missing from incomplete statistics, a removed band stays removed
    fake_api.weeks_missed = 1
    result = await options_bands_screen(
        hass, entry, fake_api, {2: "Heures Pleines", 3: "Heures Creuses", 29: "HP Hiver"})
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], schema_defaults(result))
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], dict(SETTINGS))
    await hass.async_block_till_done()
    assert entry.data["removed_bands"] == [28]

    # No longer found, a removed band is forgotten
    fake_api.weeks_missed = 0
    result = await options_bands_screen(
        hass, entry, fake_api, {2: "Heures Pleines", 3: "Heures Creuses", 29: "HP Hiver"})
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], schema_defaults(result))
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], dict(SETTINGS))
    await hass.async_block_till_done()
    assert "removed_bands" not in entry.data


# --- Repair of the bands not configured


async def test_unknown_bands_are_repaired(hass, fake_api):
    """New bands raise a repair issue; fixing it adds their sensors."""
    fake_api.values["_unknown_bands"] = {8: "HP Semaine", 9: "HC Semaine"}
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)

    issue_registry = ir.async_get(hass)
    issue_id = f"unknown_bands_{entry.entry_id}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.is_fixable
    assert issue.translation_placeholders == {
        "name": "user", "bands": "HC Semaine, HP Semaine"}

    flow = await repairs.async_create_fix_flow(hass, issue_id, issue.data)
    flow.hass = hass
    result = await flow.async_step_init()
    assert result["type"] == FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "bands": "HC Semaine, HP Semaine"}

    # Once the entry reloads, the bands are configured
    fake_api.values["_unknown_bands"] = {}
    fake_api.values["_band_values"] = {"band_8": 6.43, "band_9": 18.29}
    fake_api.values["_kwh"] = 24.72
    result = await flow.async_step_confirm({})
    await hass.async_block_till_done()
    assert result["type"] == CREATE_ENTRY
    bands = entry.data["tariff_bands"]
    assert [(b["id"], b["key"], b["category"]) for b in bands] == [
        (2, "hp_grid_consumption", "hp"),
        (3, "hc_grid_consumption", "hc"),
        (8, "band_8", "hp"),
        (9, "band_9", "hc"),
    ]
    assert entry.state is ConfigEntryState.LOADED
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_band_8")
    state = hass.states.get(entity_id)
    assert state.state == "6.43"
    assert state.attributes["friendly_name"] == "Ecojoko HP Semaine"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_repair_issue_is_removed_with_the_entry(hass, fake_api):
    """Removing the entry removes its repair issue."""
    fake_api.values["_unknown_bands"] = {8: "HP Semaine"}
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    issue_registry = ir.async_get(hass)
    issue_id = f"unknown_bands_{entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_no_issue_while_the_bands_are_unknown(hass, fake_api):
    """Nothing is reported before the bands of a day are read."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    issue_id = f"unknown_bands_{entry.entry_id}"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


# --- Current tariff period


def period_entity(hass, entry):
    """Return the entity id of the current tariff period sensor, if any."""
    return er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_current_tariff_period")


async def test_tariff_period_follows_the_counter_that_increases(hass, fake_api):
    """With the HC/HP option, the period is the one whose counter increased."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    entity_id = period_entity(hass, entry)
    state = hass.states.get(entity_id)
    # Not known before a counter increases
    assert state.state == "unknown"
    assert state.attributes["device_class"] == "enum"
    assert state.attributes["options"] == ["hc", "hp"]
    assert state.attributes["friendly_name"] == "Ecojoko Current Tariff Period"

    fake_api.values["_kwh_hp_ns"] = 2.6
    await refresh(hass, entry)
    assert hass.states.get(entity_id).state == "hp"
    # Kept while no counter increases
    await refresh(hass, entry)
    assert hass.states.get(entity_id).state == "hp"
    fake_api.values["_kwh_hc_ns"] = 1.6
    await refresh(hass, entry)
    assert hass.states.get(entity_id).state == "hc"


async def test_tariff_period_with_tempo(hass, fake_api):
    """With a Tempo contract, the period gives the color of the day."""
    values = dict.fromkeys(TEMPO_KEYS, 0)
    fake_api.values["_band_values"] = {
        **values, "red_hc_grid_consumption": 0.5, "red_hp_grid_consumption": 1.0}
    tempo_bands = [
        {"id": band_id, "label": label, "key": key, "name": None,
         "category": "hc" if label.startswith("HC") else "hp"}
        for (band_id, label), key in zip(TEMPO_FOUND.items(), [
            "blue_hp_grid_consumption", "blue_hc_grid_consumption",
            "white_hp_grid_consumption", "white_hc_grid_consumption",
            "red_hp_grid_consumption", "red_hc_grid_consumption"])
    ]
    entry = add_entry(hass, data={
        **DATA, "use_hchp_feature": False, "tariff_bands": tempo_bands})
    assert await setup_entry(hass, entry)
    entity_id = period_entity(hass, entry)
    assert hass.states.get(entity_id).attributes["options"] == [
        "hc_blue", "hp_blue", "hc_white", "hp_white", "hc_red", "hp_red"]

    fake_api.values["_band_values"] = {
        **values, "red_hc_grid_consumption": 0.5, "red_hp_grid_consumption": 1.1}
    await refresh(hass, entry)
    assert hass.states.get(entity_id).state == "hp_red"


async def test_no_tariff_period_without_option(hass, fake_api):
    """Without the HC/HP nor the Tempo option, the sensor is not created."""
    entry = add_entry(hass, data={**DATA, "use_hchp_feature": False})
    assert await setup_entry(hass, entry)
    assert period_entity(hass, entry) is None


async def test_tariff_period_is_restored_after_a_restart(hass, fake_api):
    """The last period is shown until the counters tell the current one."""
    entity_id = "sensor.ecojoko_current_tariff_period"
    mock_restore_cache_with_extra_data(
        hass, ((State(entity_id, "hc"), {"native_value": "hc"}),))
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    assert period_entity(hass, entry) == entity_id
    assert hass.states.get(entity_id).state == "hc"

    fake_api.values["_kwh_hp_ns"] = 2.6
    await refresh(hass, entry)
    assert hass.states.get(entity_id).state == "hp"


# --- Activity of the account


SAVINGS = "sensor.ecojoko_gap_over_7_days"


async def refresh_activity(hass, entry):
    """Read the activity of the account once."""
    await entry.runtime_data.activity.async_refresh()
    await hass.async_block_till_done()


async def test_activity_sensors(hass, fake_api):
    """The activity of the account gives its sensors."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)

    savings = hass.states.get(SAVINGS)
    assert savings.state == "-3"
    assert savings.attributes["unit_of_measurement"] == "%"
    assert savings.attributes["reference_consumption"] == 74.4
    assert savings.attributes["friendly_name"] == "Ecojoko Gap over 7 Days"
    cost = hass.states.get("sensor.ecojoko_cost_over_7_days")
    assert cost.state == "16.6"
    assert cost.attributes["device_class"] == "monetary"
    assert cost.attributes["unit_of_measurement"] == "EUR"
    consumption = hass.states.get("sensor.ecojoko_consumption_over_7_days")
    assert consumption.state == "74.33"
    assert consumption.attributes["daily_consumption"] == [
        9.14, 12.46, 9.55, 12.43, 12.36, 7.92, 10.37]
    assert hass.states.get("sensor.ecojoko_total_savings").state == "393.83"
    assert hass.states.get("sensor.ecojoko_max_power_since_the_start").state == "7386"


async def test_activity_failure_does_not_stop_the_polls(hass, fake_api):
    """The activity sensors fail alone; the real-time ones go on."""
    fake_api.activity_error = lm_api.LittleMonkeyApiClientCommunicationError("slow")
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(SAVINGS).state == "unavailable"
    assert hass.states.get(REALTIME).state == "512"

    fake_api.activity_error = None
    await refresh_activity(hass, entry)
    assert hass.states.get(SAVINGS).state == "-3"


async def test_activity_keeps_its_values_during_an_hour(hass, fake_api):
    """A failure keeps the last values, until it lasts an hour."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    fake_api.activity_error = lm_api.LittleMonkeyApiClientCommunicationError("slow")
    await refresh_activity(hass, entry)
    assert hass.states.get(SAVINGS).state == "-3"

    entry.runtime_data.activity._last_success -= 3600
    await refresh_activity(hass, entry)
    assert hass.states.get(SAVINGS).state == "unavailable"


async def test_no_savings_without_reference_week(hass, fake_api):
    """Without a reference week, the savings are unknown."""
    fake_api.activity.update(savings_7_days=None, reference_consumption_7_days=None)
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    assert hass.states.get(SAVINGS).state == "unknown"
    assert hass.states.get("sensor.ecojoko_cost_over_7_days").state == "16.6"


async def test_activity_in_diagnostics(hass, fake_api):
    """Diagnostics show the state of the activity."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["activity"]["last_update_success"] is True
    assert diagnostics["activity"]["data"]["savings_7_days"] == -3


# --- Savings of the account


WEEK = "sensor.ecojoko_savings_this_week"


async def test_savings_sensors(hass, fake_api):
    """The savings of the account give their sensors."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)

    savings = hass.states.get("sensor.ecojoko_savings_over_12_months")
    assert savings.state == "337.63"
    assert savings.attributes["unit_of_measurement"] == "EUR"
    assert savings.attributes["device_class"] == "monetary"
    assert savings.attributes["savings_kwh"] == 1617.28
    assert savings.attributes["level"] == 5
    cost = hass.states.get("sensor.ecojoko_consumption_cost_over_12_months")
    assert cost.state == "483.6"
    assert cost.attributes["consumption"] == 1701.72
    reference = hass.states.get("sensor.ecojoko_reference_cost_over_12_months")
    assert reference.state == "821.23"
    assert reference.attributes["reference_consumption"] == 3319

    week = hass.states.get(WEEK)
    assert week.state == "-0.35"
    assert week.attributes["savings_kwh"] == -2.58
    assert week.attributes["start"] == "2026-11-16"
    assert week.attributes["bars"][0]["savings"] == -0.35
    assert week.attributes["bars"][1]["savings"] is None
    assert hass.states.get("sensor.ecojoko_savings_this_month").state == "-8.69"
    assert hass.states.get("sensor.ecojoko_savings_this_year").state == "322.32"


async def test_savings_failure_does_not_stop_the_polls(hass, fake_api):
    """The savings sensors fail alone; the real-time ones go on."""
    fake_api.savings_error = lm_api.LittleMonkeyApiClientCommunicationError("slow")
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    assert hass.states.get(WEEK).state == "unavailable"
    assert hass.states.get(REALTIME).state == "512"
    assert hass.states.get(SAVINGS).state == "-3"

    fake_api.savings_error = None
    await entry.runtime_data.savings.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(WEEK).state == "-0.35"


async def test_savings_in_diagnostics(hass, fake_api):
    """Diagnostics show the state of the savings."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["savings"]["last_update_success"] is True
    assert diagnostics["savings"]["data"]["savings_12_months"] == 337.63


async def get_savings(hass, **data):
    """Call the service of the savings and return its answer."""
    return await hass.services.async_call(
        DOMAIN, "get_savings", data, blocking=True, return_response=True)


async def test_savings_service(hass, fake_api):
    """The service gives the savings of any week, month or year."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)

    answer = await get_savings(hass, period="year", date="2025-03-04")
    assert fake_api.savings_periods == [("year", dt.date(2025, 3, 4))]
    assert answer["period"] == "year"
    assert answer["date"] == "2025-03-04"
    assert answer["savings"] == 322.32
    assert len(answer["bars"]) == 12

    # Today by default, and the entry can be given
    answer = await get_savings(hass, period="week", config_entry_id=entry.entry_id)
    assert fake_api.savings_periods[-1] == (
        "week", dt_util.now().astimezone(dt_util.get_time_zone("Europe/Paris")).date())
    assert answer["bars"][0]["savings"] == -0.35


async def test_savings_service_errors(hass, fake_api):
    """The service tells which installation is missing, or ecojoko's error."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    with pytest.raises(ServiceValidationError):
        await get_savings(hass, period="week", config_entry_id="unknown")
    with pytest.raises(vol.Invalid):
        await get_savings(hass, period="day")

    fake_api.savings_error = lm_api.LittleMonkeyApiClientCommunicationError("slow")
    with pytest.raises(HomeAssistantError):
        await get_savings(hass, period="week")


async def call_service(hass, service, **data):
    """Call a service of the integration and return its answer."""
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True)


async def test_analysis_services(hass, fake_api):
    """The services of the analysis of the consumption."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)

    answer = await call_service(hass, "get_consumption_analysis", period="week")
    assert answer["period"] == "week"
    assert answer["cost"] == 14.46
    await call_service(hass, "get_consumption_analysis", period="month", date="2026-10-15")
    answer = await call_service(hass, "get_category_history", category=8, date="2026-03-04")
    assert answer["category"] == {"id": 8}
    answer = await call_service(hass, "get_activations")
    assert answer["page"] == 0
    await call_service(hass, "get_activations", page=3)
    assert fake_api.analysis_calls == [
        ("analysis", "week", None),
        ("analysis", "month", dt.date(2026, 10, 15)),
        ("history", 8, dt.date(2026, 3, 4)),
        ("activations", 0),
        ("activations", 3),
    ]

    fake_api.savings_error = lm_api.LittleMonkeyApiClientCommunicationError("slow")
    with pytest.raises(HomeAssistantError):
        # A period not read yet: the week is kept from above
        await call_service(hass, "get_consumption_analysis", period="month")
    with pytest.raises(vol.Invalid):
        await call_service(hass, "get_activations", page=-1)
    # ecojoko does not analyse years: it would give the current week
    with pytest.raises(vol.Invalid):
        await call_service(hass, "get_consumption_analysis", period="year")


async def test_contract_sensor(hass, fake_api):
    """The contract sensor gives the offer and its details."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    state = hass.states.get("sensor.ecojoko_contract")
    assert state.state == "Zen Fixe - Option HP/HC"
    assert state.attributes["supplier"] == "EDF"
    assert state.attributes["power"] == 9
    assert state.attributes["subscription_price"] == 24.77
    assert state.attributes["start_date"] == "2026-08-04"
    assert state.attributes["off_peak_timeslots"][1] == {"start": "14:00", "stop": "16:30"}
    assert state.attributes["resale_price"] == 0.1109
    assert [band["key"] for band in state.attributes["bands"]] == [
        band["key"] for band in entry.data["tariff_bands"]]
    entity = er.async_get(hass).async_get("sensor.ecojoko_contract")
    assert entity.entity_category == "diagnostic"


async def test_contract_unknown_until_read(hass, fake_api):
    """Before ecojoko gives the contract, its sensor is unknown."""
    fake_api.values["_contract"] = None
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    state = hass.states.get("sensor.ecojoko_contract")
    assert state.state == "unknown"
    assert state.attributes["off_peak_timeslots"] == []


# --- Current tariff band

ZEN_WEEKEND_PLUS = [
    {"id": band_id, "label": label, "key": f"band_{band_id}", "name": None,
     "category": "hc" if label.startswith("HC") else "hp"}
    for band_id, label in (
        (8, "HP Semaine"), (9, "HC Semaine"),
        (10, "HP Jour Sp\u00e9cial"), (11, "HC Jour Sp\u00e9cial"),
        (6, "HP Weekend"), (7, "HC Weekend"),
    )
]


async def test_tariff_band_of_a_special_day(hass, fake_api):
    """The period sensor tells the band of the day whose counter increases."""
    bands = [*HCHP_BANDS, *ZEN_WEEKEND_PLUS]
    bands[5] = {**bands[5], "name": "HC jour sp\u00e9cial"}
    values = {band["key"]: 0 for band in ZEN_WEEKEND_PLUS}
    fake_api.values.update({
        "_band_values": {**values, "band_10": 1.0, "band_11": 0.5},
        "_kwh_hp_ns": 1.0, "_kwh_hc_ns": 0.5,
    })
    entry = add_entry(hass, data={**DATA, "tariff_bands": bands})
    assert await setup_entry(hass, entry)
    entity_id = period_entity(hass, entry)

    fake_api.values.update({
        "_band_values": {**values, "band_10": 1.0, "band_11": 0.7},
        "_kwh_hc_ns": 0.7,
    })
    await refresh(hass, entry)
    state = hass.states.get(entity_id)
    assert state.state == "hc"
    assert state.attributes["tariff_band"] == "HC jour sp\u00e9cial"

    fake_api.values.update({
        "_band_values": {**values, "band_10": 1.2, "band_11": 0.7},
        "_kwh_hp_ns": 1.2,
    })
    await refresh(hass, entry)
    state = hass.states.get(entity_id)
    assert state.state == "hp"
    assert state.attributes["tariff_band"] == "HP Jour Sp\u00e9cial"


async def test_tariff_band_unknown_at_first(hass, fake_api):
    """The band is unknown until a counter increases."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    state = hass.states.get(period_entity(hass, entry))
    assert "tariff_band" not in state.attributes


async def test_piloted_equipment_has_its_device(hass, fake_api):
    """A piloted equipment is a device of its own, linked to the Ecojoko device."""
    fake_api.equipments = [TEMP_HUM_EQUIPMENT, WATER_HEATER]
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)

    assert hass.states.get("sensor.chauffe_eau_power").state == "2784"
    assert hass.states.get("sensor.chauffe_eau_consumption_today").state == "0.97"
    assert hass.states.get("sensor.chauffe_eau_cost_today").state == "0.14"
    mode = hass.states.get("sensor.chauffe_eau_mode")
    assert mode.state == "forced"
    assert mode.attributes["options"] == ["auto", "forced", "absence"]
    assert mode.attributes["until"] == "2026-11-18T21:00:00+01:00"
    assert mode.attributes["source"] == "command"
    # The contactor, apart from the mode: on, since when and why
    contactor = hass.states.get("binary_sensor.chauffe_eau_contactor")
    assert contactor.state == "on"
    assert contactor.attributes["since"] == "2026-11-18T20:00:00+01:00"
    assert contactor.attributes["source"] == "command"

    devices = dr.async_get(hass)
    heater = registry_device(devices, (DOMAIN, f"{entry.entry_id}_630220"), entry.entry_id)
    main = registry_device(devices, (DOMAIN, entry.entry_id), entry.entry_id)
    assert heater.name == "Chauffe-eau"
    # Versions as the Ecojoko device: Little Monkey, then the equipment
    assert heater.sw_version == main.sw_version
    assert heater.hw_version == "1.01.11"
    assert heater.via_device_id == main.id
    # The device of a current equipment cannot be removed, the others can
    assert not await async_remove_config_entry_device(hass, entry, heater)
    # An equipment that is not piloted has no device
    assert registry_device(devices, (DOMAIN, f"{entry.entry_id}_3"), entry.entry_id) is None


async def test_equipments_service(hass, fake_api):
    """The service gives every equipment, the piloted ones with their day."""
    fake_api.equipments = [TEMP_HUM_EQUIPMENT, WATER_HEATER]
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)

    answer = await call_service(hass, "get_equipments")
    sensor, heater = answer["equipments"]
    assert sensor["name"] == "Sonde" and sensor["device_id"] is None
    assert "day" not in sensor
    assert heater["day"]["energy"] == 0.97
    heater_device = registry_device(
        dr.async_get(hass), (DOMAIN, f"{entry.entry_id}_630220"), entry.entry_id)
    assert heater["device_id"] == heater_device.id
    # The entity of each value, for its details
    assert heater["entities"]["power"] == "sensor.chauffe_eau_power"
    assert heater["entities"]["voltage"] == "sensor.chauffe_eau_voltage"
    assert heater["entities"]["max_power"] == "sensor.chauffe_eau_max_measured_power"
    assert heater["entities"]["control"] == "select.chauffe_eau_control"
    assert heater["entities"]["switch"] == "binary_sensor.chauffe_eau_contactor"
    assert heater["entities"]["wifi_signal"] == "sensor.chauffe_eau_wifi_connection"
    assert hass.states.get("sensor.chauffe_eau_voltage").state == "232.5"
    # The sensor: its diagnostics, and its measures on the Ecojoko device
    assert sensor["entities"]["signal"] == "sensor.ecojoko_sonde_connection_strength"
    assert sensor["entities"]["temperature"] == "sensor.ecojoko_indoor_temperature"
    assert sensor["entities"]["humidity"] == "sensor.ecojoko_indoor_humidity"


async def test_equipment_failure_keeps_the_entry(hass, fake_api):
    """The equipments are read apart: a failure leaves the other sensors."""
    fake_api.equipments = [WATER_HEATER]
    fake_api.equipment_error = lm_api.LittleMonkeyApiClientCommunicationError("slow")
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    assert hass.states.get("sensor.chauffe_eau_power").state == "unavailable"
    assert hass.states.get(REALTIME).state == "512"


async def test_equipment_diagnostic_sensors(hass, fake_api):
    """Every equipment has its connection, signal and battery, when given.

    On the device of a piloted equipment, on the Ecojoko device for the others.
    """
    fake_api.equipments = [TEMP_HUM_EQUIPMENT, WATER_HEATER]
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)

    assert hass.states.get("sensor.ecojoko_sonde_connection_to_the_assistant").state == "connected"
    assert hass.states.get("sensor.ecojoko_sonde_connection_strength").state == "66"
    assert hass.states.get("sensor.ecojoko_sonde_battery").state == "80"
    assert hass.states.get("sensor.ecojoko_sonde_battery_voltage").state == "5.09"
    assert hass.states.get("sensor.ecojoko_sonde_installation_state").state == "Bien placé"
    assert hass.states.get("sensor.chauffe_eau_battery_voltage") is None
    # Given for the water heater only
    assert hass.states.get("sensor.ecojoko_sonde_wifi_connection") is None
    assert hass.states.get("sensor.chauffe_eau_wifi_connection").state == "30"
    assert hass.states.get("sensor.chauffe_eau_battery") is None
    entities = er.async_get(hass)
    entity = entities.async_get("sensor.ecojoko_sonde_connection_strength")
    assert entity.entity_category == "diagnostic"
    main = registry_device(dr.async_get(hass), (DOMAIN, entry.entry_id), entry.entry_id)
    assert entity.device_id == main.id
    assert entities.async_get("sensor.chauffe_eau_wifi_connection").device_id != main.id

    # Read with the list of the gateways, by the polls
    fake_api.equipments = [{**TEMP_HUM_EQUIPMENT, "connected": False, "signal": 12}]
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.ecojoko_sonde_connection_to_the_assistant").state == "disconnected"
    assert hass.states.get("sensor.ecojoko_sonde_connection_strength").state == "12"
    # An equipment no longer listed by ecojoko is unavailable
    assert hass.states.get("sensor.chauffe_eau_wifi_connection").state == "unavailable"


def heater_device(hass, entry):
    """Return the device of the water heater."""
    return registry_device(
        dr.async_get(hass), (DOMAIN, f"{entry.entry_id}_630220"), entry.entry_id)


async def test_equipment_mode_select(hass, fake_api):
    """The list pilots the equipment: an hour of forced mode, an absence until midnight."""
    fake_api.equipments = [copy.deepcopy(WATER_HEATER)]
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    state = hass.states.get("select.chauffe_eau_control")
    assert state.state == "forced"
    assert state.attributes["options"] == ["auto", "forced", "absence"]

    await hass.services.async_call(
        "select", "select_option", {"entity_id": "select.chauffe_eau_control", "option": "auto"},
        blocking=True)
    await hass.async_block_till_done()
    assert fake_api.commands == [("630220", "auto", None)]
    # Read again after the command
    assert hass.states.get("select.chauffe_eau_control").state == "auto"
    assert hass.states.get("sensor.chauffe_eau_mode").state == "auto"

    await hass.services.async_call(
        "select", "select_option", {"entity_id": "select.chauffe_eau_control", "option": "forced"},
        blocking=True)
    await hass.services.async_call(
        "select", "select_option", {"entity_id": "select.chauffe_eau_control", "option": "absence"},
        blocking=True)
    assert fake_api.commands[1] == ("630220", "forced", 3600)
    mode, seconds = fake_api.commands[2][1:]
    assert mode == "absence" and 0 < seconds <= 24 * 3600


async def test_contactor_of_an_equipment_in_automatic_mode(hass, fake_api):
    """The contactor follows ecojoko in automatic mode, the mode does not change.

    An equipment switched only on and off has no contactor sensor: its mode
    is the state of its contactor already.
    """
    heater = copy.deepcopy(WATER_HEATER)
    heater["state"].update(on=False, forced=False, mode="auto", source="schedule")
    plug = copy.deepcopy(WATER_HEATER)
    plug.update(id="630221", name="Prise", controls=["on", "off"])
    plug["state"].update(mode="on")
    fake_api.equipments = [heater, plug]
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    assert hass.states.get("binary_sensor.chauffe_eau_contactor").state == "off"
    assert hass.states.get("binary_sensor.prise_contactor") is None
    assert hass.states.get("sensor.prise_mode").state == "on"

    # ecojoko switches the heater on: the mode stays automatic
    fake_api.equipments[0]["state"].update(on=True, power=2850)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("binary_sensor.chauffe_eau_contactor").state == "on"
    assert hass.states.get("sensor.chauffe_eau_mode").state == "auto"


def test_config_entries_of_a_device():
    """The config entry of a device, whatever the version of Home Assistant.

    Since 2026 a device has a single one, config_entry_id; the older
    versions only know config_entries, deprecated since.
    """
    assert device_entry_ids(types.SimpleNamespace(config_entry_id="a")) == {"a"}
    assert device_entry_ids(types.SimpleNamespace(config_entry_id=None)) == set()
    assert device_entry_ids(types.SimpleNamespace(config_entries={"a", "b"})) == {"a", "b"}


def test_absence_of_the_list_ends_at_midnight():
    """An absence chosen in the list ends at the next midnight in Paris."""
    paris = dt_util.get_time_zone("Europe/Paris")
    assert lm_select.seconds_until_midnight(dt.datetime(2026, 11, 18, 23, 0, tzinfo=paris)) == 3600
    # The day the clocks go back lasts 25 hours
    assert lm_select.seconds_until_midnight(dt.datetime(2026, 10, 25, 0, 0, tzinfo=paris)) == 25 * 3600
    # In the last minute of the day, the shortest absence accepted
    assert lm_select.seconds_until_midnight(dt.datetime(2026, 11, 18, 23, 59, 30, tzinfo=paris)) == 60


async def test_set_equipment_mode_service(hass, fake_api):
    """The service pilots the equipment for any duration."""
    fake_api.equipments = [copy.deepcopy(WATER_HEATER), TEMP_HUM_EQUIPMENT]
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    device_id = heater_device(hass, entry).id

    async def set_mode(**data):
        await hass.services.async_call(
            DOMAIN, "set_equipment_mode", {"device_id": device_id, **data}, blocking=True)

    await set_mode(mode="forced")
    await set_mode(mode="forced", duration=30)
    await set_mode(mode="absence", duration=120)
    until = dt_util.now() + dt.timedelta(days=2)
    await set_mode(mode="absence", until=until.isoformat())
    await set_mode(mode="auto")
    commands = fake_api.commands
    assert commands[:3] == [
        ("630220", "forced", 3600), ("630220", "forced", 1800), ("630220", "absence", 7200)]
    assert abs(commands[3][2] - 2 * 86400) < 60
    assert commands[4] == ("630220", "auto", None)

    with pytest.raises(ServiceValidationError):
        # An absence needs its end
        await set_mode(mode="absence")
    with pytest.raises(ServiceValidationError):
        await set_mode(mode="absence", until=(dt_util.now() - dt.timedelta(hours=1)).isoformat())
    with pytest.raises(ServiceValidationError):
        await set_mode(mode="forced", duration=25 * 60)
    with pytest.raises(ServiceValidationError):
        # Without a forced mode only
        await set_mode(mode="on")
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "set_equipment_mode", {"device_id": "unknown", "mode": "auto"}, blocking=True)
    # The Ecojoko device is not an equipment
    main = registry_device(dr.async_get(hass), (DOMAIN, entry.entry_id), entry.entry_id)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "set_equipment_mode", {"device_id": main.id, "mode": "auto"}, blocking=True)
    assert len(fake_api.commands) == 5

    # ecojoko does not answer: an error, and the equipment is read again
    fake_api.command_error = lm_api.LittleMonkeyApiClientCommunicationError("timeout")
    with pytest.raises(HomeAssistantError):
        await set_mode(mode="auto")


async def test_devices_of_equipments_no_longer_piloted_are_removed(hass, fake_api):
    """Only a piloted equipment keeps a device: the others are removed."""
    fake_api.equipments = [TEMP_HUM_EQUIPMENT, WATER_HEATER]
    entry = add_entry(hass)
    devices = dr.async_get(hass)
    # Left by a version that gave a device to every equipment
    devices.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, f"{entry.entry_id}_3")},
        name="Sonde")
    assert await setup_entry(hass, entry)

    assert registry_device(devices, (DOMAIN, f"{entry.entry_id}_3"), entry.entry_id) is None
    assert registry_device(devices, (DOMAIN, f"{entry.entry_id}_630220"), entry.entry_id)
    assert registry_device(devices, (DOMAIN, entry.entry_id), entry.entry_id)


async def test_measures_of_the_day_of_an_equipment_are_read_less_often(
    hass, fake_api, monkeypatch
):
    """The power curve every third reading, the changes of state every fifth."""
    clock = {"now": 1000.0}
    monkeypatch.setattr(
        lm_coordinator, "time", types.SimpleNamespace(monotonic=lambda: clock["now"]))
    fake_api.equipments = [copy.deepcopy(WATER_HEATER), TEMP_HUM_EQUIPMENT]
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    coordinator = entry.runtime_data.equipment
    # The first reading takes the whole day
    assert fake_api.day_reads == [("power", "switches")]

    async def read_at(seconds):
        clock["now"] = 1000.0 + seconds
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    reads = fake_api.equipment_reads
    await read_at(120)
    await read_at(240)
    # The state is read every time, the measures of the day kept
    assert fake_api.equipment_reads == reads + 2
    assert fake_api.day_reads == [("power", "switches")]
    assert coordinator.data["630220"]["day"]["energy"] == 0.97
    assert coordinator.data["630220"]["day"]["switches"]
    await read_at(360)
    assert fake_api.day_reads[-1] == ("power",)
    await read_at(480)
    await read_at(600)
    assert fake_api.day_reads[-1] == ("switches",)
    assert len(fake_api.day_reads) == 3

    # After a command, the whole day at once
    device_id = heater_device(hass, entry).id
    await hass.services.async_call(
        DOMAIN, "set_equipment_mode", {"device_id": device_id, "mode": "auto"}, blocking=True)
    assert fake_api.day_reads[-1] == ("power", "switches")


async def test_equipment_is_read_again_at_the_end_of_a_forced_mode(hass, fake_api):
    """The end of a forced mode is seen at once, not at the next reading."""
    heater = copy.deepcopy(WATER_HEATER)
    heater["state"]["until"] = (dt_util.utcnow() + dt.timedelta(seconds=30)).isoformat()
    fake_api.equipments = [heater]
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    reads = fake_api.equipment_reads

    # ecojoko ended the forced mode
    heater["state"].update(mode="auto", until=None)
    async_fire_time_changed(hass, dt_util.utcnow() + dt.timedelta(seconds=45))
    await hass.async_block_till_done()
    assert fake_api.equipment_reads == reads + 1
    assert hass.states.get("sensor.chauffe_eau_mode").state == "auto"

    # Nothing more is planned without a forced mode
    async_fire_time_changed(hass, dt_util.utcnow() + dt.timedelta(seconds=100))
    await hass.async_block_till_done()
    assert fake_api.equipment_reads == reads + 1


async def test_contract_sensor_gives_the_price_of_a_kwh(hass, fake_api):
    """Each band of the contract has the price of a kWh, exact or estimated."""
    fake_api.values["_exact_prices"] = [{"label": "Heures Pleines", "price": 0.2016}]
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    bands = {
        band["key"]: band
        for band in hass.states.get("sensor.ecojoko_contract").attributes["bands"]}
    assert bands["hp_grid_consumption"]["price"] == 0.2016
    assert bands["hp_grid_consumption"]["price_exact"] is True
    # Not enough statistics to estimate the other one
    assert bands["hc_grid_consumption"]["price"] is None
    assert "id" not in bands["hc_grid_consumption"]


async def test_options_enter_the_prices_of_the_contract(hass, fake_api):
    """The prices entered replace ecojoko's in the contract, during their validity."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    result = await options_bands_screen(
        hass, entry, fake_api, {2: "Heures Pleines", 3: "Heures Creuses"})
    defaults = schema_defaults(result)
    assert defaults["use_contract_prices"] is False

    async def configure(data):
        return await hass.config_entries.options.async_configure(result["flow_id"], data)

    result = await configure({**defaults, "use_contract_prices": True})
    assert result["step_id"] == "prices"
    assert set(schema_defaults(result)) == {
        "Heures Pleines – €/kWh", "Heures Creuses – €/kWh",
        "subscription_price", "prices_start", "prices_end"}
    result = await configure({})
    assert result["errors"] == {"base": "prices_required"}
    prices = {"Heures Pleines – €/kWh": 0.180336, "Heures Creuses – €/kWh": 0.134736,
              "subscription_price": 31.14, "prices_start": "2026-08-25"}
    result = await configure({**prices, "prices_end": "2026-08-01"})
    assert result["errors"] == {"prices_end": "prices_dates"}
    result = await configure({**prices, "prices_end": "2099-06-30"})
    assert result["step_id"] == "settings"
    result = await configure(dict(SETTINGS))
    await hass.async_block_till_done()
    assert entry.data["contract_prices"] == {
        "prices": {"2": 0.180336, "3": 0.134736}, "subscription": 31.14,
        "start": "2026-08-25", "end": "2099-06-30"}

    attributes = hass.states.get("sensor.ecojoko_contract").attributes
    bands = {band["key"]: band for band in attributes["bands"]}
    assert bands["hp_grid_consumption"]["price"] == 0.180336
    assert bands["hp_grid_consumption"]["price_source"] == "entered"
    assert attributes["entered_prices"] == {"start": "2026-08-25", "end": "2099-06-30"}

    # Unchecked, ecojoko's prices apply again
    result = await options_bands_screen(
        hass, entry, fake_api, {2: "Heures Pleines", 3: "Heures Creuses"})
    assert schema_defaults(result)["use_contract_prices"] is True
    result = await configure({**schema_defaults(result), "use_contract_prices": False})
    assert result["step_id"] == "settings"
    result = await configure(dict(SETTINGS))
    await hass.async_block_till_done()
    assert "contract_prices" not in entry.data
    assert hass.states.get("sensor.ecojoko_contract").attributes["entered_prices"] is None


async def test_answers_of_the_services_are_shared(hass, fake_api, monkeypatch):
    """The same data asked again is read once, for the time it may not change."""
    clock = {"now": 1000.0}
    monkeypatch.setattr(lm_api, "time", types.SimpleNamespace(monotonic=lambda: clock["now"]))
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    calls = len(fake_api.analysis_calls)

    for _ in range(2):
        await call_service(hass, "get_activations")
        await call_service(hass, "get_measures", measure="electricity", period="day")
        await call_service(
            hass, "get_measures", measure="electricity", period="month", date="2025-03-04")
    assert len(fake_api.analysis_calls) == calls + 3

    # The day is read again after four minutes, the activations after half an hour
    clock["now"] += 240
    await call_service(hass, "get_measures", measure="electricity", period="day")
    await call_service(hass, "get_activations")
    assert len(fake_api.analysis_calls) == calls + 4
    clock["now"] += 1800
    await call_service(hass, "get_activations")
    await call_service(
        hass, "get_measures", measure="electricity", period="month", date="2025-03-04")
    # An old month is kept a day
    assert len(fake_api.analysis_calls) == calls + 5
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["client"]["service_cache"]["misses"] == 5


def test_how_long_an_answer_is_kept():
    """A period that may still change is kept a few minutes, an old one a day."""
    today = dt_util.now().astimezone(dt_util.get_time_zone("Europe/Paris")).date()
    seconds = lm_services.cache_seconds
    assert seconds("measures", "day", today) == 240
    assert seconds("measures", "day", today - dt.timedelta(days=1)) == 240
    assert seconds("measures", "day", today - dt.timedelta(days=2)) == 24 * 3600
    assert seconds("measures", "year", today) == 240
    assert seconds("analysis", "week", None) == 3600
    assert seconds("savings", "month", dt.date(2025, 3, 4)) == 24 * 3600
    assert lm_services.period_end("week", dt.date(2026, 11, 18)) == dt.date(2026, 11, 22)
    assert lm_services.period_end("month", dt.date(2024, 2, 10)) == dt.date(2024, 2, 29)
    assert lm_services.period_end("year", dt.date(2026, 3, 4)) == dt.date(2026, 12, 31)


async def test_measures_service(hass, fake_api):
    """The service gives the measures of a period, today by default."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    answer = await call_service(hass, "get_measures", measure="electricity", period="week")
    assert answer["measure"] == "electricity" and answer["period"] == "week"
    await call_service(hass, "get_measures", measure="humidity", period="day", date="2026-11-18")
    assert fake_api.analysis_calls[-1] == ("measures", "humidity", "day", dt.date(2026, 11, 18))
    with pytest.raises(vol.Invalid):
        await call_service(hass, "get_measures", measure="water", period="day")


async def test_equipment_device_is_linked_by_the_id_of_the_ecojoko_device(hass, fake_api):
    """The device of an equipment is linked to the Ecojoko device by its id."""
    fake_api.equipments = [WATER_HEATER]
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    devices = dr.async_get(hass)
    main = registry_device(devices, (DOMAIN, entry.entry_id), entry.entry_id)
    heater = registry_device(devices, (DOMAIN, f"{entry.entry_id}_630220"), entry.entry_id)
    assert entry.runtime_data.main_device_id == main.id
    assert heater.via_device_id == main.id
    assert main.name == "Ecojoko"


async def test_groups_of_sensors_are_off_by_default(hass, fake_api):
    """Without their options, no sensor of the groups and no reading of them."""
    fake_api.equipments = [WATER_HEATER, TEMP_HUM_EQUIPMENT]
    entry = add_entry(hass, data={key: value for key, value in DATA.items() if key not in GROUPS})
    assert await setup_entry(hass, entry)

    unique_ids = {
        entity.unique_id
        for entity in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}
    for key in [*ACTIVITY_KEYS, *SAVINGS_KEYS, "contract"]:
        assert f"{entry.entry_id}_{key}" not in unique_ids, key
    assert not [unique_id for unique_id in unique_ids if "_630220_" in unique_id or "_3_" in unique_id]
    assert hass.states.get("select.chauffe_eau_control") is None
    # Nothing read from ecojoko for them
    assert fake_api.activity_calls == 0
    assert fake_api.equipment_reads == 0
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert [device.identifiers for device in devices] == [{(DOMAIN, entry.entry_id)}]

    # The card of the equipments asks to turn the option on
    answer = await call_service(hass, "get_equipments")
    assert answer == {"enabled": False, "equipments": []}
    # So do the cards read on demand, without reading ecojoko
    calls = len(fake_api.analysis_calls)
    assert (await call_service(hass, "get_activations"))["enabled"] is False
    assert (await call_service(hass, "get_savings", period="week"))["enabled"] is False
    assert fake_api.savings_periods == []
    assert (await call_service(hass, "get_consumption_analysis", period="week"))["enabled"] is False
    assert (await call_service(hass, "get_category_history", category=8))["enabled"] is False
    answer = await call_service(hass, "get_measures", measure="electricity", period="day")
    assert answer["enabled"] is False
    assert len(fake_api.analysis_calls) == calls
    answer = await call_service(hass, "get_measures", measure="temperature", period="day", check=True)
    assert answer == {"enabled": False}


async def test_sensors_of_a_group_turned_off_are_removed(hass, fake_api):
    """Turning an option off removes its sensors and the devices of the equipments."""
    fake_api.equipments = [WATER_HEATER, TEMP_HUM_EQUIPMENT]
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    entities = er.async_get(hass)
    assert entities.async_get("sensor.ecojoko_gap_over_7_days") is not None
    assert entities.async_get("sensor.chauffe_eau_power") is not None

    hass.config_entries.async_update_entry(entry, data={
        **entry.data, "use_activity_feature": False, "use_equipment_feature": False})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entities.async_get("sensor.ecojoko_gap_over_7_days") is None
    assert entities.async_get("sensor.chauffe_eau_power") is None
    assert entities.async_get("sensor.ecojoko_sonde_connection_to_the_assistant") is None
    assert entities.async_get("select.chauffe_eau_control") is None
    assert entities.async_get("binary_sensor.chauffe_eau_contactor") is None
    # The other groups are kept
    assert entities.async_get("sensor.ecojoko_contract") is not None
    assert entities.async_get("sensor.ecojoko_savings_this_week") is not None
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert [device.identifiers for device in devices] == [{(DOMAIN, entry.entry_id)}]
