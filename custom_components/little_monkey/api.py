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
    active_contract,
    bands_of,
    bands_of_offer,
    day_values,
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

        # Internal
        # Monotonic time the contract is due to be read again
        self._contract_due = None
        # Labels of the bands counted in neither HC nor HP, logged once
        self._unclassified_bands = set()
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
            "gateway_firmware_version": self._gateway_firmware_version,
            "seconds_since_stat_refresh": {
                name: None if last is None else round(now - last, 1)
                for name, last in self._last_stat_refresh.items()
            },
            "failing_apis": sorted(self._warned | self._failed_once),
            "contract": self._contract,
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

    async def _async_request(self, name, url, method="GET", timeout=None,
                             **kwargs):
        """Send a request to ecojoko.

        Return the JSON payload (None when the answer is not JSON) and the
        cookies of the response. The timeout (CONF_API_TIMEOUT by default)
        covers the whole exchange, body included, and the connection is
        always released.
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
                    if response.status >= 400:
                        raise LittleMonkeyApiClientCommunicationError(
                            f"API {name} returned HTTP {response.status}",
                        )
                    payload = None
                    content_type = response.headers.get("Content-Type", "")
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

    def _parse_powerstat(self, payload, day) -> None:
        """Update the energy properties from the powerstat response of a day."""
        week_day = day.weekday()
        stat = payload['stat']
        data = stat['data']
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
        values, totals, unclassified = day_values(
            data[week_day]['subconsumption'], self._configured_bands)
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

        value_json = gateways[0].get('devices')
        # Looking for humidity temperature and  power meter devices id
        for item in value_json:
            if item["device_type"] == "TEMP_HUM":
                self._temp_hum_id = item["device_id"]
            if item["device_type"] == "POWER_METER":
                self._power_meter_id = item["device_id"]
