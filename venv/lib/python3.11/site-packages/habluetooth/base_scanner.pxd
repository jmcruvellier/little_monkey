
import cython

from .models cimport BluetoothServiceInfoBleak
from .manager cimport BluetoothManager

cdef object parse_advertisement_data_bytes
cdef object NO_RSSI_VALUE
cdef object BluetoothServiceInfoBleak
cdef object AdvertisementData
cdef object BLEDevice
cdef bint TYPE_CHECKING

cdef class BaseHaScanner:

    cdef public str adapter
    cdef public bint connectable
    cdef public str source
    cdef public object connector
    cdef public unsigned int _connecting
    cdef public str name
    cdef public bint scanning
    cdef public double _last_detection
    cdef public object _start_time
    cdef public object _cancel_watchdog
    cdef public object _loop
    cdef BluetoothManager _manager
    cdef public object details
    cdef public object current_mode
    cdef public object requested_mode
    cdef public dict _previous_service_info
    cdef public double _expire_seconds
    cdef public dict _details
    cdef public object _cancel_track
    cdef public dict _connect_failures
    cdef public dict _connect_in_progress

    cpdef void _clear_connection_history(self) except *

    cpdef void _finished_connecting(self, str address, bint connected) except *

    cdef void _increase_count(self, dict target, str address) except *

    cdef void _add_connect_failure(self, str address) except *

    cpdef void _add_connecting(self, str address) except *

    cdef void _remove_connecting(self, str address) except *

    cdef void _clear_connect_failure(self, str address) except *

    @cython.locals(
        in_progress=Py_ssize_t,
        count=Py_ssize_t
    )
    cpdef _connections_in_progress(self)

    cpdef _connection_failures(self, str address)

    @cython.locals(
        score=double,
        scanner_connections_in_progress=Py_ssize_t,
        previous_failures=Py_ssize_t
    )
    cpdef _score_connection_paths(self, int rssi_diff, object scanner_device)

    cpdef tuple get_discovered_device_advertisement_data(self, str address)

    cpdef float time_since_last_detection(self)

    @cython.locals(info=BluetoothServiceInfoBleak)
    cdef dict _build_discovered_device_advertisement_datas(self)

    @cython.locals(info=BluetoothServiceInfoBleak)
    cdef dict _build_discovered_device_timestamps(self)

    @cython.locals(parsed=tuple, prev_info=BluetoothServiceInfoBleak, info=BluetoothServiceInfoBleak)
    cpdef void _async_on_raw_advertisement(
        self,
        str address,
        int rssi,
        bytes raw,
        dict details,
        double advertisement_monotonic_time
    )

    @cython.locals(
        prev_name=str,
        prev_discovery=tuple,
        has_local_name=bint,
        has_manufacturer_data=bint,
        has_service_data=bint,
        has_service_uuids=bint,
        sub_value=bytes,
        super_value=bytes,
        info=BluetoothServiceInfoBleak,
        prev_info=BluetoothServiceInfoBleak
    )
    cdef void _async_on_advertisement_internal(
        self,
        str address,
        int rssi,
        str local_name,
        list service_uuids,
        dict service_data,
        dict manufacturer_data,
        object tx_power,
        dict details,
        double advertisement_monotonic_time,
        bytes raw
    )

    cpdef void _async_on_advertisement(
        self,
        str address,
        int rssi,
        str local_name,
        list service_uuids,
        dict service_data,
        dict manufacturer_data,
        object tx_power,
        dict details,
        double advertisement_monotonic_time
    )

    @cython.locals(now=double, timestamp=double, info=BluetoothServiceInfoBleak)
    cpdef void _async_expire_devices(self)

    cpdef void _schedule_expire_devices(self)

cdef class BaseHaRemoteScanner(BaseHaScanner):

    @cython.locals(info=BluetoothServiceInfoBleak)
    cpdef tuple get_discovered_device_advertisement_data(self, str address)
