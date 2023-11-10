"""API Client for little_monkey."""
from __future__ import annotations

import asyncio
import datetime
import socket

import json

import aiohttp
import async_timeout

from .const import (
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
        """API Client."""
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
        self._power_meter_id = None
        self._temp_hum_id = None
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
        # Get the current date
        self._current_date = datetime.date.today()
        # Format the date as 'YYYY-MM-DD'
        self._formatted_date = self._current_date.strftime('%Y-%m-%d')

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

    async def async_get_data(self) -> None:
        """Get data from the API."""
        if self._cookies is None:
            await self.async_get_cookiesdata()
        if self._gateway_id is None:
            await self.async_get_gatewaydata()
        await self.async_get_realtime_conso()
        await self.async_get_kwhstat()
        if self._use_temphum is True:
            await self.async_get_tempstat()
            await self.async_get_humstat()
        else:
            LOGGER.debug("NE RETOURNE PAS DE TEMPHUM")

    async def async_get_realtime_conso(self) -> any:
        """Get Ecojoko realtime consumption"""
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
        except Exception as exception:  # pylint: disable=broad-except
            raise LittleMonkeyApiClientError(
                "Something really wrong happened!"
            ) from exception

    async def async_get_kwhstat(self) -> any:
        """Get Ecojoko kwhstat"""
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
        except Exception as exception:  # pylint: disable=broad-except
            raise LittleMonkeyApiClientError(
                "Something really wrong happened!"
            ) from exception

    async def async_get_tempstat(self) -> any:
        """Get Ecojoko tempstat"""
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
        except Exception as exception:  # pylint: disable=broad-except
            raise LittleMonkeyApiClientError(
                "Something really wrong happened!"
            ) from exception

    async def async_get_humstat(self) -> any:
        """Get Ecojoko humstat"""
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
        except Exception as exception:  # pylint: disable=broad-except
            raise LittleMonkeyApiClientError(
                "Something really wrong happened!"
            ) from exception

    async def _cookiesapi_wrapper(
        self,
        data: dict | None = None,
    ) -> any:
        """Get cookies from the API."""
        try:
            async with async_timeout.timeout(1):
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
            LOGGER.error("API CK timeout error: %s", exception)
            raise LittleMonkeyApiClientCommunicationError(
                "Timeout error fetching information",
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            LOGGER.error("API CK client error: %s", exception)
            raise LittleMonkeyApiClientCommunicationError(
                "Error fetching information",
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            LOGGER.error("API CK other error: %s", exception)
            raise LittleMonkeyApiClientError(
                "Something really wrong happened!"
            ) from exception

    async def _gatewayapi_wrapper(self) -> any:
        """Get gateway Id from the API."""
        try:
            async with async_timeout.timeout(1):
                response = await self._session.get(
                    url=ECOJOKO_GATEWAYS_URL,
                    headers=self._headers,
                    cookies=self._cookies,
                )
            if response.status in (401, 403):
                raise LittleMonkeyApiClientAuthenticationError(
                    "Invalid credentials",
                )
            value_json = await response.json()
            gateways = value_json.get('gateways')

            # Looking for gateway Id
            gateway_id = gateways[0].get('gateway_id')
            self._gateway_id = gateway_id

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
            LOGGER.error("API GTW timeout error: %s", exception)
            raise LittleMonkeyApiClientCommunicationError(
                "Timeout error fetching information",
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            LOGGER.error("API GTW client error: %s", exception)
            raise LittleMonkeyApiClientCommunicationError(
                "Error fetching information",
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            LOGGER.error("API GTW other error: %s", exception)
            raise LittleMonkeyApiClientError(
                "Something really wrong happened!"
            ) from exception

    async def _realtimeconso_wrapper(self) -> any:
        """Get realtime consumption from the API."""
        try:
            url = ECOJOKO_GATEWAY_URL + f"/{self._gateway_id}/device/{self._power_meter_id}/realtime_conso"
            async with async_timeout.timeout(1):
                response = await self._session.get(
                    url=url,
                    headers=self._headers,
                    cookies=self._cookies,
                )
            if response.status in (401, 403):
                raise LittleMonkeyApiClientAuthenticationError(
                    "Invalid credentials",
                )
            value_json = await response.json()
            self._realtime_conso = value_json['real_time']['value']
            response.raise_for_status()
            return await response.json()

        except asyncio.TimeoutError as exception:
            LOGGER.error("API RT timeout error: %s", exception)
            raise LittleMonkeyApiClientCommunicationError(
                "Timeout error fetching information",
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            LOGGER.error("API RT client error: %s", exception)
            raise LittleMonkeyApiClientCommunicationError(
                "Error fetching information",
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            LOGGER.error("API RT other error: %s", exception)
            raise LittleMonkeyApiClientError(
                "Something really wrong happened!"
            ) from exception

    async def _kwhstat_wrapper(self) -> any:
        """Get kwhstat from the API."""
        try:
            url = ECOJOKO_GATEWAY_URL + f"/{self._gateway_id}/device/{self._power_meter_id}/kwhstat"
            async with async_timeout.timeout(1):
                response = await self._session.get(
                    url=url,
                    headers=self._headers,
                    cookies=self._cookies,
                )
            if response.status in (401, 403):
                raise LittleMonkeyApiClientAuthenticationError(
                    "Invalid credentials",
                )
            value_json = await response.json()
            self._kwh = value_json['stat']['period']['kwh']
            if self._use_hchp is True:
                self._kwh_hp_ns = value_json['stat']['period']['kwh_hp_ns']
                self._kwh_hc_ns = value_json['stat']['period']['kwh_hc_ns']
            else:
                LOGGER.debug("NE RETOURNE PAS DE HC/HP")
            if self._use_tempo is True:
                pricing_details = value_json['stat']['pricing_details']
                # Looking for humidity temperature and  power meter devices id
                for item in pricing_details:
                    if item["label"] == "HC Bleu":
                        self._tempo_hc_blue = self._kwh_hc_ns
                    elif item["label"] == "HP Bleu":
                        self._tempo_hp_blue = self._kwh_hp_ns
                    elif item["label"] == "HC Blanc":
                        self._tempo_hc_white = self._kwh_hc_ns
                    elif item["label"] == "HP Blanc":
                        self._tempo_hp_white = self._kwh_hp_ns
                    elif item["label"] == "HC Rouge":
                        self._tempo_hc_red = self._kwh_hc_ns
                    elif item["label"] == "HP Rouge":
                        self._tempo_hp_red = self._kwh_hp_ns
            if self._use_prod is True:
                self._kwh_prod = -float(value_json['stat']['period']['kwh_prod'])
            else:
                LOGGER.debug("NE RETOURNE PAS DE PROD")
            response.raise_for_status()
            return await response.json()

        except asyncio.TimeoutError as exception:
            LOGGER.error("API KWHSTAT timeout error: %s", exception)
            raise LittleMonkeyApiClientCommunicationError(
                "Timeout error fetching information",
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            LOGGER.error("API KWHSTAT client error: %s", exception)
            raise LittleMonkeyApiClientCommunicationError(
                "Error fetching information",
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            LOGGER.error("API KWHSTAT other error: %s", exception)
            raise LittleMonkeyApiClientError(
                "Something really wrong happened!"
            ) from exception

    async def _tempstat_wrapper(self) -> any:
        """Get tempstat from the API."""
        try:
            url = ECOJOKO_GATEWAY_URL + f"/{self._gateway_id}/device/{self._temp_hum_id}/tempstat/d4/{self._formatted_date}"
            async with async_timeout.timeout(1):
                response = await self._session.get(
                    url=url,
                    headers=self._headers,
                    cookies=self._cookies,
                )
            if response.status in (401, 403):
                raise LittleMonkeyApiClientAuthenticationError(
                    "Invalid credentials",
                )
            value_json = await response.json()
            self._indoor_temp = value_json['stat']['data'][-1]['value']
            self._outdoor_temp = value_json['stat']['data'][-1]['ext_value']
            response.raise_for_status()
            return await response.json()

        except asyncio.TimeoutError as exception:
            LOGGER.error("API TEMPSTAT timeout error: %s", exception)
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
            url = ECOJOKO_GATEWAY_URL + f"/{self._gateway_id}/device/{self._temp_hum_id}/humstat/d4/{self._formatted_date}"
            async with async_timeout.timeout(1):
                response = await self._session.get(
                    url=url,
                    headers=self._headers,
                    cookies=self._cookies,
                )
            if response.status in (401, 403):
                raise LittleMonkeyApiClientAuthenticationError(
                    "Invalid credentials",
                )
            value_json = await response.json()
            self._indoor_hum = value_json['stat']['data'][-1]['value']
            self._outdoor_hum = value_json['stat']['data'][-1]['ext_value']
            response.raise_for_status()
            return await response.json()

        except asyncio.TimeoutError as exception:
            LOGGER.error("API HUMSTAT timeout error: %s", exception)
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
