"""Base classes for HA Bluetooth scanners for bluetooth."""

from __future__ import annotations

import asyncio
import logging
import warnings
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Final, final

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak_retry_connector import NO_RSSI_VALUE, Allocations
from bluetooth_adapters import adapter_human_name
from bluetooth_data_tools import monotonic_time_coarse, parse_advertisement_data_bytes

from .central_manager import get_manager
from .const import (
    CALLBACK_TYPE,
    CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    SCANNER_WATCHDOG_INTERVAL,
    SCANNER_WATCHDOG_TIMEOUT,
)
from .models import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    HaBluetoothConnector,
    HaScannerDetails,
    HaScannerType,
)
from .scanner_device import BluetoothScannerDevice
from .storage import DiscoveredDeviceAdvertisementData

SCANNER_WATCHDOG_INTERVAL_SECONDS: Final = SCANNER_WATCHDOG_INTERVAL.total_seconds()
_LOGGER = logging.getLogger(__name__)


_bytes = bytes
_float = float
_int = int
_str = str


class BaseHaScanner:
    """Base class for high availability BLE scanners."""

    __slots__ = (
        "_cancel_track",
        "_cancel_watchdog",
        "_connect_failures",
        "_connect_in_progress",
        "_connecting",
        "_details",
        "_expire_seconds",
        "_last_detection",
        "_loop",
        "_manager",
        "_previous_service_info",
        "_start_time",
        "adapter",
        "connectable",
        "connector",
        "current_mode",
        "details",
        "name",
        "requested_mode",
        "scanning",
        "source",
    )

    def __init__(
        self,
        source: str,
        adapter: str,
        connector: HaBluetoothConnector | None = None,
        connectable: bool = False,
        requested_mode: BluetoothScanningMode | None = None,
        current_mode: BluetoothScanningMode | None = None,
    ) -> None:
        """Initialize the scanner."""
        self.connectable = connectable
        self.source = source
        self.connector = connector
        self._connecting = 0
        self.adapter = adapter
        self.name = adapter_human_name(adapter, source) if adapter != source else source
        self.scanning: bool = True
        self.requested_mode = requested_mode
        self.current_mode = current_mode
        self._last_detection = 0.0
        self._start_time = 0.0
        self._cancel_watchdog: asyncio.TimerHandle | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._manager = get_manager()
        # Determine scanner type based on class type
        scanner_type = HaScannerType.UNKNOWN
        if isinstance(self, BaseHaRemoteScanner):
            scanner_type = HaScannerType.REMOTE
        # Try to get adapter type from manager's cached adapters
        elif (
            (adapters := self._manager.get_cached_bluetooth_adapters())
            and (adapter_details := adapters.get(adapter))
            and (adapter_type := adapter_details.get("adapter_type"))
        ):
            if adapter_type == "usb":
                scanner_type = HaScannerType.USB
            elif adapter_type == "uart":
                scanner_type = HaScannerType.UART
        self.details = HaScannerDetails(
            source=self.source,
            connectable=self.connectable,
            name=self.name,
            adapter=self.adapter,
            scanner_type=scanner_type,
        )
        self._previous_service_info: dict[str, BluetoothServiceInfoBleak] = {}
        # Scanners only care about connectable devices. The manager
        # will handle taking care of availability for non-connectable devices
        self._expire_seconds = CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
        self._details: dict[str, str | HaBluetoothConnector] = {"source": source}
        self._cancel_track: asyncio.TimerHandle | None = None
        self._connect_failures: dict[str, int] = {}
        self._connect_in_progress: dict[str, int] = {}

    def _on_start_success(self) -> None:
        """
        Called when the scanner successfully starts.

        Notifies the manager that this scanner has started.
        """
        if self._manager:
            self._manager.on_scanner_start(self)

    def _clear_connection_history(self) -> None:
        """Clear the connection history for a scanner."""
        self._connect_failures.clear()
        self._connect_in_progress.clear()

    def _finished_connecting(self, address: str, connected: bool) -> None:
        """Finished connecting."""
        self._remove_connecting(address)
        if connected:
            self._clear_connect_failure(address)
        else:
            self._add_connect_failure(address)

    def _increase_count(self, target: dict[str, int], address: str) -> None:
        """Increase the reference count."""
        if address in target:
            target[address] += 1
        else:
            target[address] = 1

    def _add_connect_failure(self, address: str) -> None:
        """Add a connect failure."""
        self._increase_count(self._connect_failures, address)

    def _add_connecting(self, address: str) -> None:
        """Add a connecting."""
        self._increase_count(self._connect_in_progress, address)
        # Clear timing collection data when scanner pauses for connection
        # to prevent collecting invalid advertising interval data
        self._manager._advertisement_tracker.async_scanner_paused(self.source)

    def _remove_connecting(self, address: str) -> None:
        """Remove a connecting."""
        if address not in self._connect_in_progress:
            _LOGGER.warning(
                "Removing a non-existing connecting %s %s", self.name, address
            )
            return
        self._connect_in_progress[address] -= 1
        if not self._connect_in_progress[address]:
            del self._connect_in_progress[address]

    def _clear_connect_failure(self, address: str) -> None:
        """Clear a connect failure."""
        self._connect_failures.pop(address, None)

    def get_allocations(self) -> Allocations | None:
        """
        Get current connection slot allocations for this scanner.

        Returns:
            Allocations object with free/limit/allocated info, or None if not available.

        Note:
            Subclasses should override this method to provide their allocation info.
            For local adapters, this will be overridden in HaScanner to query
            BleakSlotManager.
            For remote scanners, they should override to return their own tracking.

        """
        return None

    def _score_connection_paths(
        self, rssi_diff: _int, scanner_device: BluetoothScannerDevice
    ) -> float:
        """Score the connection paths considering slot availability."""
        address = scanner_device.ble_device.address
        score = scanner_device.advertisement.rssi or NO_RSSI_VALUE
        scanner_connections_in_progress = len(self._connect_in_progress)
        previous_failures = self._connect_failures.get(address, 0)

        # Use a minimum rssi_diff of 1 to ensure penalties are meaningful
        # even when scanners have identical RSSI
        effective_rssi_diff = max(rssi_diff, 1)

        # Penalize scanners with connections in progress
        if scanner_connections_in_progress:
            # Very large penalty for multiple connections in progress
            # to avoid overloading the adapter
            score -= effective_rssi_diff * scanner_connections_in_progress * 1.01

        # Penalize based on previous failures
        if previous_failures:
            score -= effective_rssi_diff * previous_failures * 0.51

        # Consider connection slot availability
        allocation = self.get_allocations()
        if allocation and allocation.slots > 0:
            if allocation.free == 0:
                # No slots available - return NO_RSSI_VALUE to indicate unavailable
                return NO_RSSI_VALUE
            if allocation.free == 1:
                # Last slot available - small penalty to prefer adapters with more slots
                score -= effective_rssi_diff * 0.76

        return score

    def _connections_in_progress(self) -> int:
        """Return if the connection is in progress."""
        in_progress = 0
        for count in self._connect_in_progress.values():
            in_progress += count
        return in_progress

    def _connection_failures(self, address: str) -> int:
        """Return the number of failures."""
        return self._connect_failures.get(address, 0)

    def time_since_last_detection(self) -> float:
        """Return the time since the last detection."""
        return monotonic_time_coarse() - self._last_detection

    @property
    def adapter_idx(self) -> int | None:
        """Return the adapter index if this is an hci adapter, None otherwise."""
        if self.adapter and self.adapter.startswith("hci"):
            return int(self.adapter.removeprefix("hci"))
        return None

    def async_setup(self) -> CALLBACK_TYPE:
        """Set up the scanner."""
        self._loop = asyncio.get_running_loop()
        self._schedule_expire_devices()
        return self._unsetup

    def _async_stop_scanner_watchdog(self) -> None:
        """Stop the scanner watchdog."""
        if self._cancel_watchdog:
            self._cancel_watchdog.cancel()
            self._cancel_watchdog = None

    def _async_setup_scanner_watchdog(self) -> None:
        """If something has restarted or updated, we need to restart the scanner."""
        self._start_time = self._last_detection = monotonic_time_coarse()
        if not self._cancel_watchdog:
            self._schedule_watchdog()

    def _schedule_watchdog(self) -> None:
        """Schedule the watchdog."""
        loop = self._loop
        if TYPE_CHECKING:
            assert loop is not None
        self._cancel_watchdog = loop.call_at(
            loop.time() + SCANNER_WATCHDOG_INTERVAL_SECONDS,
            self._async_call_scanner_watchdog,
        )

    @final
    def _async_call_scanner_watchdog(self) -> None:
        """Call the scanner watchdog and schedule the next one."""
        self._async_scanner_watchdog()
        self._schedule_watchdog()

    def _async_watchdog_triggered(self) -> bool:
        """Check if the watchdog has been triggered."""
        time_since_last_detection = self.time_since_last_detection()
        _LOGGER.debug(
            "%s: Scanner watchdog time_since_last_detection: %s",
            self.name,
            time_since_last_detection,
        )
        return time_since_last_detection > SCANNER_WATCHDOG_TIMEOUT

    def _async_scanner_watchdog(self) -> None:
        """
        Check if the scanner is running.

        Override this method if you need to do something else when the watchdog
        is triggered.
        """
        if self._async_watchdog_triggered():
            _LOGGER.debug(
                (
                    "%s: Bluetooth scanner has gone quiet for %ss, check logs on the"
                    " scanner device for more information"
                ),
                self.name,
                self.time_since_last_detection(),
            )
            self.scanning = False
            return
        self.scanning = not self._connecting

    def _unsetup(self) -> None:
        """Unset up the scanner."""
        self._cancel_expire_devices()

    @contextmanager
    def connecting(self) -> Generator[None, None, None]:
        """Context manager to track connecting state."""
        self._connecting += 1
        self.scanning = not self._connecting
        try:
            yield
        finally:
            self._connecting -= 1
            self.scanning = not self._connecting

    @property
    def discovered_devices(self) -> list[BLEDevice]:
        """Return a list of discovered devices."""
        raise NotImplementedError

    @property
    def discovered_devices_and_advertisement_data(
        self,
    ) -> dict[str, tuple[BLEDevice, AdvertisementData]]:
        """Return a list of discovered devices and their advertisement data."""
        raise NotImplementedError

    @property
    def discovered_addresses(self) -> Iterable[str]:
        """Return an iterable of discovered devices."""
        raise NotImplementedError

    def get_discovered_device_advertisement_data(
        self, address: str
    ) -> tuple[BLEDevice, AdvertisementData] | None:
        """Return the advertisement data for a discovered device."""
        raise NotImplementedError

    async def async_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic information about the scanner."""
        device_adv_datas = self.discovered_devices_and_advertisement_data.values()
        return {
            "name": self.name,
            "connectable": self.connectable,
            "start_time": self._start_time,
            "source": self.source,
            "scanning": self.scanning,
            "requested_mode": self.requested_mode,
            "current_mode": self.current_mode,
            "type": self.__class__.__name__,
            "last_detection": self._last_detection,
            "monotonic_time": monotonic_time_coarse(),
            "discovered_devices_and_advertisement_data": [
                {
                    "name": device.name,
                    "address": device.address,
                    "rssi": advertisement_data.rssi,
                    "advertisement_data": advertisement_data,
                    "details": device.details,
                }
                for device, advertisement_data in device_adv_datas
            ],
        }

    def restore_discovered_devices(
        self, history: DiscoveredDeviceAdvertisementData
    ) -> None:
        """Restore discovered devices from a previous run."""
        discovered_device_timestamps = history.discovered_device_timestamps
        self._previous_service_info = {
            address: BluetoothServiceInfoBleak(
                device.name or address,
                address,
                adv.rssi,
                adv.manufacturer_data,
                adv.service_data,
                adv.service_uuids,
                self.source,
                device,
                adv,
                self.connectable,
                discovered_device_timestamps[address],
                adv.tx_power,
                history.discovered_device_raw.get(address),
            )
            for address, (
                device,
                adv,
            ) in history.discovered_device_advertisement_datas.items()
        }
        # Expire anything that is too old
        self._async_expire_devices()

    def serialize_discovered_devices(
        self,
    ) -> DiscoveredDeviceAdvertisementData:
        """Serialize discovered devices to be stored."""
        return DiscoveredDeviceAdvertisementData(
            self.connectable,
            self._expire_seconds,
            self._build_discovered_device_advertisement_datas(),
            self._build_discovered_device_timestamps(),
            self._build_discovered_device_raw(),
        )

    @property
    def _discovered_device_timestamps(self) -> dict[str, float]:
        """Return a dict of discovered device timestamps."""
        warnings.warn(
            "BaseHaRemoteScanner._discovered_device_timestamps is deprecated "
            "and will be removed in a future version of habluetooth, use "
            "BaseHaRemoteScanner.discovered_device_timestamps instead",
            FutureWarning,
            stacklevel=2,
        )
        return self._build_discovered_device_timestamps()

    @property
    def discovered_device_timestamps(self) -> dict[str, float]:
        """Return a dict of discovered device timestamps."""
        return self._build_discovered_device_timestamps()

    def _build_discovered_device_advertisement_datas(
        self,
    ) -> dict[str, tuple[BLEDevice, AdvertisementData]]:
        """Return a list of discovered devices and advertisement data."""
        return {
            address: (info.device, info._advertisement_internal())
            for address, info in self._previous_service_info.items()
        }

    def _build_discovered_device_timestamps(self) -> dict[str, float]:
        """Return a dict of discovered device timestamps."""
        return {
            address: info.time for address, info in self._previous_service_info.items()
        }

    def _build_discovered_device_raw(self) -> dict[str, bytes | None]:
        """Return a dict of discovered device raw advertisement data."""
        return {
            address: info.raw for address, info in self._previous_service_info.items()
        }

    def _async_on_raw_advertisement(
        self,
        address: _str,
        rssi: _int,
        raw: _bytes,
        details: dict[str, Any],
        advertisement_monotonic_time: _float,
    ) -> None:
        if (
            prev_info := self._previous_service_info.get(address)
        ) is not None and prev_info.raw == raw:
            # Raw advertisement data unchanged — skip parsing and merge
            # logic, reuse the previous parsed data directly.
            self.scanning = not self._connecting
            self._last_detection = advertisement_monotonic_time
            info = BluetoothServiceInfoBleak.__new__(BluetoothServiceInfoBleak)
            info.device = prev_info.device
            info.name = prev_info.name
            info.manufacturer_data = prev_info.manufacturer_data
            info.service_data = prev_info.service_data
            info.service_uuids = prev_info.service_uuids
            info.address = address
            info.rssi = rssi
            info.source = self.source
            info._advertisement = None
            info.connectable = self.connectable
            info.time = advertisement_monotonic_time
            info.tx_power = prev_info.tx_power
            info.raw = prev_info.raw
            self._previous_service_info[address] = info
            self._manager._scanner_adv_received(info)
            return
        parsed = parse_advertisement_data_bytes(raw)
        self._async_on_advertisement_internal(
            address,
            rssi,
            parsed[0],
            parsed[1],
            parsed[2],
            parsed[3],
            parsed[4],
            details,
            advertisement_monotonic_time,
            raw,
        )

    def _async_on_advertisement(
        self,
        address: _str,
        rssi: _int,
        local_name: _str | None,
        service_uuids: list[str],
        service_data: dict[str, bytes],
        manufacturer_data: dict[int, bytes],
        tx_power: _int | None,
        details: dict[Any, Any],
        advertisement_monotonic_time: _float,
    ) -> None:
        self._async_on_advertisement_internal(
            address,
            rssi,
            local_name,
            service_uuids,
            service_data,
            manufacturer_data,
            tx_power,
            details,
            advertisement_monotonic_time,
            None,
        )

    def _async_on_advertisement_internal(
        self,
        address: _str,
        rssi: _int,
        local_name: _str | None,
        service_uuids: list[str],
        service_data: dict[str, bytes],
        manufacturer_data: dict[int, bytes],
        tx_power: _int | None,
        details: dict[Any, Any],
        advertisement_monotonic_time: _float,
        raw: _bytes | None,
    ) -> None:
        """Call the registered callback."""
        self.scanning = not self._connecting
        self._last_detection = advertisement_monotonic_time
        info = BluetoothServiceInfoBleak.__new__(BluetoothServiceInfoBleak)

        if (prev_info := self._previous_service_info.get(address)) is None:
            # We expect this is the rare case and since py3.11+ has
            # near zero cost try on success, and we can avoid .get()
            # which is slower than [] we use the try/except pattern.
            info.device = BLEDevice(
                address,
                local_name,
                {**self._details, **details},
            )
            info.manufacturer_data = manufacturer_data
            info.service_data = service_data
            info.service_uuids = service_uuids
            info.name = local_name or address
        else:
            # Merge the new data with the old data
            # to function the same as BlueZ which
            # merges the dicts on PropertiesChanged
            info.device = prev_info.device
            prev_name = prev_info.device.name
            #
            # Bleak updates the BLEDevice via create_or_update_device.
            # We need to do the same to ensure integrations that already
            # have the BLEDevice object get the updated details when they
            # change.
            #
            # https://github.com/hbldh/bleak/blob/222618b7747f0467dbb32bd3679f8cfaa19b1668/bleak/backends/scanner.py#L203
            if prev_name is not None and (
                prev_name is local_name
                or not local_name
                or len(prev_name) > len(local_name)
            ):
                info.name = prev_name
            else:
                info.device.name = local_name
                info.name = local_name if local_name else address

            has_service_uuids = bool(service_uuids)
            if (
                has_service_uuids
                and service_uuids is not prev_info.service_uuids
                and service_uuids != prev_info.service_uuids
            ):
                info.service_uuids = list({*service_uuids, *prev_info.service_uuids})
            elif not has_service_uuids:
                info.service_uuids = prev_info.service_uuids
            else:
                info.service_uuids = service_uuids

            has_service_data = bool(service_data)
            if has_service_data and service_data is not prev_info.service_data:
                for uuid, sub_value in service_data.items():
                    if (
                        super_value := prev_info.service_data.get(uuid)
                    ) is None or super_value != sub_value:
                        info.service_data = {
                            **prev_info.service_data,
                            **service_data,
                        }
                        break
                else:
                    info.service_data = prev_info.service_data
            elif not has_service_data:
                info.service_data = prev_info.service_data
            else:
                info.service_data = service_data

            has_manufacturer_data = bool(manufacturer_data)
            if (
                has_manufacturer_data
                and manufacturer_data is not prev_info.manufacturer_data
            ):
                for id_, sub_value in manufacturer_data.items():
                    if (
                        super_value := prev_info.manufacturer_data.get(id_)
                    ) is None or super_value != sub_value:
                        info.manufacturer_data = {
                            **prev_info.manufacturer_data,
                            **manufacturer_data,
                        }
                        break
                else:
                    info.manufacturer_data = prev_info.manufacturer_data
            elif not has_manufacturer_data:
                info.manufacturer_data = prev_info.manufacturer_data
            else:
                info.manufacturer_data = manufacturer_data

        info.address = address
        info.rssi = rssi
        info.source = self.source
        info._advertisement = None
        info.connectable = self.connectable
        info.time = advertisement_monotonic_time
        info.tx_power = tx_power
        info.raw = raw
        self._previous_service_info[address] = info
        self._manager._scanner_adv_received(info)

    def _async_expire_devices(self) -> None:
        """Expire old devices."""
        now = monotonic_time_coarse()
        expired = [
            address
            for address, info in self._previous_service_info.items()
            if now - info.time > self._expire_seconds
        ]
        for address in expired:
            del self._previous_service_info[address]

    def _cancel_expire_devices(self) -> None:
        """Cancel the expiration of old devices."""
        if self._cancel_track:
            self._cancel_track.cancel()
            self._cancel_track = None

    def _schedule_expire_devices(self) -> None:
        """Schedule the expiration of old devices."""
        loop = self._loop
        if TYPE_CHECKING:
            assert loop is not None
        self._cancel_expire_devices()
        self._cancel_track = loop.call_at(
            loop.time() + 30, self._async_expire_devices_schedule_next
        )

    def _async_expire_devices_schedule_next(self) -> None:
        """Expire old devices and schedule the next expiration."""
        self._async_expire_devices()
        self._schedule_expire_devices()

    def set_requested_mode(self, mode: BluetoothScanningMode | None) -> None:
        """Set the requested scanning mode and notify the manager."""
        if self.requested_mode != mode:
            self.requested_mode = mode
            self._manager.scanner_mode_changed(self)

    def set_current_mode(self, mode: BluetoothScanningMode | None) -> None:
        """Set the current scanning mode and notify the manager."""
        if self.current_mode != mode:
            self.current_mode = mode
            self._manager.scanner_mode_changed(self)


class BaseHaRemoteScanner(BaseHaScanner):
    """Base class for a high availability remote BLE scanner."""

    def _unsetup(self) -> None:
        """Unset up the scanner."""
        super()._unsetup()
        self._async_stop_scanner_watchdog()

    def async_setup(self) -> CALLBACK_TYPE:
        """Set up the scanner."""
        super().async_setup()
        self._async_setup_scanner_watchdog()
        return self._unsetup

    @property
    def discovered_devices(self) -> list[BLEDevice]:
        """Return a list of discovered devices."""
        infos = self._previous_service_info.values()
        return [device_advertisement_data.device for device_advertisement_data in infos]

    @property
    def discovered_devices_and_advertisement_data(
        self,
    ) -> dict[str, tuple[BLEDevice, AdvertisementData]]:
        """Return a list of discovered devices and advertisement data."""
        return self._build_discovered_device_advertisement_datas()

    @property
    def discovered_addresses(self) -> Iterable[str]:
        """Return an iterable of discovered devices."""
        return self._previous_service_info

    def get_discovered_device_advertisement_data(
        self, address: str
    ) -> tuple[BLEDevice, AdvertisementData] | None:
        """Return the advertisement data for a discovered device."""
        if (info := self._previous_service_info.get(address)) is not None:
            return info.device, info.advertisement
        return None

    async def async_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic information about the scanner."""
        now = monotonic_time_coarse()
        discovered_device_timestamps = self._build_discovered_device_timestamps()
        return await super().async_diagnostics() | {
            "discovered_device_timestamps": discovered_device_timestamps,
            "raw_advertisement_data": {
                address: info.raw
                for address, info in self._previous_service_info.items()
            },
            "time_since_last_device_detection": {
                address: now - timestamp
                for address, timestamp in discovered_device_timestamps.items()
            },
        }
