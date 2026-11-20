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


# --- Parts of the grid consumption (HC and HP totals, tariff bands)

HC = "hc_grid_consumption"
HP = "hp_grid_consumption"


@pytest.fixture
def parts(utils):
    """Return the HC and HP totals of a new day."""
    return utils.DayParts((HC, HP))


def test_parts_follow_ecojoko(parts):
    """Growing parts are published as they are."""
    assert parts.update(DAY, {HC: 1.5, HP: None}, 1.5) == {HC: 1.5}
    assert parts.update(DAY, {HC: 3.2, HP: 0}, 3.2) == {HC: 3.2, HP: 0}
    assert parts.update(DAY, {HC: 3.2, HP: 2.05}, 5.25) == {HC: 3.2, HP: 2.05}


def test_energy_moved_to_another_part_is_counted_once(parts):
    """Ecojoko moved 2.21 kWh of the night from HC to HP (19/11/2026)."""
    # Rounded values: HC never exceeds the grid consumption
    assert parts.update(DAY, {HC: 8.88, HP: 0}, 8.87) == {HC: 8.87, HP: 0}
    assert parts.update(DAY, {HC: 8.88, HP: 3.42}, 12.3) == {HC: 8.87, HP: 3.42}
    # The moved energy is not counted twice: HC + HP is the grid consumption
    assert parts.update(DAY, {HC: 6.67, HP: 5.63}, 12.3) == {HC: 8.87, HP: 3.43}
    # The off-peak consumption of the evening counts in HC again
    assert parts.update(DAY, {HC: 7.67, HP: 5.63}, 13.3) == {HC: 9.87, HP: 3.43}


def test_lowered_part_is_held(parts):
    """A part lowered then raised back by ecojoko is counted once."""
    parts.update(DAY, {HC: 5.0, HP: 1.0}, 6.0)
    assert parts.update(DAY, {HC: 4.9, HP: 1.0}, 6.0) == {HC: 5.0, HP: 1.0}
    assert parts.update(DAY, {HC: 5.0, HP: 1.0}, 6.0) == {HC: 5.0, HP: 1.0}
    assert parts.update(DAY, {HC: 5.3, HP: 1.0}, 6.3) == {HC: 5.3, HP: 1.0}


def test_increases_share_the_room_left(parts):
    """Increases larger than the growth of the grid consumption are reduced."""
    parts.update(DAY, {HC: 2.0, HP: 2.0}, 4.0)
    assert parts.update(DAY, {HC: 3.0, HP: 3.0}, 5.0) == {HC: 2.5, HP: 2.5}


def test_parts_without_grid_consumption(parts):
    """Without the grid consumption, the parts only never decrease."""
    parts.update(DAY, {HC: 2.0, HP: 1.0}, None)
    assert parts.update(DAY, {HC: 1.8, HP: 3.0}, None) == {HC: 2.0, HP: 3.0}


def test_new_day_restarts_the_parts(parts):
    """The parts restart from the values of the new day."""
    parts.update(DAY, {HC: 8.88, HP: 3.42}, 12.3)
    assert parts.update(NEXT_DAY, {HC: 0.4, HP: 0}, 0.4) == {HC: 0.4, HP: 0}


def test_restored_parts_of_the_day(parts):
    """The parts published before a restart of the same day are kept."""
    parts.restore(HC, DAY, 8.88)
    parts.restore(HP, "2026-11-12", 9.5)
    assert parts.update(DAY, {HC: 6.67, HP: 3.42}, 12.3) == {HC: 8.88, HP: 3.42}
    # A sensor restored after the first reading of the day
    parts.restore(HP, DAY, 3.5)
    assert parts.update(DAY, {HC: 6.67, HP: 5.63}, 12.4) == {HC: 8.88, HP: 3.52}


def test_part_restored_after_another_sensor_read_the_poll(parts):
    """A sensor restored after another one read the poll keeps its value.

    On 19/11/2026, at a restart, HC was restored and published first: HP,
    restored afterwards, published the 1.72 of ecojoko instead of its 1.83.
    """
    data = {"stat_date": DAY, "grid_consumption": 3.0, HC: 1.28, HP: 1.72}
    parts.restore(HC, DAY, 1.28)
    assert parts.value(HC, data) == 1.28
    parts.restore(HP, DAY, 1.83)
    assert parts.value(HP, data) == 1.83
    assert parts.value(HC, data) == 1.28
    # The next reading adds its increase, within the growth of the grid
    # consumption: 3.2 - 1.28 - 1.83
    assert parts.value(HP, {**data, HP: 1.9, "grid_consumption": 3.2}) == 1.92


def test_parts_are_updated_once_per_poll(parts):
    """Every sensor of a poll gets the values of the same update."""
    data = {"stat_date": DAY, "grid_consumption": 4.0, HC: 3.0, HP: 1.0}
    assert parts.value(HC, data) == 3.0
    assert parts.value(HP, data) == 1.0
    assert parts.value(HC, data) == 3.0
    assert parts.value(HC, {**data, HC: 3.5, "grid_consumption": 4.5}) == 3.5
