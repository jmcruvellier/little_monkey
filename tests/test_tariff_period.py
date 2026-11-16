"""Tests of the current tariff period deduced from the daily counters."""
from __future__ import annotations

import pytest

DAY = "2026-11-13"
NEXT_DAY = "2026-11-14"


@pytest.fixture
def period(utils):
    """Return a new tariff period."""
    return utils.TariffPeriod()


def test_unknown_until_a_counter_increases(period):
    """A first reading tells nothing: no counter can have increased yet."""
    assert period.update(DAY, {"hc": 1.2, "hp": 3.4}) is None
    assert period.update(DAY, {"hc": 1.2, "hp": 3.4}) is None
    assert period.update(DAY, {"hc": 1.2, "hp": 3.41}) == "hp"


def test_period_is_kept_while_no_counter_increases(period):
    """A low consumption does not lose the period."""
    period.update(DAY, {"hc": 1.2, "hp": 3.4})
    period.update(DAY, {"hc": 1.25, "hp": 3.4})
    assert period.update(DAY, {"hc": 1.25, "hp": 3.4}) == "hc"
    # A correction downwards is not an increase
    assert period.update(DAY, {"hc": 1.25, "hp": 3.3}) == "hc"


def test_change_of_period(period):
    """The new period is known when its counter increases."""
    period.update(DAY, {"hc": 1.2, "hp": 3.4})
    period.update(DAY, {"hc": 1.2, "hp": 3.5})
    # Both increased: the change happened between the readings
    assert period.update(DAY, {"hc": 1.3, "hp": 3.52}) == "hp"
    assert period.update(DAY, {"hc": 1.4, "hp": 3.52}) == "hc"


def test_both_increased_without_known_period(period):
    """The counter that gained the most is the likeliest period."""
    period.update(DAY, {"hc": 1.2, "hp": 3.4})
    assert period.update(DAY, {"hc": 1.21, "hp": 3.6}) == "hp"


def test_period_goes_on_over_a_new_day(period):
    """The counters restart from zero at midnight, the period goes on."""
    period.update(DAY, {"hc_blue": 4.0, "hp_blue": 9.0})
    period.update(DAY, {"hc_blue": 4.1, "hp_blue": 9.0})
    assert period.update(NEXT_DAY, {"hc_red": 0.01, "hp_red": None}) == "hc_blue"
    assert period.update(NEXT_DAY, {"hc_red": 0.03, "hp_red": None}) == "hc_red"


def test_unknown_counters_are_ignored(period):
    """A counter without value is neither an increase nor a reference."""
    period.update(DAY, {"hc": None, "hp": 3.4})
    assert period.update(DAY, {"hc": 0.5, "hp": 3.4}) is None
    assert period.update(DAY, {"hc": 0.6, "hp": 3.4}) == "hc"
