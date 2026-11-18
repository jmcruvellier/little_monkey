"""DataUpdateCoordinator for little_monkey."""
from __future__ import annotations

import asyncio
import time
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .api import (
    LittleMonkeyApiClient,
    LittleMonkeyApiClientAuthenticationError,
    LittleMonkeyApiClientCommunicationError,
    LittleMonkeyApiClientError,
    TZ,
)
from .const import (
    CONF_API_ACTIVITY_GRACE,
    CONF_API_ACTIVITY_REFRESH,
    CONF_API_EQUIPMENT_REFRESH,
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
from .utils import TariffPeriod, get_current_date

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
            "contract": self.client.contract,
            # Equipments of the gateway by id, for their diagnostic sensors
            "equipments": {
                equipment["id"]: equipment for equipment in self.client.equipments},
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


class LittleMonkeyEquipmentCoordinator(LittleMonkeySlowCoordinator):
    """Fetch the piloted equipments: their state and their measures of the day.

    The list of the equipments comes with the list of the gateways, read
    every five minutes; the state of a piloted one is read more often, and
    right after a command.
    """

    KIND = "equipment"
    REFRESH = CONF_API_EQUIPMENT_REFRESH
    # Seconds after the end of a forced mode or of an absence before the
    # equipment is read again: ecojoko takes a few seconds to apply it
    END_DELAY = 10

    def __init__(self, *args, **kwargs) -> None:
        """Initialize, without a reading planned at the end of a mode."""
        super().__init__(*args, **kwargs)
        self._end_unsub = None

    def piloted(self) -> list:
        """Return the equipments of the gateway that can be piloted."""
        return [equipment for equipment in self.client.equipments if equipment["controls"]]

    async def _async_fetch(self) -> dict:
        """Read each piloted equipment and its measures of today."""
        today = get_current_date(TZ)

        async def read(equipment):
            fresh, day = await asyncio.gather(
                self.client.async_get_equipment(equipment["id"]),
                self.client.async_get_equipment_day(equipment, today))
            return {**fresh, "day": day}

        equipments = await asyncio.gather(*(read(equipment) for equipment in self.piloted()))
        data = {equipment["id"]: equipment for equipment in equipments}
        self._plan_end_reading(data)
        return data

    def _plan_end_reading(self, equipments: dict) -> None:
        """Read the equipments again just after the end of a forced mode.

        Without it, the end of a forced mode or of an absence would be seen
        up to two minutes late, at the next reading. A mode that should have
        ended in the last minute, still forced in ecojoko, is read again
        shortly as well.
        """
        self.async_cancel_end_reading()
        now = dt_util.utcnow()
        delays = []
        for equipment in equipments.values():
            until = dt_util.parse_datetime(equipment["state"].get("until") or "")
            if until is not None:
                delays.append((until - now).total_seconds())
        delays = [delay for delay in delays if -60 < delay < self.REFRESH]
        if delays:
            self._end_unsub = async_call_later(
                self.hass, max(min(delays), 0) + self.END_DELAY, self._async_end_reading)

    async def _async_end_reading(self, _now) -> None:
        """Read the equipments at the end of a mode."""
        self._end_unsub = None
        await self.async_refresh()

    def async_cancel_end_reading(self) -> None:
        """Cancel the reading planned at the end of a mode."""
        if self._end_unsub is not None:
            self._end_unsub()
            self._end_unsub = None

    async def async_command(self, equipment_id, mode, seconds=None) -> None:
        """Pilot an equipment, then read it again to show its new state.

        It is read again even when the command failed: ecojoko may have
        applied it without answering in time.
        """
        try:
            await self.client.async_send_equipment_command(equipment_id, mode, seconds)
        except LittleMonkeyApiClientError as exception:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(exception)},
            ) from exception
        finally:
            await self.async_refresh()
