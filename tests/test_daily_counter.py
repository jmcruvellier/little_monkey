"""Tests of the daily counter that never decreases during a day."""
from __future__ import annotations

import pytest

DAY = "2026-11-13"
NEXT_DAY = "2026-11-14"


@pytest.fixture
def counter(utils):
    """Return a new daily counter."""
    return utils.DailyCounter()


def test_increasing_values_are_published(counter):
    """A growing total is published as it is."""
    assert [counter.update(DAY, value) for value in (0.1, 0.5, 2, 7.32)] == [
        0.1, 0.5, 2, 7.32
    ]


def test_lower_value_is_held_until_caught_up(counter):
    """A correction downwards is hidden until the total catches up."""
    counter.update(DAY, 7.32)
    assert counter.update(DAY, 7.05) == 7.32
    assert counter.update(DAY, 7.2) == 7.32
    assert counter.update(DAY, 7.32) == 7.32
    assert counter.update(DAY, 7.4) == 7.4


def test_large_correction_is_held_too(counter):
    """A correction over 10 %, read as a meter reset by Home Assistant, is held."""
    counter.update(DAY, 3.4)
    assert counter.update(DAY, 3.0) == 3.4
    assert counter.update(DAY, 3.5) == 3.5


def test_new_day_is_the_only_accepted_decrease(counter):
    """The total restarts from the value of the new day."""
    counter.update(DAY, 8.1)
    assert counter.update(NEXT_DAY, 0.2) == 0.2
    assert counter.update(NEXT_DAY, 0.1) == 0.2
    assert counter.update(NEXT_DAY, 0.3) == 0.3


def test_without_day_the_value_is_not_tracked(counter):
    """A value whose day is unknown is published as it is."""
    assert counter.update(None, 5) == 5
    assert counter.update(None, 4) == 4
    assert counter.value is None


def test_restored_value_of_the_same_day_is_kept(counter):
    """After a restart the value published earlier that day still holds."""
    counter.restore(DAY, 7.32)
    assert counter.update(DAY, 7.05) == 7.32
    assert counter.update(DAY, 7.5) == 7.5


def test_restored_value_of_a_previous_day_is_dropped(counter):
    """After a restart on another day the new total is published."""
    counter.restore(DAY, 7.32)
    assert counter.update(NEXT_DAY, 0.4) == 0.4
