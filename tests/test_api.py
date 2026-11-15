"""Tests of the ecojoko API client, with a fake HTTP session."""
from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import json
import logging
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
            **overrides,
        }
        self.calls = []
        self.requests = []

    def request(self, method, url, **kwargs):
        """Start a request."""
        name = next(key for key in self.routes if key in url)
        self.calls.append(name)
        self.requests.append((method, url, kwargs))
        return Request(self.routes[name])


def make_client(api, session, poll=5, hchp=False, tempo=False,
                temphum=False, prod=False):
    """Return an API client using the fake session."""
    return api.LittleMonkeyApiClient(
        username="user",
        password="secret",
        poll_interval=poll,
        use_hchp=hchp,
        use_tempo=tempo,
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
        "login", "gateways", "realtime_conso", "powerstat"
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
    """Tempo values are read by label and summed for HC/HP."""
    payload = powerstat(subconsumption=[
        {"label": "HC Bleu", "kwh": 1},
        {"label": "HP Bleu", "kwh": 2},
        {"label": "HC Blanc", "kwh": 3},
        {"label": "HP Rouge", "kwh": 4},
    ])
    session = Session(powerstat=Response(payload=payload))
    client = make_client(api, session, hchp=True, tempo=True)
    run(client.async_get_data())
    assert client.tempo_hc_blue == 1
    assert client.tempo_hp_blue == 2
    assert client.tempo_hc_white == 3
    assert client.tempo_hp_white is None
    assert client.tempo_hc_red is None
    assert client.tempo_hp_red == 4
    assert (client.kwh_hc_ns, client.kwh_hp_ns) == (4, 6)


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
    assert client.tempo_hc_blue is None
    assert client.kwh_hc_ns is None


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
        {"label": "HC Bleu", "kwh": 0.1},
        {"label": "HC Blanc", "kwh": 0.2},
        {"label": "HP Bleu", "kwh": 7.4399999999999995},
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
    assert client.tempo_hp_blue == 7.44
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
