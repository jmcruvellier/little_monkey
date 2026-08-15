# distutils: language = c++
from libcpp.string cimport string

from time import time

import cython


cdef extern from "ulid_wrapper.h":
    string _cpp_ulid_at_time(double timestamp)
    string _cpp_ulid_to_bytes(const char * ulid_string)
    string _cpp_ulid()
    string _cpp_bytes_to_ulid(string ulid_bytes)


def _ulid_now() -> str:
    return _cpp_ulid().decode("ascii")

def _ulid_at_time(_time: float) -> str:
    return _cpp_ulid_at_time(_time).decode("ascii")

def _ulid_to_bytes(ulid_str: str) -> bytes:
    if len(ulid_str) != 26:
        raise ValueError(f"ULID must be a 26 character string: {ulid_str}")
    return _cpp_ulid_to_bytes(ulid_str.encode("ascii"))

def _bytes_to_ulid(ulid_bytes: bytes) -> str:
    if len(ulid_bytes) != 16:
        raise ValueError(f"ULID bytes be 16 bytes: {ulid_bytes}")
    return _cpp_bytes_to_ulid(ulid_bytes).decode("ascii")
