"""LittleMonkeyEntity class."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER, MODEL, VERSION

class EcojokoEntity(CoordinatorEntity):
    """EcojokoEntity class."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator, entry_id, device_name, firmware_version):
        """Initialize the main device entity."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._device_name = device_name
        self._firmware_version = firmware_version
        self._child_entities = []

    @property
    def name(self):
        """Return the name of the Ecojoko device entity."""
        return f"{self._device_name}"

    @property
    def unique_id(self):
        """Return a unique ID for the Ecojoko device entity.

        It is based on the config entry, not on the name chosen by the user,
        so that renaming keeps the entities and their history.
        """
        return self._entry_id

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
    """Representation of an Ecojoko sensor."""

    def __init__(self, main_device, sensor_name, state_class, device_class, unit_of_measurement, icon):
        """Initialize the sensor."""
        super().__init__(main_device.coordinator)
        self._main_device = main_device
        self._sensor_name = sensor_name
        self._attr_state_class = state_class
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_icon = icon
        # The name comes from the Home Assistant translations
        # (entity.sensor.<key>.name), prefixed by the device name
        self._attr_has_entity_name = True
        self._attr_translation_key = sensor_name

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information of the parent Ecojoko device."""
        return self._main_device.device_info

    @property
    def unique_id(self):
        """Return a unique ID for the sensor."""
        return f"{self._main_device.unique_id}_{self._sensor_name}"

    @property
    def native_value(self):
        """Return the value of the sensor, in its native unit."""
        value = (self.coordinator.data or {}).get(self._sensor_name)
        if isinstance(value, str):
            # All the sensors are numeric
            try:
                return float(value)
            except ValueError:
                return None
        return value
