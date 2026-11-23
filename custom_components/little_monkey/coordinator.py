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
    CONF_API_EQUIPMENT_POWER_REFRESH,
    CONF_API_EQUIPMENT_REFRESH,
    CONF_API_EQUIPMENT_SWITCHES_REFRESH,
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
from .tariff import band_key, has_sensor
from .utils import DayParts, TariffPeriod, get_current_date

# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities


def unknown_bands_issue_id(entry_id: str) -> str:
    """Return the id of the repair issue of the bands not configured of an entry."""
    return f"unknown_bands_{entry_id}"


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
        # Id of the band of each key, for the price of a kWh now
        self._band_ids = {
            band["key"]: band["id"] for band in entry.data.get(CONF_TARIFF_BANDS) or []}
        # HC/HP category of each band: the period of the current band
        self._band_categories = {
            band["key"]: band.get("category") for band in entry.data.get(CONF_TARIFF_BANDS) or []}
        self._current_band_key = None
        self._tariff_band = TariffPeriod()
        # The HC and HP totals, and the tariff bands having a sensor, split
        # the grid consumption: their sum never exceeds it (see DayParts)
        self._day_parts = [
            DayParts(("hc_grid_consumption", "hp_grid_consumption")),
            DayParts(
                band["key"] for band in entry.data.get(CONF_TARIFF_BANDS) or []
                if has_sensor(band)),
        ]

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

    def day_parts(self, key):
        """Return the parts of the grid consumption a sensor belongs to, or None."""
        for parts in self._day_parts:
            if key in parts.keys:
                return parts
        return None

    @property
    def unknown_bands_issue_id(self) -> str:
        """Return the id of the repair issue of the bands not configured."""
        return unknown_bands_issue_id(self.config_entry.entry_id)

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
        period = self._tariff_period.update(client.stat_date, counters)
        if self._periods != TEMPO_PERIODS and self._current_band_key is not None:
            # The current band tells the period: HC, HP, or none for a band
            # in neither total (Heures Weekend...), whose counter alone
            # increases while the HC/HP period would stay the one before
            category = self._band_categories.get(self._current_band_key)
            return category if category in ("hc", "hp") else None
        return period

    def _current_tariff_band(self):
        """Return the name of the current tariff band, None if not known."""
        if not self._band_names:
            return None
        values = self.client.band_values
        key = self._tariff_band.update(self.client.stat_date, {
            key: values.get(key) for key in self._band_names})
        self._current_band_key = key
        return self._band_names.get(key)

    def _current_price(self, band_prices) -> float | None:
        """Return the price of a kWh of the current tariff band, None if not known.

        The price entered in the options, else ecojoko's, else estimated.
        """
        band_id = self._band_ids.get(self._current_band_key)
        return (band_prices.get(band_id) or {}).get("price")

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
            # The current band first: it tells the period
            "current_tariff_band": self._current_tariff_band(),
            "current_tariff_period": self._current_tariff_period(),
            "gateway_firmware_version": self.client.gateway_firmware_version,
            "contract": self.client.contract,
            # Price of a kWh of the solar surplus sold, None without a sale
            "resale_price": self.client.resale_price,
            # Equipments of the gateway by id, for their diagnostic sensors
            "equipments": {
                equipment["id"]: equipment for equipment in self.client.equipments},
            # Price of a kWh of each band, by band id, and of the current one
            "band_prices": (band_prices := self.client.band_prices),
            # Prices of the contract entered by the user for today, or None
            "entered_prices": self.client.entered_prices,
            # After the current band, which it needs
            "current_price": self._current_price(band_prices),
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
    right after a command. Its measures of the day are read less often than
    its state, by part, and again after a command and on a new day.
    """

    KIND = "equipment"
    REFRESH = CONF_API_EQUIPMENT_REFRESH
    # Seconds between two readings of each part of the measures of the day
    DAY_REFRESH = {
        "power": CONF_API_EQUIPMENT_POWER_REFRESH,
        "switches": CONF_API_EQUIPMENT_SWITCHES_REFRESH,
    }
    # A part is read at the first reading of the state that comes this close
    # to its delay: the readings do not fall exactly on it
    DAY_MARGIN = 5
    # Seconds after the end of a forced mode or of an absence before the
    # equipment is read again: ecojoko takes a few seconds to apply it
    END_DELAY = 10

    def __init__(self, *args, **kwargs) -> None:
        """Initialize, without a reading planned at the end of a mode."""
        super().__init__(*args, **kwargs)
        self._end_unsub = None
        # Monotonic time of the last reading of each part of the measures of
        # the day, by equipment, and whether all of them are read next time
        self._day_reads = {}
        self._read_whole_day = False

    def _day_parts(self, equipment_id, day, now, whole) -> list:
        """Return the parts of the measures of the day to read now."""
        last = ((self.data or {}).get(equipment_id) or {}).get("day") or {}
        reads = self._day_reads.get(equipment_id, {})
        if whole or last.get("date") != day.isoformat():
            return list(self.DAY_REFRESH)
        return [
            part for part, refresh in self.DAY_REFRESH.items()
            if part not in reads or now - reads[part] >= refresh - self.DAY_MARGIN
        ]

    def piloted(self) -> list:
        """Return the equipments of the gateway that can be piloted."""
        return [equipment for equipment in self.client.equipments if equipment["controls"]]

    async def _async_fetch(self) -> dict:
        """Read each piloted equipment and its measures of today."""
        today = get_current_date(TZ)
        now = time.monotonic()
        whole, self._read_whole_day = self._read_whole_day, False

        async def read(equipment):
            equipment_id = equipment["id"]
            parts = self._day_parts(equipment_id, today, now, whole)
            last = ((self.data or {}).get(equipment_id) or {}).get("day") or {}

            async def read_day():
                if not parts:
                    return {}
                return await self.client.async_get_equipment_day(equipment, today, parts)

            fresh, day = await asyncio.gather(
                self.client.async_get_equipment(equipment_id), read_day())
            if day.get("date", today.isoformat()) == last.get("date"):
                # The parts not read now keep their last values of the day
                day = {**last, **day}
            return {**fresh, "day": day}, parts

        equipments = await asyncio.gather(*(read(equipment) for equipment in self.piloted()))
        data = {equipment["id"]: equipment for equipment, _parts in equipments}
        # Once every equipment is read: a failure reads all of them again
        for equipment, parts in equipments:
            self._day_reads.setdefault(equipment["id"], {}).update(dict.fromkeys(parts, now))
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
        """Read the equipments at the end of a mode, with their measures of the day."""
        self._end_unsub = None
        self._read_whole_day = True
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
            self._read_whole_day = True
            await self.async_refresh()
