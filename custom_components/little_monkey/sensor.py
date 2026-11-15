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
from .const import (
    CONF_USE_HCHP_FEATURE,
    CONF_USE_TEMPO_FEATURE,
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
    ("weekend_grid_consumption", ENERGY, CONF_USE_HCHP_FEATURE),
    # Tempo grid consumption sensors
    ("blue_hc_grid_consumption", ENERGY, CONF_USE_TEMPO_FEATURE),
    ("blue_hp_grid_consumption", ENERGY, CONF_USE_TEMPO_FEATURE),
    ("white_hc_grid_consumption", ENERGY, CONF_USE_TEMPO_FEATURE),
    ("white_hp_grid_consumption", ENERGY, CONF_USE_TEMPO_FEATURE),
    ("red_hc_grid_consumption", ENERGY, CONF_USE_TEMPO_FEATURE),
    ("red_hp_grid_consumption", ENERGY, CONF_USE_TEMPO_FEATURE),
    # Production surplus sensor
    ("production_surplus", ENERGY, CONF_USE_PROD_FEATURE),
    # Temperature & Humidity sensors
    ("indoor_temp", TEMPERATURE, CONF_USE_TEMPHUM_FEATURE),
    ("outdoor_temp", TEMPERATURE, CONF_USE_TEMPHUM_FEATURE),
    ("indoor_hum", HUMIDITY, CONF_USE_TEMPHUM_FEATURE),
    ("outdoor_hum", HUMIDITY, CONF_USE_TEMPHUM_FEATURE),
)

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

    async_add_entities([main_device] + main_device.child_entities)
