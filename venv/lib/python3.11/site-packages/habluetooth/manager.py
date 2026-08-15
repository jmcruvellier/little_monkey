"""The bluetooth integration."""

from __future__ import annotations

import asyncio
import itertools
import logging
import platform
from collections.abc import Callable, Iterable
from dataclasses import asdict
from functools import partial
from typing import TYPE_CHECKING, Any, Final

from bleak.backends.scanner import AdvertisementDataCallback
from bleak_retry_connector import (
    NO_RSSI_VALUE,
    AllocationChangeEvent,
    Allocations,
    BleakSlotManager,
)
from bluetooth_adapters import (
    ADAPTER_ADDRESS,
    ADAPTER_PASSIVE_SCAN,
    AdapterDetails,
    BluetoothAdapters,
    get_adapters,
)
from bluetooth_data_tools import monotonic_time_coarse

from .advertisement_tracker import (
    TRACKER_BUFFERING_WOBBLE_SECONDS,
    AdvertisementTracker,
)
from .channels.bluez import CONNECTION_ERRORS, MGMTBluetoothCtl
from .const import (
    ADV_RSSI_SWITCH_THRESHOLD,
    CALLBACK_TYPE,
    FAILED_ADAPTER_MAC,
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    UNAVAILABLE_TRACK_SECONDS,
)
from .models import (
    BluetoothServiceInfoBleak,
    HaBluetoothSlotAllocations,
    HaScannerModeChange,
    HaScannerRegistration,
    HaScannerRegistrationEvent,
)
from .scanner_device import BluetoothScannerDevice
from .usage import install_multiple_bleak_catcher, uninstall_multiple_bleak_catcher
from .util import async_reset_adapter

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData

    from .base_scanner import BaseHaScanner
    from .scanner import HaScanner


SYSTEM = platform.system()
IS_LINUX = SYSTEM == "Linux"

FILTER_UUIDS: Final = "UUIDs"

APPLE_MFR_ID: Final = 76
APPLE_IBEACON_START_BYTE: Final = 0x02  # iBeacon (tilt_ble)
APPLE_HOMEKIT_START_BYTE: Final = 0x06  # homekit_controller
APPLE_DEVICE_ID_START_BYTE: Final = 0x10  # bluetooth_le_tracker
APPLE_HOMEKIT_NOTIFY_START_BYTE: Final = 0x11  # homekit_controller
APPLE_FINDMY_START_BYTE: Final = 0x12  # FindMy network advertisements


_str = str
_int = int

_LOGGER = logging.getLogger(__name__)


def _dispatch_bleak_callback(
    bleak_callback: BleakCallback,
    device: BLEDevice,
    advertisement_data: AdvertisementData,
) -> None:
    """Dispatch the callback."""
    if (
        uuids := bleak_callback.filters.get(FILTER_UUIDS)
    ) is not None and not uuids.intersection(advertisement_data.service_uuids):
        return

    try:
        bleak_callback.callback(device, advertisement_data)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Error in callback: %s", bleak_callback.callback)


class BleakCallback:
    """Bleak callback."""

    __slots__ = ("callback", "filters")

    def __init__(
        self, callback: AdvertisementDataCallback, filters: dict[str, set[str]]
    ) -> None:
        """Init bleak callback."""
        self.callback = callback
        self.filters = filters


class BluetoothManager:
    """Manage Bluetooth."""

    __slots__ = (
        "_adapter_refresh_future",
        "_adapter_sources",
        "_adapters",
        "_advertisement_tracker",
        "_all_history",
        "_allocations",
        "_allocations_callbacks",
        "_bleak_callbacks",
        "_bluetooth_adapters",
        "_cancel_allocation_callbacks",
        "_cancel_unavailable_tracking",
        "_connectable_history",
        "_connectable_scanners",
        "_connectable_unavailable_callbacks",
        "_connection_history",
        "_debug",
        "_disappeared_callbacks",
        "_fallback_intervals",
        "_intervals",
        "_loop",
        "_mgmt_ctl",
        "_non_connectable_scanners",
        "_recovery_lock",
        "_scanner_mode_change_callbacks",
        "_scanner_registration_callbacks",
        "_side_channel_scanners",
        "_sources",
        "_subclass_discover_info",
        "_unavailable_callbacks",
        "has_advertising_side_channel",
        "shutdown",
        "slot_manager",
    )

    def __init__(
        self,
        bluetooth_adapters: BluetoothAdapters | None = None,
        slot_manager: BleakSlotManager | None = None,
    ) -> None:
        """Init bluetooth manager."""
        self._cancel_unavailable_tracking: asyncio.TimerHandle | None = None

        self._advertisement_tracker = AdvertisementTracker()
        self._fallback_intervals = self._advertisement_tracker.fallback_intervals
        self._intervals = self._advertisement_tracker.intervals

        self._unavailable_callbacks: dict[
            str, set[Callable[[BluetoothServiceInfoBleak], None]]
        ] = {}
        self._connectable_unavailable_callbacks: dict[
            str, set[Callable[[BluetoothServiceInfoBleak], None]]
        ] = {}

        self._bleak_callbacks: set[BleakCallback] = set()
        self._all_history: dict[str, BluetoothServiceInfoBleak] = {}
        self._connectable_history: dict[str, BluetoothServiceInfoBleak] = {}
        self._non_connectable_scanners: set[BaseHaScanner] = set()
        self._connectable_scanners: set[BaseHaScanner] = set()
        self._adapters: dict[str, AdapterDetails] = {}
        self._adapter_sources: dict[str, str] = {}
        self._allocations: dict[str, HaBluetoothSlotAllocations] = {}
        self._sources: dict[str, BaseHaScanner] = {}
        self._bluetooth_adapters = bluetooth_adapters or get_adapters()
        self.slot_manager = slot_manager or BleakSlotManager()
        self._cancel_allocation_callbacks = (
            self.slot_manager.register_allocation_callback(
                self._async_slot_manager_changed
            )
        )
        self._debug = _LOGGER.isEnabledFor(logging.DEBUG)
        self.shutdown = False
        self.has_advertising_side_channel = False
        self._side_channel_scanners: dict[int, HaScanner] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._adapter_refresh_future: asyncio.Future[None] | None = None
        self._recovery_lock: asyncio.Lock = asyncio.Lock()
        self._disappeared_callbacks: set[Callable[[str], None]] = set()
        self._allocations_callbacks: dict[
            str | None, set[Callable[[HaBluetoothSlotAllocations], None]]
        ] = {}
        self._scanner_registration_callbacks: dict[
            str | None, set[Callable[[HaScannerRegistration], None]]
        ] = {}
        self._scanner_mode_change_callbacks: dict[
            str | None, set[Callable[[HaScannerModeChange], None]]
        ] = {}
        self._subclass_discover_info = self._discover_service_info
        self._mgmt_ctl: MGMTBluetoothCtl | None = None
        if (
            self._discover_service_info.__func__  # type: ignore[attr-defined]
            is BluetoothManager._discover_service_info
        ):
            _LOGGER.warning(
                "%s: does not implement _discover_service_info, "
                "subclasses must implement this method to consume "
                "discovery data",
                type(self).__name__,
            )

    @property
    def supports_passive_scan(self) -> bool:
        """Return if passive scan is supported."""
        return any(adapter[ADAPTER_PASSIVE_SCAN] for adapter in self._adapters.values())

    def is_operating_degraded(self) -> bool:
        """
        Return if the manager is operating in degraded mode.

        On Linux, we're in degraded mode if mgmt control is not available.
        This typically means we don't have NET_ADMIN/NET_RAW capabilities.
        """
        return IS_LINUX and self._mgmt_ctl is None

    def on_scanner_start(self, scanner: BaseHaScanner) -> None:
        """
        Called when a scanner starts.

        Subclasses can override this to perform custom actions when a scanner starts.
        """

    def async_scanner_count(self, connectable: bool = True) -> int:
        """Return the number of scanners."""
        if connectable:
            return len(self._connectable_scanners)
        return len(self._connectable_scanners) + len(self._non_connectable_scanners)

    async def async_diagnostics(self) -> dict[str, Any]:
        """Diagnostics for the manager."""
        scanner_diagnostics = await asyncio.gather(
            *[
                scanner.async_diagnostics()
                for scanner in itertools.chain(
                    self._non_connectable_scanners, self._connectable_scanners
                )
            ]
        )
        return {
            "adapters": self._adapters,
            "slot_manager": self.slot_manager.diagnostics(),
            "allocations": {
                source: asdict(allocations)
                for source, allocations in self._allocations.items()
            },
            "scanners": scanner_diagnostics,
            "connectable_history": [
                service_info.as_dict()
                for service_info in self._connectable_history.values()
            ],
            "all_history": [
                service_info.as_dict() for service_info in self._all_history.values()
            ],
            "advertisement_tracker": self._advertisement_tracker.async_diagnostics(),
        }

    def _find_adapter_by_address(self, address: str) -> str | None:
        for adapter, details in self._adapters.items():
            if details[ADAPTER_ADDRESS] == address:
                return adapter
        return None

    def async_scanner_by_source(self, source: str) -> BaseHaScanner | None:
        """Return the scanner for a source."""
        return self._sources.get(source)

    def async_register_disappeared_callback(
        self, callback: Callable[[str], None]
    ) -> CALLBACK_TYPE:
        """Register a callback to be called when an address disappears."""
        self._disappeared_callbacks.add(callback)
        return partial(self._disappeared_callbacks.discard, callback)

    async def _async_refresh_adapters(self) -> None:
        """Refresh the adapters."""
        if self._adapter_refresh_future:
            await self._adapter_refresh_future
            return
        if TYPE_CHECKING:
            assert self._loop is not None
        self._adapter_refresh_future = self._loop.create_future()
        try:
            await self._bluetooth_adapters.refresh()
            self._adapters = self._bluetooth_adapters.adapters
        finally:
            self._adapter_refresh_future.set_result(None)
            self._adapter_refresh_future = None

    def get_cached_bluetooth_adapters(self) -> dict[str, AdapterDetails] | None:
        """Get cached bluetooth adapters synchronously."""
        return self._adapters

    async def async_get_bluetooth_adapters(
        self, cached: bool = True
    ) -> dict[str, AdapterDetails]:
        """Get bluetooth adapters."""
        if not self._adapters or not cached:
            if not cached:
                await self._async_refresh_adapters()
            self._adapters = self._bluetooth_adapters.adapters
        return self._adapters

    async def async_get_adapter_from_address(self, address: str) -> str | None:
        """Get adapter from address."""
        if adapter := self._find_adapter_by_address(address):
            return adapter
        await self._async_refresh_adapters()
        return self._find_adapter_by_address(address)

    async def async_get_adapter_from_address_or_recover(
        self, address: str
    ) -> str | None:
        """Get adapter from address or recover."""
        if adapter := self._find_adapter_by_address(address):
            return adapter
        await self._async_recover_failed_adapters()
        return self._find_adapter_by_address(address)

    async def _async_recover_failed_adapters(self) -> None:
        """Recover failed adapters."""
        if self._recovery_lock.locked():
            # Already recovering, no need to
            # start another recovery
            return
        async with self._recovery_lock:
            adapters = await self.async_get_bluetooth_adapters()
            for adapter in [
                adapter
                for adapter, details in adapters.items()
                if details[ADAPTER_ADDRESS] == FAILED_ADAPTER_MAC
            ]:
                await async_reset_adapter(adapter, FAILED_ADAPTER_MAC, False)
            await self._async_refresh_adapters()

    async def async_setup(self) -> None:
        """Set up the bluetooth manager."""
        from .central_manager import CentralBluetoothManager

        if CentralBluetoothManager.manager is None:
            CentralBluetoothManager.manager = self
        self._loop = asyncio.get_running_loop()
        await self._async_refresh_adapters()
        install_multiple_bleak_catcher()
        self.async_setup_unavailable_tracking()
        if not IS_LINUX:
            return
        self._mgmt_ctl = MGMTBluetoothCtl(10.0, self._side_channel_scanners)
        try:
            await self._mgmt_ctl.setup()
        except PermissionError as ex:
            _LOGGER.error(
                "Missing required permissions for Bluetooth management: %s. "
                "Automatic adapter recovery is unavailable. "
                "Add NET_ADMIN and NET_RAW capabilities to the container to enable it",
                ex,
            )
            self._mgmt_ctl = None
        except CONNECTION_ERRORS as ex:
            _LOGGER.debug("Cannot start Bluetooth Management API: %s", ex)
            self._mgmt_ctl = None
        else:
            self.has_advertising_side_channel = True

    def async_stop(self) -> None:
        """Stop the Bluetooth integration at shutdown."""
        _LOGGER.debug("Stopping bluetooth manager")
        self.shutdown = True
        if self._cancel_unavailable_tracking:
            self._cancel_unavailable_tracking.cancel()
            self._cancel_unavailable_tracking = None
        uninstall_multiple_bleak_catcher()
        self._cancel_allocation_callbacks()
        if self._mgmt_ctl:
            self._mgmt_ctl.close()
            self._mgmt_ctl = None

    def async_scanner_devices_by_address(
        self, address: str, connectable: bool
    ) -> list[BluetoothScannerDevice]:
        """Get BluetoothScannerDevice by address."""
        if not connectable:
            scanners: Iterable[BaseHaScanner] = itertools.chain(
                self._connectable_scanners, self._non_connectable_scanners
            )
        else:
            scanners = self._connectable_scanners
        return [
            BluetoothScannerDevice(scanner, *device_adv)
            for scanner in scanners
            if (device_adv := scanner.get_discovered_device_advertisement_data(address))
        ]

    def _async_all_discovered_addresses(self, connectable: bool) -> Iterable[str]:
        """
        Return all of discovered addresses.

        Include addresses from all the scanners including duplicates.
        """
        yield from itertools.chain.from_iterable(
            scanner.discovered_addresses for scanner in self._connectable_scanners
        )
        if not connectable:
            yield from itertools.chain.from_iterable(
                scanner.discovered_addresses
                for scanner in self._non_connectable_scanners
            )

    def async_discovered_devices(self, connectable: bool) -> list[BLEDevice]:
        """Return all of combined best path to discovered from all the scanners."""
        histories = self._connectable_history if connectable else self._all_history
        return [history.device for history in histories.values()]

    def async_setup_unavailable_tracking(self) -> None:
        """Set up the unavailable tracking."""
        self._schedule_unavailable_tracking()

    def _schedule_unavailable_tracking(self) -> None:
        """Schedule the unavailable tracking."""
        if TYPE_CHECKING:
            assert self._loop is not None
        loop = self._loop
        self._cancel_unavailable_tracking = loop.call_at(
            loop.time() + UNAVAILABLE_TRACK_SECONDS, self._async_check_unavailable
        )

    def _async_check_unavailable(self) -> None:
        """Watch for unavailable devices and cleanup state history."""
        monotonic_now = monotonic_time_coarse()
        connectable_history = self._connectable_history
        all_history = self._all_history
        tracker = self._advertisement_tracker
        intervals = tracker.intervals

        for connectable in (True, False):
            if connectable:
                unavailable_callbacks = self._connectable_unavailable_callbacks
            else:
                unavailable_callbacks = self._unavailable_callbacks
            history = connectable_history if connectable else all_history
            disappeared = set(history).difference(
                self._async_all_discovered_addresses(connectable)
            )
            for address in disappeared:
                if not connectable:
                    #
                    # For non-connectable devices we also check the device has exceeded
                    # the advertising interval before we mark it as unavailable
                    # since it may have gone to sleep and since we do not need an active
                    # connection to it we can only determine its availability
                    # by the lack of advertisements
                    if advertising_interval := (
                        intervals.get(address) or self._fallback_intervals.get(address)
                    ):
                        advertising_interval += TRACKER_BUFFERING_WOBBLE_SECONDS
                    else:
                        advertising_interval = (
                            FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
                        )
                    time_since_seen = monotonic_now - all_history[address].time
                    if time_since_seen <= advertising_interval:
                        continue

                    # The second loop (connectable=False) is responsible for removing
                    # the device from all the interval tracking since it is no longer
                    # available for both connectable and non-connectable
                    tracker.async_remove_fallback_interval(address)
                    tracker.async_remove_address(address)
                    for disappear_callback in self._disappeared_callbacks:
                        try:
                            disappear_callback(address)
                        except Exception:
                            _LOGGER.exception("Error in disappeared callback")
                    self._address_disappeared(address)

                service_info = history.pop(address)

                if not (callbacks := unavailable_callbacks.get(address)):
                    continue

                for callback in callbacks.copy():
                    try:
                        callback(service_info)
                    except Exception:  # pylint: disable=broad-except
                        _LOGGER.exception("Error in unavailable callback")

        self._schedule_unavailable_tracking()

    def _address_disappeared(self, address: str) -> None:
        """
        Call when an address disappears from the stack.

        This method is intended to be overridden by subclasses.
        """

    def _prefer_previous_adv_from_different_source(
        self,
        old: BluetoothServiceInfoBleak,
        new: BluetoothServiceInfoBleak,
    ) -> bool:
        """Prefer previous advertisement from a different source if it is better."""
        if stale_seconds := self._intervals.get(
            new.address, self._fallback_intervals.get(new.address, 0)
        ):
            stale_seconds += TRACKER_BUFFERING_WOBBLE_SECONDS
        else:
            stale_seconds = FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
        if new.time - old.time > stale_seconds:
            # If the old advertisement is stale, any new advertisement is preferred
            if self._debug:
                _LOGGER.debug(
                    "%s (%s): Switching from %s to %s (time elapsed:%s > stale"
                    " seconds:%s)",
                    new.name,
                    new.address,
                    self._async_describe_source(old),
                    self._async_describe_source(new),
                    new.time - old.time,
                    stale_seconds,
                )
            return False
        if (new.rssi or NO_RSSI_VALUE) - ADV_RSSI_SWITCH_THRESHOLD > (
            old.rssi or NO_RSSI_VALUE
        ):
            # If new advertisement is ADV_RSSI_SWITCH_THRESHOLD more,
            # the new one is preferred.
            if self._debug:
                _LOGGER.debug(
                    "%s (%s): Switching from %s to %s (new rssi:%s - threshold:%s >"
                    " old rssi:%s)",
                    new.name,
                    new.address,
                    self._async_describe_source(old),
                    self._async_describe_source(new),
                    new.rssi,
                    ADV_RSSI_SWITCH_THRESHOLD,
                    old.rssi,
                )
            return False
        return True

    def get_bluez_mgmt_ctl(self) -> MGMTBluetoothCtl | None:
        """
        Get the BlueZ management controller if available.

        Returns:
            The MGMTBluetoothCtl instance or None if not available

        """
        return self._mgmt_ctl

    def scanner_adv_received(self, service_info: BluetoothServiceInfoBleak) -> None:
        """
        Handle a new advertisement from any scanner.

        Callbacks from all the scanners arrive here.

        This is the cpdef entry point for external callers.
        Internal callers should use _scanner_adv_received directly
        to avoid cpdef virtual dispatch overhead.
        """
        self._scanner_adv_received(service_info)

    def _scanner_adv_received(self, service_info: BluetoothServiceInfoBleak) -> None:
        """
        Handle a new advertisement from any scanner (internal cdef path).

        Callbacks from all the scanners arrive here.
        """
        # Pre-filter noisy apple devices as they can account for 20-35% of the
        # traffic on a typical network.
        if (
            len(service_info.service_data) == 0
            and len(service_info.manufacturer_data) == 1
            and (apple_data := service_info.manufacturer_data.get(APPLE_MFR_ID))
        ):
            apple_cstr = apple_data
            if apple_cstr[0] not in {
                APPLE_IBEACON_START_BYTE,
                APPLE_HOMEKIT_START_BYTE,
                APPLE_HOMEKIT_NOTIFY_START_BYTE,
                APPLE_DEVICE_ID_START_BYTE,
                APPLE_FINDMY_START_BYTE,
            }:
                return

        if service_info.connectable:
            old_connectable_service_info = self._connectable_history.get(
                service_info.address
            )
        else:
            old_connectable_service_info = None
        # This logic is complex due to the many combinations of scanners
        # that are supported.
        #
        # We need to handle multiple connectable and non-connectable scanners
        # and we need to handle the case where a device is connectable on one scanner
        # but not on another.
        #
        # The device may also be connectable only by a scanner that has worse
        # signal strength than a non-connectable scanner.
        #
        # all_history - the history of all advertisements from all scanners with the
        #               best advertisement from each scanner
        # connectable_history - the history of all connectable advertisements from all
        #                       scanners with the best advertisement from each
        #                       connectable scanner
        #
        if (
            (old_service_info := self._all_history.get(service_info.address))
            is not None
            and service_info.source is not old_service_info.source
            and service_info.source != old_service_info.source
            and (scanner := self._sources.get(old_service_info.source)) is not None
            and scanner.scanning
            and self._prefer_previous_adv_from_different_source(
                old_service_info, service_info
            )
        ):
            # If we are rejecting the new advertisement and the device is connectable
            # but not in the connectable history or the connectable source is the same
            # as the new source, we need to add it to the connectable history
            if service_info.connectable:
                if old_connectable_service_info is not None and (
                    # If its the same as the preferred source, we are done
                    # as we know we prefer the old advertisement
                    # from the check above
                    (old_connectable_service_info is old_service_info)
                    # If the old connectable source is different from the preferred
                    # source, we need to check it as well to see if we prefer
                    # the old connectable advertisement
                    or (
                        old_connectable_service_info.source is not service_info.source
                        and old_connectable_service_info.source != service_info.source
                        and (
                            connectable_scanner := self._sources.get(
                                old_connectable_service_info.source
                            )
                        )
                        is not None
                        and connectable_scanner.scanning
                        and self._prefer_previous_adv_from_different_source(
                            old_connectable_service_info,
                            service_info,
                        )
                    )
                ):
                    return

                self._connectable_history[service_info.address] = service_info

            return

        if service_info.connectable:
            self._connectable_history[service_info.address] = service_info

        self._all_history[service_info.address] = service_info

        # Track advertisement intervals to determine when we need to
        # switch adapters or mark a device as unavailable
        if (
            (
                last_source := self._advertisement_tracker.sources.get(
                    service_info.address
                )
            )
            is not None
            and last_source is not service_info.source
            and last_source != service_info.source
        ):
            # Source changed, remove the old address from the tracker
            self._advertisement_tracker.async_remove_address(service_info.address)
        if service_info.address not in self._advertisement_tracker.intervals:
            self._advertisement_tracker.async_collect(service_info)

        # If the advertisement data is the same as the last time we saw it, we
        # don't need to do anything else unless its connectable and we are missing
        # connectable history for the device so we can make it available again
        # after unavailable callbacks.
        if (
            # Ensure its not a connectable device missing from connectable history
            not (service_info.connectable and old_connectable_service_info is None)
            # Than check if advertisement data is the same
            and old_service_info is not None
            # This is a bit complex because we want to skip all the
            # PyObject_RichCompare overhead as its can be upwards of
            # 65% of the time spent in this method. The common case
            # is that its the same object for remote scanners.
            and not (
                (
                    service_info.manufacturer_data
                    is not old_service_info.manufacturer_data
                    and service_info.manufacturer_data
                    != old_service_info.manufacturer_data
                )
                or (
                    service_info.service_data is not old_service_info.service_data
                    and service_info.service_data != old_service_info.service_data
                )
                or (
                    service_info.service_uuids is not old_service_info.service_uuids
                    and service_info.service_uuids != old_service_info.service_uuids
                )
                or (
                    service_info.name is not old_service_info.name
                    and service_info.name != old_service_info.name
                )
            )
        ):
            return

        if not service_info.connectable and old_connectable_service_info is not None:
            # Since we have a connectable path and our BleakClient will
            # route any connection attempts to the connectable path, we
            # mark the service_info as connectable so that the callbacks
            # will be called and the device can be discovered.
            service_info = service_info._as_connectable()

        if (
            service_info.connectable or old_connectable_service_info is not None
        ) and self._bleak_callbacks:
            # Bleak callbacks must get a connectable device
            advertisement_data = service_info._advertisement_internal()
            for bleak_callback in self._bleak_callbacks:
                _dispatch_bleak_callback(
                    bleak_callback, service_info.device, advertisement_data
                )

        self._subclass_discover_info(service_info)

    def async_clear_advertisement_history(self, address: str) -> None:
        """
        Clear cached advertisement history for a device.

        Causes the next advertisement from this address to be treated as new
        data, bypassing both the advertisement-merging logic in scanners and
        the change-detection guard. Intended for devices that encode state in
        mutually-exclusive service UUIDs.
        """
        self._all_history.pop(address, None)
        self._connectable_history.pop(address, None)
        for scanner in self._sources.values():
            scanner._previous_service_info.pop(address, None)

    def _discover_service_info(self, service_info: BluetoothServiceInfoBleak) -> None:
        """
        Discover a new service info.

        This method is intended to be overridden by subclasses.
        """

    def _async_describe_source(self, service_info: BluetoothServiceInfoBleak) -> str:
        """Describe a source."""
        if scanner := self._sources.get(service_info.source):
            description = scanner.name
        else:
            description = service_info.source
        if service_info.connectable:
            description += " [connectable]"
        return description

    def _async_remove_unavailable_callback_internal(
        self,
        unavailable_callbacks: dict[
            str, set[Callable[[BluetoothServiceInfoBleak], None]]
        ],
        address: str,
        callbacks: set[Callable[[BluetoothServiceInfoBleak], None]],
        callback: Callable[[BluetoothServiceInfoBleak], None],
    ) -> None:
        """Remove a callback."""
        callbacks.remove(callback)
        if not callbacks:
            del unavailable_callbacks[address]

    def async_track_unavailable(
        self,
        callback: Callable[[BluetoothServiceInfoBleak], None],
        address: str,
        connectable: bool,
    ) -> Callable[[], None]:
        """Register a callback."""
        if connectable:
            unavailable_callbacks = self._connectable_unavailable_callbacks
        else:
            unavailable_callbacks = self._unavailable_callbacks
        callbacks = unavailable_callbacks.setdefault(address, set())
        callbacks.add(callback)
        return partial(
            self._async_remove_unavailable_callback_internal,
            unavailable_callbacks,
            address,
            callbacks,
            callback,
        )

    def async_ble_device_from_address(
        self, address: str, connectable: bool
    ) -> BLEDevice | None:
        """Return the BLEDevice if present."""
        histories = self._connectable_history if connectable else self._all_history
        if history := histories.get(address):
            return history.device
        return None

    def async_address_present(self, address: str, connectable: bool) -> bool:
        """Return if the address is present."""
        histories = self._connectable_history if connectable else self._all_history
        return address in histories

    def async_discovered_service_info(
        self, connectable: bool
    ) -> Iterable[BluetoothServiceInfoBleak]:
        """Return all the discovered services info."""
        histories = self._connectable_history if connectable else self._all_history
        return histories.values()

    def async_last_service_info(
        self, address: str, connectable: bool
    ) -> BluetoothServiceInfoBleak | None:
        """Return the last service info for an address."""
        histories = self._connectable_history if connectable else self._all_history
        return histories.get(address)

    def _async_unregister_scanner_internal(
        self,
        scanners: set[BaseHaScanner],
        scanner: BaseHaScanner,
        connection_slots: int | None,
    ) -> None:
        """Unregister a scanner."""
        _LOGGER.debug("Unregistering scanner %s", scanner.name)
        self._advertisement_tracker.async_remove_source(scanner.source)
        scanners.remove(scanner)
        scanner._clear_connection_history()
        del self._sources[scanner.source]
        del self._adapter_sources[scanner.adapter]
        self._allocations.pop(scanner.source, None)
        if connection_slots:
            self.slot_manager.remove_adapter(scanner.adapter)
        if (idx := scanner.adapter_idx) is not None:
            self._side_channel_scanners.pop(idx, None)
        self._async_on_scanner_registration(scanner, HaScannerRegistrationEvent.REMOVED)

    def async_register_scanner(
        self,
        scanner: BaseHaScanner,
        connection_slots: int | None = None,
    ) -> CALLBACK_TYPE:
        """Register a new scanner."""
        _LOGGER.debug("Registering scanner %s", scanner.name)
        if scanner.connectable:
            scanners = self._connectable_scanners
        else:
            scanners = self._non_connectable_scanners
            self._allocations[scanner.source] = HaBluetoothSlotAllocations(
                source=scanner.source, slots=0, free=0, allocated=[]
            )
        scanners.add(scanner)
        scanner._clear_connection_history()
        self._sources[scanner.source] = scanner
        self._adapter_sources[scanner.adapter] = scanner.source
        if (idx := scanner.adapter_idx) is not None:
            self._side_channel_scanners[idx] = scanner  # type: ignore[assignment]
        if connection_slots:
            self.slot_manager.register_adapter(scanner.adapter, connection_slots)
            self.async_on_allocation_changed(
                self.slot_manager.get_allocations(scanner.adapter)
            )
        self._async_on_scanner_registration(scanner, HaScannerRegistrationEvent.ADDED)
        return partial(
            self._async_unregister_scanner_internal, scanners, scanner, connection_slots
        )

    def async_register_bleak_callback(
        self, callback: AdvertisementDataCallback, filters: dict[str, set[str]]
    ) -> CALLBACK_TYPE:
        """Register a callback."""
        callback_entry = BleakCallback(callback, filters)
        self._bleak_callbacks.add(callback_entry)
        # Replay the history since otherwise we miss devices
        # that were already discovered before the callback was registered
        # or we are in passive mode
        for history in self._connectable_history.values():
            _dispatch_bleak_callback(
                callback_entry, history.device, history.advertisement
            )

        return partial(self._bleak_callbacks.remove, callback_entry)

    def async_release_connection_slot(self, device: BLEDevice) -> None:
        """Release a connection slot."""
        self.slot_manager.release_slot(device)

    def async_allocate_connection_slot(self, device: BLEDevice) -> bool:
        """Allocate a connection slot."""
        return self.slot_manager.allocate_slot(device)

    def async_get_learned_advertising_interval(self, address: str) -> float | None:
        """Get the learned advertising interval for a MAC address."""
        return self._intervals.get(address)

    def async_get_fallback_availability_interval(self, address: str) -> float | None:
        """Get the fallback availability timeout for a MAC address."""
        return self._fallback_intervals.get(address)

    def async_set_fallback_availability_interval(
        self, address: str, interval: float
    ) -> None:
        """Override the fallback availability timeout for a MAC address."""
        self._fallback_intervals[address] = interval

    def _async_slot_manager_changed(self, event: AllocationChangeEvent) -> None:
        """Handle slot manager changes."""
        self.async_on_allocation_changed(
            self.slot_manager.get_allocations(event.adapter)
        )

    def async_on_allocation_changed(self, allocations: Allocations) -> None:
        """Call allocation callbacks."""
        source = self._adapter_sources.get(allocations.adapter, allocations.adapter)
        ha_slot_allocations = HaBluetoothSlotAllocations(
            source=source,
            slots=allocations.slots,
            free=allocations.free,
            allocated=allocations.allocated,
        )
        self._allocations[source] = ha_slot_allocations
        for source_key in (source, None):
            if not (
                allocation_callbacks := self._allocations_callbacks.get(source_key)
            ):
                continue
            for callback_ in allocation_callbacks:
                try:
                    callback_(ha_slot_allocations)
                except Exception:
                    _LOGGER.exception("Error in allocation callback")

    def _async_on_scanner_registration(
        self, scanner: BaseHaScanner, event: HaScannerRegistrationEvent
    ) -> None:
        """Call scanner callbacks."""
        for source_key in (scanner.source, None):
            if not (
                scanner_callbacks := self._scanner_registration_callbacks.get(
                    source_key
                )
            ):
                continue
            for callback_ in scanner_callbacks:
                try:
                    callback_(HaScannerRegistration(event, scanner))
                except Exception:
                    _LOGGER.exception("Error in scanner callback")

    def async_current_allocations(
        self, source: str | None = None
    ) -> list[HaBluetoothSlotAllocations] | None:
        """Return the current allocations."""
        if source:
            if allocations := self._allocations.get(source):
                return [allocations]
            return []
        return list(self._allocations.values())

    def async_register_allocation_callback(
        self,
        callback: Callable[[HaBluetoothSlotAllocations], None],
        source: str | None = None,
    ) -> CALLBACK_TYPE:
        """Register a callback to be called when an allocations change."""
        self._allocations_callbacks.setdefault(source, set()).add(callback)
        return partial(self._async_unregister_allocation_callback, callback, source)

    def _async_unregister_allocation_callback(
        self, callback: Callable[[HaBluetoothSlotAllocations], None], source: str | None
    ) -> None:
        if (callbacks := self._allocations_callbacks.get(source)) is not None:
            callbacks.discard(callback)
            if not callbacks:
                del self._allocations_callbacks[source]

    def async_register_scanner_registration_callback(
        self, callback: Callable[[HaScannerRegistration], None], source: str | None
    ) -> CALLBACK_TYPE:
        """Register a callback to be called when a scanner is added or removed."""
        self._scanner_registration_callbacks.setdefault(source, set()).add(callback)
        return partial(
            self._async_unregister_scanner_registration_callback, callback, source
        )

    def _async_unregister_scanner_registration_callback(
        self, callback: Callable[[HaScannerRegistration], None], source: str | None
    ) -> None:
        if (callbacks := self._scanner_registration_callbacks.get(source)) is not None:
            callbacks.discard(callback)
            if not callbacks:
                del self._scanner_registration_callbacks[source]

    def async_current_scanners(self) -> list[BaseHaScanner]:
        """Return the current scanners."""
        return list(self._sources.values())

    def async_register_scanner_mode_change_callback(
        self, callback: Callable[[HaScannerModeChange], None], source: str | None
    ) -> CALLBACK_TYPE:
        """Register a callback to be called when a scanner mode changes."""
        self._scanner_mode_change_callbacks.setdefault(source, set()).add(callback)
        return partial(
            self._async_unregister_scanner_mode_change_callback, callback, source
        )

    def _async_unregister_scanner_mode_change_callback(
        self, callback: Callable[[HaScannerModeChange], None], source: str | None
    ) -> None:
        """Unregister a scanner mode change callback."""
        if (callbacks := self._scanner_mode_change_callbacks.get(source)) is not None:
            callbacks.discard(callback)
            if not callbacks:
                del self._scanner_mode_change_callbacks[source]

    def scanner_mode_changed(self, scanner: BaseHaScanner) -> None:
        """Notify callbacks that a scanner's mode has changed."""
        mode_change = HaScannerModeChange(
            scanner=scanner,
            requested_mode=scanner.requested_mode,
            current_mode=scanner.current_mode,
        )
        for source_key in (scanner.source, None):
            if not (
                mode_callbacks := self._scanner_mode_change_callbacks.get(source_key)
            ):
                continue
            for callback_ in mode_callbacks:
                try:
                    callback_(mode_change)
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Error in scanner mode change callback")
