"""Utils for little_monkey."""
from __future__ import annotations

import datetime
import pytz

def has_day_changed(datetime1, datetime2):
    """Compare two dates and return if day has changed."""
    # Extract date components (year, month, day)
    _date1 = datetime1.date()
    _date2 = datetime2.date()
    # Compare dates
    return _date1 != _date2

def get_paris_timezone():
    """Get Paris timezone."""
    return pytz.timezone('Europe/Paris')

def get_current_date(timezone):
    """Return local date."""
    return datetime.datetime.now(timezone).date()

def get_current_time(timezone):
    """Return local time."""
    return datetime.datetime.now(timezone).time()

def get_value_from_json_array(json_array, item_key, item_value, value_key):
    """Return value from JSON array."""
    for item in json_array:
        if item[item_key] == item_value:
            return item[value_key]
    return None

def convert_to_float(value):
    """Convert to float."""
    return float(value) if value is not None else 0
