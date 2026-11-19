"""Fixtures for the tests running inside a Home Assistant core.

These tests need pytest-homeassistant-custom-component (see
requirements_test_ha.txt). The ecojoko API client is patched: no test uses
the network.
"""
from __future__ import annotations

import copy
import datetime as dt
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.little_monkey import api as lm_api


@pytest.fixture(autouse=True, scope="session")
def pycares_shutdown_thread():
    """Start the shutdown thread of pycares before the first test.

    From pycares 4.9.0, the first destroyed DNS channel starts a thread
    that lasts until the end. The test tooling of the oldest supported Home
    Assistant fails the test that starts it, as a thread left behind: started
    beforehand, it is among the threads that every test finds.
    """
    try:
        import pycares
    except ImportError:
        return
    manager = getattr(pycares, "_shutdown_manager", None)
    if manager is not None and hasattr(manager, "destroy_channel"):
        # Nothing to destroy: the thread starts and waits
        manager.destroy_channel(None)

# What the patched client reports after a successful poll
VALUES = {
    "_gateway_firmware_version": "1.9",
    "_realtime_conso": 512,
    "_kwh": 4.2,
    "_kwh_hc_ns": 1.5,
    "_kwh_hp_ns": 2.5,
    "_indoor_temp": 20,
    "_outdoor_temp": 8.5,
    "_indoor_hum": 50,
    "_outdoor_hum": 80,
    "_contract": {
        "supplier_name": "EDF",
        "offer_id": 5480,
        "offer_name": "Zen Fixe - Option HP/HC",
        "offer_type": "HP/HC",
        "is_hchp": 1,
        "special_day": 1,
        "power": 9,
        "subscription_price": 24.77,
        "off_peak_timeslots": [{"start": "01:30", "stop": "07:00"}, {"start": "14:00", "stop": "16:30"}],
        "start_date": "2026-08-04",
    },
}


# What the patched client reports for the activity of the account
ACTIVITY = {
    "savings_7_days": -3,
    "reference_consumption_7_days": 74.4,
    "consumption_7_days": 74.33,
    "daily_consumption_7_days": [9.14, 12.46, 9.55, 12.43, 12.36, 7.92, 10.37],
    "cost_7_days": 16.6,
    "total_savings": 393.83,
    "max_power_month": 4290,
    "max_power_year": 6260,
    "max_power_alltime": 7386,
}


# What the patched client reports for the savings of the account
WEEK_BARS = [
    {"date": "2026-11-16", "savings": -0.35, "savings_kwh": -2.58, "cost": 1.8,
     "consumption": 7.58, "reference_cost": 1.45, "reference_consumption": 5.01},
] + [
    {"date": f"2026-11-{day}", "savings": None, "savings_kwh": None, "cost": None,
     "consumption": None, "reference_cost": None, "reference_consumption": None}
    for day in range(17, 23)
]


def savings_period(savings, start, bars):
    """Return the savings of a period as the patched client reports them."""
    return {
        "savings": savings, "savings_kwh": -2.58, "cost": 1.8, "consumption": 7.58,
        "reference_cost": 1.45, "reference_consumption": 5.01,
        "start": start, "missing_data": False, "bars": bars,
    }


SAVINGS = {
    "consumption_cost_12_months": 483.6,
    "reference_cost_12_months": 821.23,
    "savings_12_months": 337.63,
    "consumption_12_months": 1701.72,
    "reference_consumption_12_months": 3319,
    "savings_kwh_12_months": 1617.28,
    "savings_level": 5,
    "week": savings_period(-0.35, "2026-11-16", WEEK_BARS),
    "month": savings_period(-8.69, "2026-11-02", WEEK_BARS[:5]),
    "year": savings_period(322.32, "2026-01-01", WEEK_BARS[:1] * 12),
}


EQUIPMENT_DAY = {
    "date": "2026-11-18", "energy": 0.97, "cost": 0.14,
    "power": [{"time": "2026-11-18T20:00:00+01:00", "value": 2784}],
    "switches": [{"start": "2026-11-18T20:00:00+01:00", "end": None, "on": True,
                  "forced": True, "source": "command"}],
}


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load the integration from custom_components."""
    return


class FakeApi:
    """Control what the patched API client does."""

    def __init__(self) -> None:
        """Initialize: every call succeeds."""
        self.login_error = None
        self.data_error = None
        self.data_calls = 0
        # Values reported by the client, and the day they belong to
        self.values = dict(VALUES)
        self.stat_date = dt.datetime.now(ZoneInfo("Europe/Paris")).date()
        # Contract and tariff bands read by the setup
        self.contract = {
            "supplier_name": "EDF",
            "offer_name": "Zen Fixe - Option HP/HC",
            "offer_type": "HP/HC",
        }
        self.bands = {2: "Heures Pleines", 3: "Heures Creuses"}
        # Values of the activity of the account, or the error to raise
        self.activity = dict(ACTIVITY)
        self.activity_error = None
        self.activity_calls = 0
        # Savings of the account, or the error to raise
        self.savings = copy.deepcopy(SAVINGS)
        self.savings_error = None
        # Savings of the past periods asked for: (period, day)
        self.savings_periods = []
        # Analysis of the consumption, and the calls of its services
        self.analysis = {"available": True, "start": "2026-11-02", "cost": 14.46,
                         "consumption": 60.6, "categories": []}
        self.analysis_calls = []
        # Equipments of the gateway: none by default
        self.equipments = []
        self.equipment_error = None
        # Commands sent: (equipment id, mode, seconds), or the error to raise
        self.commands = []
        self.command_error = None
        # Readings of the equipments
        self.equipment_reads = 0

    def apply(self, equipment_id, mode):
        """Apply a mode to an equipment, as ecojoko does after a command."""
        for equipment in self.equipments:
            if equipment["id"] == equipment_id:
                equipment["state"]["mode"] = mode


@pytest.fixture
def fake_api():
    """Patch the API client; set the errors to raise on the returned object."""
    state = FakeApi()

    async def login(self):
        if state.login_error:
            raise state.login_error

    async def gateway(self):
        return None

    async def tariff_setup(self, weeks=4):
        if state.login_error:
            raise state.login_error
        return state.contract, dict(state.bands)

    async def get_data(self):
        state.data_calls += 1
        if state.data_error:
            raise state.data_error
        for name, value in state.values.items():
            setattr(self, name, value)
        self._equipments = copy.deepcopy(state.equipments)
        self._stat_date = state.stat_date

    async def get_activity(self):
        state.activity_calls += 1
        if state.activity_error:
            raise state.activity_error
        return dict(state.activity)

    async def get_savings(self):
        if state.savings_error:
            raise state.savings_error
        return copy.deepcopy(state.savings)

    async def get_savings_period(self, period, day):
        state.savings_periods.append((period, day))
        if state.savings_error:
            raise state.savings_error
        return copy.deepcopy(state.savings[period])

    async def get_analysis(self, period, day=None):
        state.analysis_calls.append(("analysis", period, day))
        if state.savings_error:
            raise state.savings_error
        return dict(state.analysis)

    async def get_category_history(self, category, day):
        state.analysis_calls.append(("history", category, day))
        return {"category": {"id": category}, "start": "2026-01-05", "bars": []}

    async def get_measures(self, measure, period, day):
        state.analysis_calls.append(("measures", measure, period, day))
        return {"start": None, "previous": None, "next": None, "bars": []}

    async def get_activations(self, page=0):
        state.analysis_calls.append(("activations", page))
        return {"start": None, "end": None, "pending": False, "activations": []}

    async def get_equipment(self, equipment_id):
        state.equipment_reads += 1
        if state.equipment_error:
            raise state.equipment_error
        return copy.deepcopy(next(
            equipment for equipment in state.equipments if equipment["id"] == equipment_id))

    async def get_equipment_day(self, equipment, day):
        return copy.deepcopy(EQUIPMENT_DAY)

    async def send_equipment_command(self, equipment_id, mode, seconds=None):
        state.commands.append((equipment_id, mode, seconds))
        if state.command_error:
            raise state.command_error
        state.apply(equipment_id, mode)

    client = lm_api.LittleMonkeyApiClient
    with patch.object(client, "async_get_cookiesdata", login), \
            patch.object(client, "async_get_gatewaydata", gateway), \
            patch.object(client, "async_get_data", get_data), \
            patch.object(client, "async_get_tariff_setup", tariff_setup),             patch.object(client, "async_get_activity", get_activity),             patch.object(client, "async_get_savings", get_savings),             patch.object(client, "async_get_savings_period", get_savings_period), \
            patch.object(client, "async_get_analysis", get_analysis), \
            patch.object(client, "async_get_category_history", get_category_history), \
            patch.object(client, "async_get_activations", get_activations), \
            patch.object(client, "async_get_measures", get_measures), \
            patch.object(client, "async_get_equipment", get_equipment), \
            patch.object(client, "async_get_equipment_day", get_equipment_day), \
            patch.object(client, "async_send_equipment_command", send_equipment_command):
        yield state
