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
from homeassistant.helpers import issue_registry as ir

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
    CONF_API_SAVINGS_REFRESH,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    POLL_INTERVAL,
    LOGGER,
    CONF_TARIFF_BANDS,
    TEMPO_BAND_PERIODS,
    TEMPO_PERIODS,
    tariff_periods,
)
from .tariff import band_key
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
        # Current tariff band (Semaine, Week-end, Jour Spécial...), deduced
        # the same way from the counters of the configured bands
        self._band_names = {
            band["key"]: band.get("name") or band.get("label")
            for band in entry.data.get(CONF_TARIFF_BANDS) or []
        }
        self._tariff_band = TariffPeriod()

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

    @property
    def unknown_bands_issue_id(self) -> str:
        """Return the id of the repair issue of the bands not configured."""
        return f"unknown_bands_{self.config_entry.entry_id}"

    def _check_unknown_bands(self) -> None:
        """Report the tariff bands of the contract not configured yet.

        They appear after a change of contract, or in an entry migrated from
        the HC/HP and Tempo options with another contract. The repair adds
        them; the issue disappears once every band of the day is configured.
        """
        unknown = self.client.unknown_bands
        if unknown is None:
            return
        issue_id = self.unknown_bands_issue_id
        if not unknown:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="unknown_bands",
            translation_placeholders={
                "name": str(self.config_entry.title),
                "bands": ", ".join(sorted(unknown.values())),
            },
            data={
                "entry_id": self.config_entry.entry_id,
                "bands": {str(band_id): label for band_id, label in unknown.items()},
            },
        )

    def _current_tariff_period(self):
        """Return the current tariff period, None without HC/HP nor Tempo option."""
        if self._periods is None:
            return None
        client = self.client
        if self._periods == TEMPO_PERIODS:
            values = client.band_values
            counters = {
                period: values.get(band_key(band_id))
                for band_id, period in TEMPO_BAND_PERIODS.items()
            }
        else:
            counters = {"hc": client.kwh_hc_ns, "hp": client.kwh_hp_ns}
        return self._tariff_period.update(client.stat_date, counters)

    def _current_tariff_band(self):
        """Return the name of the current tariff band, None if not known."""
        if not self._band_names:
            return None
        values = self.client.band_values
        key = self._tariff_band.update(self.client.stat_date, {
            key: values.get(key) for key in self._band_names})
        return self._band_names.get(key)

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
        self._check_unknown_bands()
        return {
            # Energy of the tariff bands, by key of their sensor
            **self.client.band_values,
            "current_tariff_period": self._current_tariff_period(),
            "current_tariff_band": self._current_tariff_band(),
            "gateway_firmware_version": self.client.gateway_firmware_version,
            "stat_date": self.client.stat_date,
            "realtime_consumption": self.client.realtime_conso,
            "realtime_apparent_power": self.client.realtime_va,
            "grid_consumption": self.client.kwh,
            "hc_grid_consumption": self.client.kwh_hc_ns,
            "hp_grid_consumption": self.client.kwh_hp_ns,
            "production_surplus": self.client.kwh_prod,
            "indoor_temp": self.client.indoor_temp,
            "outdoor_temp": self.client.outdoor_temp,
            "indoor_hum": self.client.indoor_hum,
            "outdoor_hum": self.client.outdoor_hum,
        }


class LittleMonkeySlowCoordinator(DataUpdateCoordinator):
    """Fetch data of the account that ecojoko is slow to compute.

    It is apart from the polls, and its values change slowly. A failure
    never makes the real-time sensors unavailable, and the last values are
    kept for CONF_API_ACTIVITY_GRACE seconds.
    """

    config_entry: ConfigEntry
    # Name of the data, in the logs, and seconds between two readings
    KIND = ""
    REFRESH = CONF_API_ACTIVITY_REFRESH

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
            name=f"{DOMAIN} {self.KIND}",
            update_interval=timedelta(seconds=self.REFRESH),
        )

    async def _async_fetch(self) -> dict:
        """Read the data from ecojoko."""
        raise NotImplementedError

    async def _async_update_data(self):
        """Read the data, or keep the last values during a short failure."""
        try:
            data = await self._async_fetch()
        except LittleMonkeyApiClientError as exception:
            if (
                self.data is not None
                and self._last_success is not None
                and time.monotonic() - self._last_success < CONF_API_ACTIVITY_GRACE
            ):
                LOGGER.debug(
                    "ecojoko %s not read, the last values are kept: %s",
                    self.KIND, exception)
                return self.data
            raise UpdateFailed(exception) from exception
        self._last_success = time.monotonic()
        return data


class LittleMonkeyActivityCoordinator(LittleMonkeySlowCoordinator):
    """Fetch the activity of the account (savings over 7 days...)."""

    KIND = "activity"

    async def _async_fetch(self) -> dict:
        """Read the activity of the account."""
        return await self.client.async_get_activity()


class LittleMonkeySavingsCoordinator(LittleMonkeySlowCoordinator):
    """Fetch the savings: over 12 months, this week, month and year."""

    KIND = "savings"
    REFRESH = CONF_API_SAVINGS_REFRESH

    async def _async_fetch(self) -> dict:
        """Read the savings of the account."""
        return await self.client.async_get_savings()
