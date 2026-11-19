"""API Client for little_monkey."""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import math
import socket
import time
import aiohttp
from .const import (
    CONF_API_ACTIVITY_TIMEOUT,
    CONF_API_TIMEOUT,
    CONF_API_STAT_REFRESH,
    CONF_API_KEEP_LIVE,
    CONF_API_KEEP_LIVE_RETRY,
    CONF_API_CONTRACT_REFRESH,
    CONF_API_CONTRACT_RETRY,
    ECOJOKO_ACTIVITY_URL,
    ECOJOKO_LOGIN_URL,
    ECOJOKO_GATEWAYS_URL,
    ECOJOKO_GATEWAY_URL,
    LOGGER,
    VERSION
)
from .utils import (
    get_current_date,
    get_paris_timezone,
    finite_number,
    round_value)
from .tariff import (
    OFF_PEAK,
    PEAK,
    PRICE_DAYS,
    active_contract,
    bands_of,
    TOTAL_BANDS,
    bands_of_offer,
    day_costs,
    day_values,
    estimate_prices,
    exact_prices,
    local_date)

TZ = get_paris_timezone()

# Response headers left out of the diagnostics: they hold the session
HIDDEN_HEADERS = {"set-cookie", "set-cookie2"}

# Errors raised when an API response does not have the expected format
PARSE_ERRORS = (KeyError, IndexError, TypeError, ValueError, AttributeError)


class LittleMonkeyApiClientError(Exception):
    """Exception to indicate a general API error."""


class LittleMonkeyApiClientCommunicationError(
    LittleMonkeyApiClientError
):
    """Exception to indicate a communication error."""


class LittleMonkeyApiClientAuthenticationError(
    LittleMonkeyApiClientError
):
    """Exception to indicate an authentication error."""


def _daily_consumption(data) -> list | None:
    """Return the consumption of each of the last 7 days, in kWh.

    ecojoko gives the mean power of each day, in W, the oldest first.
    """
    if not isinstance(data, list):
        return None
    days = [finite_number(power) for power in data]
    if any(power is None for power in days):
        return None
    return [round_value(power * 24 / 1000) for power in days]


def parse_activity(payload) -> dict:
    """Return the values of an answer of the activity API, by sensor key.

    savings_7_days: gap in % between the consumption of the last 7 days and
    the reference consumption, negative for a saving. ecojoko gives it only
    once a reference week is known: None before.
    """
    activity = payload["activity"]
    savings = activity.get("savings_7j") or {}
    consumption = activity.get("conso_7j") or {}
    max_power = activity.get("max_power") or {}
    reference_week = activity.get("week_reference") == 1
    return {
        "savings_7_days": (
            finite_number(savings.get("value")) if reference_week else None),
        "reference_consumption_7_days": (
            finite_number(savings.get("ref_kwh")) if reference_week else None),
        "consumption_7_days": finite_number(consumption.get("kwh")),
        "daily_consumption_7_days": _daily_consumption(consumption.get("data")),
        "cost_7_days": finite_number(consumption.get("value")),
        "total_savings": finite_number(
            (activity.get("conso_all") or {}).get("value")),
        "max_power_month": finite_number(max_power.get("month")),
        "max_power_year": finite_number(max_power.get("year")),
        "max_power_alltime": finite_number(max_power.get("alltime")),
    }


def parse_savings_summary(payload) -> dict:
    """Return the savings over the last 12 months, by key.

    In euros: the cost of the consumption, the cost of the reference
    consumption and their difference, the savings; in kWh: the consumption,
    the reference one and their difference. The level of the savings goes
    from 1 to 5.
    """
    savings = payload["savings"]
    mine = (savings.get("savings") or {}).get("me") or {}
    consumption = finite_number(savings.get("kwh"))
    reference = finite_number(savings.get("profil_initial_kwh"))
    return {
        "consumption_cost_12_months": finite_number(savings.get("conso")),
        "reference_cost_12_months": finite_number(savings.get("profil_initial")),
        "savings_12_months": finite_number(mine.get("data")),
        "consumption_12_months": consumption,
        "reference_consumption_12_months": reference,
        "savings_kwh_12_months": (
            None if consumption is None or reference is None
            else round_value(reference - consumption)),
        "savings_level": finite_number(mine.get("level")),
    }


def _savings_values(item) -> dict:
    """Return the savings of a period or of a bar of savingstat.

    ecojoko gives the savings in euros with their sign, negative for an
    overconsumption, but in kWh without it: the sign of the euros is given
    to the kWh.
    """
    savings = finite_number(item.get("val"))
    savings_kwh = finite_number(item.get("val_kwh"))
    if savings_kwh is not None and savings is not None and savings < 0:
        savings_kwh = -abs(savings_kwh)
    return {
        "savings": savings,
        "savings_kwh": savings_kwh,
        "cost": finite_number(item.get("price", item.get("conso"))),
        "consumption": finite_number(item.get("kwh", item.get("conso_kwh"))),
        "reference_cost": finite_number(item.get("ref")),
        "reference_consumption": finite_number(item.get("ref_kwh")),
    }


def parse_savingstat(payload, today) -> dict:
    """Return the savings of a week, a month or a year, and their bars.

    The bars are the days of a week, the weeks of a month or the months of
    a year. A bar after today has no value yet: ecojoko gives zeros, which
    are replaced by None.
    """
    stat = payload["stat"]
    period = stat["period"]
    start = local_date(period.get("this"))
    bars = []
    for item in stat["data"]:
        day = local_date(item.get("time"))
        values = _savings_values(item)
        if day is None or day > today:
            values = dict.fromkeys(values)
        bars.append({"date": None if day is None else day.isoformat(), **values})
    return {
        **_savings_values(period),
        "start": None if start is None else start.isoformat(),
        "missing_data": bool(period.get("missing_data")),
        "bars": bars,
    }


# Periods of the detail of the savings, and their letter in the ecojoko URL
SAVINGS_PERIODS = {"week": "w", "month": "m", "year": "y"}

# Trend of a category of the analysis, from its evol_status
ANALYSIS_TRENDS = {1: "up", 2: "down"}


def _iso_day(milliseconds) -> str | None:
    """Return a time in milliseconds as an ISO date in Paris, or None."""
    day = local_date(milliseconds)
    return None if day is None else day.isoformat()


def _iso_time(seconds, scale=1) -> str | None:
    """Return a time as an ISO date and time in Paris, or None.

    The time is in seconds, or in milliseconds with a scale of 1000.
    """
    number = finite_number(seconds)
    if number is None:
        return None
    return dt.datetime.fromtimestamp(number / scale, TZ).isoformat()


def _analysis_category(item, children=True) -> dict:
    """Return a category of the analysis of the consumption."""
    category = item.get("category") or {}
    result = {
        "id": category.get("id"),
        "name": category.get("name"),
        "color": category.get("color"),
        "cost": finite_number(item.get("price")),
        "consumption": finite_number(item.get("kwh")),
        "percentage": finite_number(item.get("percentage")),
    }
    if children:
        result["trend"] = ANALYSIS_TRENDS.get(item.get("evol_status"))
        result["beta"] = bool(item.get("is_beta"))
        result["children"] = [
            _analysis_category(child, children=False)
            for child in item.get("usage_childrens") or []
        ]
    return result


def parse_analysis(payload) -> dict:
    """Return the analysis of the consumption of a period, by category.

    ecojoko analyses a period once it is over: before, it answers with an
    error and its explanation, returned as unavailable with its message.
    """
    if payload.get("error_id"):
        period = (payload.get("stat") or {}).get("period") or payload.get("period") or {}
        return {
            "available": False,
            "message": payload.get("error_desc"),
            "start": _iso_day(period.get("this")),
        }
    stat = payload["stat"]
    period = stat["period"]
    return {
        "available": True,
        "start": _iso_day(period.get("this")),
        "cost": finite_number(period.get("price")),
        "consumption": finite_number(period.get("kwh")),
        "categories": [_analysis_category(item) for item in stat["data"]],
    }


def parse_category_history(payload) -> dict:
    """Return the consumption of a category, week by week over a year.

    ecojoko gives two points a week, its start and its end, for a chart in
    steps: one bar a week is kept.
    """
    history = payload["usage_history"]
    category = history.get("category") or {}
    weeks = {}
    for item in history["data"]:
        week = item.get("dtime", item.get("time"))
        if week not in weeks:
            weeks[week] = {
                "date": _iso_day(week),
                "cost": finite_number(item.get("price")),
                "consumption": finite_number(item.get("kwh")),
                "percentage": finite_number(item.get("percentage")),
            }
    return {
        "category": {
            "id": category.get("id"),
            "name": category.get("name"),
            "color": category.get("color"),
        },
        "start": _iso_day((history.get("period") or {}).get("this")),
        "bars": list(weeks.values()),
    }


def parse_activations(payload) -> dict:
    """Return the activations of the appliances detected over 48 hours.

    Each one has its start, its end, its mean power, its energy and the
    shape ecojoko draws for it: width, height and color.
    """
    activations = []
    for item in payload["appliances"]:
        picto = item.get("picto") or {}
        activations.append({
            "start": _iso_time(item.get("start_date"), 1000),
            "end": _iso_time(item.get("end_date"), 1000),
            "power": finite_number(item.get("power")),
            "energy": finite_number(item.get("kwh")),
            "shape": {
                "width": finite_number(picto.get("w")),
                "height": finite_number(picto.get("h")),
                "color": picto.get("color"),
            },
        })
    return {
        "start": _iso_time(payload.get("start_time")),
        "end": _iso_time(payload.get("stop_time")),
        "pending": bool(payload.get("is_pending")),
        "activations": activations,
    }


# Scales of the measures of ecojoko, by period: as its page « Mesures », a
# day of power every few minutes, 7 days, 30 days ending on the date (its
# « Mois »), and the 12 months of a year
MEASURE_PERIODS = {"day": "d4", "week": "w", "month": "m6", "year": "y"}
# Kinds of measures: the API and the device that measures them
MEASURES = {"electricity": "powerstat", "temperature": "tempstat", "humidity": "humstat"}
# The temperature and humidity sensor has no 30 days ending on a date (m6
# gives a single day): its month is the calendar month
CLIMATE_MONTH = "m"


def _measure_period(period) -> dict:
    """Return the start of a period of measures, and of the ones around it."""
    return {
        "start": _iso_time(period.get("this"), 1000),
        "previous": _iso_time(period.get("prev"), 1000),
        "next": _iso_time(period.get("next"), 1000),
    }


def _measure_bands(stat) -> list:
    """Return the tariff bands of a statistics response: id, label and color."""
    return [
        {"id": item.get("id"), "label": item.get("label"), "color": item.get("color")}
        for item in stat.get("pricing_details") or []
        if isinstance(item, dict)
    ]


def parse_power_day(payload) -> dict:
    """Return the power of a day, every few minutes, with its tariff band.

    Each point has its power and the base load (consobase) in watts, and the
    id of the band of its time.
    """
    stat = payload["stat"]
    period = stat["period"]
    return {
        **_measure_period(period),
        "energy": finite_number(period.get("kwh")),
        "cost": finite_number(period.get("price")),
        "production": _positive(period.get("kwh_prod")),
        "bands": _measure_bands(stat),
        "points": [
            {
                "time": _iso_time(item.get("time"), 1000),
                "power": finite_number(item.get("value")),
                "base": finite_number(item.get("consobase")),
                "band": item.get("pricing"),
            }
            for item in stat.get("data") or []
        ],
    }


def _positive(value):
    """Return a production, given negative by ecojoko, as a positive number."""
    number = finite_number(value)
    return None if number is None else abs(number)


def parse_energy_bars(payload) -> dict:
    """Return the energy of the days or months of a period, by tariff band.

    Each bar has its energy and cost, those of each band, its base load and
    the production injected into the grid.
    """
    stat = payload["stat"]
    period = stat["period"]
    bars = []
    for item in stat.get("data") or []:
        bars.append({
            "date": _iso_day(item.get("time")),
            "energy": finite_number(item.get("kwh")),
            "cost": finite_number(item.get("value")),
            "base_energy": finite_number(item.get("consobase_kwh")),
            "production": _positive(item.get("kwh_prod")),
            "bands": [
                {
                    "id": band.get("id"),
                    "energy": finite_number(band.get("kwh")),
                    "cost": finite_number(band.get("price")),
                }
                for band in item.get("subconsumption") or []
                if isinstance(band, dict)
            ],
        })
    return {
        **_measure_period(period),
        "energy": finite_number(period.get("kwh")),
        "cost": finite_number(period.get("price")),
        "production": _positive(period.get("kwh_prod")),
        "bands": _measure_bands(stat),
        "bars": bars,
    }


def parse_climate(payload) -> dict:
    """Return the temperature or humidity of a period, inside and outside.

    Just after midnight, a day may come without its period yet.
    """
    stat = payload["stat"]
    period = stat.get("period") or {}
    return {
        **_measure_period(period),
        "unit": period.get("measure_unit"),
        "points": [
            {
                "time": _iso_time(item.get("time"), 1000),
                "inside": finite_number(item.get("value")),
                "outside": finite_number(item.get("ext_value")),
            }
            for item in stat.get("data") or []
        ],
    }


# Origin of the last change of state of a piloted equipment, by ecojoko id
SWITCH_SOURCES = {1: "command", 2: "schedule", 3: "timer"}
# ecojoko gives this battery level to an equipment plugged in the mains
MAINS_BATTERY_LEVEL = 255


def battery_percent(level) -> int | None:
    """Return the battery of an equipment as ecojoko shows it, in percent.

    ecojoko gives a level from 0 to 10 (the voltage of the batteries apart),
    which its application draws as a battery of five bars: 7 is shown as
    80 %. None for an equipment plugged in the mains or without a level.
    """
    level = finite_number(level)
    if level is None or level == MAINS_BATTERY_LEVEL or level < 0:
        return None
    for top, percent in ((0, 0), (2, 20), (4, 40), (6, 60), (8, 80)):
        if level <= top:
            return percent
    return 100


def _percent(value) -> float | None:
    """Return a percentage given as a number or as a text such as "66%"."""
    if isinstance(value, str):
        value = value.strip().rstrip("%").strip()
        try:
            value = float(value)
        except ValueError:
            return None
    number = finite_number(value)
    return number if number is not None and 0 <= number <= 100 else None


def _local_time(text) -> dt.datetime | None:
    """Return a time "YYYY-MM-DD HH:MM:SS" in Paris, or None."""
    try:
        return dt.datetime.strptime(str(text), "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)
    except ValueError:
        return None


def equipment_controls(commands, showable) -> list:
    """Return the controls ecojoko offers for an equipment.

    Its web application shows the same buttons: forced, absence and back to
    automatic when the equipment has a forced mode, on and off otherwise,
    nothing when ecojoko hides them. An equipment of an unknown type is
    piloted the same way as soon as it has these commands.
    """
    commands = set(commands)
    showable = showable if isinstance(showable, dict) else {}
    if showable.get("show_switch_buttons", 1) != 1:
        return []
    if showable.get("switch_forced_mode", 1) and {"on_forced", "off_forced"} <= commands:
        return ["forced", "absence", "auto"]
    if {"on", "off"} <= commands:
        return ["on", "off"]
    return []


def _equipment_state(state, controls) -> dict:
    """Return the state of an equipment: power, on, forced, mode..."""
    state = state if isinstance(state, dict) else {}
    on = state.get("onoff")
    forced = state.get("forced")
    mode = None
    if "auto" in controls and forced is not None:
        # Forced on, or off for an absence; automatic otherwise
        mode = ("forced" if on else "absence") if forced else "auto"
    elif "on" in controls and on is not None:
        mode = "on" if on else "off"
    until = finite_number(state.get("switch_until"))
    # A temperature sensor gives tenths of a degree
    temperature = finite_number(state.get("temperature"))
    return {
        "power": finite_number(state.get("power_level")),
        "on": None if on is None else bool(on),
        "forced": None if forced is None else bool(forced),
        "mode": mode,
        # As ecojoko words it: "Éteint depuis 05:24"
        "switch_state": state.get("switch_state"),
        "since": _iso_time(state.get("switch_time"), 1000),
        # Only while a forced mode lasts: -1 or the end of the last one otherwise
        "until": _iso_time(until, 1000) if forced and until and until > 0 else None,
        "source": SWITCH_SOURCES.get(state.get("switch_last_source")),
        "voltage": finite_number(state.get("voltage")),
        "max_power": finite_number(state.get("max_power_level")),
        "temperature": None if temperature is None else round_value(temperature / 10, 1),
        "humidity": finite_number(state.get("humidity")),
    }


def parse_equipment(device) -> dict:
    """Return an equipment of the gateway: its identity, status and state.

    Every equipment has the same description in ecojoko, whatever its type:
    its controls and measures come from the commands it accepts.
    """
    settings = device.get("device_settings") or {}
    commands = [command for command in device.get("device_commands") or []
                if isinstance(command, str)]
    controls = equipment_controls(commands, device.get("device_showable_settings"))
    battery = device.get("battery") or {}
    wifi = (device.get("lulo_network_status") or {}).get("wifi") or {}
    status = device.get("device_status")
    return {
        "id": str(device["device_id"]),
        "type": device.get("device_type"),
        "model": device.get("device_model"),
        "name": settings.get("name") or device.get("device_type"),
        "firmware": device.get("device_fw_ver"),
        "connected": None if status is None else status == 1,
        "status": device.get("device_status_desc"),
        "signal": _percent((device.get("signal") or {}).get("value")),
        "battery": battery_percent(battery.get("level")),
        "wifi_signal": _percent(wifi.get("signal")) if wifi.get("state") == 1 else None,
        "controls": controls,
        # Measures of the day: power and energy, and the changes of state
        "measures": "plugstat" in commands,
        "switches": "switchstat" in commands,
        "state": _equipment_state(device.get("device_state"), controls),
    }


# Durations accepted for a forced mode and an absence, in seconds. ecojoko
# offers 1 to 4 hours of forced mode and an absence until a day, but accepts
# any duration
EQUIPMENT_DURATIONS = {"forced": (60, 24 * 3600), "absence": (60, 366 * 24 * 3600)}


def equipment_command(mode, seconds=None) -> str:
    """Return the ecojoko command of a mode of a piloted equipment.

    Forced on or off (absence) for a number of seconds, back to automatic
    (what the "Automatique" button of ecojoko sends), or on and off for an
    equipment without a forced mode.
    """
    if mode == "auto":
        return "off_forced/1"
    if mode in ("on", "off"):
        return mode
    if mode in EQUIPMENT_DURATIONS:
        low, high = EQUIPMENT_DURATIONS[mode]
        if seconds is None or not low <= int(seconds) <= high:
            raise ValueError(f"Duration of {mode} out of range: {seconds}")
        return f"{'on' if mode == 'forced' else 'off'}_forced/{int(seconds)}"
    raise ValueError(f"Unknown mode {mode}")


def parse_equipments(payload) -> list:
    """Return the equipments of the first gateway of the list of gateways."""
    devices = payload["gateways"][0].get("devices") or []
    return [parse_equipment(device) for device in devices if "device_id" in device]


def parse_equipment_power(payload) -> dict:
    """Return the energy, cost and power curve of an equipment over a day."""
    stat = payload["stat"]
    period = stat.get("period") or {}
    return {
        "energy": finite_number(period.get("kwh")),
        "cost": finite_number(period.get("price")),
        "power": [
            {"time": _iso_time(item.get("time"), 1000), "value": finite_number(item.get("value"))}
            for item in stat.get("data") or []
        ],
    }


def _switched_on(state) -> bool:
    """Tell whether a change of state switched the equipment on.

    The name says it, "Allumé" or "Allumé (forcé)" against "Eteint": the
    value is 1 for "Allumé" but another one for a forced state. The value
    decides only for a name in another language.
    """
    name = str(state.get("name", "")).strip().lower()
    if name.startswith(("allum", "on")):
        return True
    if name.startswith(("etein", "étein", "off")):
        return False
    return state.get("val") == 1


def parse_equipment_switches(payload) -> list:
    """Return the changes of state of an equipment over a day, the oldest first.

    Each one has its start, its end (None while it lasts), whether the
    equipment was on, whether it was forced, and its origin.
    """
    switches = []
    for item in payload.get("switch_state_logs") or []:
        start = _local_time(item.get("state_time"))
        if start is None:
            continue
        state = item.get("switch_state") or {}
        duration = finite_number(item.get("duration"))
        end = None if duration is None or duration < 0 else start + dt.timedelta(seconds=duration)
        switches.append({
            "start": start.isoformat(),
            "end": None if end is None else end.isoformat(),
            "on": _switched_on(state),
            # "Allumé (forcé)", "Eteint (forcé)"
            "forced": "forc" in str(state.get("name", "")).lower(),
            "source": SWITCH_SOURCES.get((item.get("switch_source") or {}).get("val")),
        })
    switches.sort(key=lambda switch: switch["start"])
    return switches


class LittleMonkeyApiClient:
    """API Client to retrieve ecojoko data."""

    def __init__(
        self,
        username: str,
        password: str,
        poll_interval: int,
        use_hchp: bool,
        use_temphum: bool,
        use_prod: bool,
        session: aiohttp.ClientSession,
        bands: list | None = None,
    ) -> None:
        """Initialize."""
        self._username = username
        self._password = password
        self._poll_interval = poll_interval
        self._use_hchp = use_hchp
        # Configured tariff bands (see tariff.py)
        self._configured_bands = list(bands or [])
        self._use_temphum = use_temphum
        self._use_prod = use_prod
        self._session = session
        # ecojoko returns degraded powerstat data to the default
        # Home Assistant User-Agent, so the integration sends its own
        self._headers = {
            "Content-type": "application/json",
            "User-Agent": f"little_monkey/{VERSION}",
        }
        self._cookies = None
        self._gateway_id = None
        self._power_meter_id = None
        self._temp_hum_id = None
        # Properties
        self._gateway_firmware_version = None
        self._realtime_conso = None
        self._realtime_va = None
        self._kwh = None
        self._kwh_hc_ns = None
        self._kwh_hp_ns = None
        # Energy of the day by sensor key of the configured bands
        self._band_values = {}
        self._kwh_prod = None
        self._indoor_temp = None
        self._outdoor_temp = None
        self._indoor_hum = None
        self._outdoor_hum = None
        # Active contract of the installation, and tariff bands {id: label}
        # met in the statistics since the start
        self._contract = None
        self._bands = {}
        # Equipments of the gateway, read with the list of the gateways
        self._equipments = []
        # Energy and cost of each band, each day of the last two weeks, for
        # the estimation of the price of a kWh; the exact prices when
        # ecojoko gives them (with a water heater it pilots)
        self._day_costs = {}
        self._exact_prices = None

        # Internal
        # Monotonic time the contract is due to be read again
        self._contract_due = None
        # Labels of the bands counted in neither HC nor HP, logged once
        self._unclassified_bands = set()
        # Bands of the day not configured {id: label}, None until the
        # bands of a day are read
        self._unknown_bands = None
        # Monotonic time of the last call of each statistics API
        self._last_stat_refresh = {
            "powerstat": None,
            "tempstat": None,
            "humstat": None,
        }
        # APIs whose failure has already been logged as a warning
        self._warned = set()
        # Statistics APIs that failed once to answer, not yet a warning
        self._failed_once = set()
        # Day (in Paris) the energy properties belong to
        self._stat_date = None
        # Monotonic time of the last login
        self._last_login = None
        # Monotonic time the list of the gateways is due again, and number
        # of times it was read, for the diagnostics
        self._gateways_due = None
        self._gateways_count = 0
        # Status and headers of the last response of each API, for the
        # diagnostics: they tell whether a proxy answered from its cache
        self._last_responses = {}
        # Number of logins since the start, for the diagnostics
        self._login_count = 0
        # Last real-time values and monotonic time of their last change
        self._last_reading = None
        self._last_reading_change = None

    @property
    def contract(self) -> dict | None:
        """Return the active contract, None until it is read."""
        return self._contract

    @property
    def equipments(self) -> list:
        """Return the equipments of the gateway, read every five minutes."""
        return list(self._equipments)

    @property
    def band_prices(self) -> dict:
        """Return the price of a kWh of each band {band id: {price, exact}}.

        The prices given by ecojoko when it has them, estimated from the
        statistics of the last two weeks otherwise.
        """
        labels = dict(self._bands)
        for band in self._configured_bands:
            labels.setdefault(band.get("id"), band.get("label"))
        exact = exact_prices(self._exact_prices, labels) if self._exact_prices else {}
        estimated = estimate_prices(self._day_costs)
        result = {
            band_id: {"price": price, "exact": False} for band_id, price in estimated.items()}
        result.update(
            {band_id: {"price": price, "exact": True} for band_id, price in exact.items()})
        return result

    @property
    def bands(self) -> dict:
        """Return the tariff bands {id: label} met since the start."""
        return dict(self._bands)

    @property
    def stat_date(self) -> str | None:
        """Return the day the energy values belong to, as an ISO date."""
        return None if self._stat_date is None else self._stat_date.isoformat()

    @property
    def gateway_firmware_version(self) -> str | None:
        """Return the firmware version."""
        return self._gateway_firmware_version

    @property
    def realtime_conso(self) -> float | None:
        """Return the realtime consumption."""
        return self._realtime_conso

    @property
    def realtime_va(self) -> float | None:
        """Return the apparent power, when ecojoko gives it."""
        return self._realtime_va

    @property
    def kwh(self) -> float | None:
        """Return the grid consumption."""
        return self._kwh

    @property
    def kwh_hc_ns(self) -> float | None:
        """Return the HC consumption."""
        return self._kwh_hc_ns

    @property
    def kwh_hp_ns(self) -> float | None:
        """Return the HP consumption."""
        return self._kwh_hp_ns

    @property
    def unknown_bands(self) -> dict | None:
        """Return the bands of the day not configured, None if not known."""
        return None if self._unknown_bands is None else dict(self._unknown_bands)

    @property
    def band_values(self) -> dict:
        """Return the energy of the day by sensor key of the configured bands."""
        return dict(self._band_values)

    @property
    def kwh_prod(self) -> float | None:
        """Return the production surplus."""
        return self._kwh_prod

    @property
    def indoor_temp(self) -> float | None:
        """Return the indoor temperature."""
        return self._indoor_temp

    @property
    def outdoor_temp(self) -> float | None:
        """Return the outdoor temperature."""
        return self._outdoor_temp

    @property
    def indoor_hum(self) -> float | None:
        """Return the indoor humidity."""
        return self._indoor_hum

    @property
    def outdoor_hum(self) -> float | None:
        """Return the outdoor humidity."""
        return self._outdoor_hum

    def diagnostics(self) -> dict:
        """Return the state of the client for the diagnostics.

        It holds no credential, cookie or device identifier.
        """
        now = time.monotonic()
        return {
            "logged_in": self._cookies is not None,
            "login_count": self._login_count,
            "seconds_since_login": (
                None if self._last_login is None
                else round(now - self._last_login, 1)
            ),
            "gateways_count": self._gateways_count,
            "seconds_since_realtime_change": (
                None if self._last_reading_change is None
                else round(now - self._last_reading_change, 1)
            ),
            "gateway_found": self._gateway_id is not None,
            "power_meter_found": self._power_meter_id is not None,
            "temp_hum_found": self._temp_hum_id is not None,
            # Their type, status and controls; no identifier nor network name
            "equipments": [
                {key: equipment.get(key) for key in (
                    "type", "model", "firmware", "connected", "controls", "measures", "switches")}
                for equipment in self._equipments
            ],
            "gateway_firmware_version": self._gateway_firmware_version,
            "seconds_since_stat_refresh": {
                name: None if last is None else round(now - last, 1)
                for name, last in self._last_stat_refresh.items()
            },
            "failing_apis": sorted(self._warned | self._failed_once),
            # Without its price
            "contract": None if self._contract is None else {
                key: value for key, value in self._contract.items()
                if key != "subscription_price"},
            "tariff_bands": {
                str(band_id): label
                for band_id, label in sorted(self._bands.items())
            },
            "last_responses": {
                name: {
                    "seconds_ago": round(now - last["time"], 1),
                    "status": last["status"],
                    "headers": last["headers"],
                }
                for name, last in self._last_responses.items()
            },
        }

    async def async_get_cookiesdata(self) -> None:
        """Perform login and return cookies."""
        login_data = {
            "l": f"{self._username}",
            "p": f"{self._password}"
        }
        try:
            payload_json = json.dumps(login_data)
            # A new session: the cookies of the previous one are not sent
            self._session.cookie_jar.clear()
            return await self._cookiesapi_wrapper(data=payload_json)
        except LittleMonkeyApiClientError:
            raise
        except Exception as exception:  # pylint: disable=broad-except
            raise LittleMonkeyApiClientError(
                f"Unexpected error during ecojoko login: {exception!r}"
            ) from exception

    async def async_get_gatewaydata(self) -> None:
        """Get Ecojoko gateway data."""
        try:
            if self._cookies is None:
                LOGGER.debug("Pas de cookies")
            await self._gatewayapi_wrapper()
        except LittleMonkeyApiClientError:
            raise
        except Exception as exception:  # pylint: disable=broad-except
            raise LittleMonkeyApiClientError(
                f"Unexpected error reading the ecojoko gateway: {exception!r}"
            ) from exception
        if self._gateway_id is None or self._power_meter_id is None:
            raise LittleMonkeyApiClientError(
                "No ecojoko gateway or power meter found for this account"
            )

    async def async_get_tariff_setup(self, weeks=4):
        """Return the active contract and its tariff bands, for the setup.

        The bands {id: label} are the ones of the offer type, completed by
        the ones met in the statistics of the last weeks since the start of
        the contract. The contract is None and the bands are empty when
        ecojoko does not give them: the setup goes on without them.
        Must be called after a successful login.
        """
        if self._gateway_id is None:
            await self.async_get_gatewaydata()
        gateway_url = f"{ECOJOKO_GATEWAY_URL}/{self._gateway_id}"
        try:
            payload, _cookies = await self._async_request(
                "suppliers", f"{gateway_url}/suppliers", cookies=self._cookies)
            contract = None if payload is None else active_contract(payload)
        except LittleMonkeyApiClientAuthenticationError:
            raise
        except (LittleMonkeyApiClientError, *PARSE_ERRORS) as exception:
            LOGGER.warning("The ecojoko contract was not read: %r", exception)
            return None, {}
        start = None
        if contract is not None and contract.get("start_date"):
            start = dt.date.fromisoformat(contract["start_date"])
        today = get_current_date(TZ)
        observed = {}
        for week in range(weeks):
            day = today - dt.timedelta(weeks=week)
            sunday = day + dt.timedelta(days=6 - day.weekday())
            if start is not None and sunday < start:
                break
            url = (f"{gateway_url}/device/{self._power_meter_id}"
                   f"/powerstat/w/{day.isoformat()}")
            try:
                payload, _cookies = await self._async_request(
                    "powerstat (w)", url, cookies=self._cookies)
                for item in payload['stat']['data']:
                    item_day = local_date(item.get('time'))
                    if start is not None and (item_day is None or item_day < start):
                        continue
                    observed.update(bands_of({}, item))
            except LittleMonkeyApiClientAuthenticationError:
                raise
            except (LittleMonkeyApiClientError, *PARSE_ERRORS) as exception:
                LOGGER.debug("Statistics of %s not read: %r", day, exception)
        offer_type = None if contract is None else contract.get("offer_type")
        return contract, bands_of_offer(offer_type, observed)

    async def fetch_data(self, api):
        """Retrieve data from a given URL using aiohttp.

        Return None when the API is not called or does not answer with JSON.
        """
        if api['call'] is not True:
            return None
        payload, _cookies = await self._async_request(
            api['name'], api['url'], cookies=self._cookies)
        return payload

    async def async_get_activity(self) -> dict:
        """Return the activity of the account: savings, last 7 days...

        Called apart from the polls, with its own timeout. It does not log
        in: before the first login, or when the session has expired, it
        fails and the next poll logs in again.
        """
        if self._cookies is None:
            raise LittleMonkeyApiClientCommunicationError(
                "API activity not called: not logged in")
        payload, _cookies = await self._async_request(
            "activity", ECOJOKO_ACTIVITY_URL, cookies=self._cookies,
            timeout=CONF_API_ACTIVITY_TIMEOUT)
        try:
            return parse_activity(payload)
        except PARSE_ERRORS as exception:
            raise LittleMonkeyApiClientError(
                f"Unexpected data from API activity: {exception!r}"
            ) from exception

    def _check_slow_api(self, name) -> None:
        """Fail when an API read apart from the polls cannot be called yet.

        Such an API does not log in: before the first login, or when the
        session has expired, it fails and the next poll logs in again.
        """
        if self._cookies is None or self._gateway_id is None or self._power_meter_id is None:
            raise LittleMonkeyApiClientCommunicationError(
                f"API {name} not called: not logged in")

    async def async_get_savings_period(self, period, day) -> dict:
        """Return the savings of the week, month or year holding a day."""
        self._check_slow_api("savingstat")
        url = (f"{ECOJOKO_GATEWAY_URL}/{self._gateway_id}"
               f"/device/{self._power_meter_id}"
               f"/savingstat/{SAVINGS_PERIODS[period]}/{day.isoformat()}")
        payload, _cookies = await self._async_request(
            f"savingstat ({SAVINGS_PERIODS[period]})", url, cookies=self._cookies,
            timeout=CONF_API_ACTIVITY_TIMEOUT)
        try:
            return parse_savingstat(payload, get_current_date(TZ))
        except PARSE_ERRORS as exception:
            raise LittleMonkeyApiClientError(
                f"Unexpected data from API savingstat: {exception!r}"
            ) from exception

    async def _async_get_slow(self, name, path, parse, error_payload=False, device=None):
        """Read an API of a device apart from the polls, and parse it.

        The power meter by default.
        """
        self._check_slow_api(name)
        url = (f"{ECOJOKO_GATEWAY_URL}/{self._gateway_id}"
               f"/device/{device or self._power_meter_id}/{path}")
        payload, _cookies = await self._async_request(
            name, url, cookies=self._cookies, timeout=CONF_API_ACTIVITY_TIMEOUT,
            error_payload=error_payload)
        try:
            return parse(payload)
        except PARSE_ERRORS as exception:
            raise LittleMonkeyApiClientError(
                f"Unexpected data from API {name}: {exception!r}"
            ) from exception

    async def async_get_analysis(self, period, day=None) -> dict:
        """Return the analysis of the consumption of a week or a month.

        Without a day, the last period analysed by ecojoko.
        """
        path = f"ia/conso/{SAVINGS_PERIODS[period]}"
        if day is not None:
            path += f"/{day.isoformat()}"
        return await self._async_get_slow(
            "analysis", path, parse_analysis, error_payload=True)

    async def async_get_category_history(self, category, day) -> dict:
        """Return the consumption of a category, week by week over a year."""
        return await self._async_get_slow(
            "category history", f"usage/{int(category)}/history/y/{day.isoformat()}",
            parse_category_history)

    async def async_get_measures(self, measure, period, day) -> dict:
        """Return the measures of a period holding a day, as the page « Mesures ».

        The electricity of a day is its power every few minutes, of a longer
        period the energy of its days or months by tariff band. The
        temperature and humidity are inside and outside, as curves.
        """
        scale = MEASURE_PERIODS[period]
        if measure != "electricity" and period == "month":
            scale = CLIMATE_MONTH
        path = f"{MEASURES[measure]}/{scale}/{day.isoformat()}"
        if measure != "electricity":
            if self._temp_hum_id is None:
                raise LittleMonkeyApiClientError("No temperature and humidity sensor")
            return await self._async_get_slow(
                f"{MEASURES[measure]} ({scale})", path, parse_climate, device=self._temp_hum_id)
        parse = parse_power_day if period == "day" else parse_energy_bars
        return await self._async_get_slow(f"powerstat ({scale})", path, parse)

    async def async_get_activations(self, page=0) -> dict:
        """Return the activations of the appliances over 48 hours.

        Page 0 for the last 48 hours, 1 for the 48 hours before, and so on.
        """
        return await self._async_get_slow(
            "activations", f"ia/appliances/0/{int(page)}", parse_activations)

    def _equipment_url(self, equipment_id) -> str:
        """Return the URL of an equipment of the gateway, known or not."""
        if str(equipment_id) not in {equipment["id"] for equipment in self._equipments}:
            raise LittleMonkeyApiClientError(f"Unknown equipment {equipment_id}")
        return f"{ECOJOKO_GATEWAY_URL}/{self._gateway_id}/device/{int(equipment_id)}"

    async def async_get_equipment(self, equipment_id) -> dict:
        """Return an equipment read now: its state is more recent than the list."""
        self._check_slow_api("equipment")
        payload, _cookies = await self._async_request(
            "equipment", self._equipment_url(equipment_id), cookies=self._cookies,
            timeout=CONF_API_ACTIVITY_TIMEOUT)
        try:
            return parse_equipment(payload)
        except PARSE_ERRORS as exception:
            raise LittleMonkeyApiClientError(
                f"Unexpected data from API equipment: {exception!r}"
            ) from exception

    async def async_send_equipment_command(self, equipment_id, mode, seconds=None) -> None:
        """Pilot an equipment: forced, absence, automatic, on or off.

        Only the controls ecojoko offers for the equipment are sent. ecojoko
        answers an error id, 0 when the command is accepted. When it does
        not answer, the command may have been applied all the same.
        """
        self._check_slow_api("command")
        equipment = next(
            (item for item in self._equipments if item["id"] == str(equipment_id)), None)
        if equipment is None:
            raise LittleMonkeyApiClientError(f"Unknown equipment {equipment_id}")
        if mode not in equipment["controls"]:
            raise LittleMonkeyApiClientError(
                f"Mode {mode} not offered by ecojoko for this equipment")
        command = equipment_command(mode, seconds)
        payload, _cookies = await self._async_request(
            "command", f"{self._equipment_url(equipment_id)}/{command}",
            cookies=self._cookies, timeout=CONF_API_ACTIVITY_TIMEOUT)
        error = payload.get("error_id") if isinstance(payload, dict) else None
        if error not in (0, None):
            raise LittleMonkeyApiClientError(
                f"ecojoko refused the command: {payload.get('error_desc') or error}")

    async def async_get_equipment_day(self, equipment, day) -> dict:
        """Return the measures of an equipment over a day.

        Its energy, cost and power curve when it measures its power, and its
        changes of state when it has some.
        """
        self._check_slow_api("equipment day")
        url = self._equipment_url(equipment["id"])

        async def read(name, path, parse):
            payload, _cookies = await self._async_request(
                name, f"{url}/{path}/{day.isoformat()}", cookies=self._cookies,
                timeout=CONF_API_ACTIVITY_TIMEOUT)
            try:
                return parse(payload)
            except PARSE_ERRORS as exception:
                raise LittleMonkeyApiClientError(
                    f"Unexpected data from API {name}: {exception!r}"
                ) from exception

        reads = {}
        if equipment.get("measures"):
            reads["power"] = read("plugstat", "plugstat/d4", parse_equipment_power)
        if equipment.get("switches"):
            reads["switches"] = read("switchstat", "switchstat/d", parse_equipment_switches)
        results = dict(zip(reads, await asyncio.gather(*reads.values())))
        power = results.get("power") or {}
        return {
            "date": day.isoformat(),
            "energy": power.get("energy"),
            "cost": power.get("cost"),
            "power": power.get("power", []),
            "switches": results.get("switches", []),
        }

    async def async_get_savings(self) -> dict:
        """Return the savings over 12 months, this week, month and year.

        Called apart from the polls, like the activity.
        """
        self._check_slow_api("savings")
        payload, _cookies = await self._async_request(
            "savings", f"{ECOJOKO_GATEWAY_URL}/{self._gateway_id}/savings/m/12",
            cookies=self._cookies, timeout=CONF_API_ACTIVITY_TIMEOUT)
        try:
            data = parse_savings_summary(payload)
        except PARSE_ERRORS as exception:
            raise LittleMonkeyApiClientError(
                f"Unexpected data from API savings: {exception!r}"
            ) from exception
        today = get_current_date(TZ)
        periods = await asyncio.gather(*(
            self.async_get_savings_period(period, today)
            for period in SAVINGS_PERIODS))
        data.update(zip(SAVINGS_PERIODS, periods))
        return data

    async def _async_request(self, name, url, method="GET", timeout=None,
                             error_payload=False, **kwargs):
        """Send a request to ecojoko.

        Return the JSON payload (None when the answer is not JSON) and the
        cookies of the response. The timeout (CONF_API_TIMEOUT by default)
        covers the whole exchange, body included, and the connection is
        always released. With error_payload, an answer HTTP 400 in JSON is
        returned: ecojoko explains in it why it has no data.
        """
        try:
            async with asyncio.timeout(timeout or CONF_API_TIMEOUT):
                async with self._session.request(
                    method,
                    url,
                    headers=self._headers,
                    **kwargs,
                ) as response:
                    self._last_responses[name] = {
                        "time": time.monotonic(),
                        "status": response.status,
                        "headers": {
                            key: value
                            for key, value in response.headers.items()
                            if key.lower() not in HIDDEN_HEADERS
                        },
                    }
                    if response.status in (401, 403):
                        # 71 bug fix
                        self._cookies = None
                        raise LittleMonkeyApiClientAuthenticationError(
                            f"API {name} rejected the request "
                            f"(HTTP {response.status})",
                        )
                    content_type = response.headers.get("Content-Type", "")
                    if (
                        error_payload
                        and response.status == 400
                        and "application/json" in content_type
                    ):
                        return await response.json(), response.cookies
                    if response.status >= 400:
                        raise LittleMonkeyApiClientCommunicationError(
                            f"API {name} returned HTTP {response.status}",
                        )
                    payload = None
                    if "application/json" in content_type:
                        payload = await response.json()
                    return payload, response.cookies
        except asyncio.TimeoutError as exception:
            raise LittleMonkeyApiClientCommunicationError(
                f"API {name} timeout error",
            ) from exception
        except (aiohttp.ClientError, socket.gaierror, ValueError) as exception:
            raise LittleMonkeyApiClientCommunicationError(
                f"API {name} client error: {exception!r}",
            ) from exception

    def _warn_once(self, name, error) -> None:
        """Log an API failure as a warning once, then as debug until it recovers.

        A communication failure (timeout, network) is a warning only when it
        happens twice in a row: a single one is usual and the API is called
        again after the usual delay.
        """
        if name in self._warned:
            LOGGER.debug("API %s still failing: %r", name, error)
            return
        if (
            isinstance(error, LittleMonkeyApiClientCommunicationError)
            and name not in self._failed_once
        ):
            self._failed_once.add(name)
            LOGGER.debug("API %s failed once: %r", name, error)
            return
        self._warned.add(name)
        LOGGER.warning(
            "API %s failed, its sensors keep their last value "
            "(logged once until it recovers): %r", name, error)

    def _clear_warning(self, name) -> None:
        """Log that an API works again."""
        self._failed_once.discard(name)
        if name in self._warned:
            self._warned.discard(name)
            LOGGER.info("API %s is back to normal", name)

    async def async_get_data(self) -> None:
        """Get data from ecojoko APIs.

        Raise LittleMonkeyApiClientAuthenticationError when the credentials
        are rejected, and another LittleMonkeyApiClientError when the
        real-time consumption cannot be retrieved.
        """
        # A 401/403 at login means the credentials are wrong
        if self._cookies is None:
            await self.async_get_cookiesdata()
        try:
            await self._async_refresh()
        except LittleMonkeyApiClientAuthenticationError:
            # The session has expired: log in again and retry once
            LOGGER.debug("ecojoko session rejected, logging in again")
            self._cookies = None
            await self.async_get_cookiesdata()
            try:
                await self._async_refresh()
            except LittleMonkeyApiClientAuthenticationError as exception:
                raise LittleMonkeyApiClientError(
                    "ecojoko still rejects the session after a new login"
                ) from exception

    async def _async_keep_live(self) -> None:
        """Read the list of the gateways again, to keep the data live.

        ecojoko feeds its APIs, and its own web application, with live data
        during ten minutes after this list is read. Afterwards the real-time
        values freeze for minutes and the energy totals are hours late,
        without any error. Reading the list during these ten minutes starts
        them again. A failure is not an error of the poll: the reading is
        tried again shortly.
        """
        now = time.monotonic()
        self._gateways_due = now + CONF_API_KEEP_LIVE_RETRY
        read_before = self._gateways_count
        try:
            await self._gatewayapi_wrapper()
        except LittleMonkeyApiClientAuthenticationError:
            raise
        except (LittleMonkeyApiClientError, *PARSE_ERRORS) as exception:
            LOGGER.debug("The list of the gateways was not read: %r", exception)
            return
        if self._gateways_count == read_before:
            LOGGER.debug("The list of the gateways was not read: no JSON answer")
            return
        self._gateways_due = now + CONF_API_KEEP_LIVE

    def _stats_to_call(self, now) -> list:
        """Return the statistics APIs to call during this poll.

        Each statistic is refreshed every CONF_API_STAT_REFRESH seconds.
        With a short poll interval only one of them is called per poll, to
        spread the load on the ecojoko servers; with a longer one, several
        are called together so that none waits more than the usual delay.
        """
        enabled = ["powerstat"]
        if self._use_temphum is True and self._temp_hum_id is not None:
            enabled += ["tempstat", "humstat"]
        due = [
            name for name in enabled
            if self._last_stat_refresh[name] is None
            or now - self._last_stat_refresh[name] >= CONF_API_STAT_REFRESH
        ]
        # Oldest first, the ones never called before the others
        due.sort(key=lambda name: -math.inf
                 if self._last_stat_refresh[name] is None
                 else self._last_stat_refresh[name])
        poll_interval = max(float(self._poll_interval), 1)
        per_poll = max(1, math.ceil(
            len(enabled) * poll_interval / CONF_API_STAT_REFRESH))
        return due[:per_poll]

    async def _async_refresh(self) -> None:
        """Call the ecojoko APIs and update the properties."""
        if self._gateway_id is None:
            await self.async_get_gatewaydata()
            self._gateways_due = time.monotonic() + CONF_API_KEEP_LIVE
        elif time.monotonic() >= self._gateways_due:
            await self._async_keep_live()

        # Initialization
        current_date = get_current_date(TZ)
        formatted_date = current_date.strftime('%Y-%m-%d')
        # Statistics APIs to call during this poll
        now = time.monotonic()
        stats_to_call = self._stats_to_call(now)
        #   - powerstat (for Total Consumption + HC/HP + Tempo)
        refresh_powerstat = "powerstat" in stats_to_call
        #   - Temperature
        refresh_tempstat = "tempstat" in stats_to_call
        #   - Humidity
        refresh_humstat = "humstat" in stats_to_call
        #   - Contract, read rarely: it changes a few times in years
        refresh_contract = (
            self._contract_due is None or now >= self._contract_due)

        apis = []
        powermeterurl = f"/{self._gateway_id}/device/{self._power_meter_id}"
        apis.append({"name": "realtime_conso",
                     "url": ECOJOKO_GATEWAY_URL + powermeterurl +
                     "/realtime_conso",
                     "call": True})
        apis.append({"name": "powerstat (w)",
                     "url": ECOJOKO_GATEWAY_URL + powermeterurl +
                     f"/powerstat/w/{formatted_date}",
                     "call": refresh_powerstat})
        temphumurl = f"/{self._gateway_id}/device/{self._temp_hum_id}"
        apis.append({"name": "tempstat (d)",
                     "url": ECOJOKO_GATEWAY_URL + temphumurl +
                     f"/tempstat/d4/{formatted_date}",
                     "call": refresh_tempstat})
        apis.append({"name": "humstat (d)",
                     "url": ECOJOKO_GATEWAY_URL + temphumurl +
                     f"/humstat/d4/{formatted_date}",
                     "call": refresh_humstat})
        apis.append({"name": "suppliers",
                     "url": ECOJOKO_GATEWAY_URL + f"/{self._gateway_id}"
                     "/suppliers",
                     "call": refresh_contract})
        # The week before, with the contract: for the price of a kWh
        previous_week = (current_date - dt.timedelta(days=7)).strftime('%Y-%m-%d')
        apis.append({"name": "powerstat (w-1)",
                     "url": ECOJOKO_GATEWAY_URL + powermeterurl +
                     f"/powerstat/w/{previous_week}",
                     "call": refresh_contract})

        tasks = [self.fetch_data(api) for api in apis]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # An expired session concerns every API: let the caller log in again
        for result in results:
            if isinstance(result, LittleMonkeyApiClientAuthenticationError):
                raise result
        # The real-time consumption is mandatory, statistics are best effort
        for index, result in enumerate(results):
            if isinstance(result, BaseException):
                if index == 0:
                    raise result
                self._warn_once(apis[index]['name'], result)
                results[index] = None

        # Real-time consumption
        if results[0] is None:
            raise LittleMonkeyApiClientCommunicationError(
                "API realtime_conso did not return JSON data"
            )
        try:
            real_time = results[0]['real_time']
            self._realtime_conso = real_time['value']
            # Apparent power in VA, read from the Linky meter. Not every
            # installation has it, and it is negative when power is injected
            apparent_power = finite_number(real_time.get('value2'))
            # Installations without this measure get a constant 0, which
            # cannot be a real value while some power is consumed or injected
            if apparent_power == 0 and self._realtime_conso != 0:
                apparent_power = None
            self._realtime_va = apparent_power
            reading = (self._realtime_conso, apparent_power)
            if reading != self._last_reading:
                self._last_reading = reading
                self._last_reading_change = now
        except PARSE_ERRORS as exception:
            raise LittleMonkeyApiClientError(
                f"Unexpected data from API realtime_conso: {exception!r}"
            ) from exception

        # A statistics API that failed or returned an unexpected format
        # is called again after the usual delay, not at each poll
        for name in stats_to_call:
            self._last_stat_refresh[name] = now

        # Total Consumption + HC/HP + Tempo
        if results[1] is not None:
            try:
                self._parse_powerstat(results[1], current_date)
            except PARSE_ERRORS as exception:
                self._warn_once(apis[1]['name'], exception)
            else:
                self._clear_warning(apis[1]['name'])
        # Temperature
        if results[2] is not None:
            try:
                # 101 bug fix
                data = results[2]['stat']['data']
                # No measure yet just after midnight: the values are kept
                if len(data) > 0:
                    last = data[-1]
                    self._indoor_temp = round_value(last['value'])
                    self._outdoor_temp = round_value(last['ext_value'])
            except PARSE_ERRORS as exception:
                self._warn_once(apis[2]['name'], exception)
            else:
                self._clear_warning(apis[2]['name'])
        # Humidity
        if results[3] is not None:
            try:
                # 101 bug fix
                data = results[3]['stat']['data']
                # No measure yet just after midnight: the values are kept
                if len(data) > 0:
                    last = data[-1]
                    self._indoor_hum = round_value(last['value'])
                    self._outdoor_hum = round_value(last['ext_value'])
            except PARSE_ERRORS as exception:
                self._warn_once(apis[3]['name'], exception)
            else:
                self._clear_warning(apis[3]['name'])
        # Contract
        if refresh_contract:
            self._parse_contract(results[4], now, apis[4]['name'])
            self._parse_previous_week(results[5], current_date, apis[5]['name'])

    def _parse_contract(self, payload, now, name) -> None:
        """Update the active contract from the suppliers response.

        The contract is not needed for the energy values: a failure is
        logged and the contract read again a bit later.
        """
        self._contract_due = now + CONF_API_CONTRACT_RETRY
        if payload is None:
            return
        try:
            contract = active_contract(payload)
        except PARSE_ERRORS as exception:
            self._warn_once(name, exception)
            return
        self._clear_warning(name)
        self._contract = contract
        self._contract_due = now + CONF_API_CONTRACT_REFRESH

    def _parse_previous_week(self, payload, today, name) -> None:
        """Keep the costs of the bands of the week before, for their prices."""
        if payload is None:
            return
        try:
            self._add_day_costs(payload['stat'], today)
        except PARSE_ERRORS as exception:
            self._warn_once(name, exception)
        else:
            self._clear_warning(name)

    def _add_day_costs(self, stat, today) -> None:
        """Keep the energy and cost of the bands of the days of a statistics response."""
        self._day_costs.update(day_costs(stat))
        oldest = (today - dt.timedelta(days=PRICE_DAYS)).isoformat()
        self._day_costs = {
            day: bands for day, bands in self._day_costs.items() if day > oldest}

    def _parse_powerstat(self, payload, day) -> None:
        """Update the energy properties from the powerstat response of a day."""
        week_day = day.weekday()
        stat = payload['stat']
        data = stat['data']
        self._add_day_costs(stat, day)
        kwh = data[week_day]['kwh']
        self._bands.update(bands_of(stat, data[week_day]))
        if day != self._stat_date:
            # New day: a value of the previous day must not be taken for a
            # value of this one when the response does not give it yet
            self._kwh_prod = None
            self._kwh_hc_ns = None
            self._kwh_hp_ns = None
            self._band_values = {}
        self._kwh = round_value(kwh)
        self._stat_date = day
        # Surplus Production
        # 78 bug fix
        if self._use_prod is True and 'kwh_prod' in data[week_day]:
            if float(data[week_day]['kwh_prod']) != 0:
                self._kwh_prod = round_value(
                    abs(float(data[week_day]['kwh_prod'])))
            else:
                self._kwh_prod = 0
        # Tariff bands, and the HC/HP totals: every band of a category is
        # added, whatever the contract (Tempo, week-end, special day...)
        # 78 bug fix
        if 'subconsumption' not in data[week_day]:
            return
        subconsumption = data[week_day]['subconsumption']
        values, totals, unclassified = day_values(
            subconsumption, self._configured_bands)
        configured = {band["id"] for band in self._configured_bands}
        self._unknown_bands = {
            band_id: label
            for band_id, label in bands_of({}, data[week_day]).items()
            if band_id not in configured
            # Without the HC/HP totals, Heures Pleines and Heures Creuses
            # would have no sensor: the user did not want them
            and (self._use_hchp is True or band_id not in TOTAL_BANDS)
        }
        self._band_values = {
            key: round_value(value) for key, value in values.items()}
        if self._use_hchp is True:
            self._kwh_hc_ns = round_value(totals[OFF_PEAK])
            self._kwh_hp_ns = round_value(totals[PEAK])
            for label in unclassified:
                if label not in self._unclassified_bands:
                    self._unclassified_bands.add(label)
                    LOGGER.info(
                        "Tariff band %r is counted in neither HC nor HP",
                        label)

    async def _cookiesapi_wrapper(
        self,
        data: str | None = None,
    ) -> None:
        """Log in and keep the session cookies."""
        # The credentials are sent in the body: POST is the method made for
        # it, a body in a GET request can be dropped by a proxy
        _payload, cookies = await self._async_request(
            "Cookies", ECOJOKO_LOGIN_URL, method="POST", data=data)
        self._cookies = cookies
        self._last_login = time.monotonic()
        self._login_count += 1

    async def _gatewayapi_wrapper(self) -> None:
        """Get the gateway and device ids from the API."""
        value_json, _cookies = await self._async_request(
            "Gateway", ECOJOKO_GATEWAYS_URL, cookies=self._cookies)
        if value_json is None:
            return
        self._gateways_count += 1
        gateways = value_json.get('gateways')

        # Looking for gateway Id
        gateway_id = gateways[0].get('gateway_id')
        self._gateway_id = gateway_id

        # Looking for gateway firmware
        gateway_firmware_version = gateways[0].get(
            'gateway_firmware_version')
        self._gateway_firmware_version = gateway_firmware_version

        try:
            self._equipments = parse_equipments(value_json)
        except PARSE_ERRORS as exception:
            LOGGER.debug("Equipments not read: %r", exception)

        value_json = gateways[0].get('devices')
        # Prices of the contract, given with a water heater piloted by ecojoko
        # and only for some offers
        self._exact_prices = next((
            pricing.get("prices")
            for item in value_json or []
            if isinstance(pricing := (item.get("device_external_settings") or {})
                          .get("pricing_data"), dict)
            and pricing.get("prices")
        ), None)
        # Looking for humidity temperature and  power meter devices id
        for item in value_json:
            if item["device_type"] == "TEMP_HUM":
                self._temp_hum_id = item["device_id"]
            if item["device_type"] == "POWER_METER":
                self._power_meter_id = item["device_id"]
