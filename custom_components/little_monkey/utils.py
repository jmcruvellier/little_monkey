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
