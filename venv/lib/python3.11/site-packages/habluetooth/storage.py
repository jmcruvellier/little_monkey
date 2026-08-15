"""Serialize/Deserialize bluetooth adapter discoveries."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Final, TypedDict

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

_LOGGER = logging.getLogger(__name__)


@dataclass
class DiscoveredDeviceAdvertisementData:
    """Discovered device advertisement data deserialized from storage."""

    connectable: bool
    expire_seconds: float
    discovered_device_advertisement_datas: dict[
        str, tuple[BLEDevice, AdvertisementData]
    ]
    discovered_device_timestamps: dict[str, float]
    discovered_device_raw: dict[str, bytes | None] = field(default_factory=dict)


CONNECTABLE: Final = "connectable"
EXPIRE_SECONDS: Final = "expire_seconds"
DISCOVERED_DEVICE_ADVERTISEMENT_DATAS: Final = "discovered_device_advertisement_datas"
DISCOVERED_DEVICE_TIMESTAMPS: Final = "discovered_device_timestamps"
DISCOVERED_DEVICE_RAW: Final = "discovered_device_raw"


class DiscoveredDeviceAdvertisementDataDict(TypedDict):
    """Discovered device advertisement data dict in storage."""

    connectable: bool
    expire_seconds: float
    discovered_device_advertisement_datas: dict[str, DiscoveredDeviceDict]
    discovered_device_timestamps: dict[str, float]
    discovered_device_raw: dict[str, str | None]


ADDRESS: Final = "address"
NAME: Final = "name"
RSSI: Final = "rssi"
DETAILS: Final = "details"


class BLEDeviceDict(TypedDict):
    """BLEDevice dict."""

    address: str
    name: str | None
    rssi: int | None  # Kept for backward compatibility
    details: dict[str, Any]


LOCAL_NAME: Final = "local_name"
MANUFACTURER_DATA: Final = "manufacturer_data"
SERVICE_DATA: Final = "service_data"
SERVICE_UUIDS: Final = "service_uuids"
TX_POWER: Final = "tx_power"
PLATFORM_DATA: Final = "platform_data"


class AdvertisementDataDict(TypedDict):
    """AdvertisementData dict."""

    local_name: str | None
    manufacturer_data: dict[str, str]
    service_data: dict[str, str]
    service_uuids: list[str]
    rssi: int
    tx_power: int | None
    platform_data: list[Any]


class DiscoveredDeviceDict(TypedDict):
    """Discovered device dict."""

    device: BLEDeviceDict
    advertisement_data: AdvertisementDataDict


def expire_stale_scanner_discovered_device_advertisement_data(
    data_by_scanner: dict[str, DiscoveredDeviceAdvertisementDataDict],
) -> None:
    """Expire stale discovered device advertisement data."""
    now = time.time()
    expired_scanners: list[str] = []
    for scanner, data in data_by_scanner.items():
        expire: list[str] = []
        expire_seconds = data[EXPIRE_SECONDS]
        timestamps = data[DISCOVERED_DEVICE_TIMESTAMPS]
        discovered_device_advertisement_datas = data[
            DISCOVERED_DEVICE_ADVERTISEMENT_DATAS
        ]
        discovered_device_raw = data.get(DISCOVERED_DEVICE_RAW, {})
        for address, timestamp in timestamps.items():
            time_diff = now - timestamp
            if time_diff > expire_seconds:
                expire.append(address)
            elif time_diff < 0:
                _LOGGER.warning(
                    "Discarding timestamp %s for %s on "
                    "scanner %s as it is the future (now = %s)",
                    timestamp,
                    address,
                    scanner,
                    now,
                )
                expire.append(address)
        for address in expire:
            del timestamps[address]
            del discovered_device_advertisement_datas[address]
            discovered_device_raw.pop(address, None)
        if not timestamps:
            expired_scanners.append(scanner)
        _LOGGER.debug(
            "Loaded %s fresh discovered devices for %s", len(timestamps), scanner
        )

    for scanner in expired_scanners:
        del data_by_scanner[scanner]


def discovered_device_advertisement_data_from_dict(
    data: DiscoveredDeviceAdvertisementDataDict,
) -> DiscoveredDeviceAdvertisementData | None:
    """Build discovered_device_advertisement_data dict."""
    try:
        return DiscoveredDeviceAdvertisementData(
            data[CONNECTABLE],
            data[EXPIRE_SECONDS],
            _deserialize_discovered_device_advertisement_datas(
                data[DISCOVERED_DEVICE_ADVERTISEMENT_DATAS]
            ),
            _deserialize_discovered_device_timestamps(
                data[DISCOVERED_DEVICE_TIMESTAMPS]
            ),
            _deserialize_discovered_device_raw(data.get(DISCOVERED_DEVICE_RAW, {})),
        )
    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.exception(
            "Error deserializing discovered_device_advertisement_data"
            ", adapter startup will be slow: %s",
            err,
        )
    return None


def discovered_device_advertisement_data_to_dict(
    data: DiscoveredDeviceAdvertisementData,
) -> DiscoveredDeviceAdvertisementDataDict:
    """Build discovered_device_advertisement_data dict."""
    return DiscoveredDeviceAdvertisementDataDict(
        connectable=data.connectable,
        expire_seconds=data.expire_seconds,
        discovered_device_advertisement_datas=_serialize_discovered_device_advertisement_datas(
            data.discovered_device_advertisement_datas
        ),
        discovered_device_timestamps=_serialize_discovered_device_timestamps(
            data.discovered_device_timestamps
        ),
        discovered_device_raw=_serialize_discovered_device_raw(
            data.discovered_device_raw
        ),
    )


def _serialize_discovered_device_advertisement_datas(
    discovered_device_advertisement_datas: dict[
        str, tuple[BLEDevice, AdvertisementData]
    ],
) -> dict[str, DiscoveredDeviceDict]:
    """Serialize discovered_device_advertisement_datas."""
    return {
        address: DiscoveredDeviceDict(
            device=_ble_device_to_dict(device, advertisement_data),
            advertisement_data=_advertisement_data_to_dict(advertisement_data),
        )
        for (
            address,
            (device, advertisement_data),
        ) in discovered_device_advertisement_datas.items()
    }


def _deserialize_discovered_device_advertisement_datas(
    discovered_device_advertisement_datas: dict[str, DiscoveredDeviceDict],
) -> dict[str, tuple[BLEDevice, AdvertisementData]]:
    """Deserialize discovered_device_advertisement_datas."""
    return {
        address: (
            _ble_device_from_dict(device_advertisement_data["device"]),
            _advertisement_data_from_dict(
                device_advertisement_data["advertisement_data"]
            ),
        )
        for (
            address,
            device_advertisement_data,
        ) in discovered_device_advertisement_datas.items()
    }


def _ble_device_from_dict(device_dict: BLEDeviceDict) -> BLEDevice:
    """Deserialize BLEDevice from dict, handling backward compatibility."""
    # Remove rssi from dict as BLEDevice no longer accepts it in bleak 1.x
    device_data = device_dict.copy()
    device_data.pop("rssi", None)  # type: ignore[misc]  # Remove rssi if present (backward compatibility)
    return BLEDevice(**device_data)


def _ble_device_to_dict(
    ble_device: BLEDevice, advertisement_data: AdvertisementData
) -> BLEDeviceDict:
    """Serialize ble_device."""
    return BLEDeviceDict(
        address=ble_device.address,
        name=ble_device.name,
        rssi=advertisement_data.rssi,  # For backward compatibility
        details=ble_device.details,
    )


def _advertisement_data_from_dict(
    advertisement_data: AdvertisementDataDict,
) -> AdvertisementData:
    """Deserialize advertisement_data."""
    return AdvertisementData(
        local_name=advertisement_data[LOCAL_NAME],
        manufacturer_data={
            int(manufacturer_id): bytes.fromhex(manufacturer_data)
            for manufacturer_id, manufacturer_data in advertisement_data[
                MANUFACTURER_DATA
            ].items()
        },
        service_data={
            service_uuid: bytes.fromhex(service_data)
            for service_uuid, service_data in advertisement_data[SERVICE_DATA].items()
        },
        service_uuids=advertisement_data[SERVICE_UUIDS],
        rssi=advertisement_data[RSSI],
        tx_power=advertisement_data[TX_POWER],
        platform_data=tuple(advertisement_data[PLATFORM_DATA]),
    )


def _advertisement_data_to_dict(
    advertisement_data: AdvertisementData,
) -> AdvertisementDataDict:
    """Serialize advertisement_data."""
    return AdvertisementDataDict(
        local_name=advertisement_data.local_name,
        manufacturer_data={
            str(manufacturer_id): manufacturer_data.hex()
            for manufacturer_id, manufacturer_data in advertisement_data.manufacturer_data.items()  # noqa: E501
        },
        service_data={
            service_uuid: service_data.hex()
            for service_uuid, service_data in advertisement_data.service_data.items()
        },
        service_uuids=advertisement_data.service_uuids,
        rssi=advertisement_data.rssi,
        tx_power=advertisement_data.tx_power,
        platform_data=list(advertisement_data.platform_data),
    )


def _get_monotonic_time_diff() -> float:
    """Get monotonic time diff."""
    return time.time() - time.monotonic()


def _deserialize_discovered_device_timestamps(
    discovered_device_timestamps: dict[str, float],
) -> dict[str, float]:
    """Deserialize discovered_device_timestamps."""
    time_diff = _get_monotonic_time_diff()
    return {
        address: unix_time - time_diff
        for address, unix_time in discovered_device_timestamps.items()
    }


def _serialize_discovered_device_timestamps(
    discovered_device_timestamps: dict[str, float],
) -> dict[str, float]:
    """Serialize discovered_device_timestamps."""
    time_diff = _get_monotonic_time_diff()
    return {
        address: monotonic_time + time_diff
        for address, monotonic_time in discovered_device_timestamps.items()
    }


def _deserialize_discovered_device_raw(
    discovered_device_raw: dict[str, str | None],
) -> dict[str, bytes | None]:
    """Deserialize discovered_device_timestamps."""
    return {
        address: None if raw is None else bytes.fromhex(raw)
        for address, raw in discovered_device_raw.items()
    }


def _serialize_discovered_device_raw(
    discovered_device_raw: dict[str, bytes | None],
) -> dict[str, str | None]:
    """Serialize discovered_device_timestamps."""
    return {
        address: None if raw is None else raw.hex()
        for address, raw in discovered_device_raw.items()
    }


DiscoveryStorageType = dict[str, DiscoveredDeviceAdvertisementDataDict]
