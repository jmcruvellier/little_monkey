"""Tests of the ecojoko API client, with a fake HTTP session."""
from __future__ import annotations

import asyncio
import contextlib
import copy
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
# Solar settings of an installation selling its surplus, as ecojoko gives
# them (19/11/2026), without its list of brands and its measures
PRODUCER = {
    "install": {"date": "2025-09-16", "power": 6},
    "self_consumption": 1,
    "repurchase_price": 0.04,
    "is_producer": 1,
    "sell_solar_excess": 9,
    "sell_solar_excess_desc": "Oui (Édition bloquée)",
    "storage_battery": 0,
}

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
    "battery": {"level": 7, "value": "5.09V", "type": "4 piles LR14"},
    "signal": {"level": 4, "value": "66%", "type": "UNET"},
    "device_settings": {"name": "Sonde de température"},
}
GATEWAYS_WITH_EQUIPMENTS = {
    "gateways": [
        {
            "gateway_id": 1,
            "gateway_firmware_version": "9",
            "devices": [{"device_type": "POWER_METER", "device_id": 2,
                         "device_state": {"power_level": 24, "install_state": 5,
                                          "install_state_desc": "Bien placé"}},
                        TEMP_HUM_DEVICE,
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
        # A forced state has another value than "Allumé"
        {"duration": 300, "state_time": "2026-11-18 20:22:48",
         "switch_source": {"name": "Cloud", "val": 1},
         "switch_state": {"name": "Allumé (forcé)", "val": 3}},
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
            "producer": Response(payload={"is_producer": 0}),
            "activity": Response(payload=ACTIVITY),
            "savings/m": Response(payload=SAVINGS_SUMMARY),
            "savingstat": Response(payload=SAVINGSTAT_WEEK),
            "ia/conso": Response(payload=ANALYSIS_WEEK),
            "history": Response(payload=CATEGORY_HISTORY),
            "ia/appliances": Response(payload=ACTIVATIONS),
            "plugstat": Response(payload=PLUGSTAT),
            "switchstat": Response(payload=SWITCHSTAT),
            "_forced/": Response(payload={"error_id": 0, "error_desc": ""}),
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
    # The week before is read with the contract, for the prices of a kWh
    assert session.calls == [
        "login", "gateways", "realtime_conso", "powerstat", "suppliers", "powerstat",
        "producer",
    ]


def test_user_agent_is_sent(api):
    """Every request identifies the integration (1.2.8 fix)."""
    session = Session()
    run(make_client(api, session).async_get_data())
    for _method, _url, kwargs in session.requests:
        # Named as crawlers are: ecojoko returns only the last point of the
        # temperature and humidity to a User-Agent unlike a browser's
        assert kwargs["headers"]["User-Agent"].startswith("Mozilla/5.0 (compatible; little_monkey/")


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
        "producer": "GET",
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
    assert after["failing_apis"] == ["powerstat (w)", "powerstat (w-1)"]
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
        "Cookies", "Gateway", "realtime_conso", "powerstat (w)", "suppliers",
        "powerstat (w-1)", "producer"}
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


def test_diagnostics_count_the_requests_and_their_changes(api):
    """The requests of each API are counted, with the answers that changed."""
    readings = iter([512, 512, 640])
    session = Session(realtime_conso=lambda: Response(
        payload={"real_time": {"value": next(readings)}}))
    client = make_client(api, session)
    for _poll in range(3):
        run(client.async_get_data())

    async def read_by_service():
        # As the services do: counted apart from the polls
        token = api.REQUEST_SOURCE.set("service")
        try:
            await client.async_get_analysis("week")
        finally:
            api.REQUEST_SOURCE.reset(token)

    run(read_by_service())
    run(client.async_get_analysis("week"))
    requests = client.diagnostics()["requests"]
    assert requests["seconds_counted"] >= 0
    realtime = requests["apis"]["realtime_conso"]
    # The first answer has nothing to be compared with
    assert (realtime["poll"], realtime["service"]) == (3, 0)
    # The seconds between the 3 requests, from the second one on
    assert len(realtime["seconds_between_requests"]) == 2
    assert all(seconds >= 0 for seconds in realtime["seconds_between_requests"])
    assert requests["apis"]["Cookies"]["seconds_between_requests"] == []
    assert (realtime["unchanged"], realtime["changed"]) == (1, 1)
    assert realtime["seconds_since_change"] >= 0
    assert realtime["seconds_between_changes"] == []
    analysis = requests["apis"]["analysis"]
    assert (analysis["poll"], analysis["service"]) == (1, 1)
    assert (analysis["unchanged"], analysis["changed"]) == (1, 0)
    # Neither the URLs, which hold the device ids, nor the answers
    text = repr(requests)
    for secret in ("gw-1", "http", "512", "640"):
        assert secret not in text


def test_diagnostics_compare_the_values_of_powerstat_its_sensors_use(api):
    """A powerstat answer changed elsewhere than in its energies is told apart."""
    client = make_client(api, Session())
    stats = client._count_request("powerstat (w)")
    url = "https://ecojoko/powerstat/w"

    def answer(kwh, price, hc=1.234):
        return {"stat": {"period": {"price": price}, "data": [
            {"kwh": kwh, "kwh_prod": 0, "time": "2026-11-20",
             "subconsumption": [{"id": 3, "kwh": hc, "price": price}]}]}}

    for kwh, price, hc in [(4.2, 0.1, 1.234), (4.2, 0.2, 1.234), (4.2, 0.3, 1.231), (4.3, 0.3, 1.231)]:
        client._count_request("powerstat (w)")
        client._count_answer(stats, url, answer(kwh, price, hc))
    powerstat = client.diagnostics()["requests"]["apis"]["powerstat (w)"]
    # The whole answer changed each time, its energies only once: a change
    # of the band under the rounding of the sensors (1.234 -> 1.231) is not one
    assert (powerstat["changed"], powerstat["unchanged"]) == (3, 0)
    assert (powerstat["values"]["changed"], powerstat["values"]["unchanged"]) == (1, 2)
    assert powerstat["values"]["seconds_since_change"] >= 0
    # An answer that cannot be read is compared as such
    client._count_answer(stats, url, {"unexpected": True})
    assert client.diagnostics()["requests"]["apis"]["powerstat (w)"]["values"]["changed"] == 2
    # The other APIs have no values of their own
    assert "values" not in client.diagnostics()["requests"]["apis"].get("realtime_conso", {})


def test_diagnostics_keep_the_last_answers_of_a_bounded_number_of_urls(api):
    """Reading many days does not keep their answers without end."""
    client = make_client(api, Session())
    stats = client._count_request("powerstat (d4)")
    for day in range(api.REQUEST_URLS_KEPT + 50):
        client._count_answer(stats, f"https://ecojoko/day/{day}", {"day": day})
    assert len(client._answer_digests) == api.REQUEST_URLS_KEPT
    # The most recent URL is still compared with its last answer
    last = f"https://ecojoko/day/{api.REQUEST_URLS_KEPT + 49}"
    client._count_answer(stats, last, {"day": api.REQUEST_URLS_KEPT + 49})
    assert stats["unchanged"] == 1


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


def test_slow_statistic_does_not_hold_the_real_time(api, monkeypatch):
    """A statistic slower than the usual timeout is used by a later poll.

    With a short poll interval, ecojoko often takes more than the usual
    timeout to answer the statistics: they have a longer one, in the
    background, and the real-time consumption does not wait for them.
    """
    monkeypatch.setattr(api, "CONF_API_TIMEOUT", 0.05)
    session = Session(powerstat=Response(payload=powerstat(), delay=0.2))
    client = make_client(api, session)

    async def polls():
        loop = asyncio.get_running_loop()
        start = loop.time()
        await client.async_get_data()
        # The poll ends after the usual timeout, without the statistic
        assert loop.time() - start < 0.2
        assert client.realtime_conso == 512 and client.kwh is None
        await asyncio.sleep(0.3)
        await client.async_get_data()

    run(polls())
    # Its answer is used by the next poll, without asking for it again
    assert client.kwh == 4.2
    assert session.calls.count("powerstat") == 2  # the week, and the week before


def test_statistics_are_not_read_after_the_unload(api, monkeypatch):
    """The statistics read in the background stop with the entry."""
    monkeypatch.setattr(api, "CONF_API_TIMEOUT", 0.01)
    session = Session(powerstat=Response(payload=powerstat(), delay=5))
    client = make_client(api, session)

    async def poll_then_unload():
        await client.async_get_data()
        tasks = [task for task, _name, _day in client._stat_tasks.values()]
        assert tasks
        client.cancel_statistics()
        await asyncio.sleep(0)
        assert all(task.cancelled() for task in tasks)
        assert client._stat_tasks == {}

    run(poll_then_unload())


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
    # Called again after the usual delay only, not at each poll (the week
    # before is read with the contract)
    assert session.calls.count("powerstat") == 2
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
    # And once the week before, with the contract
    assert session.calls.count("powerstat") == 6
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


@pytest.mark.parametrize(("payload", "expected"), [
    (PRODUCER, 0.04),
    # Surplus not sold, or no solar panels
    ({**PRODUCER, "sell_solar_excess": 0}, None),
    ({**PRODUCER, "is_producer": 0}, None),
    ({"is_producer": 0}, None),
    ({**PRODUCER, "repurchase_price": "0.1109"}, 0.1109),
    ({**PRODUCER, "repurchase_price": 0}, None),
    ({**PRODUCER, "repurchase_price": None}, None),
])
def test_resale_price_of_the_solar_surplus(api, payload, expected):
    """The price of the surplus is known only when the surplus is sold."""
    assert api.parse_resale_price(payload) == expected


def test_resale_price_is_read_with_the_contract(api, monkeypatch):
    """The solar settings are read with the contract, every six hours."""
    clock = fake_clock(api, monkeypatch)
    session = Session(producer=Response(payload=PRODUCER))
    client = make_client(api, session)
    run(client.async_get_data())
    assert client.resale_price == 0.04
    poll_during(client, clock, 600)
    assert session.calls.count("producer") == 1


@pytest.mark.parametrize("answer", [
    Response(status=404, payload={"error_id": 301}),
    aiohttp.ClientError("boom"),
    Response(payload=["unexpected"]),
])
def test_solar_settings_failure_is_quiet(api, caplog, answer):
    """Without solar settings, nothing is logged as a warning."""
    client = make_client(api, Session(producer=answer))
    run(client.async_get_data())
    assert client.resale_price is None
    assert client.realtime_conso == 512
    assert not [record for record in caplog.records if record.levelname == "WARNING"]


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
            # The week before, read with the contract, is not a statistic of the poll
            called = [n for n in dict.fromkeys(session.calls[before:]) if n in times]
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
        assert max(gaps) <= api.CONF_API_STAT_REFRESH[name] + 2 * poll, name
        # And never before its delay, less the margin
        assert min(gaps) >= api.CONF_API_STAT_REFRESH[name] - api.CONF_API_STAT_MARGIN, name
    assert (client.indoor_temp, client.outdoor_temp) == (20, 8)
    assert (client.indoor_hum, client.outdoor_hum) == (50, 80)


def test_statistics_are_read_at_their_own_pace(api, monkeypatch):
    """Energies every minute, temperature and humidity every two minutes.

    With the default poll of 30 s, a statistic due at the next poll is read
    then, not one poll later.
    """
    _, times, _ = simulate(api, monkeypatch, 30, duration=1200)
    for name, delay in (("powerstat", 60), ("tempstat", 120), ("humstat", 120)):
        gaps = [later - earlier for earlier, later in zip(times[name], times[name][1:])]
        assert all(delay <= gap <= delay + 2 for gap in gaps), (name, gaps)


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
    assert client.tariff_weeks_missed == 0


def test_tariff_setup_counts_the_weeks_not_read(api, monkeypatch):
    """A week of statistics that fails is counted: the bands may be incomplete."""
    monkeypatch.setattr(api, "get_current_date", lambda timezone: dt.date(2026, 6, 14))
    suppliers = {"suppliers": [{"is_active": 1, "offer_type": "UNKNOWN TYPE"}]}
    session = Session(
        suppliers=Response(payload=suppliers),
        powerstat=Response(status=500),
    )
    client = make_client(api, session)
    run(client.async_get_cookiesdata())
    contract, bands = run(client.async_get_tariff_setup())
    assert contract["offer_type"] == "UNKNOWN TYPE"
    assert bands == {}
    assert client.tariff_weeks_missed == 4


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


def test_removed_bands_are_not_unknown(api):
    """The bands removed by the user are not reported while ecojoko gives them."""
    payload = powerstat(subconsumption=[
        {"id": 28, "label": "HC Hiver", "kwh": 6.67},
        {"id": 29, "label": "HP Hiver", "kwh": 5.63},
    ])
    client = api.LittleMonkeyApiClient(
        username="user", password="secret", poll_interval=5, use_hchp=True,
        bands=tariff_module(api).legacy_bands(True, False), removed_bands=[28],
        use_temphum=False, use_prod=False,
        session=Session(powerstat=Response(payload=payload)))
    run(client.async_get_data())
    assert client.unknown_bands == {29: "HP Hiver"}


@pytest.mark.parametrize(("key", "expected"), [
    ("band_28", True),
    ("blue_hc_grid_consumption", True),
    ("hc_grid_consumption", False),
    ("grid_consumption", False),
    ("band_count", False),
])
def test_keys_of_the_band_sensors(api, key, expected):
    """The sensors of the bands are told apart from the others."""
    assert tariff_module(api).is_band_key(key) is expected


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
    "savings": -0.35, "savings_kwh": -2.57, "cost": 1.8, "consumption": 7.58,
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


def test_savings_in_kwh_are_the_reference_minus_the_consumption(api, savings_day):
    """The kWh saved are the reference consumption minus the consumption.

    For a period, ecojoko gives the sum of the differences of its bars
    without their sign: observed on 19/11/2026 for a week of +12.94, -9.37
    and +4.22 kWh.
    """
    answer = json.loads(json.dumps(SAVINGSTAT_WEEK))
    answer["stat"]["period"].update(
        val=1.73, val_kwh=26.53, price=15.85, kwh=89.52, ref=17.58, ref_kwh=97.3)
    answer["stat"]["data"][0].update(
        val=-1.18, val_kwh=9.37, conso=7.08, conso_kwh=42.07, ref=5.9, ref_kwh=32.7)
    client = make_client(api, Session(savingstat=Response(payload=answer)))
    run(client.async_get_data())
    values = run(client.async_get_savings_period("week", SAVINGS_DAY))
    assert (values["savings"], values["savings_kwh"]) == (1.73, 7.78)
    assert values["bars"][0]["savings_kwh"] == -9.37


def test_saving_in_kwh_without_the_consumptions(api, savings_day):
    """Without both consumptions, ecojoko's kWh take the sign of the euros."""
    answer = json.loads(json.dumps(SAVINGSTAT_WEEK))
    del answer["stat"]["period"]["kwh"]
    answer["stat"]["data"][0].pop("ref_kwh")
    client = make_client(api, Session(savingstat=Response(payload=answer)))
    run(client.async_get_data())
    values = run(client.async_get_savings_period("week", SAVINGS_DAY))
    assert (values["savings"], values["savings_kwh"]) == (-0.35, -2.58)
    assert values["bars"][0]["savings_kwh"] == -2.58
    answer["stat"]["period"].update(val=25.85, val_kwh=67.62)
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


def test_battery_is_shown_as_in_the_ecojoko_application(api):
    """The level from 0 to 10 is a battery of five bars; 255 is the mains."""
    levels = {0: 0, 1: 20, 2: 20, 3: 40, 5: 60, 7: 80, 8: 80, 9: 100, 10: 100}
    assert {level: api.battery_percent(level) for level in levels} == levels
    assert api.battery_percent(255) is None
    assert api.battery_percent(None) is None
    assert api.battery_percent("") is None
    assert api.battery_percent(-1) is None


def test_battery_voltage_is_read_from_its_text(api):
    """The voltage of the batteries comes as "5.09V", empty on the mains."""
    assert api._voltage("5.09V") == 5.09
    assert api._voltage(" 3,1 v ") == 3.1
    assert api._voltage("") is None
    assert api._voltage("n/a") is None
    assert api._voltage(None) is None


def test_equipments_are_read_with_the_gateways(api):
    """Every equipment of the gateway is described the same way."""
    client, _session = equipment_client(api)
    power_meter, sensor, heater = client.equipments
    assert power_meter["controls"] == [] and power_meter["state"]["mode"] is None
    assert sensor["name"] == "Sonde de température"
    assert sensor["battery"] == 80 and sensor["signal"] == 66
    # The voltage of its batteries, and where the electricity sensor is placed
    assert sensor["battery_voltage"] == 5.09 and sensor["install_state"] is None
    assert power_meter["install_state"] == "Bien placé" and power_meter["battery_voltage"] is None
    # Its measures, the temperature in tenths of a degree
    assert sensor["state"]["temperature"] == 20.8 and sensor["state"]["humidity"] == 50
    assert sensor["controls"] == [] and sensor["measures"] is False
    assert heater == {
        "id": "630220", "type": "LULO", "model": "LULO", "name": "Chauffe-eau",
        "firmware": "1.01.11", "connected": True, "status": "Connecté",
        "signal": 29, "battery": None, "battery_voltage": None, "install_state": None,
        "wifi_signal": 30,
        "controls": ["forced", "absence", "auto"], "measures": True, "switches": True,
        "state": {
            "power": 0, "on": False, "forced": True, "mode": "absence",
            "switch_state": "Mode absence jusqu'à 20:25",
            "since": "2026-11-18T20:20:44+01:00", "until": "2026-11-18T20:25:45+01:00",
            "source": "command", "voltage": 232.5, "max_power": 3131,
            "temperature": None, "humidity": None,
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


def test_equipment_day_reads_only_the_parts_asked_for(api):
    """The power curve and the changes of state can be read apart."""
    client, session = equipment_client(api)
    equipment = run(client.async_get_equipment("630220"))
    before = len(session.requests)
    day = run(client.async_get_equipment_day(equipment, dt.date(2026, 11, 18), ("switches",)))
    urls = [request[1] for request in session.requests[before:]]
    assert len(urls) == 1 and urls[0].endswith("/device/630220/switchstat/d/2026-11-18")
    assert set(day) == {"date", "switches"}
    day = run(client.async_get_equipment_day(equipment, dt.date(2026, 11, 18), ("power",)))
    assert session.requests[-1][1].endswith("/device/630220/plugstat/d4/2026-11-18")
    assert set(day) == {"date", "energy", "cost", "power"}


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


@pytest.mark.parametrize(("mode", "seconds", "command"), [
    ("forced", 300, "on_forced/300"),
    ("forced", 14400, "on_forced/14400"),
    ("absence", 7 * 86400, "off_forced/604800"),
    # The "Automatique" button of ecojoko
    ("auto", None, "off_forced/1"),
    ("on", None, "on"),
    ("off", None, "off"),
])
def test_equipment_command(api, mode, seconds, command):
    """Each mode has its ecojoko command."""
    assert api.equipment_command(mode, seconds) == command


@pytest.mark.parametrize(("mode", "seconds"), [
    ("forced", None), ("forced", 59), ("forced", 24 * 3600 + 1), ("absence", 30), ("up", None)])
def test_equipment_command_out_of_range(api, mode, seconds):
    """A forced mode or an absence needs a duration that ecojoko accepts."""
    with pytest.raises(ValueError):
        api.equipment_command(mode, seconds)


def test_equipment_is_piloted(api):
    """A command is sent to the equipment, and its answer checked."""
    client, session = equipment_client(api)
    run(client.async_send_equipment_command("630220", "forced", 300))
    assert session.requests[-1][1].endswith("/gateway/1/device/630220/on_forced/300")
    run(client.async_send_equipment_command("630220", "auto"))
    assert session.requests[-1][1].endswith("/gateway/1/device/630220/off_forced/1")


def test_equipment_command_refused(api):
    """An error id of ecojoko is an error."""
    client, session = equipment_client(api)
    session.routes["_forced/"] = Response(payload={"error_id": 12, "error_desc": "Hors ligne"})
    with pytest.raises(api.LittleMonkeyApiClientError, match="Hors ligne"):
        run(client.async_send_equipment_command("630220", "forced", 3600))


def test_equipment_command_not_offered(api):
    """A mode ecojoko does not offer is not sent."""
    client, session = equipment_client(api)
    calls = len(session.calls)
    with pytest.raises(api.LittleMonkeyApiClientError):
        run(client.async_send_equipment_command("630220", "on"))
    with pytest.raises(api.LittleMonkeyApiClientError):
        run(client.async_send_equipment_command("3", "forced", 3600))
    assert len(session.calls) == calls


@pytest.mark.parametrize(("state", "on"), [
    ({"name": "Allumé", "val": 1}, True),
    ({"name": "Allumé (forcé)", "val": 3}, True),
    ({"name": "Eteint", "val": 0}, False),
    ({"name": "Éteint (forcé)", "val": 2}, False),
    # A name in another language: the value decides
    ({"name": "Acceso", "val": 1}, True),
    ({"name": "Spento", "val": 0}, False),
])
def test_equipment_switched_on(api, state, on):
    """Whether an equipment was on comes from the name of its state."""
    switches = api.parse_equipment_switches({"switch_state_logs": [
        {"duration": 60, "state_time": "2026-11-18 20:00:00", "switch_state": state}]})
    assert switches[0]["on"] is on


# --- Price of a kWh of each band

# Ten real days of an HP/HC contract (Gaz de Bordeaux, November 2026): the
# cost of a band includes a share of the subscription, about 0.43 € for HP
# and 0.22 € for HC a day
REAL_COSTS = {
    2: [(3.17, 1.00), (8.7, 2.00), (3.23, 1.01), (5.92, 1.5), (6.28, 1.56),
        (7.69, 1.81), (6.99, 1.69), (4.41, 1.23), (5.17, 1.36), (5.13, 1.35)],
    3: [(5, 0.91), (3, 0.63), (2.88, 0.61), (6.54, 1.12), (3.26, 0.67),
        (4.72, 0.87), (5.37, 0.96), (3.61, 0.72), (5.17, 0.93), (3.87, 0.75)],
}


def week_of_costs(start, costs):
    """Return a powerstat response whose days hold the costs of the bands."""
    paris = ZoneInfo("Europe/Paris")
    data = []
    for index in range(len(costs[2])):
        day = start + dt.timedelta(days=index)
        midnight = dt.datetime(day.year, day.month, day.day, tzinfo=paris)
        data.append({"time": int(midnight.timestamp() * 1000), "kwh": 0, "subconsumption": [
            {"id": band_id, "label": label, "kwh": values[index][0], "price": values[index][1]}
            for band_id, label, values in (
                (2, "Heures Pleines", costs[2]), (3, "Heures Creuses", costs[3]))]})
    return {"stat": {"data": data}}


def test_prices_are_estimated_from_the_costs(api):
    """The price of a kWh is the slope of the costs against the energies."""
    tariff = tariff_module(api)
    days = tariff.day_costs(week_of_costs(dt.date(2026, 11, 8), REAL_COSTS)["stat"])
    assert len(days) == 10
    assert tariff.estimate_prices(days) == {2: 0.18, 3: 0.139}


def test_prices_need_enough_different_days(api):
    """Two days, or days too alike, give no price."""
    tariff = tariff_module(api)
    two = tariff.day_costs(week_of_costs(
        dt.date(2026, 11, 8), {2: REAL_COSTS[2][:2], 3: REAL_COSTS[3][:2]})["stat"])
    assert tariff.estimate_prices(two) == {}
    alike = {f"2026-11-0{day}": {2: (5.0 + day / 100, 1.3)} for day in range(1, 6)}
    assert tariff.estimate_prices(alike) == {}


def test_exact_prices_by_id_or_label(api):
    """The prices of ecojoko are matched by id, or by label, as text or numbers."""
    tariff = tariff_module(api)
    labels = {2: "Heures Pleines", 3: "Heures Creuses"}
    assert tariff.exact_prices([
        {"label": "heures pleines ", "price": "0,2016"},
        {"id": 3, "label": "HC", "price": 0.1612},
        {"label": "Inconnue", "price": 0.3},
        {"label": "Heures Creuses", "price": "abc"},
    ], labels) == {2: 0.2016, 3: 0.1612}


def test_band_prices_of_the_client(api):
    """The client estimates the prices over two weeks, the exact ones win."""
    today = dt.datetime.now(ZoneInfo("Europe/Paris")).date()
    start = today - dt.timedelta(days=9)
    gateways = {"gateways": [{
        "gateway_id": 1, "gateway_firmware_version": "9",
        "devices": [{"device_type": "POWER_METER", "device_id": 2}],
    }]}
    session = Session(gateways=Response(payload=gateways),
                      powerstat=Response(payload=week_of_costs(start, REAL_COSTS)))
    client = make_client(api, session, hchp=True)
    run(client.async_get_data())
    assert client.band_prices == {
        2: {"price": 0.18, "exact": False, "source": "estimated"},
        3: {"price": 0.139, "exact": False, "source": "estimated"}}

    # With a water heater piloted by ecojoko, its prices
    gateways["gateways"][0]["devices"].append({
        "device_type": "LULO", "device_id": 9, "device_external_settings": {"pricing_data": {
            "prices": [{"label": "Heures Pleines", "price": 0.2016}]}}})
    run(client._gatewayapi_wrapper())
    assert client.band_prices == {
        2: {"price": 0.2016, "exact": True, "source": "ecojoko"},
        3: {"price": 0.139, "exact": False, "source": "estimated"}}

    # The prices entered by the user win, during their validity only
    client._contract_prices = {
        "prices": {"3": 0.134736}, "subscription": 31.14,
        "start": (today - dt.timedelta(days=1)).isoformat(), "end": today.isoformat()}
    assert client.band_prices[3] == {"price": 0.134736, "exact": True, "source": "entered"}
    assert client.band_prices[2]["source"] == "ecojoko"
    assert client.contract["subscription_price"] == 31.14
    client._contract_prices["end"] = (today - dt.timedelta(days=1)).isoformat()
    assert client.band_prices[3]["source"] == "estimated"
    assert client.entered_prices is None


def test_entered_prices_apply_during_their_validity(api):
    """Prices entered by the user apply from their start to their end, included."""
    entered_prices = tariff_module(api).entered_prices
    entered = {"prices": {"2": 0.180336, "3": "0,134736", "x": 1, "4": 0},
               "subscription": None, "start": "2026-08-25", "end": "2027-06-30"}
    assert entered_prices(entered, dt.date(2026, 8, 24)) is None
    assert entered_prices(entered, dt.date(2026, 8, 25)) == {
        "prices": {2: 0.180336, 3: 0.134736}, "subscription": None,
        "start": "2026-08-25", "end": "2027-06-30"}
    assert entered_prices(entered, dt.date(2027, 6, 30))["prices"][2] == 0.180336
    assert entered_prices(entered, dt.date(2027, 7, 1)) is None
    # Without dates, always; without any price, never
    assert entered_prices({"prices": {"2": 0.2}}, dt.date(2030, 1, 1))["prices"] == {2: 0.2}
    assert entered_prices({"prices": {}, "subscription": None}, dt.date(2026, 9, 1)) is None
    assert entered_prices({"subscription": 31.14}, dt.date(2026, 9, 1))["subscription"] == 31.14
    assert entered_prices(None, dt.date(2026, 9, 1)) is None


# --- Measures (page « Mesures »)

POWER_DAY = {"stat": {
    "period": {"this": 1794956400000, "prev": 1794870000000, "next": 1795042800000,
               "measure_unit": "W", "kwh": 15.3736, "price": 3.063763571, "kwh_prod": 0.6286,
               "price_prod": -0.02514},
    "pricing_details": [{"color": "#0087B1", "id": 2, "label": "Heures Pleines"},
                        {"color": "#6BBED8", "id": 3, "label": "Heures Creuses"}],
    "data": [{"time": 1794956400000, "consobase": 6, "value": 299, "price": 0.00057,
              "is_hchp": 1, "pricing": 3}],
}}
ENERGY_WEEK = {"stat": {
    "period": {"this": 1794783600000, "prev": 1794178800000, "measure_unit": "EUR",
               "price": 16.3, "kwh": 95.32, "kwh_prod": 1.35, "price_prod": -0.05},
    "pricing_details": [{"id": 2, "label": "Heures Pleines", "color": "#0087B1", "enable_filter": 1}],
    "data": [{"time": 1794783600000, "value": 3.47, "consobase_kwh": 11.69, "kwh": 30.88,
              "kwh_prod": -0.02, "value_prod": -0.01, "subconsumption": [
                  {"id": 2, "kwh": 16.4, "price": 3.3, "label": "Heures Pleines"},
                  {"id": 3, "kwh": 14.47, "price": 2.24, "label": "Heures Creuses"}]},
             {"time": 1795302000000, "value": 0, "kwh": 0, "consobase_kwh": 0, "kwh_prod": 0}],
}}
TEMPERATURE_DAY = {"stat": {
    "period": {"this": 1794956400000, "prev": 1794870000000, "next": 1795042800000,
               "measure_unit": "°C"},
    "data": [{"time": 1794956400000, "value": 23.8, "ext_value": 10.66}],
}}


def test_power_of_a_day(api):
    """The power of a day, every few minutes, with the band of its time."""
    session = Session()
    client = make_client(api, session)
    run(client.async_get_data())
    session.routes["powerstat"] = Response(payload=POWER_DAY)
    day = run(client.async_get_measures("electricity", "day", dt.date(2026, 11, 18)))
    assert session.requests[-1][1].endswith("/device/2/powerstat/d4/2026-11-18")
    assert day["start"] == "2026-11-18T00:00:00+01:00"
    assert day["previous"] == "2026-11-17T00:00:00+01:00"
    assert day["energy"] == 15.37 and day["cost"] == 3.06 and day["production"] == 0.63
    assert day["resale"] == 0.03
    assert day["bands"][0] == {"id": 2, "label": "Heures Pleines", "color": "#0087B1"}
    assert day["points"] == [
        {"time": "2026-11-18T00:00:00+01:00", "power": 299, "base": 6, "band": 3}]


def test_energy_of_a_week_by_band(api):
    """The days of a week, each with its bands, base load and production."""
    session = Session()
    client = make_client(api, session)
    run(client.async_get_data())
    session.routes["powerstat"] = Response(payload=ENERGY_WEEK)
    week = run(client.async_get_measures("electricity", "week", dt.date(2026, 11, 18)))
    assert session.requests[-1][1].endswith("/powerstat/w/2026-11-18")
    assert week["next"] is None and week["previous"] == "2026-11-09T00:00:00+01:00"
    assert week["bars"][0] == {
        "date": "2026-11-16", "energy": 30.88, "cost": 5.54, "base_energy": 11.69,
        "production": 0.02, "resale": 0.01, "bands": [
            {"id": 2, "energy": 16.4, "cost": 3.3}, {"id": 3, "energy": 14.47, "cost": 2.24}]}
    # The amount of the surplus sold, positive
    assert week["resale"] == 0.05
    # A day to come has no bands
    assert week["bars"][1]["bands"] == [] and week["bars"][1]["energy"] == 0
    run(client.async_get_measures("electricity", "month", dt.date(2026, 11, 18)))
    assert session.requests[-1][1].endswith("/powerstat/m6/2026-11-18")
    run(client.async_get_measures("electricity", "year", dt.date(2026, 11, 18)))
    assert session.requests[-1][1].endswith("/powerstat/y/2026-11-18")


def test_week_of_today_is_asked_at_another_day(api):
    """The week of today is asked at another day of the same week.

    ecojoko answers it at the date of today, which the polls read, without
    its period.
    """
    session = Session()
    client = make_client(api, session)
    run(client.async_get_data())
    session.routes["powerstat"] = Response(payload=ENERGY_WEEK)
    today = dt.datetime.now(ZoneInfo("Europe/Paris")).date()
    run(client.async_get_measures("electricity", "week", today))
    asked = dt.date.fromisoformat(session.requests[-1][1].rsplit("/", 1)[1])
    assert asked != today
    assert asked.isocalendar()[:2] == today.isocalendar()[:2]
    # The day and the month of today are asked at their date
    run(client.async_get_measures("electricity", "day", today))
    assert session.requests[-1][1].endswith(f"/powerstat/d4/{today.isoformat()}")


def test_cost_of_a_bar_includes_the_base_load(api):
    """The cost of a day is that of its bands, base load included.

    ecojoko gives in « value » the cost without the base load: on 19/11/2026
    1.08 €, with 0.04 € of base load, where its page shows 1.12 €.
    """
    bars = api.parse_energy_bars({"stat": {"data": [
        {"time": 1795042800000, "value": 1.08, "consobase": 0.04458, "kwh": 3.91,
         "subconsumption": [{"id": 2, "kwh": 1.67, "price": 0.65},
                            {"id": 3, "kwh": 2.25, "price": 0.47}]},
        # Without the bands, its cost and that of the base load
        {"time": 1795129200000, "value": 1.08, "consobase": 0.04458, "kwh": 3.91},
        {"time": 1795215600000, "value": 0, "kwh": 0},
    ]}})["bars"]
    assert [bar["cost"] for bar in bars] == [1.12, 1.12, 0]


def test_measures_without_their_period(api):
    """Measures that ecojoko gives without their period are read all the same.

    On 19/11/2026 the week under way came without it. The dates of the
    period are left out, not given as empty: the card would take an empty
    previous period for the first one.
    """
    session = Session()
    client = make_client(api, session)
    run(client.async_get_data())
    week = copy.deepcopy(ENERGY_WEEK)
    del week["stat"]["period"]
    session.routes["powerstat"] = Response(payload=week)
    measures = run(client.async_get_measures("electricity", "week", dt.date(2026, 11, 19)))
    assert not {"start", "previous", "next"} & measures.keys()
    assert measures["bars"][0]["energy"] == 30.88 and len(measures["bars"]) == 2
    # The totals of the week are those of its days
    assert measures["energy"] == 30.88 and measures["cost"] == 5.54
    assert measures["production"] == 0.02
    assert measures["resale"] == 0.01

    day = copy.deepcopy(POWER_DAY)
    del day["stat"]["period"]
    session.routes["powerstat"] = Response(payload=day)
    measures = run(client.async_get_measures("electricity", "day", dt.date(2026, 11, 19)))
    assert "previous" not in measures and measures["energy"] is None
    assert measures["points"][0]["power"] == 299


def test_temperature_and_humidity(api):
    """Inside and outside, read from the temperature and humidity sensor."""
    session = Session(tempstat=Response(payload=TEMPERATURE_DAY))
    client = make_client(api, session)
    run(client.async_get_data())
    day = run(client.async_get_measures("temperature", "day", dt.date(2026, 11, 18)))
    assert session.requests[-1][1].endswith("/device/3/tempstat/d4/2026-11-18")
    assert day["unit"] == "°C"
    assert day["points"] == [
        {"time": "2026-11-18T00:00:00+01:00", "inside": 23.8, "outside": 10.66}]
    run(client.async_get_measures("humidity", "week", dt.date(2026, 11, 18)))
    assert session.requests[-1][1].endswith("/device/3/humstat/w/2026-11-18")
    # The month of the sensor is the calendar month
    run(client.async_get_measures("humidity", "month", dt.date(2026, 11, 18)))
    assert session.requests[-1][1].endswith("/device/3/humstat/m/2026-11-18")


def test_climate_measures_need_the_sensor(api):
    """Without a temperature and humidity sensor, nothing is read."""
    session = Session(gateways=Response(payload=GATEWAYS_WITHOUT_TEMP_HUM))
    client = make_client(api, session)
    run(client.async_get_data())
    with pytest.raises(api.LittleMonkeyApiClientError):
        run(client.async_get_measures("humidity", "day", dt.date(2026, 11, 18)))


# --- Cache of the answers of the services


def test_service_answer_is_kept_for_its_time(api, monkeypatch):
    """The same data asked again within its time is not read again."""
    clock = {"now": 1000.0}
    monkeypatch.setattr(api, "time", types.SimpleNamespace(monotonic=lambda: clock["now"]))
    client = make_client(api, Session())
    reads = []

    async def read():
        reads.append(clock["now"])
        return {"bars": [1, 2]}

    async def scenario():
        first = await client.async_cached(("savings", "week"), 240, read)
        # Each caller gets its own copy: a change does not reach the cache
        first["bars"].append(3)
        clock["now"] += 239
        second = await client.async_cached(("savings", "week"), 240, read)
        # Another key is read apart
        await client.async_cached(("savings", "month"), 240, read)
        clock["now"] += 1
        third = await client.async_cached(("savings", "week"), 240, read)
        return second, third

    second, third = run(scenario())
    assert second == third == {"bars": [1, 2]}
    assert reads == [1000.0, 1239.0, 1240.0]
    cache = client.diagnostics()["service_cache"]
    assert cache == {"entries": 2, "hits": 1, "misses": 3}


def test_same_requests_at_the_same_time_share_one_reading(api):
    """Two cards asking for the same data at once make a single request."""
    client = make_client(api, Session())
    reads = []

    async def read():
        reads.append(1)
        await asyncio.sleep(0.01)
        return {"activations": []}

    async def scenario():
        return await asyncio.gather(*(
            client.async_cached(("activations", 0), 1800, read) for _ in range(3)))

    answers = run(scenario())
    assert answers == [{"activations": []}] * 3
    assert len(reads) == 1


def test_a_failed_reading_is_not_kept(api):
    """After a failure, the next request reads ecojoko again."""
    client = make_client(api, Session())
    answers = iter([api.LittleMonkeyApiClientCommunicationError("timeout"), {"ok": True}])

    async def read():
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    async def scenario():
        with pytest.raises(api.LittleMonkeyApiClientCommunicationError):
            await client.async_cached(("analysis", "week", None), 3600, read)
        return await client.async_cached(("analysis", "week", None), 3600, read)

    assert run(scenario()) == {"ok": True}


def test_the_cache_keeps_a_bounded_number_of_answers(api, monkeypatch):
    """The least recently used answers leave the cache first."""
    monkeypatch.setattr(api, "SERVICE_CACHE_SIZE", 3)
    client = make_client(api, Session())

    async def scenario():
        for day in range(4):
            await client.async_cached(("measures", day), 240, lambda day=day: asyncio.sleep(0, day))

    run(scenario())
    assert list(client._service_cache) == [("measures", 1), ("measures", 2), ("measures", 3)]


# --- Costs at the prices entered by the user


def test_gap_of_a_cost_at_the_prices_entered(api):
    """Only the price of the kWh changes; the subscription by its own gap."""
    tariff = tariff_module(api)
    assert tariff.price_gap({2: 10, 3: 4, 9: 1}, {2: 0.2, 3: 0.15}, {2: 0.18, 3: 0.135}) == \
        pytest.approx(10 * -0.02 + 4 * -0.015)
    assert tariff.price_gap({2: 10}, {}, {2: 0.18}) is None
    assert tariff.subscription_gap(31.14, 30.49, 365) == pytest.approx(0.65 * 12)
    assert tariff.subscription_gap(None, 30.49, 30) == 0
    # A point holds its power until the next one, the last one the usual interval
    points = [
        {"time": "2026-11-18T00:00:00+01:00", "power": 1000, "band": 3},
        {"time": "2026-11-18T00:30:00+01:00", "power": 2000, "band": 3},
        {"time": "2026-11-18T01:00:00+01:00", "power": 4000, "band": 2},
        {"time": "2026-11-18T01:30:00+01:00", "power": None, "band": 2},
    ]
    assert tariff.energies_of_points(points) == {3: 1.5, 2: 2.0}


def entered_client(api, start="2026-11-01", end="2026-11-30", subscription=None):
    """Return a client with prices entered, and ecojoko's prices known."""
    client = make_client(api, Session())
    client._contract_prices = {"prices": {"2": 0.18, "3": 0.135}, "subscription": subscription,
                               "start": start, "end": end}
    client._ecojoko_prices = lambda: ({2: 0.2}, {3: 0.15})
    client._contract = {"subscription_price": 30.49}
    return client


def test_measures_at_the_prices_entered(api):
    """The days and months the prices apply cost the prices entered."""
    client = entered_client(api)
    week = {"cost": 10.0, "bars": [
        {"date": "2026-10-31", "cost": 5.0, "bands": [{"id": 2, "energy": 10, "cost": 5.0}]},
        {"date": "2026-11-01", "cost": 5.0, "bands": [
            {"id": 2, "energy": 10, "cost": 3.0}, {"id": 3, "energy": 10, "cost": 2.0}]},
    ]}
    measures = client.correct_measures(week, "week", dt.date(2026, 11, 1))
    # Before the prices: ecojoko's; after: 10 kWh at -0.02 and 10 at -0.015
    assert measures["bars"][0]["cost"] == 5.0
    assert measures["bars"][1]["cost"] == 4.65
    assert [band["cost"] for band in measures["bars"][1]["bands"]] == [2.8, 1.85]
    assert measures["cost"] == 9.65
    assert measures["entered_prices"] is True

    # A month counts only when the prices apply to all of it
    year = {"cost": 20.0, "bars": [
        {"date": "2026-10-01", "cost": 10.0, "bands": [{"id": 2, "energy": 50, "cost": 10.0}]},
        {"date": "2026-11-01", "cost": 10.0, "bands": [{"id": 2, "energy": 50, "cost": 10.0}]},
    ]}
    measures = client.correct_measures(year, "year", dt.date(2026, 11, 1))
    assert [bar["cost"] for bar in measures["bars"]] == [10.0, 9.0]

    # A day of power: the energy of each band from its points
    day = {"cost": 1.0, "points": [
        {"time": "2026-11-18T00:00:00+01:00", "power": 2000, "band": 2},
        {"time": "2026-11-18T01:00:00+01:00", "power": 2000, "band": 2},
    ]}
    assert client.correct_measures(day, "day", dt.date(2026, 11, 18))["cost"] == 0.92
    # Without prices entered, nothing changes
    plain = make_client(api, Session())
    assert plain.correct_measures({"cost": 1.0, "bars": []}, "week", dt.date(2026, 11, 1)) == {
        "cost": 1.0, "bars": []}


def test_subscription_entered_in_the_costs(api):
    """The subscription entered changes the cost of each day by its gap."""
    client = entered_client(api, subscription=31.14)
    gap = client.cost_gap(dt.date(2026, 11, 2), dt.date(2026, 11, 2), {})
    assert gap == pytest.approx(0.65 * 12 / 365)


def test_cost_of_7_days_and_of_an_equipment_at_the_prices_entered(api):
    """The last 7 days and the equipments cost the prices entered."""
    today = dt.datetime.now(ZoneInfo("Europe/Paris")).date()
    client = entered_client(api, start=None, end=None)
    client._day_costs = {
        (today - dt.timedelta(days=offset)).isoformat(): {2: (10, 2.0), 3: (10, 1.5)}
        for offset in range(8)}
    assert client.cost_gap(today, today, {2: 10, 3: 10}) == pytest.approx(-0.35)
    # An equipment: its share of the cost of the house this day
    assert client.correct_day_cost(today, 0.35, 2.0) == round(0.35 * 3.15 / 3.5, 2)
    assert client.correct_day_cost(today, None, 2.0) is None

    session = Session(activity=Response(payload=ACTIVITY))
    client._session = session
    client._cookies = {"session": "abc"}
    plain = parse_activity_cost(api)
    activity = run(client.async_get_activity())
    assert activity["cost_7_days"] == round(plain - 7 * 0.35, 2)


def parse_activity_cost(api):
    """Return ecojoko's cost of the last 7 days of the activity of the tests."""
    return api.parse_activity(ACTIVITY)["cost_7_days"]


def test_savings_at_the_prices_entered(api):
    """The cost of each bar at the prices entered, its reference at the average price."""
    client = entered_client(api)
    savings = {"cost": 7.0, "reference_cost": 8.0, "savings": 1.0, "bars": [
        {"date": "2026-10-31", "cost": 3.0, "consumption": 15, "reference_cost": 4.0,
         "reference_consumption": 20, "savings": 1.0},
        {"date": "2026-11-01", "cost": 4.0, "consumption": 20, "reference_cost": 4.0,
         "reference_consumption": 30, "savings": 0.0},
    ]}
    energies = {dt.date(2026, 10, 31): {2: 15}, dt.date(2026, 11, 1): {2: 10, 3: 10}}
    corrected = client.correct_savings(savings, "week", energies)
    # Before the prices: ecojoko's; after: -0.35 € for 20 kWh, -0.525 € for the 30 of reference
    assert corrected["bars"][0] == savings["bars"][0]
    bar = corrected["bars"][1]
    assert (bar["cost"], bar["reference_cost"], bar["savings"]) == (3.65, 3.47, -0.18)
    assert (corrected["cost"], corrected["reference_cost"], corrected["savings"]) == (6.65, 7.47, 0.82)
    assert corrected["entered_prices"] is True


def test_analysis_at_the_prices_entered(api):
    """Each category of the analysis changes as the cost of the whole period."""
    client = entered_client(api)

    async def energies(_period, _day):
        return {dt.date(2026, 11, 2 + offset): {2: 10} for offset in range(7)}

    client._async_period_energies = energies
    analysis = {"available": True, "start": "2026-11-02", "cost": 14.0, "categories": [
        {"cost": 7.0, "children": [{"cost": 3.5}]}, {"cost": 7.0, "children": []}]}
    corrected = run(client._async_correct_analysis(analysis, "week"))
    # 70 kWh at -0.02 €: -1.4 € over 14 €, -10 %
    assert corrected["cost"] == 12.6
    assert [category["cost"] for category in corrected["categories"]] == [6.3, 6.3]
    assert corrected["categories"][0]["children"][0]["cost"] == 3.15
    unavailable = {"available": False, "start": "2026-11-02"}
    assert run(client._async_correct_analysis(unavailable, "week")) == unavailable


def test_savings_of_12_months_at_the_prices_entered(api):
    """Month by month, the months the prices cover."""
    today = dt.datetime.now(ZoneInfo("Europe/Paris")).date()
    client = entered_client(api, start=None, end=None)

    async def energies(_period, _day):
        month = today.replace(day=1)
        return {month: {2: 100}}

    client._async_period_energies = energies
    summary = {"consumption_cost_12_months": 400.0, "reference_cost_12_months": 500.0,
               "savings_12_months": 100.0, "consumption_12_months": 2000,
               "reference_consumption_12_months": 3000}
    run(client._async_correct_summary(summary, today))
    # 100 kWh at -0.02 €; the reference at the same average price
    assert summary["consumption_cost_12_months"] == 398.0
    assert summary["reference_cost_12_months"] == 497.0
    assert summary["savings_12_months"] == 99.0


# --- Reference of the savings: the same period of last year


def last_year_client(api):
    """Return a client comparing with last year, at ecojoko's prices."""
    client = make_client(api, Session())
    client._reference = "last_year"
    client._ecojoko_prices = lambda: ({2: 0.2}, {3: 0.15})
    return client


def test_reference_of_last_year_at_the_prices_of_today(api):
    """The energy of last year at today's prices, the rest of the cost kept."""
    client = last_year_client(api)
    # 10 kWh consumed (2.5 € of energy) cost 3 €: 0.5 € of subscription kept
    kwh, cost = client._last_year_values(3.0, {2: 5, 3: 5}, {2: 10, 3: 10}, dt.date(2026, 11, 2))
    assert (kwh, cost) == (20, pytest.approx(3.0 + 3.5 - 1.75))
    assert client._last_year_values(3.0, {2: 5}, {}, dt.date(2026, 11, 2)) is None


def test_savings_against_the_same_week_of_last_year(api):
    """Each day against the same day of the week 52 weeks before."""
    client = last_year_client(api)
    year = dt.timedelta(weeks=52)

    async def day_energies(first, last):
        # Nothing the year before for the first day
        return {dt.date(2026, 11, 3) - year: {2: 10}}

    client._async_day_energies = day_energies
    savings = {"cost": 4.0, "consumption": 16, "reference_cost": 5.0,
               "reference_consumption": 25, "savings": 1.0, "savings_kwh": 9, "bars": [
                   {"date": "2026-11-02", "cost": 2.0, "consumption": 8, "reference_cost": 2.5,
                    "reference_consumption": 12.5, "savings": 0.5, "savings_kwh": 4.5},
                   {"date": "2026-11-03", "cost": 2.0, "consumption": 8, "reference_cost": 2.5,
                    "reference_consumption": 12.5, "savings": 0.5, "savings_kwh": 4.5},
                   {"date": "2026-11-04", "cost": None}]}
    energies = {dt.date(2026, 11, 2): {2: 8}, dt.date(2026, 11, 3): {2: 8}}
    result = run(client._async_last_year_savings(savings, "week", dt.date(2026, 11, 2), energies))
    assert result["bars"][0]["reference_cost"] == 2.5
    bar = result["bars"][1]
    # 10 kWh last year at 0.2 €, 8 kWh this year: +0.4 € of reference
    assert (bar["reference_consumption"], bar["reference_cost"]) == (10, 2.4)
    assert (bar["savings"], bar["savings_kwh"]) == (0.4, 2)
    assert (result["reference_consumption"], result["reference_cost"]) == (22.5, 4.9)
    assert (result["savings"], result["savings_kwh"]) == (0.9, 6.5)
    assert result["reference_source"] == "mixed"


def test_savings_of_12_months_and_of_7_days_against_last_year(api):
    """The 12 months before, and the same 7 days 52 weeks before."""
    today = dt.datetime.now(ZoneInfo("Europe/Paris")).date()
    client = last_year_client(api)

    async def period_energies(_period, day):
        months = {}
        month = dt.date(day.year, 1, 1)
        while month.year == day.year:
            months[month] = {2: 100 if day.year == today.year else 150}
            month = (month + dt.timedelta(days=32)).replace(day=1)
        return months

    async def day_energies(first, last):
        return {first + dt.timedelta(days=offset): {2: 3} for offset in range(7)}

    client._async_period_energies = period_energies
    client._async_day_energies = day_energies
    summary = {"consumption_cost_12_months": 300.0, "reference_cost_12_months": 400.0,
               "savings_12_months": 100.0, "consumption_12_months": 1200,
               "reference_consumption_12_months": 2000, "savings_kwh_12_months": 800}
    run(client._async_last_year_summary(summary, today))
    assert summary["reference_source"] == "last_year"
    consumed = sum(100 if today.month >= offset + 1 else 150 for offset in range(12))
    reference = 150 * (12 - today.month) + 150 * today.month if today.year else 0
    assert summary["reference_consumption_12_months"] == reference
    assert summary["reference_cost_12_months"] == pytest.approx(
        300.0 + 0.2 * reference - 0.2 * consumed, abs=0.01)

    activity = {"consumption_7_days": 42, "reference_consumption_7_days": 30, "savings_7_days": 40}
    run(client._async_last_year_activity(activity, today))
    # 21 kWh the same days of last year: 100 % more
    assert activity == {"consumption_7_days": 42, "reference_consumption_7_days": 21,
                        "savings_7_days": 100}
