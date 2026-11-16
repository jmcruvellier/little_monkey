"""Sensor platform for little_monkey."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.const import (
    UnitOfApparentPower,
    UnitOfPower,
    UnitOfEnergy,
    UnitOfTemperature,
    PERCENTAGE,
    CONF_NAME,
)

from .entity import EcojokoEntity, EcojokoSensor
from .tariff import KNOWN_BANDS, TEMPO_BANDS, band_key, has_sensor
from .const import (
    CONF_USE_HCHP_FEATURE,
    CONF_TARIFF_BANDS,
    CONF_USE_TEMPHUM_FEATURE,
    CONF_USE_PROD_FEATURE
)

# Kinds of sensors: state class, device class, unit, icon
POWER = (
    SensorStateClass.MEASUREMENT,
    SensorDeviceClass.POWER,
    UnitOfPower.WATT,
    "mdi:flash",
)
APPARENT_POWER = (
    SensorStateClass.MEASUREMENT,
    SensorDeviceClass.APPARENT_POWER,
    UnitOfApparentPower.VOLT_AMPERE,
    "mdi:flash-outline",
)
ENERGY = (
    SensorStateClass.TOTAL_INCREASING,
    SensorDeviceClass.ENERGY,
    UnitOfEnergy.KILO_WATT_HOUR,
    "mdi:lightning-bolt",
)
TEMPERATURE = (
    SensorStateClass.MEASUREMENT,
    SensorDeviceClass.TEMPERATURE,
    UnitOfTemperature.CELSIUS,
    "mdi:thermometer",
)
HUMIDITY = (
    SensorStateClass.MEASUREMENT,
    SensorDeviceClass.HUMIDITY,
    PERCENTAGE,
    "mdi:water",
)

# Sensors, in creation order: key, kind, option that enables it (None = always)
SENSORS = (
    # Real time sensor
    ("realtime_consumption", POWER, None),
    # Apparent power sensor
    ("realtime_apparent_power", APPARENT_POWER, None),
    # Grid consumption sensor
    ("grid_consumption", ENERGY, None),
    # HC/HP grid consumption sensors
    ("hc_grid_consumption", ENERGY, CONF_USE_HCHP_FEATURE),
    ("hp_grid_consumption", ENERGY, CONF_USE_HCHP_FEATURE),
    # Production surplus sensor
    ("production_surplus", ENERGY, CONF_USE_PROD_FEATURE),
    # Temperature & Humidity sensors
    ("indoor_temp", TEMPERATURE, CONF_USE_TEMPHUM_FEATURE),
    ("outdoor_temp", TEMPERATURE, CONF_USE_TEMPHUM_FEATURE),
    ("indoor_hum", HUMIDITY, CONF_USE_TEMPHUM_FEATURE),
    ("outdoor_hum", HUMIDITY, CONF_USE_TEMPHUM_FEATURE),
)

# Keys of every sensor ever created by an option, Tempo included: their
# unique ids are rewritten by the migration of the 1.2.7 entries
SENSOR_KEYS = [key for key, _kind, _option in SENSORS] + [
    band_key(band_id) for band_id in TEMPO_BANDS]

# Sensors created only when ecojoko gives their value: it depends on the
# installation of the user, not on an option
IF_PROVIDED = {"realtime_apparent_power"}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the custom component sensors."""
    coordinator = config_entry.runtime_data

    # Create the main device entity
    firmware = coordinator.data["gateway_firmware_version"]
    main_device = EcojokoEntity(
        coordinator, config_entry.entry_id, config_entry.data.get(CONF_NAME), firmware)

    # Create child entities and link them to the main device
    for key, kind, option in SENSORS:
        if key in IF_PROVIDED and coordinator.data.get(key) is None:
            continue
        if option is None or config_entry.data.get(option) is True:
            main_device.add_child_entity(EcojokoSensor(main_device, key, *kind))
    # One sensor per tariff band of the contract
    for band in config_entry.data.get(CONF_TARIFF_BANDS) or []:
        if has_sensor(band):
            # A known sensor without a chosen name keeps its translated name
            name = band.get("name")
            if not name and band["id"] not in KNOWN_BANDS:
                name = band.get("label")
            main_device.add_child_entity(EcojokoSensor(
                main_device, band["key"], *ENERGY, name=name))

    async_add_entities([main_device] + main_device.child_entities)
