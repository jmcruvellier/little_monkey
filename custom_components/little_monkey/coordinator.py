"""DataUpdateCoordinator for little_monkey."""
from __future__ import annotations

import time
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import (
    LittleMonkeyApiClient,
    LittleMonkeyApiClientAuthenticationError,
    LittleMonkeyApiClientCommunicationError,
    LittleMonkeyApiClientError,
)
from .const import (
    CONF_API_ACTIVITY_GRACE,
    CONF_API_ACTIVITY_REFRESH,
    CONF_API_FAILURE_GRACE,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    POLL_INTERVAL,
    LOGGER,
    TEMPO_PERIODS,
    tariff_periods,
)
from .utils import TariffPeriod

# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities


class LittleMonkeyDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Ecojoko APIs."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: LittleMonkeyApiClient,
    ) -> None:
        """Initialize."""
        self.hass = hass
        self.config_entry = entry
        self.client = client
        # Monotonic time of the first failure of the current series
        self._failing_since = None
        self._periods = tariff_periods(entry.data)
        self._tariff_period = TariffPeriod()

        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=int(entry.data.get(POLL_INTERVAL, DEFAULT_POLL_INTERVAL))),
        )

    def _is_brief_failure(self) -> bool:
        """Tell whether ecojoko has been unreachable for a short time only.

        A timeout or a network error on a single poll is usual: the last
        values are kept for CONF_API_FAILURE_GRACE seconds before the
        sensors become unavailable.
        """
        if self.data is None:
            # Nothing to keep before the first successful poll
            return False
        now = time.monotonic()
        if self._failing_since is None:
            self._failing_since = now
        return now - self._failing_since < CONF_API_FAILURE_GRACE

    def _current_tariff_period(self):
        """Return the current tariff period, None without HC/HP nor Tempo option."""
        if self._periods is None:
            return None
        client = self.client
        if self._periods == TEMPO_PERIODS:
            counters = {
                "hc_blue": client.tempo_hc_blue,
                "hp_blue": client.tempo_hp_blue,
                "hc_white": client.tempo_hc_white,
                "hp_white": client.tempo_hp_white,
                "hc_red": client.tempo_hc_red,
                "hp_red": client.tempo_hp_red,
            }
        else:
            counters = {"hc": client.kwh_hc_ns, "hp": client.kwh_hp_ns}
        return self._tariff_period.update(client.stat_date, counters)

    async def _async_update_data(self):
        """Update data via library."""
        try:
            await self.client.async_get_data()
        except LittleMonkeyApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except LittleMonkeyApiClientCommunicationError as exception:
            if self._is_brief_failure():
                LOGGER.debug(
                    "ecojoko unreachable, the last values are kept: %s",
                    exception)
                return self.data
            raise UpdateFailed(exception) from exception
        except LittleMonkeyApiClientError as exception:
            raise UpdateFailed(exception) from exception
        except Exception as exception:  # pylint: disable=broad-except
            raise UpdateFailed(exception) from exception
        self._failing_since = None
        return {
            "current_tariff_period": self._current_tariff_period(),
            "gateway_firmware_version": self.client.gateway_firmware_version,
            "stat_date": self.client.stat_date,
            "realtime_consumption": self.client.realtime_conso,
            "realtime_apparent_power": self.client.realtime_va,
            "grid_consumption": self.client.kwh,
            "hc_grid_consumption": self.client.kwh_hc_ns,
            "hp_grid_consumption": self.client.kwh_hp_ns,
            "blue_hc_grid_consumption": self.client.tempo_hc_blue,
            "blue_hp_grid_consumption": self.client.tempo_hp_blue,
            "white_hc_grid_consumption": self.client.tempo_hc_white,
            "white_hp_grid_consumption": self.client.tempo_hp_white,
            "red_hc_grid_consumption": self.client.tempo_hc_red,
            "red_hp_grid_consumption": self.client.tempo_hp_red,
            "production_surplus": self.client.kwh_prod,
            "indoor_temp": self.client.indoor_temp,
            "outdoor_temp": self.client.outdoor_temp,
            "indoor_hum": self.client.indoor_hum,
            "outdoor_hum": self.client.outdoor_hum,
        }


class LittleMonkeyActivityCoordinator(DataUpdateCoordinator):
    """Fetch the activity of the account (savings over 7 days...).

    It is apart from the polls: ecojoko is slow to compute it, and its
    values change slowly. A failure never makes the real-time sensors
    unavailable, and the last values are kept for CONF_API_ACTIVITY_GRACE
    seconds.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: LittleMonkeyApiClient,
    ) -> None:
        """Initialize."""
        self.config_entry = entry
        self.client = client
        # Monotonic time of the last successful reading
        self._last_success = None
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=f"{DOMAIN} activity",
            update_interval=timedelta(seconds=CONF_API_ACTIVITY_REFRESH),
        )

    async def _async_update_data(self):
        """Read the activity of the account."""
        try:
            data = await self.client.async_get_activity()
        except LittleMonkeyApiClientError as exception:
            if (
                self.data is not None
                and self._last_success is not None
                and time.monotonic() - self._last_success < CONF_API_ACTIVITY_GRACE
            ):
                LOGGER.debug(
                    "ecojoko activity not read, the last values are kept: %s",
                    exception)
                return self.data
            raise UpdateFailed(exception) from exception
        self._last_success = time.monotonic()
        return data
