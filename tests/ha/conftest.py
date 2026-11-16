"""Fixtures for the tests running inside a Home Assistant core.

These tests need pytest-homeassistant-custom-component (see
requirements_test_ha.txt). The ecojoko API client is patched: no test uses
the network.
"""
from __future__ import annotations

import datetime as dt
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.little_monkey import api as lm_api

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
        # Values of the activity of the account, or the error to raise
        self.activity = dict(ACTIVITY)
        self.activity_error = None
        self.activity_calls = 0


@pytest.fixture
def fake_api():
    """Patch the API client; set the errors to raise on the returned object."""
    state = FakeApi()

    async def login(self):
        if state.login_error:
            raise state.login_error

    async def gateway(self):
        return None

    async def get_data(self):
        state.data_calls += 1
        if state.data_error:
            raise state.data_error
        for name, value in state.values.items():
            setattr(self, name, value)
        self._stat_date = state.stat_date

    async def get_activity(self):
        state.activity_calls += 1
        if state.activity_error:
            raise state.activity_error
        return dict(state.activity)

    client = lm_api.LittleMonkeyApiClient
    with patch.object(client, "async_get_cookiesdata", login), \
            patch.object(client, "async_get_gatewaydata", gateway), \
            patch.object(client, "async_get_data", get_data), \
            patch.object(client, "async_get_activity", get_activity):
        yield state
