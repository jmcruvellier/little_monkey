"""LittleMonkeyEntity class."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER, MODEL, VERSION

class EcojokoEntity(CoordinatorEntity):
    """EcojokoEntity class."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator, device_name, firmware_version):
        """Initialize the main device entity."""
        super().__init__(coordinator)
        self._device_name = device_name
        self._firmware_version = firmware_version
        self._child_entities = []

    @property
    def name(self):
        """Return the name of the Ecojoko device entity."""
        return f"{self._device_name}"

    @property
    def unique_id(self):
        """Return a unique ID for the Ecojoko device entity."""
        return f"{DOMAIN}_{self._device_name}"
        # return f"{DOMAIN}_main_device_{self._device_name}"

    @property
    def state(self):
        """Return the state of the main device."""
        return self._firmware_version

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the main device."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": VERSION,
            "hw_version": self._firmware_version,
        }

    @property
    def child_entities(self):
        """Return a list of child entities linked to the main device."""
        return self._child_entities

    def add_child_entity(self, child_entity):
        """Add a child entity to the main device."""
        self._child_entities.append(child_entity)

class EcojokoSensor(CoordinatorEntity, SensorEntity):
    """Representation of a my_device sensor."""

    def __init__(self, main_device, sensor_name, state_class, device_class, unit_of_measurement, icon):
        """Initialize the sensor."""
        super().__init__(main_device.coordinator)
        self._main_device = main_device
        self._sensor_name = sensor_name
        self._state_class = state_class
        self._device_class = device_class
        self._unit_of_measurement = unit_of_measurement
        self._icon = icon
        self._attr_translation_key = sensor_name
        self._attr_has_entity_name = True

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._main_device.name} - {self._main_device.coordinator.tranfile[self._sensor_name]}"

    @property
    def unique_id(self):
        """Return a unique ID for the sensor."""
        return f"{self._main_device.unique_id}_{self._sensor_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get(self._sensor_name)

    @property
    def state_class(self):
        """Return the state class of the sensor."""
        return self._state_class

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            "device_name": self._main_device.name,
            "firmware_version": self._main_device._firmware_version,
        }

    # def update(self):
    #     """Update the sensor data."""
    #     # Add code here to update sensor data (e.g., read temperature from the device)
    #     # For simplicity, we'll set a dummy value
    #     self.coordinator.data[self._sensor_name] = 27.0  # Replace with actual sensor data
