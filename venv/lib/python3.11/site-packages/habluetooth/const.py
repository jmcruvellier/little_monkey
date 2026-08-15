"""Constants."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from enum import Enum
from typing import Final

CALLBACK_TYPE = Callable[[], None]

SOURCE_LOCAL: Final = "local"

START_TIMEOUT = 15
STOP_TIMEOUT = 5

# The maximum time between advertisements for a device to be considered
# stale when the advertisement tracker cannot determine the interval.
#
# We have to set this quite high as we don't know
# when devices fall out of the ESPHome device (and other non-local scanners)'s
# stack like we do with BlueZ so its safer to assume its available
# since if it does go out of range and it is in range
# of another device the timeout is much shorter and it will
# switch over to using that adapter anyways.
#
FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS: Final = 60 * 15

# The maximum time between advertisements for a device to be considered
# stale when the advertisement tracker can determine the interval for
# connectable devices.
#
# BlueZ uses 180 seconds by default but we give it a bit more time
# to account for the esp32's bluetooth stack being a bit slower
# than BlueZ's.
CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS: Final = 195


# We must recover before we hit the 180s mark
# where the device is removed from the stack
# or the devices will go unavailable. Since
# we only check every 30s, we need this number
# to be
# 180s Time when device is removed from stack
# - 30s check interval
# - 30s scanner restart time * 2
#
SCANNER_WATCHDOG_TIMEOUT: Final = 90
# How often to check if the scanner has reached
# the SCANNER_WATCHDOG_TIMEOUT without seeing anything
SCANNER_WATCHDOG_INTERVAL: Final = timedelta(seconds=30)


UNAVAILABLE_TRACK_SECONDS: Final = 60 * 5


FAILED_ADAPTER_MAC = "00:00:00:00:00:00"


ADV_RSSI_SWITCH_THRESHOLD: Final = 16
# The switch threshold for the rssi value
# to switch to a different adapter for advertisements
# Note that this does not affect the connection
# selection that uses RSSI_SWITCH_THRESHOLD from
# bleak_retry_connector


# Connection parameter constants (units of 1.25ms for intervals)
# Fast connection parameters for initial connection and service discovery
FAST_MIN_CONN_INTERVAL: Final = 0x06  # 6 * 1.25ms = 7.5ms (BLE minimum)
FAST_MAX_CONN_INTERVAL: Final = 0x06  # 6 * 1.25ms = 7.5ms
FAST_CONN_LATENCY: Final = 0  # No latency for fast response
FAST_CONN_TIMEOUT: Final = 1000  # 1000 * 10ms = 10s

# Medium connection parameters for standard operation
# Balanced for stability with WiFi-based BLE proxies
MEDIUM_MIN_CONN_INTERVAL: Final = 0x07  # 7 * 1.25ms = 8.75ms
MEDIUM_MAX_CONN_INTERVAL: Final = 0x09  # 9 * 1.25ms = 11.25ms
MEDIUM_CONN_LATENCY: Final = 0  # No latency
MEDIUM_CONN_TIMEOUT: Final = 800  # 800 * 10ms = 8s

# Bluetooth address types
BDADDR_BREDR: Final = 0x00
BDADDR_LE_PUBLIC: Final = 0x01
BDADDR_LE_RANDOM: Final = 0x02


class ConnectParams(Enum):
    """Connection parameter presets."""

    FAST = "fast"
    MEDIUM = "medium"
