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
    CONF_API_FAILURE_GRACE,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    POLL_INTERVAL,
    LOGGER
)

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
            "gateway_firmware_version": self.client.gateway_firmware_version,
            "stat_date": self.client.stat_date,
            "realtime_consumption": self.client.realtime_conso,
            "realtime_apparent_power": self.client.realtime_va,
            "grid_consumption": self.client.kwh,
            "hc_grid_consumption": self.client.kwh_hc_ns,
            "hp_grid_consumption": self.client.kwh_hp_ns,
            "weekend_grid_consumption": self.client.kwh_weekend,
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
