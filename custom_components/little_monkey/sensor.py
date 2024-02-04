"""Sensor platform for mon_ecojoko."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.const import UnitOfPower, UnitOfEnergy, UnitOfTemperature, PERCENTAGE, CONF_NAME

from custom_components.little_monkey.entity import EcojokoEntity, EcojokoSensor
from .const import (
    DOMAIN,
    CONF_USE_HCHP_FEATURE,
    CONF_USE_TEMPO_FEATURE,
    CONF_USE_TEMPHUM_FEATURE,
    CONF_USE_PROD_FEATURE,
    CONF_USE_LAST_MEASURE_FEATURE
)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the custom component sensors."""
    # Fetch data or configure your sensors here
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create the main device entity
    firmware = coordinator.data["gateway_firmware_version"]
    main_device = EcojokoEntity(coordinator, config_entry.data.get(CONF_NAME), firmware)

    # Create child entities and link them to the main device

    # Real time sensor
    main_device.add_child_entity(EcojokoSensor(
        main_device,
        "realtime_consumption",
        SensorStateClass.MEASUREMENT,
        SensorDeviceClass.POWER,
        UnitOfPower.WATT,
        "mdi:flash"))

    # Grid consumption sensor
    main_device.add_child_entity(EcojokoSensor(
        main_device,
        "grid_consumption",
        SensorStateClass.TOTAL_INCREASING,
        SensorDeviceClass.ENERGY,
        UnitOfEnergy.KILO_WATT_HOUR,
        "mdi:lightning-bolt"))

    # HC/HP grid consumption sensors
    if config_entry.data.get(CONF_USE_HCHP_FEATURE) is True:
        main_device.add_child_entity(EcojokoSensor(
            main_device,
            "hc_grid_consumption",
            SensorStateClass.TOTAL_INCREASING,
            SensorDeviceClass.ENERGY,
            UnitOfEnergy.KILO_WATT_HOUR,
            "mdi:lightning-bolt"))
        main_device.add_child_entity(EcojokoSensor(
            main_device,
            "hp_grid_consumption",
            SensorStateClass.TOTAL_INCREASING,
            SensorDeviceClass.ENERGY,
            UnitOfEnergy.KILO_WATT_HOUR,
            "mdi:lightning-bolt"))

    # Tempo grid consumption sensors
    if config_entry.data.get(CONF_USE_TEMPO_FEATURE) is True:
        main_device.add_child_entity(EcojokoSensor(
            main_device,
            "blue_hc_grid_consumption",
            SensorStateClass.TOTAL_INCREASING,
            SensorDeviceClass.ENERGY,
            UnitOfEnergy.KILO_WATT_HOUR,
            "mdi:lightning-bolt"))
        main_device.add_child_entity(EcojokoSensor(
            main_device,
            "blue_hp_grid_consumption",
            SensorStateClass.TOTAL_INCREASING,
            SensorDeviceClass.ENERGY,
            UnitOfEnergy.KILO_WATT_HOUR,
            "mdi:lightning-bolt"))
        main_device.add_child_entity(EcojokoSensor(
            main_device,
            "white_hc_grid_consumption",
            SensorStateClass.TOTAL_INCREASING,
            SensorDeviceClass.ENERGY,
            UnitOfEnergy.KILO_WATT_HOUR,
            "mdi:lightning-bolt"))
        main_device.add_child_entity(EcojokoSensor(
            main_device,
            "white_hp_grid_consumption",
            SensorStateClass.TOTAL_INCREASING,
            SensorDeviceClass.ENERGY,
            UnitOfEnergy.KILO_WATT_HOUR,
            "mdi:lightning-bolt"))
        main_device.add_child_entity(EcojokoSensor(
            main_device,
            "red_hc_grid_consumption",
            SensorStateClass.TOTAL_INCREASING,
            SensorDeviceClass.ENERGY,
            UnitOfEnergy.KILO_WATT_HOUR,
            "mdi:lightning-bolt"))
        main_device.add_child_entity(EcojokoSensor(
            main_device,
            "red_hp_grid_consumption",
            SensorStateClass.TOTAL_INCREASING,
            SensorDeviceClass.ENERGY,
            UnitOfEnergy.KILO_WATT_HOUR,
            "mdi:lightning-bolt"))

    # Production surplus sensor
    if config_entry.data.get(CONF_USE_PROD_FEATURE) is True:
        main_device.add_child_entity(EcojokoSensor(
            main_device,
            "production_surplus",
            SensorStateClass.TOTAL_INCREASING,
            SensorDeviceClass.ENERGY,
            UnitOfEnergy.KILO_WATT_HOUR,
            "mdi:lightning-bolt"))

    # Temperature & Humidity sensors
    if config_entry.data.get(CONF_USE_TEMPHUM_FEATURE) is True:
        main_device.add_child_entity(EcojokoSensor(
            main_device,
            "indoor_temp",
            SensorStateClass.MEASUREMENT,
            SensorDeviceClass.TEMPERATURE,
            UnitOfTemperature.CELSIUS,
            "mdi:thermometer"))
        main_device.add_child_entity(EcojokoSensor(
            main_device,
            "outdoor_temp",
            SensorStateClass.MEASUREMENT,
            SensorDeviceClass.TEMPERATURE,
            UnitOfTemperature.CELSIUS,
            "mdi:thermometer"))
        main_device.add_child_entity(EcojokoSensor(
            main_device,
            "indoor_hum",
            SensorStateClass.MEASUREMENT,
            SensorDeviceClass.HUMIDITY,
            PERCENTAGE,
            "mdi:water"))
        main_device.add_child_entity(EcojokoSensor(
            main_device,
            "outdoor_hum",
            SensorStateClass.MEASUREMENT,
            SensorDeviceClass.HUMIDITY,
            PERCENTAGE,
            "mdi:water"))

    # Last Consumption Measure sensor
    if config_entry.data.get(CONF_USE_LAST_MEASURE_FEATURE) is True:
        main_device.add_child_entity(EcojokoSensor(
            main_device,
            "last_consumption_measure",
            SensorStateClass.MEASUREMENT,
            SensorDeviceClass.POWER,
            UnitOfPower.WATT,
            "mdi:flash"))
        # Last HC/HP grid consumption measure sensors
        if config_entry.data.get(CONF_USE_HCHP_FEATURE) is True:
            main_device.add_child_entity(EcojokoSensor(
                main_device,
                "last_hc_grid_consumption_measure",
                SensorStateClass.TOTAL_INCREASING,
                SensorDeviceClass.ENERGY,
                UnitOfEnergy.KILO_WATT_HOUR,
                "mdi:lightning-bolt"))
            main_device.add_child_entity(EcojokoSensor(
                main_device,
                "last_hp_grid_consumption_measure",
                SensorStateClass.TOTAL_INCREASING,
                SensorDeviceClass.ENERGY,
                UnitOfEnergy.KILO_WATT_HOUR,
                "mdi:lightning-bolt"))

    async_add_entities([main_device] + main_device.child_entities)
