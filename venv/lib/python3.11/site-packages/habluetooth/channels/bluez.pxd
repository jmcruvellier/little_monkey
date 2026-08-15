
import cython

from ..scanner cimport HaScanner
cdef bint TYPE_CHECKING

cdef unsigned short DEVICE_FOUND
cdef unsigned short ADV_MONITOR_DEVICE_FOUND
cdef unsigned short MGMT_OP_GET_CONNECTIONS
cdef unsigned short MGMT_OP_LOAD_CONN_PARAM
cdef unsigned short MGMT_EV_CMD_COMPLETE
cdef unsigned short MGMT_EV_CMD_STATUS

cdef class BluetoothMGMTProtocol:

    cdef public object transport
    cdef object connection_made_future
    cdef bytes _buffer
    cdef unsigned int _buffer_len
    cdef unsigned int _pos
    cdef dict _scanners
    cdef object _on_connection_lost
    cdef object _is_shutting_down
    cdef dict _pending_commands
    cdef public object _sock

    @cython.locals(bytes_data=bytes)
    cdef void _add_to_buffer(self, object data) except *

    @cython.locals(end_of_frame_pos="unsigned int", cstr="const unsigned char *")
    cdef void _remove_from_buffer(self) except *

    @cython.locals(
        header="const unsigned char *",
        event_code="unsigned short",
        controller_idx="unsigned short",
        param_len="unsigned short",
        rssi="short",
        flags="unsigned int",
        data="bytes",
        parse_offset="unsigned short",
        scanner=HaScanner,
        opcode="unsigned short",
        status="unsigned char",
        param_offset="unsigned short",
        param_count="unsigned short"
    )
    cpdef void data_received(self, object data) except *

    cdef void _handle_load_conn_param_response(
        self, unsigned char status, unsigned short controller_idx
    ) except *
