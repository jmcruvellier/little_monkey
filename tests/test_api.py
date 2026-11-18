"""Tests of the ecojoko API client, with a fake HTTP session."""
from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import json
import logging
import sys
import types
from zoneinfo import ZoneInfo

import aiohttp
import pytest

WEEK_DAY = dt.datetime.now(ZoneInfo("Europe/Paris")).weekday()

GATEWAYS = {
    "gateways": [
        {
            "gateway_id": 1,
            "gateway_firmware_version": "9",
            "devices": [
                {"device_type": "POWER_METER", "device_id": 2},
                {"device_type": "TEMP_HUM", "device_id": 3},
            ],
        }
    ]
}
GATEWAYS_WITHOUT_TEMP_HUM = {
    "gateways": [
        {
            "gateway_id": 1,
            "gateway_firmware_version": "9",
            "devices": [{"device_type": "POWER_METER", "device_id": 2}],
        }
    ]
}
STAT_APIS = ("powerstat", "tempstat", "humstat")
# Contracts of an installation, as observed: the active one first
SUPPLIERS = {
    "suppliers": [
        {
            "id": 283901,
            "is_active": 1,
            "is_hchp": 1,
            "offer_id": 5480,
            "offer_name": "Zen Fixe - Option HP/HC",
            "offer_type": "HP/HC",
            "off_peak_timeslot": {
                "timeslot_id": 16637,
                "timeslots": [
                    {"start": "01:30", "stop": "07:00"},
                    {"start": "14:00", "stop": "16:30"},
                ],
            },
            "power": 9,
            "special_day": 1,
            "start_date": 1785880800000,
            "subscription_price": 24.77,
            "supplier_id": 17,
            "supplier_name": "EDF",
        },
        {
            "id": 150559,
            "is_hchp": 1,
            "offer_id": 2564,
            "offer_name": "Zen Week-End Plus - Option HP/HC",
            "offer_type": "HC SEM WE LUNDI",
            "off_peak_timeslot": {"timeslot_id": 1, "timeslots": [
                {"start": "00:00", "stop": "08:00"}]},
            "special_day": 3,
            "start_date": 1738364400000,
            "stop_date": 1739574000000,
            "supplier_name": "EDF",
        },
    ]
}
# Answer of the activity API observed on 15/11/2026
ACTIVITY = {
    "activity": {
        "savings_7j": {"value": -3, "degree": 180, "ref_kwh": 74.4},
        "conso_7j": {
            "value": 16.6, "kwh": 74.33, "kwh_with_ref": 74.33, "unit": "EUR",
            "unit_str": "€", "conso_unit_str": "kWh",
            "data": [381, 519, 398, 518, 515, 330, 432],
        },
        "conso_all": {"value": 393.83, "unit": "EUR", "unit_str": "€"},
        "classement": 1,
        "co2_emis": 74.3,
        "week_reference": 1,
        "max_power": {
            "month": 4290, "year": 6260, "alltime": 7386, "injection_month": 342,
            "injection_year": 2111, "injection_alltime": 2111, "unit_str": "W",
        },
        "ecowatt_signal": "#c4fbdb",
        "ecowatt_signal_val": 0,
        "max_injection": 1600,
        "max_consumption": 7386,
    }
}


# Answers of the savings APIs observed on 16/11/2026, a Monday
SAVINGS_SUMMARY = {
    "savings": {
        "conso": 483.6, "profil_initial": 821.23, "best": 816.28, "home": 1256,
        "unit": "EUR", "kwh": 1701.7201000000011, "kwh_with_ref": 1693.222,
        "profil_initial_kwh": 3319, "week_reference": 1,
        "savings": {"me": {"level": 5, "data": 337.63},
                    "best": {"level": 1, "data": -335.6}},
    }
}
SAVINGS_DAY = dt.date(2026, 11, 16)
SAVINGSTAT_WEEK = {
    "stat": {
        "period": {
            "this": 1794783600000, "prev": 1794178800000, "measure_unit": "EUR",
            "veille_price": 0.5824, "veille_kwh": 7, "missing_data": 0,
            "ref": 1.45, "ref_kwh": 5.01, "val": -0.35, "val_kwh": 2.58,
            "price": 1.8, "kwh": 7.58,
        },
        "data": [
            {"time": 1794783600000, "conso": 1.8, "val": -0.35, "ref": 1.45,
             "conso_kwh": 7.58, "ref_kwh": 5.01, "val_kwh": 2.58},
        ] + [
            {"time": 1794783600000 + day * 86400000, "conso": 0, "val": 0,
             "val_kwh": 0, "ref": 0, "conso_kwh": 0, "ref_kwh": 0}
            for day in range(1, 7)
        ],
        "pricing_details": [],
        "axis": {"y": {"max": 5, "min": -5}},
    }
}


# Answers of the analysis APIs observed on 16/11/2026
ANALYSIS_WEEK = {
    "stat": {
        "period": {"this": 1793574000000, "prev": 1792969200000, "next": 1794178800000,
                   "measure_unit": "EUR", "price": 14.46, "kwh": 60.6},
        "data": [
            {"kwh": 37.1, "price": 5.03, "percentage": 61, "evol_status": 1,
             "category": {"id": 7, "name": "Talon de consommation", "color": "#022469"}},
            {"kwh": 1.78, "price": 0.71, "percentage": 3, "evol_status": 1, "is_beta": True,
             "category": {"id": 5, "name": "Gros électroménager", "color": "#05a1fb"},
             "usage_childrens": [
                 {"kwh": 0.73, "price": 0.29, "percentage": 1,
                  "category": {"id": 12, "name": "Lave-vaisselle", "color": "#05a1fb",
                               "image_link": "https://service.ecojoko.com/x.webp"}},
             ]},
            {"kwh": 12.4, "price": 4.95, "percentage": 20, "evol_status": 2,
             "category": {"id": 9, "name": "Autres appareils", "color": "#acc5cf"}},
        ],
    }
}
ANALYSIS_PENDING = {
    "error_id": 300,
    "stat": {"period": {"this": 1794178800000, "prev": 1794118320000}},
    "error_desc": "Vos données sont en cours d’analyse.",
}
CATEGORY_HISTORY = {
    "usage_history": {
        "period": {"this": 1767567600000, "prev": 1736031600000, "measure_unit": "EUR"},
        "category": {"id": 8, "name": "Éclairage", "color": "#ffed21"},
        "data": [
            {"time": 1767567600000, "kwh": 0, "price": 0, "percentage": 0, "dtime": 1767567600000},
            {"time": 1768168080000, "kwh": 0, "price": 0, "percentage": 0, "dtime": 1767567600000},
            {"time": 1768172400000, "kwh": 0.67, "price": 0.11, "percentage": 0.8,
             "dtime": 1768172400000},
            {"time": 1768772880000, "kwh": 0.67, "price": 0.11, "percentage": 0.8,
             "dtime": 1768172400000},
        ],
    }
}
ACTIVATIONS = {
    "error_id": 0,
    "is_pending": 0,
    "start_time": 1794625200,
    "stop_time": 1794798000,
    "appliances": [
        {"id": 1794783780, "start_date": 1794783780000, "end_date": 1794792540000,
         "power": 694, "kwh": 1.69, "picto": {"w": 96, "h": 16, "color": "#FA6200"}},
        {"id": 1794770140, "start_date": 1794770140000, "end_date": 1794770170000,
         "power": 1260, "kwh": 0.01, "picto": {"w": 3, "h": 29, "color": "#5FC2FF"}},
    ],
}


# Water heater piloted by ecojoko, as observed (identifiers changed)
WATER_HEATER = {
    "device_id": 630220,
    "device_status": 1,
    "device_status_desc": "Connecté",
    "device_type": "LULO",
    "device_model": "LULO",
    "device_fw_ver": "1.01.11",
    "device_state": {
        "power_level": 0, "onoff": 0, "voltage": 232.5, "forced": 1, "max_power_level": 3131,
        "switch_last_source": 1, "switch_state": "Mode absence jusqu'à 20:25",
        "switch_time": 1795029644000, "switch_until": 1795029945000,
    },
    "device_commands": ["on", "off", "on_forced", "off_forced", "reset_max_power", "powerstat",
                        "plugstat", "switchstat"],
    "battery": {"level": 255, "value": "", "type": "Alimentation"},
    "signal": {"level": 3, "value": "29%", "type": "ESP-NOW"},
    "device_settings": {"name": "Chauffe-eau", "operating_mode": 1},
    "lulo_network_status": {"wifi": {"state": 1, "mac": "00:00:00:00:00:00", "ssid": "Box",
                                     "signal": 30}},
    "device_showable_settings": {"show_switch_buttons": 1, "switch_forced_mode": 1},
}
TEMP_HUM_DEVICE = {
    "device_id": 3, "device_type": "TEMP_HUM", "device_status": 1,
    "device_status_desc": "Connecté", "device_state": {"temperature": 208, "humidity": 50},
    "device_commands": ["tempstat", "humstat"],
    "battery": {"level": 80, "value": "80%", "type": "AAA"},
    "signal": {"level": 4, "value": "66%", "type": "UNET"},
    "device_settings": {"name": "Sonde de température"},
}
GATEWAYS_WITH_EQUIPMENTS = {
    "gateways": [
        {
            "gateway_id": 1,
            "gateway_firmware_version": "9",
            "devices": [{"device_type": "POWER_METER", "device_id": 2}, TEMP_HUM_DEVICE,
                        WATER_HEATER],
        }
    ]
}
PLUGSTAT = {
    "stat": {
        "period": {"kwh": 0.9666, "price": 0.141521761, "kwh_hc_ns": 0.7382},
        "data": [{"time": 1794956400000, "value": 0, "price": 0},
                 {"time": 1794956640000, "value": 2784, "price": 0.01}],
    }
}
SWITCHSTAT = {
    # The most recent first
    "switch_state_logs": [
        {"duration": -1, "state_time": "2026-11-18 20:27:48",
         "switch_source": {"name": "Switch for", "val": 3},
         "switch_state": {"name": "Eteint", "val": 0}},
        {"duration": 300, "state_time": "2026-11-18 20:22:48",
         "switch_source": {"name": "Cloud", "val": 1},
         "switch_state": {"name": "Allumé (forcé)", "val": 1}},
        {"duration": 3, "state_time": "not a time",
         "switch_source": {"name": "Cloud", "val": 1},
         "switch_state": {"name": "Eteint", "val": 0}},
    ]
}


def powerstat(kwh=4.2, **today):
    """Return a powerstat response whose current day holds the given values."""
    data = [{"kwh": 0} for _ in range(7)]
    data[WEEK_DAY] = {"kwh": kwh, **today}
    return {"stat": {"data": data}}


class Response:
    """Fake aiohttp response."""

    def __init__(self, status=200, payload=None, is_json=True, delay=0):
        """Initialize."""
        self.status = status
        self.cookies = {"session": "abc"}
        self.headers = {
            "Content-Type": "application/json" if is_json else "text/html"
        }
        self.released = False
        self._payload = payload
        self._delay = delay

    async def json(self):
        """Return the JSON payload, after the delay if any."""
        await asyncio.sleep(self._delay)
        return self._payload


class Request:
    """Fake aiohttp request: an async context manager giving the response."""

    def __init__(self, answer):
        """Initialize with a Response, an exception or a function."""
        self._answer = answer
        self._response = None

    async def __aenter__(self):
        """Return the response or raise the error of the request."""
        answer = self._answer
        if callable(answer):
            answer = answer()
        if asyncio.iscoroutine(answer):
            answer = await answer
        if isinstance(answer, BaseException):
            raise answer
        self._response = answer
        return answer

    async def __aexit__(self, *exc_info):
        """Release the connection."""
        if self._response is not None:
            self._response.released = True
        return False


class CookieJar:
    """Fake aiohttp cookie jar."""

    def __init__(self):
        """Initialize."""
        self.cleared = 0

    def clear(self):
        """Forget the cookies."""
        self.cleared += 1


class Session:
    """Fake aiohttp session.

    Each API is answered by a Response, an exception to raise, or a function
    (possibly async) returning one of them.
    """

    def __init__(self, **overrides):
        """Initialize with working answers, replaced by the overrides."""
        self.routes = {
            "login": Response(),
            "gateways": Response(payload=GATEWAYS),
            "realtime_conso": Response(payload={"real_time": {"value": 512}}),
            "powerstat": Response(payload=powerstat()),
            "tempstat": Response(
                payload={"stat": {"data": [{"value": 20, "ext_value": 8}]}}
            ),
            "humstat": Response(
                payload={"stat": {"data": [{"value": 50, "ext_value": 80}]}}
            ),
            "suppliers": Response(payload=SUPPLIERS),
            "activity": Response(payload=ACTIVITY),
            "savings/m": Response(payload=SAVINGS_SUMMARY),
            "savingstat": Response(payload=SAVINGSTAT_WEEK),
            "ia/conso": Response(payload=ANALYSIS_WEEK),
            "history": Response(payload=CATEGORY_HISTORY),
            "ia/appliances": Response(payload=ACTIVATIONS),
            "plugstat": Response(payload=PLUGSTAT),
            "switchstat": Response(payload=SWITCHSTAT),
            "device/630220": Response(payload=WATER_HEATER),
            **overrides,
        }
        self.calls = []
        self.requests = []
        self.cookie_jar = CookieJar()

    def request(self, method, url, **kwargs):
        """Start a request."""
        name = next(key for key in self.routes if key in url)
        self.calls.append(name)
        self.requests.append((method, url, kwargs))
        return Request(self.routes[name])


def tariff_module(api):
    """Return the tariff module loaded with the api module."""
    return sys.modules[api.__package__ + ".tariff"]


def make_client(api, session, poll=5, hchp=False, tempo=False,
                temphum=False, prod=False):
    """Return an API client using the fake session."""
    return api.LittleMonkeyApiClient(
        username="user",
        password="secret",
        poll_interval=poll,
        use_hchp=hchp,
        bands=tariff_module(api).legacy_bands(hchp, tempo),
        use_temphum=temphum,
        use_prod=prod,
        session=session,
    )


def run(coroutine):
    """Run a coroutine to completion."""
    return asyncio.run(coroutine)


# --- Nominal case


def test_nominal(api):
    """The first poll logs in, reads the gateway and the consumption."""
    session = Session()
    client = make_client(api, session)
    run(client.async_get_data())
    assert client.realtime_conso == 512
    assert client.kwh == 4.2
    assert client.gateway_firmware_version == "9"
    assert session.calls == [
        "login", "gateways", "realtime_conso", "powerstat", "suppliers"
    ]


def test_user_agent_is_sent(api):
    """Every request identifies the integration (1.2.8 fix)."""
    session = Session()
    run(make_client(api, session).async_get_data())
    for _method, _url, kwargs in session.requests:
        assert kwargs["headers"]["User-Agent"].startswith("little_monkey/")


def test_login_is_a_post_with_the_credentials_in_the_body(api):
    """The login sends the credentials as JSON in a POST request."""
    session = Session()
    run(make_client(api, session).async_get_data())
    methods = {
        name: method
        for name, (method, _url, _kwargs) in zip(session.calls, session.requests)
    }
    assert methods == {
        "login": "POST",
        "gateways": "GET",
        "realtime_conso": "GET",
        "powerstat": "GET",
        "suppliers": "GET",
    }
    _method, url, kwargs = session.requests[0]
    assert url == "https://service.ecojoko.com/login"
    assert json.loads(kwargs["data"]) == {"l": "user", "p": "secret"}
    assert kwargs["headers"]["Content-type"] == "application/json"
    # The credentials never travel in the address
    assert "user" not in url
    assert "secret" not in url


def test_diagnostics_hold_no_secret(api):
    """The diagnostics describe the client without credential or identifier."""
    session = Session(powerstat=aiohttp.ClientError("boom"))
    client = make_client(api, session, temphum=True)
    before = client.diagnostics()
    assert before["logged_in"] is False
    assert before["gateway_found"] is False
    assert before["seconds_since_stat_refresh"]["powerstat"] is None

    run(client.async_get_data())
    after = client.diagnostics()
    assert after["logged_in"] is True
    assert after["gateway_found"] is True
    assert after["power_meter_found"] is True
    assert after["temp_hum_found"] is True
    assert after["gateway_firmware_version"] == "9"
    assert after["failing_apis"] == ["powerstat (w)"]
    assert after["seconds_since_stat_refresh"]["powerstat"] is not None
    assert after["seconds_since_stat_refresh"]["tempstat"] is None
    text = repr(after)
    for secret in ("user", "secret", "abc"):
        assert secret not in text


def test_diagnostics_show_the_response_headers(api):
    """The headers of the last responses tell whether a proxy cached them."""
    answer = Response(payload={"real_time": {"value": 512}})
    answer.headers.update({
        "Age": "540",
        "X-Cache": "HIT",
        "Set-Cookie": "session=abc; Path=/",
    })
    session = Session(realtime_conso=answer, powerstat=Response(status=503))
    client = make_client(api, session)
    run(client.async_get_data())
    responses = client.diagnostics()["last_responses"]
    assert set(responses) == {
        "Cookies", "Gateway", "realtime_conso", "powerstat (w)", "suppliers"}
    realtime_conso = responses["realtime_conso"]
    assert realtime_conso["status"] == 200
    assert realtime_conso["headers"] == {
        "Content-Type": "application/json",
        "Age": "540",
        "X-Cache": "HIT",
    }
    assert realtime_conso["seconds_ago"] >= 0
    # A response that is an error is recorded as well
    assert responses["powerstat (w)"]["status"] == 503
    # Neither the session cookie nor the URL, which holds the device ids
    text = repr(responses)
    for secret in ("abc", "gw-1", "http"):
        assert secret not in text


# --- Login errors


@pytest.mark.parametrize("status", [401, 403])
def test_login_rejected(api, status):
    """Wrong credentials raise the authentication error."""
    client = make_client(api, Session(login=Response(status=status)))
    with pytest.raises(api.LittleMonkeyApiClientAuthenticationError):
        run(client.async_get_cookiesdata())
    with pytest.raises(api.LittleMonkeyApiClientAuthenticationError):
        run(client.async_get_data())


@pytest.mark.parametrize(
    "failure", [asyncio.TimeoutError(), aiohttp.ClientError("dns")]
)
def test_login_network_error(api, failure):
    """A network failure at login raises the communication error."""
    client = make_client(api, Session(login=failure))
    with pytest.raises(api.LittleMonkeyApiClientCommunicationError):
        run(client.async_get_cookiesdata())


def test_login_unexpected_error(api):
    """Any other failure at login raises the generic error."""
    client = make_client(api, Session(login=RuntimeError("boom")))
    with pytest.raises(api.LittleMonkeyApiClientError) as raised:
        run(client.async_get_cookiesdata())
    assert type(raised.value) is api.LittleMonkeyApiClientError


# --- Gateway errors


@pytest.mark.parametrize(
    "answer",
    [
        Response(is_json=False),
        Response(payload={"gateways": []}),
        Response(payload={"gateways": [{"gateway_id": 1, "devices": []}]}),
    ],
)
def test_gateway_not_found(api, answer):
    """An account without gateway or power meter raises an error."""
    session = Session(gateways=answer)
    with pytest.raises(api.LittleMonkeyApiClientError):
        run(make_client(api, session).async_get_data())
    assert "realtime_conso" not in session.calls


# --- Real-time consumption errors: the update fails


@pytest.mark.parametrize(
    "answer",
    [
        aiohttp.ClientError("down"),
        asyncio.TimeoutError(),
        Response(is_json=False),
    ],
)
def test_realtime_unreachable(api, answer):
    """Without real-time consumption the communication error is raised."""
    client = make_client(api, Session(realtime_conso=answer))
    with pytest.raises(api.LittleMonkeyApiClientCommunicationError):
        run(client.async_get_data())


def test_slow_api_times_out(api, monkeypatch):
    """An API slower than the timeout raises the communication error."""
    monkeypatch.setattr(api, "CONF_API_TIMEOUT", 0.01)

    async def too_slow():
        await asyncio.sleep(5)

    client = make_client(api, Session(realtime_conso=too_slow))
    with pytest.raises(api.LittleMonkeyApiClientCommunicationError):
        run(client.async_get_data())


def test_realtime_unexpected_format(api):
    """An unexpected real-time payload raises the generic error."""
    session = Session(realtime_conso=Response(payload={"oops": 1}))
    with pytest.raises(api.LittleMonkeyApiClientError):
        run(make_client(api, session).async_get_data())


# --- HTTP errors and release of the connections


@pytest.mark.parametrize("status", [400, 404, 500, 503])
def test_login_http_error_is_not_a_success(api, status):
    """An HTTP error at login is reported, not taken as a valid session."""
    session = Session(login=Response(status=status))
    client = make_client(api, session)
    with pytest.raises(api.LittleMonkeyApiClientCommunicationError):
        run(client.async_get_cookiesdata())
    assert client._cookies is None
    with pytest.raises(api.LittleMonkeyApiClientCommunicationError):
        run(client.async_get_data())
    assert "gateways" not in session.calls


@pytest.mark.parametrize("status", [404, 500, 503])
def test_realtime_http_error(api, status):
    """An HTTP error on the real-time API fails the update, even with JSON."""
    answer = Response(status=status, payload={"real_time": {"value": 1}})
    client = make_client(api, Session(realtime_conso=answer))
    with pytest.raises(api.LittleMonkeyApiClientCommunicationError):
        run(client.async_get_data())
    assert client.realtime_conso is None


def test_statistic_http_error_is_best_effort(api):
    """An HTTP error on a statistics API keeps the real-time value."""
    answer = Response(status=500, payload=powerstat())
    client = make_client(api, Session(powerstat=answer))
    run(client.async_get_data())
    assert client.realtime_conso == 512
    assert client.kwh is None


def test_slow_body_times_out(api, monkeypatch):
    """The timeout also covers the reading of the response body."""
    monkeypatch.setattr(api, "CONF_API_TIMEOUT", 0.01)
    answer = Response(payload={"real_time": {"value": 1}}, delay=5)
    client = make_client(api, Session(realtime_conso=answer))
    with pytest.raises(api.LittleMonkeyApiClientCommunicationError):
        run(client.async_get_data())
    assert answer.released is True


@pytest.mark.parametrize("status", [200, 401, 500])
def test_responses_are_released(api, status):
    """The connection is released whatever the answer."""
    answer = Response(status=status, payload={"real_time": {"value": 512}})
    session = Session(realtime_conso=answer)
    with contextlib.suppress(api.LittleMonkeyApiClientError):
        run(make_client(api, session).async_get_data())
    assert answer.released is True
    for name in ("login", "gateways"):
        assert session.routes[name].released is True


# --- Session expiry


def test_session_expiry_logs_in_again(api):
    """A rejected session triggers one new login, then the poll succeeds."""
    answers = iter(
        [Response(status=401), Response(payload={"real_time": {"value": 7}})]
    )
    session = Session(realtime_conso=lambda: next(answers))
    client = make_client(api, session)
    run(client.async_get_data())
    assert client.realtime_conso == 7
    assert session.calls.count("login") == 2
    # The statistics skipped by the failed attempt are not postponed
    assert client.kwh == 4.2


def test_session_still_rejected_after_login(api):
    """A session rejected after a new login is not a credentials error."""
    session = Session(realtime_conso=Response(status=401))
    with pytest.raises(api.LittleMonkeyApiClientError) as raised:
        run(make_client(api, session).async_get_data())
    assert type(raised.value) is api.LittleMonkeyApiClientError
    assert session.calls.count("login") == 2


# --- Live data: ecojoko serves outdated data ten minutes after /gateways


def fake_clock(api, monkeypatch):
    """Replace the clock of the API client by one the test moves."""
    clock = {"now": 1000.0}
    monkeypatch.setattr(
        api, "time", types.SimpleNamespace(monotonic=lambda: clock["now"])
    )
    return clock


def poll_during(client, clock, seconds, step=5):
    """Poll every `step` seconds of the fake clock."""

    async def scenario():
        for _ in range(seconds // step):
            await client.async_get_data()
            clock["now"] += step

    run(scenario())


def test_gateways_are_read_again_every_five_minutes(api, monkeypatch):
    """The list of the gateways is read often enough to keep the data live."""
    clock = fake_clock(api, monkeypatch)
    session = Session()
    client = make_client(api, session)
    poll_during(client, clock, 295)
    assert session.calls.count("gateways") == 1
    poll_during(client, clock, 10)
    assert session.calls.count("gateways") == 2
    # One hour: the first reading, then one every five minutes
    poll_during(client, clock, 3295)
    assert session.calls.count("gateways") == 12
    diagnostics = client.diagnostics()
    assert diagnostics["gateways_count"] == 12
    # Never a new login: the session is kept
    assert session.calls.count("login") == 1
    assert diagnostics["login_count"] == 1


def test_frozen_values_do_not_log_in_again(api, monkeypatch):
    """Values that do not change are reported, without a new login."""
    clock = fake_clock(api, monkeypatch)
    session = Session()
    client = make_client(api, session)
    poll_during(client, clock, 900)
    assert session.calls.count("login") == 1
    assert client.diagnostics()["seconds_since_realtime_change"] == 900


def test_gateways_reading_updates_the_firmware_version(api, monkeypatch):
    """The periodic reading refreshes what the gateway reports."""
    clock = fake_clock(api, monkeypatch)
    session = Session()
    client = make_client(api, session)
    poll_during(client, clock, 5)
    updated = json.loads(json.dumps(GATEWAYS))
    updated["gateways"][0]["gateway_firmware_version"] = "10"
    session.routes["gateways"] = Response(payload=updated)
    poll_during(client, clock, 300)
    assert client.gateway_firmware_version == "10"


@pytest.mark.parametrize("answer", [
    lambda: aiohttp.ClientError("boom"),
    lambda: Response(status=503),
    lambda: Response(payload={"gateways": []}),
    lambda: Response(is_json=False),
])
def test_failed_gateways_reading_is_tried_again_shortly(api, monkeypatch, answer):
    """A reading that fails neither fails the poll nor waits five minutes."""
    clock = fake_clock(api, monkeypatch)
    session = Session()
    client = make_client(api, session)
    poll_during(client, clock, 300)
    session.routes["gateways"] = answer()
    poll_during(client, clock, 5)
    assert session.calls.count("gateways") == 2
    assert client.realtime_conso == 512
    # Not at each poll
    poll_during(client, clock, 25)
    assert session.calls.count("gateways") == 2
    session.routes["gateways"] = Response(payload=GATEWAYS)
    poll_during(client, clock, 5)
    assert session.calls.count("gateways") == 3
    # Back to the usual delay
    poll_during(client, clock, 295)
    assert session.calls.count("gateways") == 3
    poll_during(client, clock, 5)
    assert session.calls.count("gateways") == 4


def test_gateways_reading_rejected_logs_in_again(api, monkeypatch):
    """A session rejected by the periodic reading is replaced, as for any API."""
    clock = fake_clock(api, monkeypatch)
    session = Session()
    client = make_client(api, session)
    poll_during(client, clock, 300)
    answers = iter([Response(status=401), Response(payload=GATEWAYS)])
    session.routes["gateways"] = lambda: next(answers)
    poll_during(client, clock, 5)
    assert session.calls.count("login") == 2
    assert client.realtime_conso == 512


# --- Statistics errors: the update succeeds, a lasting failure warns once


def test_powerstat_network_error(api, caplog):
    """A failing statistic keeps the real-time value, without a warning yet."""
    session = Session(powerstat=aiohttp.ClientError("boom"))
    client = make_client(api, session)

    async def poll_twice():
        await client.async_get_data()
        await client.async_get_data()

    with caplog.at_level(logging.DEBUG):
        run(poll_twice())
    assert client.realtime_conso == 512
    assert client.kwh is None
    # Called again after the usual delay only, not at each poll
    assert session.calls.count("powerstat") == 1
    # A single network failure is usual: it is not worth a warning
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


def test_powerstat_network_error_twice_in_a_row_warns_once(api, caplog):
    """A statistic that fails again at its next call warns, only once."""
    session = Session(powerstat=aiohttp.ClientError("boom"))
    client = make_client(api, session)

    async def scenario():
        for _ in range(3):
            client._last_stat_refresh["powerstat"] = None
            await client.async_get_data()
        session.routes["powerstat"] = Response(payload=powerstat(9))
        client._last_stat_refresh["powerstat"] = None
        await client.async_get_data()
        # After a recovery, a single failure is silent again
        session.routes["powerstat"] = aiohttp.ClientError("boom")
        client._last_stat_refresh["powerstat"] = None
        await client.async_get_data()

    with caplog.at_level(logging.INFO):
        run(scenario())
    assert session.calls.count("powerstat") == 5
    levels = [r.levelno for r in caplog.records]
    assert levels == [logging.WARNING, logging.INFO]


@pytest.mark.parametrize("name", ["tempstat", "humstat"])
def test_no_measure_yet_keeps_the_values_without_warning(api, caplog, name):
    """Just after midnight the list of the day is empty: nothing is wrong."""
    session = Session()
    client = make_client(api, session, poll=60, temphum=True)

    async def scenario():
        await client.async_get_data()
        session.routes[name] = Response(payload={"stat": {"data": []}})
        client._last_stat_refresh[name] = None
        await client.async_get_data()

    with caplog.at_level(logging.INFO):
        run(scenario())
    assert session.calls.count(name) == 2
    assert (client.indoor_temp, client.outdoor_temp) == (20, 8)
    assert (client.indoor_hum, client.outdoor_hum) == (50, 80)
    assert caplog.records == []


def test_powerstat_unexpected_format_then_recovery(api, caplog):
    """An unexpected statistic format warns once, then recovery is logged."""
    session = Session(powerstat=Response(payload={"stat": {"data": []}}))
    client = make_client(api, session)

    async def scenario():
        await client.async_get_data()
        session.routes["powerstat"] = Response(payload=powerstat(9))
        client._last_stat_refresh["powerstat"] = None
        await client.async_get_data()

    with caplog.at_level(logging.INFO):
        run(scenario())
    assert client.kwh == 9
    levels = [r.levelno for r in caplog.records]
    assert levels == [logging.WARNING, logging.INFO]


# --- Parsing of the energy statistics


def test_hchp(api):
    """HC/HP values are read from the sub-consumptions."""
    payload = powerstat(subconsumption=[
        {"label": "Heures Creuses", "kwh": "1.5"},
        {"label": "Heures Pleines", "kwh": 2},
    ])
    session = Session(powerstat=Response(payload=payload))
    client = make_client(api, session, hchp=True)
    run(client.async_get_data())
    assert (client.kwh_hc_ns, client.kwh_hp_ns) == (1.5, 2.0)


def test_tempo(api):
    """Tempo bands are read by id, keep their sensors and add up in HC/HP."""
    payload = powerstat(subconsumption=[
        {"id": 19, "label": "HC Bleu", "kwh": 1},
        {"id": 18, "label": "HP Bleu", "kwh": 2},
        {"id": 21, "label": "HC Blanc", "kwh": 3},
        # A renamed band is still found by its id
        {"id": 22, "label": "HP Jour Rouge", "kwh": 4},
    ])
    session = Session(powerstat=Response(payload=payload))
    client = make_client(api, session, hchp=True, tempo=True)
    run(client.async_get_data())
    values = client.band_values
    assert values["blue_hc_grid_consumption"] == 1
    assert values["blue_hp_grid_consumption"] == 2
    assert values["white_hc_grid_consumption"] == 3
    # A band absent from the day counts 0
    assert values["white_hp_grid_consumption"] == 0
    assert values["red_hc_grid_consumption"] == 0
    assert values["red_hp_grid_consumption"] == 4
    assert (client.kwh_hc_ns, client.kwh_hp_ns) == (4, 6)


# Days observed on real accounts: (sub-consumptions, HC, HP)
REAL_DAYS = {
    # EDF Zen Week-End Plus, weekday, special day and Saturday
    "zen_weekend_plus_weekday": ([
        {"id": 8, "label": "HP Semaine", "kwh": 25.91},
        {"id": 9, "label": "HC Semaine", "kwh": 19.09},
    ], 19.09, 25.91),
    "zen_weekend_plus_special_day": ([
        {"id": 10, "label": "HP Jour Spécial", "kwh": 23.41},
        {"id": 11, "label": "HC Jour Spécial", "kwh": 9.58},
    ], 9.58, 23.41),
    "zen_weekend_plus_saturday": ([
        {"id": 6, "label": "HP Weekend", "kwh": 20.76},
        {"id": 7, "label": "HC Weekend", "kwh": 16.1},
    ], 16.1, 20.76),
    # EDF Tempo: a day changing from blue to white has two HC bands
    "tempo_blue_to_white": ([
        {"id": 19, "label": "HC Bleu", "kwh": 3.83},
        {"id": 20, "label": "HP Blanc", "kwh": 7.47},
        {"id": 21, "label": "HC Blanc", "kwh": 0.78},
    ], 4.61, 7.47),
    # EDF HC + Week-end: a single band on Saturday and Sunday (PR #125)
    "hc_weekend_saturday": ([
        {"id": 13, "label": "Heures Weekend", "kwh": 26.19},
    ], 0, 0),
    # Gaz de Bordeaux, HC given before HP
    "hc_first": ([
        {"id": 3, "label": "Heures Creuses", "kwh": 4.09},
        {"id": 2, "label": "Heures Pleines", "kwh": 2.9},
    ], 4.09, 2.9),
}


@pytest.mark.parametrize("day", REAL_DAYS)
def test_hchp_adds_every_band_of_a_category(api, day):
    """HC and HP add all the bands of their category, whatever the contract."""
    subconsumption, hc, hp = REAL_DAYS[day]
    payload = powerstat(subconsumption=subconsumption)
    session = Session(powerstat=Response(payload=payload))
    client = make_client(api, session, hchp=True)
    run(client.async_get_data())
    assert (client.kwh_hc_ns, client.kwh_hp_ns) == (hc, hp)


def test_unclassified_band_is_logged_once(api, monkeypatch, caplog):
    """A band counted in neither HC nor HP is logged once."""
    clock = fake_clock(api, monkeypatch)
    payload = powerstat(subconsumption=[
        {"id": 13, "label": "Heures Weekend", "kwh": 26.19},
    ])
    session = Session(powerstat=Response(payload=payload))
    client = make_client(api, session, hchp=True)
    with caplog.at_level(logging.INFO):
        poll_during(client, clock, 120)
    messages = [r.getMessage() for r in caplog.records
                if "Heures Weekend" in r.getMessage()]
    assert messages == [
        "Tariff band 'Heures Weekend' is counted in neither HC nor HP"]


@pytest.mark.parametrize(("label", "category"), [
    ("Heures Creuses", "hc"),
    ("HC Rouge", "hc"),
    (" hc semaine", "hc"),
    ("Heures Pleines", "hp"),
    ("HP Jour Spécial", "hp"),
    ("Heures Weekend", None),
    ("HCHP", None),
    ("", None),
    (None, None),
])
def test_category_of(api, label, category):
    """The category of a band is deduced from the first words of its label."""
    assert tariff_module(api).category_of(label) == category


@pytest.mark.parametrize(("raw", "expected"), [(-1.5, 1.5), ("0", 0), (2, 2)])
def test_production_surplus_is_positive(api, raw, expected):
    """The production surplus is always reported as a positive value."""
    session = Session(powerstat=Response(payload=powerstat(kwh_prod=raw)))
    client = make_client(api, session, prod=True)
    run(client.async_get_data())
    assert client.kwh_prod == expected


def test_options_off_ignore_extra_data(api):
    """Without the options, sub-consumptions and production are ignored."""
    payload = powerstat(
        kwh_prod=3, subconsumption=[{"label": "HC Bleu", "kwh": 1}]
    )
    session = Session(powerstat=Response(payload=payload))
    client = make_client(api, session)
    run(client.async_get_data())
    assert client.kwh_prod is None
    assert client.band_values == {}
    assert client.kwh_hc_ns is None


# --- Contract and tariff bands


def test_contract_is_read_without_prices(api):
    """The active contract is read with its subscription, without the ids.

    The diagnostics leave out the price of the subscription.
    """
    session = Session()
    client = make_client(api, session)
    assert client.contract is None
    run(client.async_get_data())
    assert client.contract == {
        "supplier_name": "EDF",
        "offer_id": 5480,
        "offer_name": "Zen Fixe - Option HP/HC",
        "offer_type": "HP/HC",
        "is_hchp": 1,
        "special_day": 1,
        "power": 9,
        "subscription_price": 24.77,
        "off_peak_timeslots": [
            {"start": "01:30", "stop": "07:00"},
            {"start": "14:00", "stop": "16:30"},
        ],
        "start_date": "2026-08-05",
    }
    diagnostics = client.diagnostics()
    assert diagnostics["contract"] == {
        key: value for key, value in client.contract.items() if key != "subscription_price"}
    assert "24.77" not in repr(diagnostics)
    assert "283901" not in repr(diagnostics)


def test_contract_without_active_flag(api):
    """Without an active flag, the contract with no end date is taken."""
    suppliers = {"suppliers": [
        {"offer_type": "TEMPO", "stop_date": 1781042400000},
        {"offer_type": "HP/HC", "start_date": 1781042400000},
    ]}
    session = Session(suppliers=Response(payload=suppliers))
    client = make_client(api, session)
    run(client.async_get_data())
    assert client.contract["offer_type"] == "HP/HC"
    assert client.contract["off_peak_timeslots"] == []


def test_contract_is_read_again_after_six_hours(api, monkeypatch):
    """The contract is read at the first poll, then every six hours."""
    clock = fake_clock(api, monkeypatch)
    session = Session()
    client = make_client(api, session)
    poll_during(client, clock, 6 * 3600 - 10)
    assert session.calls.count("suppliers") == 1
    poll_during(client, clock, 30)
    assert session.calls.count("suppliers") == 2


@pytest.mark.parametrize("answer", [
    Response(status=500),
    Response(payload={"error": 1}),
    Response(is_json=False),
])
def test_contract_failure_is_not_an_error(api, monkeypatch, answer):
    """The energy values do not depend on the contract, read again later."""
    clock = fake_clock(api, monkeypatch)
    session = Session(suppliers=answer)
    client = make_client(api, session)
    run(client.async_get_data())
    assert client.realtime_conso == 512
    assert client.kwh == 4.2
    assert client.contract is None
    poll_during(client, clock, 590)
    assert session.calls.count("suppliers") == 1
    poll_during(client, clock, 30)
    assert session.calls.count("suppliers") == 2


def test_tariff_bands_are_collected_by_id(api):
    """The bands of the period and of the day are kept by id."""
    payload = powerstat(subconsumption=[
        {"id": 18, "label": "HP Bleu", "kwh": 1},
        {"id": 19, "label": "HC Bleu", "kwh": 2},
    ])
    payload["stat"]["pricing_details"] = [
        {"id": 18, "label": "HP Bleu", "color": "#0087B1"},
        {"id": 19, "label": "HC Bleu", "color": "#6BBED8"},
        {"id": 20, "label": "HP Blanc", "color": "#ffffff"},
        {"label": "no id"},
        "unexpected",
    ]
    session = Session(powerstat=Response(payload=payload))
    client = make_client(api, session)
    run(client.async_get_data())
    assert client.bands == {18: "HP Bleu", 19: "HC Bleu", 20: "HP Blanc"}
    assert client.diagnostics()["tariff_bands"] == {
        "18": "HP Bleu", "19": "HC Bleu", "20": "HP Blanc"}


# --- Day of the statistics


def week(**days):
    """Return a powerstat response from the values of each week day."""
    data = [{"kwh": 0} for _ in range(7)]
    for index, values in days.items():
        data[int(index[1:])] = values
    return {"stat": {"data": data}}


def test_stat_date_follows_the_statistics(api, monkeypatch):
    """The client tells which day its energy values belong to."""
    monday = dt.date(2026, 11, 9)
    monkeypatch.setattr(api, "get_current_date", lambda timezone: monday)
    session = Session(powerstat=Response(payload=week(d0={"kwh": 7})))
    client = make_client(api, session)
    assert client.stat_date is None
    run(client.async_get_data())
    assert client.stat_date == "2026-11-09"
    assert client.kwh == 7


def test_values_of_the_previous_day_are_dropped(api, monkeypatch):
    """A value missing from the response of a new day is not kept."""
    today = {"date": dt.date(2026, 11, 9)}
    monkeypatch.setattr(api, "get_current_date", lambda timezone: today["date"])
    monday = {
        "kwh": 8,
        "kwh_prod": 5,
        "subconsumption": [
            {"label": "Heures Creuses", "kwh": 3},
            {"label": "Heures Pleines", "kwh": 5},
        ],
    }
    session = Session(powerstat=Response(payload=week(d0=monday)))
    client = make_client(api, session, hchp=True, prod=True)

    async def scenario():
        await client.async_get_data()
        assert (client.kwh, client.kwh_prod) == (8, 5)
        assert (client.kwh_hc_ns, client.kwh_hp_ns) == (3, 5)
        # Tuesday, before ecojoko gives production and sub-consumptions
        today["date"] = dt.date(2026, 11, 10)
        session.routes["powerstat"] = Response(
            payload=week(d0=monday, d1={"kwh": 0.1})
        )
        client._last_stat_refresh["powerstat"] = None
        await client.async_get_data()

    run(scenario())
    assert client.stat_date == "2026-11-10"
    assert client.kwh == 0.1
    assert client.kwh_prod is None
    assert client.kwh_hc_ns is None
    assert client.kwh_hp_ns is None


# --- Scheduling of the statistics APIs


def simulate(api, monkeypatch, poll, temphum=True, gateways=GATEWAYS,
             duration=600):
    """Poll during `duration` seconds of a fake clock.

    Return the client, the call times of each statistics API and the
    highest number of statistics APIs called during one poll.
    """
    clock = {"now": 1000.0}
    monkeypatch.setattr(
        api, "time", types.SimpleNamespace(monotonic=lambda: clock["now"])
    )
    session = Session(gateways=Response(payload=gateways))
    client = make_client(api, session, poll=poll, temphum=temphum)
    times = {name: [] for name in STAT_APIS}
    busiest = 0

    async def scenario():
        nonlocal busiest
        while clock["now"] - 1000.0 <= duration:
            before = len(session.calls)
            await client.async_get_data()
            called = [n for n in session.calls[before:] if n in times]
            busiest = max(busiest, len(called))
            for name in called:
                times[name].append(clock["now"] - 1000.0)
            # The coordinator waits for the poll interval after each update
            clock["now"] += poll + 0.3

    run(scenario())
    return client, times, busiest


@pytest.mark.parametrize("poll", [3, 5, 10, 15, 20, 30, 60])
def test_every_statistic_is_refreshed(api, monkeypatch, poll):
    """Whatever the poll interval, no statistic is left behind."""
    client, times, _ = simulate(api, monkeypatch, poll)
    for name in STAT_APIS:
        calls = times[name]
        assert len(calls) >= 3, name
        gaps = [later - earlier for earlier, later in zip(calls, calls[1:])]
        # Usual delay, plus the granularity of the polls
        assert max(gaps) <= api.CONF_API_STAT_REFRESH + 2 * poll, name
    assert (client.indoor_temp, client.outdoor_temp) == (20, 8)
    assert (client.indoor_hum, client.outdoor_hum) == (50, 80)


@pytest.mark.parametrize("poll", [3, 5, 10])
def test_short_poll_spreads_the_statistics(api, monkeypatch, poll):
    """With a short poll interval one statistics API is called per poll."""
    _, _, busiest = simulate(api, monkeypatch, poll)
    assert busiest == 1


def test_temphum_option_off(api, monkeypatch):
    """Temperature and humidity are not requested without the option."""
    _, times, _ = simulate(api, monkeypatch, 5, temphum=False)
    assert times["tempstat"] == []
    assert times["humstat"] == []
    assert len(times["powerstat"]) > 10


def test_no_temphum_device(api, monkeypatch):
    """Temperature and humidity are not requested without the device."""
    _, times, _ = simulate(
        api, monkeypatch, 5, gateways=GATEWAYS_WITHOUT_TEMP_HUM
    )
    assert times["tempstat"] == []
    assert times["humstat"] == []


def test_values_are_rounded_to_two_decimals(api):
    """Float noise from ecojoko or from a sum does not reach the sensors."""
    payload = powerstat(kwh=22.920000000000002, subconsumption=[
        {"id": 19, "label": "HC Bleu", "kwh": 0.1},
        {"id": 21, "label": "HC Blanc", "kwh": 0.2},
        {"id": 18, "label": "HP Bleu", "kwh": 7.4399999999999995},
    ])
    session = Session(
        powerstat=Response(payload=payload),
        tempstat=Response(payload={"stat": {"data": [
            {"value": 19.900000000000002, "ext_value": 9.92}]}}),
        humstat=Response(payload={"stat": {"data": [
            {"value": 46, "ext_value": 58.599999999999994}]}}),
    )
    # A poll of 30 seconds calls the three statistics APIs at once
    client = make_client(
        api, session, poll=30, hchp=True, tempo=True, temphum=True)
    run(client.async_get_data())
    assert client.kwh == 22.92
    assert (client.kwh_hc_ns, client.kwh_hp_ns) == (0.3, 7.44)
    assert client.band_values["blue_hp_grid_consumption"] == 7.44
    assert (client.indoor_temp, client.outdoor_temp) == (19.9, 9.92)
    assert (client.indoor_hum, client.outdoor_hum) == (46, 58.6)
    assert isinstance(client.indoor_hum, int)


@pytest.mark.parametrize(("real_time", "expected"), [
    ({"value": 512, "value2": 640}, 640),
    ({"value": -224, "value2": -310.456}, -310.46),
    ({"value": 512, "value2": "640"}, 640.0),
    ({"value": 430, "value2": 0}, None),
    ({"value": -224, "value2": 0}, None),
    ({"value": 0, "value2": 0}, 0),
    ({"value": 512}, None),
    ({"value": 512, "value2": None}, None),
    ({"value": 512, "value2": "n/a"}, None),
    ({"value": 512, "value2": float("nan")}, None),
    ({"value": 512, "value2": True}, None),
])
def test_apparent_power(api, real_time, expected):
    """The apparent power is optional and never breaks the real-time value."""
    session = Session(realtime_conso=Response(payload={"real_time": real_time}))
    client = make_client(api, session)
    run(client.async_get_data())
    assert client.realtime_conso == real_time["value"]
    assert client.realtime_va == expected


def test_apparent_power_is_not_kept_when_it_disappears(api):
    """A value of a previous poll is not published as the current one."""
    answers = iter([
        Response(payload={"real_time": {"value": 1, "value2": 2}}),
        Response(payload={"real_time": {"value": 3}}),
    ])
    client = make_client(api, Session(realtime_conso=lambda: next(answers)))
    run(client.async_get_data())
    assert client.realtime_va == 2
    run(client.async_get_data())
    assert client.realtime_va is None


def test_round_value_leaves_other_values_alone(utils):
    """Only numbers are rounded."""
    assert utils.round_value(None) is None
    assert utils.round_value("1.239") == "1.239"
    assert utils.round_value(True) is True
    assert utils.round_value(1.239) == 1.24


# --- Tariff bands configured in the entry


def test_unconfigured_band_is_classified_by_its_label(api):
    """A band of the contract not configured yet still counts in HC/HP."""
    payload = powerstat(subconsumption=[
        {"id": 8, "label": "HP Semaine", "kwh": 6.43},
        {"id": 9, "label": "HC Semaine", "kwh": 18.29},
    ])
    session = Session(powerstat=Response(payload=payload))
    # An entry migrated from the HC/HP option only knows bands 2 and 3
    client = make_client(api, session, hchp=True)
    run(client.async_get_data())
    assert (client.kwh_hc_ns, client.kwh_hp_ns) == (18.29, 6.43)


def test_configured_category_wins_over_the_label(api):
    """The category chosen by the user decides, and each band has its value."""
    tariff = tariff_module(api)
    weekend = {**tariff.new_band(13, "Heures Weekend"), "category": "hc"}
    weekday_hc = tariff.new_band(9, "HC Semaine")
    payload = powerstat(subconsumption=[
        {"id": 13, "label": "Heures Weekend", "kwh": 26.19},
    ])
    session = Session(powerstat=Response(payload=payload))
    client = api.LittleMonkeyApiClient(
        username="user", password="secret", poll_interval=5, use_hchp=True,
        use_temphum=False, use_prod=False, session=session,
        bands=[weekend, weekday_hc])
    run(client.async_get_data())
    assert client.band_values == {"band_13": 26.19, "band_9": 0}
    assert (client.kwh_hc_ns, client.kwh_hp_ns) == (26.19, 0)


def test_legacy_bands_keep_the_sensor_keys(api):
    """The bands of the old options keep the keys of their sensors."""
    tariff = tariff_module(api)
    assert tariff.legacy_bands(False, False) == []
    assert [b["key"] for b in tariff.legacy_bands(True, False)] == [
        "hp_grid_consumption", "hc_grid_consumption"]
    tempo = tariff.legacy_bands(False, True)
    assert [(b["id"], b["key"], b["category"]) for b in tempo] == [
        (18, "blue_hp_grid_consumption", "hp"),
        (19, "blue_hc_grid_consumption", "hc"),
        (20, "white_hp_grid_consumption", "hp"),
        (21, "white_hc_grid_consumption", "hc"),
        (22, "red_hp_grid_consumption", "hp"),
        (23, "red_hc_grid_consumption", "hc"),
    ]
    assert not any(tariff.has_sensor(b) for b in tariff.legacy_bands(True, False))
    assert all(tariff.has_sensor(b) for b in tempo)


def day_item(day, *bands):
    """Return the item of a day in a weekly powerstat response."""
    midnight = dt.datetime.combine(day, dt.time(), ZoneInfo("Europe/Paris"))
    return {
        "time": int(midnight.timestamp() * 1000),
        "kwh": 1,
        "subconsumption": [
            {"id": band_id, "label": label, "kwh": 0.5} for band_id, label in bands
        ],
    }


def test_tariff_setup_of_a_tempo_contract(api, monkeypatch):
    """A Tempo contract gets its six bands, even without a red day seen."""
    today = dt.date(2026, 7, 15)
    monkeypatch.setattr(api, "get_current_date", lambda timezone: today)
    week_payload = {"stat": {"data": [
        day_item(today, (18, "HP Bleu"), (19, "HC Bleu")),
    ]}}
    suppliers = {"suppliers": [{
        "is_active": 1, "offer_type": "TEMPO", "offer_name": "TEMPO",
        "supplier_name": "EDF", "start_date": 1690754400000,
    }]}
    session = Session(
        suppliers=Response(payload=suppliers),
        powerstat=Response(payload=week_payload),
    )
    client = make_client(api, session)
    run(client.async_get_cookiesdata())
    contract, bands = run(client.async_get_tariff_setup())
    assert contract["offer_type"] == "TEMPO"
    assert bands == {
        18: "HP Bleu", 19: "HC Bleu", 20: "HP Blanc",
        21: "HC Blanc", 22: "HP Rouge", 23: "HC Rouge",
    }
    assert session.calls.count("powerstat") == 4


def test_tariff_setup_ignores_the_previous_contract(api, monkeypatch):
    """Bands seen before the start of the contract are left out."""
    today = dt.date(2026, 6, 14)
    start = dt.date(2026, 6, 11)
    monkeypatch.setattr(api, "get_current_date", lambda timezone: today)
    week_payload = {"stat": {"data": [
        day_item(dt.date(2026, 6, 10), (18, "HP Bleu"), (19, "HC Bleu")),
        day_item(start, (2, "Heures Pleines"), (3, "Heures Creuses")),
        day_item(today, (2, "Heures Pleines"), (3, "Heures Creuses")),
    ]}}
    start_ms = int(dt.datetime.combine(
        start, dt.time(), ZoneInfo("Europe/Paris")).timestamp() * 1000)
    suppliers = {"suppliers": [
        {"is_active": 1, "offer_type": "UNKNOWN TYPE", "start_date": start_ms},
        {"offer_type": "TEMPO", "stop_date": start_ms},
    ]}
    session = Session(
        suppliers=Response(payload=suppliers),
        powerstat=Response(payload=week_payload),
    )
    client = make_client(api, session)
    run(client.async_get_cookiesdata())
    _contract, bands = run(client.async_get_tariff_setup())
    assert bands == {2: "Heures Pleines", 3: "Heures Creuses"}
    # The contract started this week: the weeks before are not read
    assert session.calls.count("powerstat") == 1


def test_tariff_setup_without_contract(api):
    """The setup goes on without bands when the contract cannot be read."""
    session = Session(suppliers=Response(status=500))
    client = make_client(api, session)
    run(client.async_get_cookiesdata())
    assert run(client.async_get_tariff_setup()) == (None, {})


# --- Bands of the day not configured


def test_unknown_bands_of_a_new_contract(api):
    """The bands of the day missing from the configuration are reported."""
    payload = powerstat(subconsumption=[
        {"id": 8, "label": "HP Semaine", "kwh": 6.43},
        {"id": 9, "label": "HC Semaine", "kwh": 18.29},
    ])
    session = Session(powerstat=Response(payload=payload))
    client = make_client(api, session, hchp=True)
    assert client.unknown_bands is None
    run(client.async_get_data())
    assert client.unknown_bands == {8: "HP Semaine", 9: "HC Semaine"}


@pytest.mark.parametrize(("hchp", "expected"), [
    (True, {}),
    (False, {}),
])
def test_configured_bands_are_not_unknown(api, hchp, expected):
    """Configured bands, and HP/HC without their totals, are not reported."""
    payload = powerstat(subconsumption=[
        {"id": 2, "label": "Heures Pleines", "kwh": 2.9},
        {"id": 3, "label": "Heures Creuses", "kwh": 4.09},
    ])
    session = Session(powerstat=Response(payload=payload))
    # Without HC/HP the entry has no band: HP and HC were not wanted
    client = make_client(api, session, hchp=hchp)
    run(client.async_get_data())
    assert client.unknown_bands == expected


# --- Activity of the account


def test_activity(api):
    """The activity API gives the savings and the values of the last 7 days."""
    session = Session()
    client = make_client(api, session)
    run(client.async_get_data())
    assert run(client.async_get_activity()) == {
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
    method, url, kwargs = session.requests[-1]
    assert (method, url) == ("GET", "https://service.ecojoko.com/user/activity")
    assert kwargs["cookies"] == {"session": "abc"}


def test_activity_without_reference_week(api):
    """Without a reference week, ecojoko gives no savings."""
    answer = json.loads(json.dumps(ACTIVITY))
    answer["activity"]["week_reference"] = 0
    client = make_client(api, Session(activity=Response(payload=answer)))
    run(client.async_get_data())
    values = run(client.async_get_activity())
    assert values["savings_7_days"] is None
    assert values["reference_consumption_7_days"] is None
    assert values["consumption_7_days"] == 74.33


def test_activity_needs_a_login(api):
    """The activity API does not log in: the polls do it."""
    session = Session()
    client = make_client(api, session)
    with pytest.raises(api.LittleMonkeyApiClientCommunicationError):
        run(client.async_get_activity())
    assert session.calls == []


def test_activity_has_a_longer_timeout(api, monkeypatch):
    """The activity is slow to compute: it has its own timeout."""
    monkeypatch.setattr(api, "CONF_API_TIMEOUT", 0.01)
    client = make_client(api, Session(activity=Response(payload=ACTIVITY, delay=0.1)))
    run(client.async_get_data())
    assert run(client.async_get_activity())["cost_7_days"] == 16.6

    monkeypatch.setattr(api, "CONF_API_ACTIVITY_TIMEOUT", 0.01)
    with pytest.raises(api.LittleMonkeyApiClientCommunicationError):
        run(client.async_get_activity())


def test_activity_session_expired(api):
    """A rejected session is left to the next poll, which logs in again."""
    client = make_client(api, Session(activity=Response(status=401)))
    run(client.async_get_data())
    with pytest.raises(api.LittleMonkeyApiClientAuthenticationError):
        run(client.async_get_activity())
    assert client.diagnostics()["logged_in"] is False


@pytest.mark.parametrize("answer", [
    Response(payload={"error": "unknown"}),
    Response(payload=None, is_json=False),
    Response(payload={"activity": None}),
])
def test_activity_unexpected_answer(api, answer):
    """An unexpected answer is an error of the activity only."""
    client = make_client(api, Session(activity=answer))
    run(client.async_get_data())
    with pytest.raises(api.LittleMonkeyApiClientError):
        run(client.async_get_activity())


@pytest.mark.parametrize("data", [None, "x", [381, None, 398], [381, "a"]])
def test_activity_without_daily_values(api, data):
    """Unexpected daily values are left out, the other values are kept."""
    answer = json.loads(json.dumps(ACTIVITY))
    answer["activity"]["conso_7j"]["data"] = data
    client = make_client(api, Session(activity=Response(payload=answer)))
    run(client.async_get_data())
    values = run(client.async_get_activity())
    assert values["daily_consumption_7_days"] is None
    assert values["consumption_7_days"] == 74.33


# --- Savings of the account


@pytest.fixture
def savings_day(api, monkeypatch):
    """Make the day of the observed savings today."""
    monkeypatch.setattr(api, "get_current_date", lambda _tz: SAVINGS_DAY)


WEEK = {
    "savings": -0.35, "savings_kwh": -2.58, "cost": 1.8, "consumption": 7.58,
    "reference_cost": 1.45, "reference_consumption": 5.01,
}
EMPTY_BAR = dict.fromkeys(WEEK)


def test_savings(api, savings_day):
    """The savings over 12 months, this week, month and year."""
    session = Session()
    client = make_client(api, session)
    run(client.async_get_data())
    values = run(client.async_get_savings())
    assert {key: value for key, value in values.items()
            if key not in api.SAVINGS_PERIODS} == {
        "consumption_cost_12_months": 483.6,
        "reference_cost_12_months": 821.23,
        "savings_12_months": 337.63,
        "consumption_12_months": 1701.72,
        "reference_consumption_12_months": 3319,
        "savings_kwh_12_months": 1617.28,
        "savings_level": 5,
    }
    assert values["week"] == {
        **WEEK,
        "start": "2026-11-16",
        "missing_data": False,
        "bars": [{"date": "2026-11-16", **WEEK}] + [
            {"date": f"2026-11-{day}", **EMPTY_BAR} for day in range(17, 23)],
    }
    urls = [url for _method, url, _kwargs in session.requests[-4:]]
    assert urls == [
        "https://service.ecojoko.com/gateway/1/savings/m/12",
        "https://service.ecojoko.com/gateway/1/device/2/savingstat/w/2026-11-16",
        "https://service.ecojoko.com/gateway/1/device/2/savingstat/m/2026-11-16",
        "https://service.ecojoko.com/gateway/1/device/2/savingstat/y/2026-11-16",
    ]


def test_savings_of_a_past_period(api, savings_day):
    """The savings of any week, month or year, for the history of the card."""
    session = Session()
    client = make_client(api, session)
    run(client.async_get_data())
    values = run(client.async_get_savings_period("year", dt.date(2025, 3, 4)))
    assert values["savings"] == -0.35
    assert session.requests[-1][1].endswith("/savingstat/y/2025-03-04")


def test_saving_in_kwh_is_positive(api, savings_day):
    """A saving keeps its kWh positive."""
    answer = json.loads(json.dumps(SAVINGSTAT_WEEK))
    answer["stat"]["period"].update(val=25.85, val_kwh=67.62, is_saving=1)
    client = make_client(api, Session(savingstat=Response(payload=answer)))
    run(client.async_get_data())
    values = run(client.async_get_savings_period("week", SAVINGS_DAY))
    assert (values["savings"], values["savings_kwh"]) == (25.85, 67.62)


def test_savings_need_a_login(api):
    """The savings APIs do not log in: the polls do it."""
    session = Session()
    client = make_client(api, session)
    with pytest.raises(api.LittleMonkeyApiClientCommunicationError):
        run(client.async_get_savings())
    with pytest.raises(api.LittleMonkeyApiClientCommunicationError):
        run(client.async_get_savings_period("week", SAVINGS_DAY))
    assert session.calls == []


@pytest.mark.parametrize("route", ["savings/m", "savingstat"])
@pytest.mark.parametrize("answer", [
    Response(payload={"error": "unknown"}),
    Response(payload=None, is_json=False),
    Response(status=500),
])
def test_savings_unexpected_answer(api, route, answer):
    """An unexpected answer is an error of the savings only."""
    client = make_client(api, Session(**{route: answer}))
    run(client.async_get_data())
    with pytest.raises(api.LittleMonkeyApiClientError):
        run(client.async_get_savings())


# --- Analysis of the consumption


def test_analysis(api):
    """The analysis gives the categories of the consumption of a period."""
    session = Session()
    client = make_client(api, session)
    run(client.async_get_data())
    analysis = run(client.async_get_analysis("week"))
    assert session.requests[-1][1] == (
        "https://service.ecojoko.com/gateway/1/device/2/ia/conso/w")
    assert analysis == {
        "available": True,
        "start": "2026-11-02",
        "cost": 14.46,
        "consumption": 60.6,
        "categories": [
            {"id": 7, "name": "Talon de consommation", "color": "#022469", "cost": 5.03,
             "consumption": 37.1, "percentage": 61, "trend": "up", "beta": False,
             "children": []},
            {"id": 5, "name": "Gros électroménager", "color": "#05a1fb", "cost": 0.71,
             "consumption": 1.78, "percentage": 3, "trend": "up", "beta": True,
             "children": [{"id": 12, "name": "Lave-vaisselle", "color": "#05a1fb",
                           "cost": 0.29, "consumption": 0.73, "percentage": 1}]},
            {"id": 9, "name": "Autres appareils", "color": "#acc5cf", "cost": 4.95,
             "consumption": 12.4, "percentage": 20, "trend": "down", "beta": False,
             "children": []},
        ],
    }
    run(client.async_get_analysis("month", dt.date(2026, 10, 15)))
    assert session.requests[-1][1].endswith("/ia/conso/m/2026-10-15")


def test_analysis_not_ready(api):
    """A period not analysed yet gives the explanation of ecojoko."""
    client = make_client(api, Session(**{"ia/conso": Response(status=400, payload=ANALYSIS_PENDING)}))
    run(client.async_get_data())
    assert run(client.async_get_analysis("week", dt.date(2026, 11, 9))) == {
        "available": False,
        "message": "Vos données sont en cours d’analyse.",
        "start": "2026-11-09",
    }


def test_analysis_other_errors_are_errors(api):
    """Only an answer HTTP 400 in JSON is an explanation."""
    client = make_client(api, Session(**{"ia/conso": Response(status=500, payload={})}))
    run(client.async_get_data())
    with pytest.raises(api.LittleMonkeyApiClientCommunicationError):
        run(client.async_get_analysis("week"))
    client = make_client(api, Session(**{"ia/conso": Response(status=400, is_json=False)}))
    run(client.async_get_data())
    with pytest.raises(api.LittleMonkeyApiClientCommunicationError):
        run(client.async_get_analysis("week"))


def test_category_history(api):
    """The history of a category keeps one bar a week."""
    session = Session()
    client = make_client(api, session)
    run(client.async_get_data())
    history = run(client.async_get_category_history(8, dt.date(2026, 11, 16)))
    assert session.requests[-1][1].endswith("/usage/8/history/y/2026-11-16")
    assert history == {
        "category": {"id": 8, "name": "Éclairage", "color": "#ffed21"},
        "start": "2026-01-05",
        "bars": [
            {"date": "2026-01-05", "cost": 0, "consumption": 0, "percentage": 0},
            {"date": "2026-01-12", "cost": 0.11, "consumption": 0.67, "percentage": 0.8},
        ],
    }


def test_activations(api):
    """The activations of the appliances, 48 hours a page."""
    session = Session()
    client = make_client(api, session)
    run(client.async_get_data())
    activations = run(client.async_get_activations(2))
    assert session.requests[-1][1].endswith("/ia/appliances/0/2")
    assert activations["start"] == "2026-11-14T04:00:00+01:00"
    assert activations["end"] == "2026-11-16T04:00:00+01:00"
    assert activations["pending"] is False
    assert activations["activations"][0] == {
        "start": "2026-11-16T00:03:00+01:00",
        "end": "2026-11-16T02:29:00+01:00",
        "power": 694,
        "energy": 1.69,
        "shape": {"width": 96, "height": 16, "color": "#FA6200"},
    }


def test_analysis_apis_need_a_login(api):
    """The analysis APIs do not log in: the polls do it."""
    session = Session()
    client = make_client(api, session)
    for call in (client.async_get_analysis("week"),
                 client.async_get_category_history(8, dt.date(2026, 11, 16)),
                 client.async_get_activations()):
        with pytest.raises(api.LittleMonkeyApiClientCommunicationError):
            run(call)
    assert session.calls == []


@pytest.mark.parametrize("route, read", [
    ("ia/conso", lambda client: client.async_get_analysis("week")),
    ("history", lambda client: client.async_get_category_history(8, dt.date(2026, 11, 16))),
    ("ia/appliances", lambda client: client.async_get_activations()),
])
def test_analysis_unexpected_answer(api, route, read):
    """An unexpected answer is an error."""
    client = make_client(api, Session(**{route: Response(payload={"x": 1})}))
    run(client.async_get_data())
    with pytest.raises(api.LittleMonkeyApiClientError):
        run(read(client))


# --- Equipments


def equipment_client(api):
    """Return a client that read a gateway with equipments, and its session."""
    session = Session(gateways=Response(payload=GATEWAYS_WITH_EQUIPMENTS))
    client = make_client(api, session)
    run(client.async_get_data())
    return client, session


def test_equipments_are_read_with_the_gateways(api):
    """Every equipment of the gateway is described the same way."""
    client, _session = equipment_client(api)
    power_meter, sensor, heater = client.equipments
    assert power_meter["controls"] == [] and power_meter["state"]["mode"] is None
    assert sensor["name"] == "Sonde de température"
    assert sensor["battery"] == 80 and sensor["signal"] == 66
    assert sensor["controls"] == [] and sensor["measures"] is False
    assert heater == {
        "id": "630220", "type": "LULO", "model": "LULO", "name": "Chauffe-eau",
        "firmware": "1.01.11", "connected": True, "status": "Connecté",
        "signal": 29, "battery": None, "wifi_signal": 30,
        "controls": ["forced", "absence", "auto"], "measures": True, "switches": True,
        "state": {
            "power": 0, "on": False, "forced": True, "mode": "absence",
            "switch_state": "Mode absence jusqu'à 20:25",
            "since": "2026-11-18T20:20:44+01:00", "until": "2026-11-18T20:25:45+01:00",
            "source": "command", "voltage": 232.5, "max_power": 3131,
        },
    }
    # No identifier nor network name in the diagnostics
    text = json.dumps(client.diagnostics())
    assert "630220" not in text and "Box" not in text and '"LULO"' in text


@pytest.mark.parametrize(("state", "showable", "commands", "controls", "mode"), [
    # Forced on for a while, then back to automatic
    ({"onoff": 1, "forced": 1}, {}, ["on", "off", "on_forced", "off_forced"],
     ["forced", "absence", "auto"], "forced"),
    ({"onoff": 1, "forced": 0}, {}, ["on", "off", "on_forced", "off_forced"],
     ["forced", "absence", "auto"], "auto"),
    # Without a forced mode, ecojoko offers on and off
    ({"onoff": 1, "forced": 0}, {"switch_forced_mode": 0},
     ["on", "off", "on_forced", "off_forced"], ["on", "off"], "on"),
    # A plug of an unknown type is piloted by its commands
    ({"onoff": 0}, None, ["on", "off"], ["on", "off"], "off"),
    # Buttons hidden by ecojoko
    ({"onoff": 0}, {"show_switch_buttons": 0}, ["on", "off"], [], None),
])
def test_equipment_controls(api, state, showable, commands, controls, mode):
    """The controls come from the commands, as in the web application."""
    equipment = api.parse_equipment({
        "device_id": 9, "device_type": "SOMETHING_NEW", "device_state": state,
        "device_commands": commands, "device_showable_settings": showable})
    assert equipment["controls"] == controls
    assert equipment["state"]["mode"] == mode
    assert equipment["name"] == "SOMETHING_NEW"


def test_equipment_until_only_while_forced(api):
    """The end of the last forced mode, kept by ecojoko, is not shown."""
    equipment = api.parse_equipment({**WATER_HEATER, "device_state": {
        **WATER_HEATER["device_state"], "forced": 0, "switch_until": 1795030069000}})
    assert equipment["state"]["until"] is None
    assert equipment["state"]["mode"] == "auto"


def test_equipment_and_its_day(api):
    """A piloted equipment is read again, with its measures of the day."""
    client, session = equipment_client(api)
    equipment = run(client.async_get_equipment("630220"))
    assert session.requests[-1][1].endswith("/gateway/1/device/630220")
    assert equipment["state"]["mode"] == "absence"
    day = run(client.async_get_equipment_day(equipment, dt.date(2026, 11, 18)))
    urls = [request[1] for request in session.requests[-2:]]
    assert any(url.endswith("/device/630220/plugstat/d4/2026-11-18") for url in urls)
    assert any(url.endswith("/device/630220/switchstat/d/2026-11-18") for url in urls)
    assert day["energy"] == 0.97 and day["cost"] == 0.14
    assert day["power"][1] == {"time": "2026-11-18T00:04:00+01:00", "value": 2784}
    # The oldest first, the unreadable ones left out
    assert day["switches"] == [
        {"start": "2026-11-18T20:22:48+01:00", "end": "2026-11-18T20:27:48+01:00",
         "on": True, "forced": True, "source": "command"},
        {"start": "2026-11-18T20:27:48+01:00", "end": None,
         "on": False, "forced": False, "source": "timer"},
    ]


def test_equipment_day_without_measures(api):
    """An equipment without measures has an empty day, read from nowhere."""
    client, session = equipment_client(api)
    calls = len(session.calls)
    day = run(client.async_get_equipment_day(client.equipments[1], dt.date(2026, 11, 18)))
    assert len(session.calls) == calls
    assert day == {"date": "2026-11-18", "energy": None, "cost": None, "power": [],
                   "switches": []}


def test_unknown_equipment_is_refused(api):
    """Only the equipments of the gateway are read."""
    client, _session = equipment_client(api)
    with pytest.raises(api.LittleMonkeyApiClientError):
        run(client.async_get_equipment("12"))


def test_equipment_unexpected_answer(api):
    """An unexpected answer is an error of the client."""
    client, session = equipment_client(api)
    session.routes["plugstat"] = Response(payload={"nothing": 1})
    with pytest.raises(api.LittleMonkeyApiClientError):
        run(client.async_get_equipment_day(client.equipments[2], dt.date(2026, 11, 18)))
