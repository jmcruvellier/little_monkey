"""Tests of the integration inside a Home Assistant core.

They cover what needs the registries, the config entries and the flows:
migration from 1.2.7, entity names, availability, setup, reauthentication,
the setup form and the options.
"""
from __future__ import annotations

import datetime as dt
import json

from homeassistant import config_entries, data_entry_flow
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
)

from custom_components.little_monkey import (
    api as lm_api,
    async_remove_config_entry_device,
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
# Sensors created with the options of DATA
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
    """Set up a config entry and return whether it succeeded."""
    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
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

    # Same entity ids, new unique ids, nothing created, nothing duplicated
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == count_before
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
    assert len(entities) == count_before
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
    expected = [entry.entry_id, *[f"{entry.entry_id}_{key}" for key in ENABLED]]
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
    """Entities are unavailable while the API fails, then come back."""
    entry = add_entry(hass)
    assert await setup_entry(hass, entry)
    coordinator = hass.data[DOMAIN][entry.entry_id]

    fake_api.data_error = lm_api.LittleMonkeyApiClientCommunicationError("down")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(REALTIME).state == "unavailable"

    fake_api.data_error = None
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(REALTIME).state == "512"


# --- Energy totals never decrease during a day


async def refresh(hass, entry):
    """Poll ecojoko once."""
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
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
    entry = add_entry(hass, title="User@Example.com")
    assert await setup_entry(hass, entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    text = json.dumps(diagnostics, default=str)
    assert "pw" not in json.dumps(diagnostics["entry"]["data"])
    for secret in ("User@Example.com", "user@example.com"):
        assert secret not in text
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
