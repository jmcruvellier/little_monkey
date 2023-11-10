"""Sensor platform for mon_ecojoko."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfPower, UnitOfEnergy, UnitOfTemperature, PERCENTAGE
from custom_components.little_monkey.coordinator import LittleMonkeyDataUpdateCoordinator

from custom_components.little_monkey.entity import LittleMonkeyEntity
from .const import (
    DOMAIN,
    CONF_USE_HCHP_FEATURE,
    CONF_USE_TEMPO_FEATURE,
    CONF_USE_TEMPHUM_FEATURE,
    CONF_USE_PROD_FEATURE
)

SENSOR_TYPES = {
    "realtime_consumption": SensorEntityDescription(
        key="realtime_consumption",
        name="Real-Time Consumption",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:flash",
    ),
    "grid_consumption": SensorEntityDescription(
        key="grid_consumption",
        name="Grid Consumption",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:lightning-bolt",
    ),
    "hc_grid_consumption": SensorEntityDescription(
        key="hc_grid_consumption",
        name="HC Grid Consumption",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:lightning-bolt",
    ),
    "hp_grid_consumption": SensorEntityDescription(
        key="hp_grid_consumption",
        name="HP Grid Consumption",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:lightning-bolt",
    ),
    "blue_hc_grid_consumption": SensorEntityDescription(
        key="blue_hc_grid_consumption",
        name="Blue HC Grid Consumption",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:lightning-bolt",
    ),
    "blue_hp_grid_consumption": SensorEntityDescription(
        key="blue_hp_grid_consumption",
        name="Blue HP Grid Consumption",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:lightning-bolt",
    ),
    "white_hc_grid_consumption": SensorEntityDescription(
        key="white_hc_grid_consumption",
        name="White HC Grid Consumption",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:lightning-bolt",
    ),
    "white_hp_grid_consumption": SensorEntityDescription(
        key="white_hp_grid_consumption",
        name="White HP Grid Consumption",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:lightning-bolt",
    ),
    "red_hc_grid_consumption": SensorEntityDescription(
        key="red_hc_grid_consumption",
        name="Red HC Grid Consumption",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:lightning-bolt",
    ),
    "red_hp_grid_consumption": SensorEntityDescription(
        key="red_hp_grid_consumption",
        name="Red HP Grid Consumption",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:lightning-bolt",
    ),
    "production_surplus": SensorEntityDescription(
        key="production_surplus",
        name="Production Surplus",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:lightning-bolt",
    ),
    "indoor_temp": SensorEntityDescription(
        key="indoor_temp",
        name="Indoor Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
    ),
    "outdoor_temp": SensorEntityDescription(
        key="outdoor_temp",
        name="Outdoor Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
    ),
    "indoor_hum": SensorEntityDescription(
        key="indoor_hum",
        name="Indoor Humidity",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.HUMIDITY,
        unit_of_measurement=PERCENTAGE,
        icon="mdi:water",
    ),
    "outdoor_hum": SensorEntityDescription(
        key="outdoor_hum",
        name="Outdoor Humidity",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.HUMIDITY,
        unit_of_measurement=PERCENTAGE,
        icon="mdi:water",
    ),
}

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the custom component sensors."""
    # Fetch data or configure your sensors here
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create a list of sensor entities
    entities = []

    # Adding real time sensor
    real_time_sensor = LittleMonkeySensor(
        coordinator=coordinator,
        sensor_type="realtime_consumption",
        tr_key="realtime_consumption"
        )
    entities.append(real_time_sensor)

    # Adding daily grid consumption sensor
    grid_consumption_sensor = LittleMonkeySensor(
        coordinator=coordinator,
        sensor_type="grid_consumption",
        tr_key="grid_consumption"
        )
    entities.append(grid_consumption_sensor)

    if CONF_USE_HCHP_FEATURE in config_entry.options:
        if config_entry.options[CONF_USE_HCHP_FEATURE] is True:
            # Adding daily hc grid consumption sensor
            hc_grid_consumption_sensor = LittleMonkeySensor(
                coordinator=coordinator,
                sensor_type="hc_grid_consumption",
                tr_key="hc_grid_consumption"
                )
            entities.append(hc_grid_consumption_sensor)

            # Adding daily hp grid consumption sensor
            hp_grid_consumption_sensor = LittleMonkeySensor(
                coordinator=coordinator,
                sensor_type="hp_grid_consumption",
                tr_key="hp_grid_consumption"
                )
            entities.append(hp_grid_consumption_sensor)

    if CONF_USE_TEMPO_FEATURE in config_entry.options:
        if config_entry.options[CONF_USE_TEMPO_FEATURE] is True:
            # Adding daily blue hc grid consumption sensor
            blue_hc_grid_consumption_sensor = LittleMonkeySensor(
                coordinator=coordinator,
                sensor_type="blue_hc_grid_consumption",
                tr_key="blue_hc_grid_consumption"
                )
            entities.append(blue_hc_grid_consumption_sensor)

            # Adding daily blue hp grid consumption sensor
            blue_hp_grid_consumption_sensor = LittleMonkeySensor(
                coordinator=coordinator,
                sensor_type="blue_hp_grid_consumption",
                tr_key="blue_hp_grid_consumption"
                )
            entities.append(blue_hp_grid_consumption_sensor)

            # Adding daily white hc grid consumption sensor
            white_hc_grid_consumption_sensor = LittleMonkeySensor(
                coordinator=coordinator,
                sensor_type="white_hc_grid_consumption",
                tr_key="white_hc_grid_consumption"
                )
            entities.append(white_hc_grid_consumption_sensor)

            # Adding daily white hp grid consumption sensor
            white_hp_grid_consumption_sensor = LittleMonkeySensor(
                coordinator=coordinator,
                sensor_type="white_hp_grid_consumption",
                tr_key="white_hp_grid_consumption"
                )
            entities.append(white_hp_grid_consumption_sensor)

            # Adding daily red hc grid consumption sensor
            red_hc_grid_consumption_sensor = LittleMonkeySensor(
                coordinator=coordinator,
                sensor_type="red_hc_grid_consumption",
                tr_key="red_hc_grid_consumption"
                )
            entities.append(red_hc_grid_consumption_sensor)

            # Adding daily red hp grid consumption sensor
            red_hp_grid_consumption_sensor = LittleMonkeySensor(
                coordinator=coordinator,
                sensor_type="red_hp_grid_consumption",
                tr_key="red_hp_grid_consumption"
                )
            entities.append(red_hp_grid_consumption_sensor)

    if CONF_USE_PROD_FEATURE in config_entry.options:
        if config_entry.options[CONF_USE_PROD_FEATURE] is True:
            # Adding daily production surplus sensor
            production_surplus_sensor = LittleMonkeySensor(
                coordinator=coordinator,
                sensor_type="production_surplus",
                tr_key="production_surplus"
                )
            entities.append(production_surplus_sensor)

    if CONF_USE_TEMPHUM_FEATURE in config_entry.options:
        if config_entry.options[CONF_USE_TEMPHUM_FEATURE] is True:
            # Adding indoor temperature sensor
            indoor_temp_sensor = LittleMonkeySensor(
                coordinator=coordinator,
                sensor_type="indoor_temp",
                tr_key="indoor_temp"
                )
            entities.append(indoor_temp_sensor)

            # Adding outdoor temperature sensor
            outdoor_temp_sensor = LittleMonkeySensor(
                coordinator=coordinator,
                sensor_type="outdoor_temp",
                tr_key="outdoor_temp"
                )
            entities.append(outdoor_temp_sensor)

            # Adding indoor humidity sensor
            indoor_hum_sensor = LittleMonkeySensor(
                coordinator=coordinator,
                sensor_type="indoor_hum",
                tr_key="indoor_hum"
                )
            entities.append(indoor_hum_sensor)

            # Adding outdoor humidity sensor
            outdoor_hum_sensor = LittleMonkeySensor(
                coordinator=coordinator,
                sensor_type="outdoor_hum",
                tr_key="outdoor_hum"
                )
            entities.append(outdoor_hum_sensor)

    async_add_entities(entities)

class LittleMonkeySensor(LittleMonkeyEntity,SensorEntity):
    """Representation of Little Monkey sensor."""

    #_attr_has_entity_name = True

    def __init__(
            self,
            coordinator: LittleMonkeyDataUpdateCoordinator,
            sensor_type: str,
            tr_key: str
            ):
        """Initialize the sensor."""
        super().__init__(coordinator, sensor_type)
        self.entity_description = SENSOR_TYPES[sensor_type]
        self._attr_translation_key = tr_key
        self._attr_has_entity_name = True

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._coordinator.name}_{self._sensor_type}"

    @property
    def available(self):
        """Return the availability of the sensor."""
        return self._coordinator.last_update_success

    @property
    def name(self):
        """Return the name of the sensor."""
#        return f"{self.entity_description.name}"
        return self.coordinator.tranfile[self.entity_description.key]

    @property
    def state(self) -> Any:
        """Return the state of the sensor."""
        return self._coordinator.data[self._sensor_type]

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self.entity_description.icon

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self.entity_description.unit_of_measurement

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self.entity_description.device_class

    # @property
    # def last_reset(self):
    #     """Retrun the last reset of the sensor."""
    #     return self._last_reset

    # @property
    # def translation_key(self):
    #     """Retrun the translation key of the sensor."""
    #     return self._translation_key
