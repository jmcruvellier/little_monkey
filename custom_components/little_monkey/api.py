"""API Client for little_monkey."""
from __future__ import annotations

# import traceback

import asyncio
import datetime
import socket

import json

from enum import Enum

import aiohttp
import async_timeout

import pytz

from .const import (
    CONF_API_TIMEOUT,
    ECOJOKO_LOGIN_URL,
    ECOJOKO_GATEWAYS_URL,
    ECOJOKO_GATEWAY_URL,
    LOGGER
)

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

class PricingZone(Enum):
    """Pricing zone enum."""
    HC_NIGHT = 0
    HP = 1
    HC_EVENING = 2

class LittleMonkeyApiClient:
    """API Client to retrieve cookies."""

    def __init__(
        self,
        username: str,
        password: str,
        use_hchp: bool,
        use_tempo: bool,
        use_temphum: bool,
        use_prod: bool,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize."""
        self._username = username
        self._password = password
        self._use_hchp = use_hchp
        self._use_tempo = use_tempo
        self._use_temphum = use_temphum
        self._use_prod = use_prod
        self._session = session
        self._headers={"Content-type": "application/json"}
        self._cookies = None
        self._gateway_id = None
        self._gateway_firmware_version = None
        self._power_meter_id = None
        self._temp_hum_id = None
        self._current_date = None
        self._local_time = None
        self._pricing_details = None
        self._night_pricing_details = None
        self._current_pricing = None
        self._realtime_conso = None
        self._kwh = None
        self._kwh_hc_night = None
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

    @property
    def gateway_firmware_version(self) -> str:
        """Return the native value of the sensor."""
        return self._gateway_firmware_version

    @property
    def current_date(self) -> datetime.date:
        """Return the native value of the sensor."""
        return self._current_date

    @property
    def local_time(self) -> datetime.time:
        """Return the native value of the sensor."""
        return self._local_time

    @property
    def night_pricing_details(self) -> str:
        """Return the native value of the sensor."""
        return self._night_pricing_details

    @property
    def current_pricing(self) -> PricingZone:
        """Return the native value of the sensor."""
        return self._current_pricing

    @property
    def pricing_details(self) -> str:
        """Return the native value of the sensor."""
        return self._pricing_details

    @property
    def realtime_conso(self) -> int:
        """Return the native value of the sensor."""
        return self._realtime_conso

    @property
    def kwh(self) -> int:
        """Return the native value of the sensor."""
        return self._kwh

    @property
    def kwh_hc_ns(self) -> int:
        """Return the native value of the sensor."""
        return self._kwh_hc_ns

    @property
    def kwh_hp_ns(self) -> int:
        """Return the native value of the sensor."""
        return self._kwh_hp_ns

    @property
    def tempo_hc_blue(self) -> int:
        """Return the native value of the sensor."""
        return self._tempo_hc_blue

    @property
    def tempo_hp_blue(self) -> int:
        """Return the native value of the sensor."""
        return self._tempo_hp_blue

    @property
    def tempo_hc_white(self) -> int:
        """Return the native value of the sensor."""
        return self._tempo_hc_white

    @property
    def tempo_hp_white(self) -> int:
        """Return the native value of the sensor."""
        return self._tempo_hp_white

    @property
    def tempo_hc_red(self) -> int:
        """Return the native value of the sensor."""
        return self._tempo_hc_red

    @property
    def tempo_hp_red(self) -> int:
        """Return the native value of the sensor."""
        return self._tempo_hp_red

    @property
    def kwh_prod(self) -> int:
        """Return the native value of the sensor."""
        return self._kwh_prod

    @property
    def indoor_temp(self) -> int:
        """Return the native value of the sensor."""
        return self._indoor_temp

    @property
    def outdoor_temp(self) -> int:
        """Return the native value of the sensor."""
        return self._outdoor_temp

    @property
    def indoor_hum(self) -> int:
        """Return the native value of the sensor."""
        return self._indoor_hum

    @property
    def outdoor_hum(self) -> int:
        """Return the native value of the sensor."""
        return self._outdoor_hum

    async def async_get_date_time(self) -> any:
        """Return local time"""
        # Get the current date
        self._current_date = datetime.date.today()
        paris_tz = pytz.timezone('Europe/Paris')
        self._local_time = datetime.datetime.now(paris_tz).time()
        return

    async def async_get_data(self) -> None:
        """Get data from the API."""
        if self._cookies is None:
            await self.async_get_cookiesdata()
        if self._gateway_id is None:
            await self.async_get_gatewaydata()

        await self.async_get_date_time()
        if self._current_pricing is None or (
            self._current_pricing == PricingZone.HC_NIGHT
            and
            not datetime.time(0, 0, 0) <= self._local_time <= datetime.time(5, 59, 59)
        ) or (
            self._current_pricing == PricingZone.HP
            and
            not datetime.time(6, 0, 0) <= self._local_time <= datetime.time(21, 59, 59)
        ) or (
            self._current_pricing == PricingZone.HC_EVENING
            and
            not datetime.time(22, 0, 0) <= self._local_time <= datetime.time(23, 59, 59)
        ):
            LOGGER.debug("Getting pricing details")
            await self.async_get_pricing_details()

        await self.async_get_realtime_conso()
        await self.async_get_kwhstat()
        if self._use_temphum is True:
            await self.async_get_tempstat()
            await self.async_get_humstat()
        else:
            LOGGER.debug("NE RETOURNE PAS DE TEMPHUM")

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

    async def async_get_pricing_details(self) -> any:
        """Get pricing details."""
        try:
            return await self._pricing_details_wrapper()
        except Exception:  # pylint: disable=broad-except
            return
        # except Exception as exception:  # pylint: disable=broad-except
        #     raise LittleMonkeyApiClientError(
        #         "Something really wrong happened!"
        #     ) from exception

    async def async_get_realtime_conso(self) -> any:
        """Get Ecojoko realtime consumption."""
        try:
            if self._cookies is None:
                LOGGER.debug("Pas de cookies")
                # raise exception
            if self._gateway_id is None:
                LOGGER.debug("Pas de gateway")
                # TOTO raise exception
            if self._power_meter_id is None:
                LOGGER.debug("Pas de power meter")
                # TOTO raise exception
            return await self._realtimeconso_wrapper()
        except Exception:  # pylint: disable=broad-except
            return
        # except Exception as exception:  # pylint: disable=broad-except
        #     raise LittleMonkeyApiClientError(
        #         "Something really wrong happened!"
        #     ) from exception

    async def async_get_kwhstat(self) -> any:
        """Get Ecojoko kwhstat."""
        try:
            if self._cookies is None:
                LOGGER.debug("Pas de cookies")
                # TOTO raise exception
            if self._gateway_id is None:
                LOGGER.debug("Pas de gateway")
                # TOTO raise exception
            if self._power_meter_id is None:
                LOGGER.debug("Pas de power meter")
                # TOTO raise exception
            return await self._kwhstat_wrapper()
        except Exception:  # pylint: disable=broad-except
            return
        # except Exception as exception:  # pylint: disable=broad-except
        #     raise LittleMonkeyApiClientError(
        #         "Something really wrong happened!"
        #     ) from exception

    async def async_get_tempstat(self) -> any:
        """Get Ecojoko tempstat."""
        try:
            if self._cookies is None:
                LOGGER.debug("Pas de cookies")
                # TOTO raise exception
            if self._gateway_id is None:
                LOGGER.debug("Pas de gateway")
                # TOTO raise exception
            if self._temp_hum_id is None:
                LOGGER.debug("Pas de temphum")
                # TOTO raise exception
            return await self._tempstat_wrapper()
        except Exception:  # pylint: disable=broad-except
            return
        # except Exception as exception:  # pylint: disable=broad-except
        #     raise LittleMonkeyApiClientError(
        #         "Something really wrong happened!"
        #     ) from exception

    async def async_get_humstat(self) -> any:
        """Get Ecojoko humstat."""
        try:
            if self._cookies is None:
                LOGGER.debug("Pas de cookies")
                # TOTO raise exception
            if self._gateway_id is None:
                LOGGER.debug("Pas de gateway")
                # TOTO raise exception
            if self._temp_hum_id is None:
                LOGGER.debug("Pas de temphum")
                # TOTO raise exception
            return await self._humstat_wrapper()
        except Exception:  # pylint: disable=broad-except
            return
        # except Exception as exception:  # pylint: disable=broad-except
        #     raise LittleMonkeyApiClientError(
        #         "Something really wrong happened!"
        #     ) from exception

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
                raise LittleMonkeyApiClientAuthenticationError(
                    "Invalid credentials",
                )
            self._cookies = response.cookies
            response.raise_for_status()
            return await response.json()

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

                response.raise_for_status()
                return await response.json()

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

    async def _pricing_details_wrapper(self) -> any:
        """Get pricing details from the API."""
        try:
            #63
            # Retrieve current Tempo pricing
            # Format the date as 'YYYY-MM-DD'
            formatted_date = self._current_date.strftime('%Y-%m-%d') + self._local_time.strftime('%H:%M')
            url = ECOJOKO_GATEWAY_URL + f"/{self._gateway_id}/device/{self._power_meter_id}/powerstat/h/{formatted_date}"
            #LOGGER.debug("URL: %s", url)
            async with async_timeout.timeout(CONF_API_TIMEOUT):
                response = await self._session.get(
                    url=url,
                    headers=self._headers,
                    cookies=self._cookies,
                )
            if response.status in (401, 403):
                raise LittleMonkeyApiClientAuthenticationError(
                    "Invalid credentials",
                )
            if "application/json" in response.headers.get("Content-Type", ""):
                value_json = await response.json()
                # Vérifier la présence de value_json['stat']['pricing_details'] dans la réponse
                if "pricing_details" in value_json['stat']:
                    self._pricing_details = value_json['stat']['pricing_details'][0]['label']
                    if datetime.time(0, 0, 0) <= self._local_time <= datetime.time(5, 59, 59):
                        self._current_pricing = PricingZone.HC_NIGHT
                        self._night_pricing_details = self._pricing_details
                    elif datetime.time(6, 0, 0) <= self._local_time <= datetime.time(21, 59, 59):
                        self._current_pricing = PricingZone.HP
                    elif datetime.time(22, 0, 0) <= self._local_time <= datetime.time(23, 59, 59):
                        self._current_pricing = PricingZone.HC_EVENING
            else:
                LOGGER.debug("PAS DE PRICING DETAILS")
            response.raise_for_status()
            return await response.json()

        except asyncio.TimeoutError as exception:
            LOGGER.error("API KWHSTAT timeout error: %s")
            raise LittleMonkeyApiClientCommunicationError(
                "Timeout error fetching information",
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            LOGGER.error("API KWHSTAT client error: %s", exception)
            raise LittleMonkeyApiClientCommunicationError(
                "Error fetching information",
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            # traceback.print_exc()
            LOGGER.error("API KWHSTAT other error: %s", exception)
            raise LittleMonkeyApiClientError(
                "Something really wrong happened!"
            ) from exception

    async def _realtimeconso_wrapper(self) -> any:
        """Get realtime consumption from the API."""
        try:
            url = ECOJOKO_GATEWAY_URL + f"/{self._gateway_id}/device/{self._power_meter_id}/realtime_conso"
            async with async_timeout.timeout(CONF_API_TIMEOUT):
                response = await self._session.get(
                    url=url,
                    headers=self._headers,
                    cookies=self._cookies,
                )
            if response.status in (401, 403):
                raise LittleMonkeyApiClientAuthenticationError(
                    "Invalid credentials",
                )
            if "application/json" in response.headers.get("Content-Type", ""):
                value_json = await response.json()
                self._realtime_conso = value_json['real_time']['value']
                response.raise_for_status()
                return await response.json()

        except asyncio.TimeoutError as exception:
            LOGGER.error("API Realtime timeout error")
            raise LittleMonkeyApiClientCommunicationError(
                "Timeout error fetching information",
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            LOGGER.error("API Realtime client error: %s", exception)
            raise LittleMonkeyApiClientCommunicationError(
                "Error fetching information",
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            LOGGER.error("API Realtime other error: %s", exception)
            raise LittleMonkeyApiClientError(
                "Something really wrong happened!"
            ) from exception

    async def _kwhstat_wrapper(self) -> any:
        """Get kwhstat from the API."""
        try:
            url = ECOJOKO_GATEWAY_URL + f"/{self._gateway_id}/device/{self._power_meter_id}/kwhstat"
            async with async_timeout.timeout(CONF_API_TIMEOUT):
                response = await self._session.get(
                    url=url,
                    headers=self._headers,
                    cookies=self._cookies,
                )
            if response.status in (401, 403):
                raise LittleMonkeyApiClientAuthenticationError(
                    "Invalid credentials",
                )
            if "application/json" in response.headers.get("Content-Type", ""):
                value_json = await response.json()
                self._kwh = value_json['stat']['period']['kwh']
                # LOGGER.warning("REPONSE ECOJOKO: %s", value_json)
                if self._use_hchp is True:
                    self._kwh_hp_ns = value_json['stat']['period']['kwh_hp_ns']
                    self._kwh_hc_ns = value_json['stat']['period']['kwh_hc_ns']
                else:
                    LOGGER.debug("NE RETOURNE PAS DE HC/HP")
                if self._use_tempo is True:
                    self._kwh_hp_ns = value_json['stat']['period']['kwh_hp_ns']
                    self._kwh_hc_ns = value_json['stat']['period']['kwh_hc_ns']
                    #63
                    if self._pricing_details == "HC Bleu":
                        if self.current_pricing == PricingZone.HC_EVENING:
                            if self._kwh_hc_night is not None and self._pricing_details != self._night_pricing_details:
                                self._tempo_hc_blue = self._kwh_hc_ns - self._kwh_hc_night
                            # else:
                            #     self._tempo_hc_blue = self._kwh_hc_ns
                        else:
                            self._tempo_hc_blue = self._kwh_hc_ns
                            self._kwh_hc_night = self._kwh_hc_ns
                    elif self._pricing_details == "HP Bleu":
                        self._tempo_hp_blue = self._kwh_hp_ns
                    elif self._pricing_details == "HC Blanc":
                        if self.current_pricing == PricingZone.HC_EVENING:
                            if self._kwh_hc_night is not None and self._pricing_details != self._night_pricing_details:
                                self._tempo_hc_white = self._kwh_hc_ns - self._kwh_hc_night
                            # else:
                            #     self._tempo_hc_white = self._kwh_hc_ns
                        else:
                            self._tempo_hc_white = self._kwh_hc_ns
                            self._kwh_hc_night = self._kwh_hc_ns
                    elif self._pricing_details == "HP Blanc":
                        self._tempo_hp_white = self._kwh_hp_ns
                    elif self._pricing_details == "HC Rouge":
                        if self.current_pricing == PricingZone.HC_EVENING:
                            if self._kwh_hc_night is not None and self._pricing_details != self._night_pricing_details:
                                self._tempo_hc_red = self._kwh_hc_ns - self._kwh_hc_night
                            # else:
                            #     self._tempo_hc_red = self._kwh_hc_ns
                        else:
                            self._tempo_hc_red = self._kwh_hc_ns
                            self._kwh_hc_night = self._kwh_hc_ns
                    elif self._pricing_details == "HP Rouge":
                        self._tempo_hp_red = self._kwh_hp_ns
                if self._use_prod is True:
                    self._kwh_prod = -float(value_json['stat']['period']['kwh_prod'])
                else:
                    LOGGER.debug("NE RETOURNE PAS DE PROD")
                response.raise_for_status()
                return await response.json()

        except asyncio.TimeoutError as exception:
            LOGGER.error("API KWHSTAT timeout error")
            raise LittleMonkeyApiClientCommunicationError(
                "Timeout error fetching information",
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            LOGGER.error("API KWHSTAT client error: %s", exception)
            raise LittleMonkeyApiClientCommunicationError(
                "Error fetching information",
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            # traceback.print_exc()
            LOGGER.error("API KWHSTAT other error: %s", exception)
            raise LittleMonkeyApiClientError(
                "Something really wrong happened!"
            ) from exception

    async def _tempstat_wrapper(self) -> any:
        """Get tempstat from the API."""
        try:
            #59 bug fix
            # Get the current date
            current_date = datetime.date.today()
            # Format the date as 'YYYY-MM-DD'
            formatted_date = current_date.strftime('%Y-%m-%d')
            url = ECOJOKO_GATEWAY_URL + f"/{self._gateway_id}/device/{self._temp_hum_id}/tempstat/d4/{formatted_date}"
            async with async_timeout.timeout(CONF_API_TIMEOUT):
                response = await self._session.get(
                    url=url,
                    headers=self._headers,
                    cookies=self._cookies,
                )
            if response.status in (401, 403):
                raise LittleMonkeyApiClientAuthenticationError(
                    "Invalid credentials",
                )
            if "application/json" in response.headers.get("Content-Type", ""):
                value_json = await response.json()
                if len(value_json['stat']['data']) > 1:
                    self._indoor_temp = value_json['stat']['data'][-1]['value']
                    self._outdoor_temp = value_json['stat']['data'][-1]['ext_value']
                else:
                    # LOGGER.debug("TEMP UNE SEULE VALEUR: %s", value_json)
                    self._indoor_temp = value_json['stat']['data']['value']
                    self._outdoor_temp = value_json['stat']['data']['ext_value']
                response.raise_for_status()
                return await response.json()

        except asyncio.TimeoutError as exception:
            LOGGER.error("API TEMPSTAT timeout error")
            raise LittleMonkeyApiClientCommunicationError(
                "Timeout error fetching information",
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            LOGGER.error("API TEMPSTAT client error: %s", exception)
            raise LittleMonkeyApiClientCommunicationError(
                "Error fetching information",
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            LOGGER.error("API TEMPSTAT other error: %s", exception)
            raise LittleMonkeyApiClientError(
                "Something really wrong happened!"
            ) from exception

    async def _humstat_wrapper(self) -> any:
        """Get humstat from the API."""
        try:
            #59 bug fix
            # Get the current date
            current_date = datetime.date.today()
            # Format the date as 'YYYY-MM-DD'
            formatted_date = current_date.strftime('%Y-%m-%d')
            url = ECOJOKO_GATEWAY_URL + f"/{self._gateway_id}/device/{self._temp_hum_id}/humstat/d4/{formatted_date}"
            async with async_timeout.timeout(CONF_API_TIMEOUT):
                response = await self._session.get(
                    url=url,
                    headers=self._headers,
                    cookies=self._cookies,
                )
            if response.status in (401, 403):
                raise LittleMonkeyApiClientAuthenticationError(
                    "Invalid credentials",
                )
            if "application/json" in response.headers.get("Content-Type", ""):
                value_json = await response.json()
                if len(value_json['stat']['data']) > 1:
                    self._indoor_hum = value_json['stat']['data'][-1]['value']
                    self._outdoor_hum = value_json['stat']['data'][-1]['ext_value']
                else:
                    # LOGGER.debug("HUM UNE SEULE VALEUR: %s", value_json)
                    self._indoor_hum = value_json['stat']['data']['value']
                    self._outdoor_hum = value_json['stat']['data']['ext_value']
                response.raise_for_status()
                return await response.json()

        except asyncio.TimeoutError as exception:
            LOGGER.error("API HUMSTAT timeout error")
            raise LittleMonkeyApiClientCommunicationError(
                "Timeout error fetching information",
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            LOGGER.error("API HUMSTAT client error: %s", exception)
            raise LittleMonkeyApiClientCommunicationError(
                "Error fetching information",
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            LOGGER.error("API HUMSTAT other error: %s", exception)
            raise LittleMonkeyApiClientError(
                "Something really wrong happened!"
            ) from exception
