"""API Client for little_monkey."""
from __future__ import annotations

# import traceback

from enum import Enum
from datetime import datetime, timedelta
import asyncio
import json
import socket
import aiohttp
import async_timeout
from .const import (
    CONF_API_TIMEOUT,
    CONF_API_STAT_REFRESH,
    ECOJOKO_LOGIN_URL,
    ECOJOKO_GATEWAYS_URL,
    ECOJOKO_GATEWAY_URL,
    LOGGER
)
from .utils import (
    get_current_date,
    get_current_time,
    get_paris_timezone,
    get_value_from_json_array,
    convert_to_float)

TZ = get_paris_timezone()

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

class APIStatus(Enum):
    """API status enum."""

    INIT = 0
    RUN = 1

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
        self._headers={"Content-type": "application/json"}
        self._cookies = None
        self._gateway_id = None
        self._power_meter_id = None
        self._temp_hum_id = None
        """Properties."""
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

        """Internal."""
        #67 fix
        self._status = APIStatus.INIT
        self._last_powerstat_refresh = None
        self._last_tempstat_refresh = None
        self._last_humstat_refresh = None

    @property
    def gateway_firmware_version(self) -> str:
        """Return the firmware version."""
        return self._gateway_firmware_version

    @property
    def realtime_conso(self) -> int:
        """Return the realtime consumption."""
        return self._realtime_conso

    @property
    def kwh(self) -> int:
        """Return the grid consumption."""
        return self._kwh

    @property
    def kwh_hc_ns(self) -> int:
        """Return the HC consumption."""
        return self._kwh_hc_ns

    @property
    def kwh_hp_ns(self) -> int:
        """Return the HP consumption."""
        return self._kwh_hp_ns

    @property
    def tempo_hc_blue(self) -> int:
        """Return the Blue HC consumption."""
        return self._tempo_hc_blue

    @property
    def tempo_hp_blue(self) -> int:
        """Return the Blue HP consumption."""
        return self._tempo_hp_blue

    @property
    def tempo_hc_white(self) -> int:
        """Return the White HC consumption."""
        return self._tempo_hc_white

    @property
    def tempo_hp_white(self) -> int:
        """Return the White HP consumption."""
        return self._tempo_hp_white

    @property
    def tempo_hc_red(self) -> int:
        """Return the Red HC consumption."""
        return self._tempo_hc_red

    @property
    def tempo_hp_red(self) -> int:
        """Return the Red HP consumption."""
        return self._tempo_hp_red

    @property
    def kwh_prod(self) -> int:
        """Return the production surplus."""
        return self._kwh_prod

    @property
    def indoor_temp(self) -> int:
        """Return the indoor temperature."""
        return self._indoor_temp

    @property
    def outdoor_temp(self) -> int:
        """Return the outdoor temperature."""
        return self._outdoor_temp

    @property
    def indoor_hum(self) -> int:
        """Return the indoor humidity."""
        return self._indoor_hum

    @property
    def outdoor_hum(self) -> int:
        """Return the outdoor humidity."""
        return self._outdoor_hum

    async def async_get_cookiesdata(self) -> any:
        """Perform login and return cookies."""
        login_data = {
            "l": f"{self._username}",
            "p": f"{self._password}"
        }
        try:
            payload_json = json.dumps(login_data)
            return await self._cookiesapi_wrapper(data=payload_json)
        except Exception as exception:  # pylint: disable=broad-except
            raise LittleMonkeyApiClientError(
                "Something really wrong happened!"
            ) from exception

    async def async_get_gatewaydata(self) -> any:
        """Get Ecojoko gateway data."""
        try:
            if self._cookies is None:
                LOGGER.debug("Pas de cookies")
                # raise exception
            return await self._gatewayapi_wrapper()
        except Exception as exception:  # pylint: disable=broad-except
            raise LittleMonkeyApiClientError(
                "Something really wrong happened!"
            ) from exception

    async def fetch_data(self, api):
        """Retrieve data from a given URL using aiohttp."""
        try:
            if api['call'] is True:
                async with async_timeout.timeout(CONF_API_TIMEOUT):
                    response = await self._session.get(
                        url=api['url'],
                        headers=self._headers,
                        cookies=self._cookies,
                    )
                if response.status in (401, 403):
                    #71 bug fix
                    self._cookies = None
                    raise LittleMonkeyApiClientAuthenticationError(
                        "Invalid credentials",
                    )
                if "application/json" in response.headers.get("Content-Type", ""):
                    return await response.json()
            return None
        except asyncio.TimeoutError:
            LOGGER.error("API %s timeout error", api['name'])
            # raise LittleMonkeyApiClientCommunicationError(
            #     "Timeout error fetching information",
            # ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            LOGGER.error("API %s client error: %s", api['name'], exception)
            # raise LittleMonkeyApiClientCommunicationError(
            #     "Error fetching information",
            # ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            LOGGER.error("API %s other error: %s", api['name'], exception)
            # raise LittleMonkeyApiClientError(
            #     "Something really wrong happened!"
            # ) from exception
        return

    async def async_get_data(self) -> None:
        """Get data from ecojoko APIs."""
        try:
            if self._cookies is None:
                await self.async_get_cookiesdata()
            if self._gateway_id is None:
                await self.async_get_gatewaydata()

            # Initialization
            current_date = get_current_date(TZ)
            formatted_date = current_date.strftime('%Y-%m-%d')
            current_time = get_current_time(TZ)
            current_datetime = datetime.combine(current_date, current_time)
            #   - powerstat (for Total Consumption + HC/HP + Tempo)
            if self._last_powerstat_refresh is None:
                refresh_powerstat = True
            else:
                difference = current_datetime - self._last_powerstat_refresh
                refresh_powerstat = difference > timedelta(seconds=CONF_API_STAT_REFRESH)
            #   - Temperature
            if refresh_powerstat is False:
                difference = current_datetime - self._last_powerstat_refresh
                inf = timedelta(seconds=self._poll_interval)
                sup = timedelta(seconds=2*self._poll_interval)
                refresh_tempstat = inf < difference < sup
            else:
                refresh_tempstat = False
            #   - Humidity
            if refresh_powerstat is False and refresh_tempstat is False:
                difference = current_datetime - self._last_powerstat_refresh
                inf = timedelta(seconds=2*self._poll_interval)
                sup = timedelta(seconds=3*self._poll_interval)
                refresh_humstat = inf < difference < sup
            else:
                refresh_humstat = False

            apis = []
            powermeterurl = f"/{self._gateway_id}/device/{self._power_meter_id}"
            apis.append({"name" : "realtime_conso",
                        "url" : ECOJOKO_GATEWAY_URL + powermeterurl +
                        "/realtime_conso",
                        "call" : True})
            apis.append({"name" : "powerstat (w)",
                         "url" : ECOJOKO_GATEWAY_URL + powermeterurl +
                         f"/powerstat/w/{formatted_date}",
                         "call" : refresh_powerstat})
            temphumurl = f"/{self._gateway_id}/device/{self._temp_hum_id}"
            apis.append({"name" : "tempstat (d)",
                         "url" : ECOJOKO_GATEWAY_URL + temphumurl +
                         f"/tempstat/d4/{formatted_date}",
                         "call" : refresh_tempstat})
            apis.append({"name" : "humstat (d)",
                         "url" : ECOJOKO_GATEWAY_URL + temphumurl +
                         f"/humstat/d4/{formatted_date}",
                         "call" : refresh_humstat})

            tasks = [self.fetch_data(api) for api in apis]
            results = await asyncio.gather(*tasks)
            if results[0] is not None:
                self._realtime_conso = results[0]['real_time']['value']
            week_day = current_date.weekday()
            if results[1] is not None:
                data = results[1]['stat']['data']
                self._kwh = data[week_day]['kwh']
                # Surplus Production
                if self._use_prod is True:
                    if float(data[week_day]['kwh_prod']) != 0:
                        self._kwh_prod = -float(data[week_day]['kwh_prod'])
                    else:
                        self._kwh_prod = 0
                # Tempo option
                if self._use_tempo is True:
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
                    self._kwh_hc_ns = convert_to_float(self._tempo_hc_blue) + convert_to_float(self._tempo_hc_white) + convert_to_float(self._tempo_hc_red)
                    self._kwh_hp_ns = convert_to_float(self._tempo_hp_blue) + convert_to_float(self._tempo_hp_white) + convert_to_float(self._tempo_hp_red)
                elif self._use_hchp is True:
                    self._kwh_hc_ns = get_value_from_json_array(
                        data[week_day]['subconsumption'],
                        "label",
                        "Heures Creuses",
                        "kwh")
                    self._kwh_hp_ns = get_value_from_json_array(
                        data[week_day]['subconsumption'],
                        "label",
                        "Heures Pleines",
                        "kwh")
                self._last_powerstat_refresh = datetime.combine(current_date, current_time)
            # Temperature
            if results[2] is not None:
                data = results[2]['stat']['data']
                if len(data) > 1:
                    self._indoor_temp = data[-1]['value']
                    self._outdoor_temp = data[-1]['ext_value']
                else:
                    # LOGGER.debug("TEMP UNE SEULE VALEUR: %s", value_json)
                    self._indoor_temp = data['value']
                    self._outdoor_temp = data['ext_value']
            # Humidity
            if results[3] is not None:
                data = results[3]['stat']['data']
                if len(data) > 1:
                    self._indoor_hum = data[-1]['value']
                    self._outdoor_hum = data[-1]['ext_value']
                else:
                    # LOGGER.debug("HUM UNE SEULE VALEUR: %s", value_json)
                    self._indoor_hum = data['value']
                    self._outdoor_hum = data['ext_value']

            self._status = APIStatus.RUN
            return

        except Exception:  # pylint: disable=broad-except
            # traceback.print_exc()
            return

    async def _cookiesapi_wrapper(
        self,
        data: dict | None = None,
    ) -> any:
        """Get cookies from the API."""
        try:
            async with async_timeout.timeout(CONF_API_TIMEOUT):
                response = await self._session.get(
                    url=ECOJOKO_LOGIN_URL,
                    headers=self._headers,
                    data=data
                )
            if response.status in (401, 403):
                #71 bug fix
                self._cookies = None
                raise LittleMonkeyApiClientAuthenticationError(
                    "Invalid credentials",
                )
            self._cookies = response.cookies
            #response.raise_for_status()
            return

        except asyncio.TimeoutError as exception:
            LOGGER.error("API Cookies timeout error")
            raise LittleMonkeyApiClientCommunicationError(
                "Timeout error fetching information",
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            LOGGER.error("API Cookies client error: %s", exception)
            raise LittleMonkeyApiClientCommunicationError(
                "Error fetching information",
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            LOGGER.error("API Cookies other error: %s", exception)
            raise LittleMonkeyApiClientError(
                "Something really wrong happened!"
            ) from exception

    async def _gatewayapi_wrapper(self) -> any:
        """Get gateway Id from the API."""
        try:
            async with async_timeout.timeout(CONF_API_TIMEOUT):
                response = await self._session.get(
                    url=ECOJOKO_GATEWAYS_URL,
                    headers=self._headers,
                    cookies=self._cookies,
                )
            if response.status in (401, 403):
                #71 bug fix
                self._cookies = None
                raise LittleMonkeyApiClientAuthenticationError(
                    "Invalid credentials",
                )
            if "application/json" in response.headers.get("Content-Type", ""):
                value_json = await response.json()
                gateways = value_json.get('gateways')

                # Looking for gateway Id
                gateway_id = gateways[0].get('gateway_id')
                self._gateway_id = gateway_id

                # Looking for gateway firmware
                gateway_firmware_version = gateways[0].get('gateway_firmware_version')
                self._gateway_firmware_version = gateway_firmware_version

                value_json = gateways[0].get('devices')
                # Looking for humidity temperature and  power meter devices id
                for item in value_json:
                    if item["device_type"] == "TEMP_HUM":
                        self._temp_hum_id = item["device_id"]
                    if item["device_type"] == "POWER_METER":
                        self._power_meter_id = item["device_id"]

                #response.raise_for_status()
                return

        except asyncio.TimeoutError as exception:
            LOGGER.error("API Gateway timeout error")
            raise LittleMonkeyApiClientCommunicationError(
                "Timeout error fetching information",
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            LOGGER.error("API Gateway client error: %s", exception)
            raise LittleMonkeyApiClientCommunicationError(
                "Error fetching information",
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            LOGGER.error("API Gateway other error: %s", exception)
            raise LittleMonkeyApiClientError(
                "Something really wrong happened!"
            ) from exception
