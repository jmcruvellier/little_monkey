"""API Client for little_monkey."""
from __future__ import annotations

import asyncio
import json
import math
import socket
import time
import aiohttp
from .const import (
    CONF_API_TIMEOUT,
    CONF_API_STAT_REFRESH,
    ECOJOKO_LOGIN_URL,
    ECOJOKO_GATEWAYS_URL,
    ECOJOKO_GATEWAY_URL,
    LOGGER,
    VERSION
)
from .utils import (
    get_current_date,
    get_paris_timezone,
    get_value_from_json_array,
    convert_to_float)

TZ = get_paris_timezone()

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


class LittleMonkeyApiClient:
    """API Client to retrieve ecojoko data."""

    def __init__(
        self,
        username: str,
        password: str,
        poll_interval: int,
        use_hchp: bool,
        use_tempo: bool,
        use_temphum: bool,
        use_prod: bool,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize."""
        self._username = username
        self._password = password
        self._poll_interval = poll_interval
        self._use_hchp = use_hchp
        self._use_tempo = use_tempo
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
        self._kwh = None
        self._kwh_hc_ns = None
        self._kwh_hp_ns = None
        self._tempo_hc_blue = None
        self._tempo_hp_blue = None
        self._tempo_hc_white = None
        self._tempo_hp_white = None
        self._tempo_hc_red = None
        self._tempo_hp_red = None
        self._kwh_prod = None
        self._indoor_temp = None
        self._outdoor_temp = None
        self._indoor_hum = None
        self._outdoor_hum = None

        # Internal
        # Monotonic time of the last call of each statistics API
        self._last_stat_refresh = {
            "powerstat": None,
            "tempstat": None,
            "humstat": None,
        }
        # APIs whose failure has already been logged as a warning
        self._warned = set()
        # Day (in Paris) the energy properties belong to
        self._stat_date = None

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
    def tempo_hc_blue(self) -> float | None:
        """Return the Blue HC consumption."""
        return self._tempo_hc_blue

    @property
    def tempo_hp_blue(self) -> float | None:
        """Return the Blue HP consumption."""
        return self._tempo_hp_blue

    @property
    def tempo_hc_white(self) -> float | None:
        """Return the White HC consumption."""
        return self._tempo_hc_white

    @property
    def tempo_hp_white(self) -> float | None:
        """Return the White HP consumption."""
        return self._tempo_hp_white

    @property
    def tempo_hc_red(self) -> float | None:
        """Return the Red HC consumption."""
        return self._tempo_hc_red

    @property
    def tempo_hp_red(self) -> float | None:
        """Return the Red HP consumption."""
        return self._tempo_hp_red

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
            "gateway_found": self._gateway_id is not None,
            "power_meter_found": self._power_meter_id is not None,
            "temp_hum_found": self._temp_hum_id is not None,
            "gateway_firmware_version": self._gateway_firmware_version,
            "seconds_since_stat_refresh": {
                name: None if last is None else round(now - last, 1)
                for name, last in self._last_stat_refresh.items()
            },
            "failing_apis": sorted(self._warned),
        }

    async def async_get_cookiesdata(self) -> None:
        """Perform login and return cookies."""
        login_data = {
            "l": f"{self._username}",
            "p": f"{self._password}"
        }
        try:
            payload_json = json.dumps(login_data)
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

    async def fetch_data(self, api):
        """Retrieve data from a given URL using aiohttp.

        Return None when the API is not called or does not answer with JSON.
        """
        if api['call'] is not True:
            return None
        payload, _cookies = await self._async_get(
            api['name'], api['url'], cookies=self._cookies)
        return payload

    async def _async_get(self, name, url, **kwargs):
        """Send a GET request to ecojoko.

        Return the JSON payload (None when the answer is not JSON) and the
        cookies of the response. The timeout covers the whole exchange,
        body included, and the connection is always released.
        """
        try:
            async with asyncio.timeout(CONF_API_TIMEOUT):
                async with self._session.get(
                    url=url,
                    headers=self._headers,
                    **kwargs,
                ) as response:
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
        """Log an API failure as a warning once, then as debug until it recovers."""
        if name in self._warned:
            LOGGER.debug("API %s still failing: %r", name, error)
            return
        self._warned.add(name)
        LOGGER.warning(
            "API %s failed, its sensors keep their last value "
            "(logged once until it recovers): %r", name, error)

    def _clear_warning(self, name) -> None:
        """Log that an API works again."""
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
            self._realtime_conso = results[0]['real_time']['value']
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
                last = results[2]['stat']['data'][-1]
                self._indoor_temp = last['value']
                self._outdoor_temp = last['ext_value']
            except PARSE_ERRORS as exception:
                self._warn_once(apis[2]['name'], exception)
            else:
                self._clear_warning(apis[2]['name'])
        # Humidity
        if results[3] is not None:
            try:
                # 101 bug fix
                last = results[3]['stat']['data'][-1]
                self._indoor_hum = last['value']
                self._outdoor_hum = last['ext_value']
            except PARSE_ERRORS as exception:
                self._warn_once(apis[3]['name'], exception)
            else:
                self._clear_warning(apis[3]['name'])

    def _parse_powerstat(self, payload, day) -> None:
        """Update the energy properties from the powerstat response of a day."""
        week_day = day.weekday()
        data = payload['stat']['data']
        kwh = data[week_day]['kwh']
        if day != self._stat_date:
            # New day: a value of the previous day must not be taken for a
            # value of this one when the response does not give it yet
            self._kwh_prod = None
            self._kwh_hc_ns = None
            self._kwh_hp_ns = None
            self._tempo_hc_blue = None
            self._tempo_hp_blue = None
            self._tempo_hc_white = None
            self._tempo_hp_white = None
            self._tempo_hc_red = None
            self._tempo_hp_red = None
        self._kwh = kwh
        self._stat_date = day
        # Surplus Production
        # 78 bug fix
        if self._use_prod is True and 'kwh_prod' in data[week_day]:
            if float(data[week_day]['kwh_prod']) != 0:
                self._kwh_prod = abs(float(data[week_day]['kwh_prod']))
            else:
                self._kwh_prod = 0
        # Tempo option
        # 78 bug fix
        if self._use_tempo is True and 'subconsumption' in data[week_day]:
            self._tempo_hc_blue = get_value_from_json_array(
                data[week_day]['subconsumption'],
                "label",
                "HC Bleu",
                "kwh")
            self._tempo_hp_blue = get_value_from_json_array(
                data[week_day]['subconsumption'],
                "label",
                "HP Bleu",
                "kwh")
            self._tempo_hc_white = get_value_from_json_array(
                data[week_day]['subconsumption'],
                "label",
                "HC Blanc",
                "kwh")
            self._tempo_hp_white = get_value_from_json_array(
                data[week_day]['subconsumption'],
                "label",
                "HP Blanc",
                "kwh")
            self._tempo_hc_red = get_value_from_json_array(
                data[week_day]['subconsumption'],
                "label",
                "HC Rouge",
                "kwh")
            self._tempo_hp_red = get_value_from_json_array(
                data[week_day]['subconsumption'],
                "label",
                "HP Rouge",
                "kwh")
        # HC/HP option
        if self._use_tempo is True and self._use_hchp is True:
            self._kwh_hc_ns = convert_to_float(self._tempo_hc_blue) + convert_to_float(
                self._tempo_hc_white) + convert_to_float(self._tempo_hc_red)
            self._kwh_hp_ns = convert_to_float(self._tempo_hp_blue) + convert_to_float(
                self._tempo_hp_white) + convert_to_float(self._tempo_hp_red)
        # 78 bug fix
        elif self._use_hchp is True and 'subconsumption' in data[week_day]:
            # 74 bug fix
            for item in data[week_day]['subconsumption']:
                if item['label'] == "Heures Creuses" or \
                        item['label'].startswith("HC"):
                    self._kwh_hc_ns = convert_to_float(item['kwh'])
                if item['label'] == "Heures Pleines" or \
                        item['label'].startswith("HP"):
                    self._kwh_hp_ns = convert_to_float(item['kwh'])

    async def _cookiesapi_wrapper(
        self,
        data: str | None = None,
    ) -> None:
        """Log in and keep the session cookies."""
        _payload, cookies = await self._async_get(
            "Cookies", ECOJOKO_LOGIN_URL, data=data)
        self._cookies = cookies

    async def _gatewayapi_wrapper(self) -> None:
        """Get the gateway and device ids from the API."""
        value_json, _cookies = await self._async_get(
            "Gateway", ECOJOKO_GATEWAYS_URL, cookies=self._cookies)
        if value_json is None:
            return
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
