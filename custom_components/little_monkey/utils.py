"""Utils for little_monkey."""
from __future__ import annotations

import datetime as dt
import math
from zoneinfo import ZoneInfo

def account_unique_id(username):
    """Return the unique id of the config entry of an ecojoko account."""
    return str(username).strip().lower()

class DailyCounter:
    """Published value of a counter that restarts from zero every day.

    ecojoko sometimes corrects a daily total downwards. Home Assistant reads
    a decrease of a total_increasing sensor as a possible meter reset, and
    then counts the energy twice. The published value is therefore held
    until the real one catches up: a new day is the only accepted decrease.
    """

    def __init__(self):
        """Initialize without any published value."""
        self.day = None
        self.value = None

    def restore(self, day, value):
        """Set the value published before a restart and the day it belongs to."""
        self.day = day
        self.value = value

    def update(self, day, value):
        """Return the value to publish for the value received for a day."""
        if day is None:
            return value
        if day != self.day or self.value is None or value > self.value:
            self.day = day
            self.value = value
        return self.value

class DayParts:
    """Published daily totals of the parts of the grid consumption.

    The HC and HP totals, or the tariff bands, split the energy of the day.
    ecojoko sometimes moves energy from one part to another afterwards: on
    19/11/2026 it moved 2.21 kWh of the night from HC to HP. Each part held
    at its highest value (see DailyCounter) then counts the moved energy
    twice, and their sum exceeds the grid consumption.

    A part therefore grows by the increases of its value, and the increases
    of a reading are reduced so that the sum of the parts never exceeds the
    highest grid consumption of the day. A value lowered by ecojoko is held
    as by DailyCounter; the energy moved to another part is only counted
    when the grid consumption grows. The values being rounded to the
    hundredth of kWh, a part may then lag behind ecojoko by a hundredth.
    """

    def __init__(self, keys):
        """Initialize with the keys of the parts, without any published value."""
        self.keys = tuple(keys)
        self.day = None
        self._published = {}
        self._last = {}
        self._whole = None
        self._restored = {}
        self._data = None
        self._values = {}

    def restore(self, key, day, value):
        """Set the value of a part published before a restart, and its day."""
        if self.day is None:
            self._restored[key] = (day, value)
        elif day == self.day:
            self._published[key] = max(self._published.get(key, value), value)

    def update(self, day, values, whole):
        """Return the values to publish {key: kWh} after a reading.

        values: the energy of the parts by key, None when not known; whole:
        the grid consumption of the day, None when not known.
        """
        if day != self.day:
            # New day: the parts restart from zero, or from their restored values
            self.day = day
            self._published = {
                key: value for key, (restored_day, value) in self._restored.items()
                if restored_day == day}
            self._restored = {}
            self._last = {}
            self._whole = None
        if whole is not None:
            self._whole = whole if self._whole is None else max(self._whole, whole)
        increases = {}
        for key in self.keys:
            value = values.get(key)
            if value is None:
                continue
            base = self._last.get(key, self._published.get(key, 0))
            increases[key] = max(value - base, 0)
            self._last[key] = value
        total = sum(increases.values())
        if self._whole is not None and total > 0:
            room = self._whole - sum(self._published.values())
            if total > room:
                factor = max(room, 0) / total
                increases = {key: value * factor for key, value in increases.items()}
        for key, value in increases.items():
            self._published[key] = self._published.get(key, 0) + value
        return {key: round_value(value) for key, value in self._published.items()}

    def value(self, key, data):
        """Return the value to publish for a part, from the data of a poll.

        The parts are updated once per poll, whichever sensor asks first.
        """
        if data is not self._data:
            self._data = data
            self._values = self.update(
                data.get("stat_date"),
                {key: _number(data.get(key)) for key in self.keys},
                _number(data.get("grid_consumption")))
        return self._values.get(key)

def _number(value):
    """Return a value as a number, None if it is not one."""
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return value

class TariffPeriod:
    """Current tariff period, deduced from the daily counters of the periods.

    ecojoko gives the energy of each period of the day (HC and HP, or the six
    Tempo periods), not the current period. The current period is the one
    whose counter increased since the previous reading. It is known a few
    minutes late, when the counter of the new period gains its first
    hundredth of kWh, and it is kept while no counter increases.
    """

    def __init__(self):
        """Initialize without any known period."""
        self.period = None
        self._day = None
        self._counters = {}

    def update(self, day, counters):
        """Return the current period after a reading of the counters.

        counters: energy of the day by period, None when not known.
        """
        if day != self._day:
            # The counters restart from zero: the period goes on
            self._day = day
            self._counters = {}
        increases = {}
        for period, value in counters.items():
            if value is None:
                continue
            previous = self._counters.get(period)
            if previous is not None and value > previous:
                increases[period] = value - previous
            self._counters[period] = value
        if len(increases) == 1 or (increases and self.period not in increases):
            # When several counters increased, the period changed between
            # two readings: the one that gained the most is the likeliest
            self.period = max(increases, key=increases.get)
        # Several increases including the current period: the next reading
        # tells which one goes on
        return self.period

def get_paris_timezone():
    """Get Paris timezone."""
    return ZoneInfo('Europe/Paris')

def get_current_date(timezone):
    """Return local date."""
    return dt.datetime.now(timezone).date()

def get_value_from_json_array(json_array, item_key, item_value, value_key):
    """Return value from JSON array."""
    for item in json_array:
        if item[item_key] == item_value:
            return item[value_key]
    return None

def convert_to_float(value):
    """Convert to float."""
    return float(value) if value is not None else 0

def finite_number(value):
    """Return a value as a rounded number, or None when it is not a number."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if isinstance(value, bool) or not math.isfinite(number):
        return None
    return round_value(value if isinstance(value, int) else number)

def round_value(value, digits=2):
    """Round a number, and return anything else as it is.

    ecojoko sometimes returns values such as 19.900000000000002, and a sum
    of decimal numbers gives the same kind of result.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return value
    return round(value, digits)
