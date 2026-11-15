"""Tests of the integration inside a Home Assistant core.

They cover what needs the registries, the config entries and the flows:
migration from 1.2.7, entity names, availability, setup, reauthentication,
the setup form and the options.
"""
from __future__ import annotations

import datetime as dt
import json
import types
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
)

from custom_components.little_monkey import (
    api as lm_api,
    async_remove_config_entry_device,
    config_flow,
    coordinator as lm_coordinator,
)
from custom_components.little_monkey.diagnostics import (
    async_get_config_entry_diagnostics,
)

DOMAIN = "little_monkey"
DATA = {
    "name": "Ecojoko",
    "username": "User@Example.com",
    "password": "pw",
    "use_hchp_feature": True,
    "use_tempo_feature": False,
    "use_temphum_feature": True,
    "use_prod_feature": False,
    "poll_interval": 5,
}
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
REALTIME = "sensor.ecojoko_real_time_consumption"
GRID = "sensor.ecojoko_grid_consumption"
FORM = data_entry_flow.FlowResultType.FORM
ABORT = data_entry_flow.FlowResultType.ABORT
CREATE_ENTRY = data_entry_flow.FlowResultType.CREATE_ENTRY


def add_entry(hass, **kwargs):
    """Add a config entry of the current version to Home Assistant."""
    entry = MockConfigEntry(
        **{"domain": DOMAIN, "title": "user", "version": 2, "data": DATA, **kwargs}
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
        data={**DATA, "lang": "fr-FR"},
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
    assert entry.version == 2
    assert "lang" not in entry.data
    assert entry.options == {}
    assert entry.data["password"] == "pw"
    assert entry.data["name"] == "Ecojoko"
    assert entry.unique_id == "user@example.com"

    # Same entity ids, new unique ids, nothing duplicated; only the sensors
    # added by 1.3.0 are created
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == count_before + 1 + len(ACTIVITY_KEYS)
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
    assert len(entities) == count_before + 1 + len(ACTIVITY_KEYS)
    assert hass.states.get(entity_ids["realtime_consumption"]).state == "512"


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
    keys = [*ENABLED, "current_tariff_period", *ACTIVITY_KEYS]
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
        await hass.config_entries.flow.async_configure(result["flow_id"], dict(DATA))

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
            result["flow_id"], dict(DATA)
        )
        assert result["type"] == FORM, key
        assert result["errors"] == {"base": key}

    fake_api.login_error = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(DATA)
    )
    await hass.async_block_till_done()
    assert result["type"] == CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.version == 2
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
            result["flow_id"], {**DATA, "name": name}
        )
        assert result["type"] == FORM
        assert result["errors"] == {"name": "name_required"}

    fake_api.login_error = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(DATA)
    )
    await hass.async_block_till_done()
    assert result["type"] == CREATE_ENTRY


async def test_options_flow_requires_a_name(hass, fake_api):
    """A blank name is refused in the options and nothing is saved."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**DATA, "name": " "}
    )
    assert result["type"] == FORM
    assert result["errors"] == {"name": "name_required"}
    assert entry.data["name"] == "Ecojoko"


async def test_user_flow_refuses_an_account_twice(hass, fake_api):
    """The same ecojoko account, written differently, cannot be added again."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**DATA, "username": " user@example.COM "}
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
        result["flow_id"], {**DATA, "password": "wrong", "poll_interval": 10}
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
        result["flow_id"], {**DATA, "password": "good", "poll_interval": 10}
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
    """With the Tempo option, the period gives the color of the day."""
    fake_api.values.update({"_tempo_hc_red": 0.5, "_tempo_hp_red": 1.0})
    entry = add_entry(hass, data={**DATA, "use_hchp_feature": False, "use_tempo_feature": True})
    assert await setup_entry(hass, entry)
    entity_id = period_entity(hass, entry)
    assert hass.states.get(entity_id).attributes["options"] == [
        "hc_blue", "hp_blue", "hc_white", "hp_white", "hc_red", "hp_red"]

    fake_api.values["_tempo_hp_red"] = 1.1
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


SAVINGS = "sensor.ecojoko_savings_over_7_days"


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
    assert savings.attributes["friendly_name"] == "Ecojoko Savings over 7 Days"
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
