import cython

from .advertisement_tracker cimport AdvertisementTracker
from .base_scanner cimport BaseHaScanner
from .models cimport BluetoothServiceInfoBleak

cdef int NO_RSSI_VALUE
cdef int ADV_RSSI_SWITCH_THRESHOLD
cdef double TRACKER_BUFFERING_WOBBLE_SECONDS
cdef double FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
cdef object FILTER_UUIDS
cdef object AdvertisementData
cdef object BLEDevice
cdef bint TYPE_CHECKING
cdef set APPLE_START_BYTES_WANTED

cdef unsigned char APPLE_IBEACON_START_BYTE
cdef unsigned char APPLE_HOMEKIT_START_BYTE
cdef unsigned char APPLE_HOMEKIT_NOTIFY_START_BYTE
cdef unsigned char APPLE_DEVICE_ID_START_BYTE
cdef unsigned char APPLE_FINDMY_START_BYTE

cdef object APPLE_MFR_ID

@cython.locals(uuids=set)
cdef _dispatch_bleak_callback(
    BleakCallback bleak_callback,
    object device,
    object advertisement_data
)

cdef class BleakCallback:

    cdef public object callback
    cdef public dict filters


cdef class BluetoothManager:

    cdef public object _cancel_unavailable_tracking
    cdef public AdvertisementTracker _advertisement_tracker
    cdef public dict _fallback_intervals
    cdef public dict _intervals
    cdef public dict _unavailable_callbacks
    cdef public dict _connectable_unavailable_callbacks
    cdef public set _bleak_callbacks
    cdef public dict _all_history
    cdef public dict _connectable_history
    cdef public set _non_connectable_scanners
    cdef public set _connectable_scanners
    cdef public dict _adapters
    cdef public dict _sources
    cdef public object _bluetooth_adapters
    cdef public object slot_manager
    cdef public bint _debug
    cdef public bint shutdown
    cdef public object _loop
    cdef public object _adapter_refresh_future
    cdef public object _recovery_lock
    cdef public set _disappeared_callbacks
    cdef public dict _allocations_callbacks
    cdef public object _cancel_allocation_callbacks
    cdef public dict _adapter_sources
    cdef public dict _allocations
    cdef public dict _scanner_registration_callbacks
    cdef public dict _scanner_mode_change_callbacks
    cdef public object _subclass_discover_info
    cdef public bint has_advertising_side_channel
    cdef public dict _side_channel_scanners
    cdef public object _mgmt_ctl

    @cython.locals(stale_seconds=double)
    cdef bint _prefer_previous_adv_from_different_source(
        self,
        BluetoothServiceInfoBleak old,
        BluetoothServiceInfoBleak new
    )

    cpdef void scanner_adv_received(self, BluetoothServiceInfoBleak service_info)

    @cython.locals(
        old_service_info=BluetoothServiceInfoBleak,
        old_connectable_service_info=BluetoothServiceInfoBleak,
        source=str,
        connectable=bint,
        scanner=BaseHaScanner,
        connectable_scanner=BaseHaScanner,
        apple_cstr="const unsigned char *",
        bleak_callback=BleakCallback
    )
    cdef void _scanner_adv_received(self, BluetoothServiceInfoBleak service_info)

    cpdef _async_describe_source(self, BluetoothServiceInfoBleak service_info)
