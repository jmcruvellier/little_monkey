"""LittleMonkeyEntity class."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import (
    RestoreSensor,
    SensorEntity,
    SensorStateClass,
)

from .const import ATTRIBUTION, DOMAIN, LOGGER, MANUFACTURER, MODEL, VERSION
from .utils import DailyCounter, get_paris_timezone

TZ = get_paris_timezone()

# Attributes of the activity sensors: name and key of the activity data
ACTIVITY_ATTRIBUTES = {
    "savings_7_days": {"reference_consumption": "reference_consumption_7_days"},
    # Consumption of each of the last 7 days in kWh, the oldest first
    "consumption_7_days": {"daily_consumption": "daily_consumption_7_days"},
}


def _as_number(value):
    """Return a sensor value as a number, None if it is not one."""
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return value


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

class EcojokoSensor(CoordinatorEntity, RestoreSensor):
    """Representation of an Ecojoko sensor."""

    def __init__(self, main_device, sensor_name, state_class, device_class,
                 unit_of_measurement, icon, name=None):
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
        # The translation key also identifies the sensor, for the card
        self._attr_translation_key = sensor_name
        if name:
            # Name of a tariff band, chosen by the user: it wins over the
            # translation
            self._attr_name = name
        # The daily energy totals never decrease during a day (see DailyCounter)
        self._daily_counter = (
            DailyCounter()
            if state_class == SensorStateClass.TOTAL_INCREASING
            else None
        )
        self._holding = False

    async def async_added_to_hass(self) -> None:
        """Restore the value published before a restart of Home Assistant."""
        await super().async_added_to_hass()
        if self._daily_counter is None:
            return
        last_state = await self.async_get_last_state()
        last_data = await self.async_get_last_sensor_data()
        if last_state is None or last_data is None:
            return
        value = _as_number(last_data.native_value)
        if not isinstance(value, int | float):
            return
        # The value belongs to the day it was last written
        day = last_state.last_updated.astimezone(TZ).date().isoformat()
        self._daily_counter.restore(day, value)

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
        data = self.coordinator.data or {}
        # All the sensors are numeric
        value = _as_number(data.get(self._sensor_name))
        if self._daily_counter is None or value is None:
            return value
        published = self._daily_counter.update(data.get("stat_date"), value)
        holding = published > value
        if holding and not self._holding:
            LOGGER.debug(
                "%s: ecojoko lowered the value to %s, %s is kept until it catches up",
                self._sensor_name, value, published)
        self._holding = holding
        return published


class EcojokoPeriodSensor(EcojokoSensor):
    """Current tariff period, deduced from the daily counters of the periods."""

    def __init__(self, main_device, sensor_name, state_class, device_class,
                 unit_of_measurement, icon, options):
        """Initialize the sensor with its possible values."""
        super().__init__(main_device, sensor_name, state_class, device_class,
                         unit_of_measurement, icon)
        self._attr_options = list(options)
        self._restored = None

    async def async_added_to_hass(self) -> None:
        """Restore the period published before a restart of Home Assistant.

        The period is deduced from the counters a few minutes after the
        start: the last one is shown meanwhile.
        """
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in self._attr_options:
            self._restored = last_state.state

    @property
    def native_value(self):
        """Return the current period, the restored one while it is not known."""
        value = (self.coordinator.data or {}).get(self._sensor_name)
        if value in self._attr_options:
            self._restored = None
            return value
        return self._restored

    @property
    def extra_state_attributes(self):
        """Return the current tariff band (Semaine, Week-end...), if known."""
        band = (self.coordinator.data or {}).get("current_tariff_band")
        return None if band is None else {"tariff_band": band}


class EcojokoActivitySensor(CoordinatorEntity, SensorEntity):
    """Sensor of the activity of the account: savings, last 7 days..."""

    def __init__(self, main_device, activity, sensor_name, state_class,
                 device_class, unit_of_measurement, icon):
        """Initialize the sensor, updated by the activity coordinator."""
        super().__init__(activity)
        self._main_device = main_device
        self._sensor_name = sensor_name
        self._attr_state_class = state_class
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_icon = icon
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
        return (self.coordinator.data or {}).get(self._sensor_name)

    @property
    def extra_state_attributes(self):
        """Return the details of the savings and of the consumption over 7 days."""
        attributes = ACTIVITY_ATTRIBUTES.get(self._sensor_name)
        if attributes is None:
            return None
        data = self.coordinator.data or {}
        return {name: data.get(key) for name, key in attributes.items()}
