"""Sensor platform for little_monkey."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.const import UnitOfPower, UnitOfEnergy, UnitOfTemperature, PERCENTAGE, CONF_NAME

from .entity import EcojokoEntity, EcojokoSensor
from .const import (
    DOMAIN,
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
    # Grid consumption sensor
    ("grid_consumption", ENERGY, None),
    # HC/HP grid consumption sensors
    ("hc_grid_consumption", ENERGY, CONF_USE_HCHP_FEATURE),
    ("hp_grid_consumption", ENERGY, CONF_USE_HCHP_FEATURE),
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


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the custom component sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create the main device entity
    firmware = coordinator.data["gateway_firmware_version"]
    main_device = EcojokoEntity(
        coordinator, config_entry.entry_id, config_entry.data.get(CONF_NAME), firmware)

    # Create child entities and link them to the main device
    for key, kind, option in SENSORS:
        if option is None or config_entry.data.get(option) is True:
            main_device.add_child_entity(EcojokoSensor(main_device, key, *kind))

    async_add_entities([main_device] + main_device.child_entities)
