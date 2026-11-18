"""LittleMonkeyEntity class."""
from __future__ import annotations

from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import (
    RestoreSensor,
    SensorEntity,
    SensorStateClass,
)

from .const import ATTRIBUTION, DOMAIN, LOGGER, MANUFACTURER, MODEL, VERSION

from .utils import DailyCounter, get_paris_timezone

# Modes of a piloted equipment, by its controls (see api.equipment_controls)
EQUIPMENT_MODES = {"auto": ["auto", "forced", "absence"], "on": ["on", "off"]}

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


class EcojokoContractSensor(EcojokoSensor):
    """Contract of the installation: its offer, with its details as attributes.

    The contract is read every six hours; the last one is kept meanwhile.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, main_device, sensor_name, bands, icon="mdi:file-document-outline"):
        """Initialize the sensor with the configured tariff bands."""
        super().__init__(main_device, sensor_name, None, None, None, icon)
        # Bands of the contract: sensor key, name and total (hc or hp)
        self._bands = [
            {
                "key": band.get("key"),
                "name": band.get("name") or band.get("label"),
                "category": band.get("category"),
            }
            for band in bands
        ]

    def _contract(self) -> dict | None:
        """Return the contract read from ecojoko, None until it is read."""
        contract = (self.coordinator.data or {}).get("contract")
        return contract if isinstance(contract, dict) else None

    @property
    def native_value(self):
        """Return the name of the offer, as ecojoko gives it."""
        contract = self._contract()
        if contract is None or not contract.get("offer_name"):
            return None
        # A state is at most 255 characters long
        return str(contract["offer_name"])[:255]

    @property
    def extra_state_attributes(self):
        """Return the details of the contract and its tariff bands."""
        contract = self._contract() or {}
        return {
            "supplier": contract.get("supplier_name"),
            "offer_type": contract.get("offer_type"),
            "power": contract.get("power"),
            "subscription_price": contract.get("subscription_price"),
            "start_date": contract.get("start_date"),
            "off_peak_timeslots": contract.get("off_peak_timeslots") or [],
            "bands": self._bands,
        }


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


# Attributes of the savings sensors over 12 months: name and key of the data
SAVINGS_ATTRIBUTES = {
    "consumption_cost_12_months": {"consumption": "consumption_12_months"},
    "reference_cost_12_months": {
        "reference_consumption": "reference_consumption_12_months"},
    "savings_12_months": {
        "savings_kwh": "savings_kwh_12_months", "level": "savings_level"},
}
# Savings sensors of the current week, month and year: key of their data
SAVINGS_PERIOD_SENSORS = {
    "savings_week": "week",
    "savings_month": "month",
    "savings_year": "year",
}


class EcojokoSavingsSensor(EcojokoActivitySensor):
    """Sensor of the savings: over 12 months, this week, month or year."""

    # The bars of the period are for the card: kept out of the history
    _unrecorded_attributes = frozenset({"bars"})

    def _period(self) -> dict | None:
        """Return the savings of the period of the sensor, None if not one."""
        period = SAVINGS_PERIOD_SENSORS.get(self._sensor_name)
        if period is None:
            return None
        return (self.coordinator.data or {}).get(period) or {}

    @property
    def native_value(self):
        """Return the savings, in euros."""
        period = self._period()
        if period is None:
            return super().native_value
        return period.get("savings")

    @property
    def extra_state_attributes(self):
        """Return the details of the savings: kWh, costs, bars..."""
        period = self._period()
        if period is not None:
            return {key: value for key, value in period.items() if key != "savings"}
        data = self.coordinator.data or {}
        attributes = SAVINGS_ATTRIBUTES.get(self._sensor_name, {})
        return {name: data.get(key) for name, key in attributes.items()}


def equipment_identifier(entry_id, equipment_id) -> tuple:
    """Return the identifier of the device of an equipment of the gateway."""
    return (DOMAIN, f"{entry_id}_{equipment_id}")


def equipment_modes(equipment) -> list:
    """Return the modes of a piloted equipment, empty if it is not piloted."""
    controls = equipment.get("controls") or []
    for control, modes in EQUIPMENT_MODES.items():
        if control in controls:
            return list(modes)
    return []


class EcojokoEquipmentEntity(CoordinatorEntity):
    """Entity of an equipment of the gateway (water heater...).

    Each equipment is a device of its own, linked to the Ecojoko device.
    """

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, main_device, coordinator, equipment, key):
        """Initialize the entity of an equipment, identified by its ecojoko id."""
        super().__init__(coordinator)
        self._equipment_id = equipment["id"]
        self._key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{main_device.unique_id}_{equipment['id']}_{key}"
        self._attr_device_info = {
            "identifiers": {equipment_identifier(main_device.unique_id, equipment["id"])},
            "name": equipment.get("name") or equipment.get("type"),
            "manufacturer": MODEL,
            "model": equipment.get("model") or equipment.get("type"),
            "sw_version": equipment.get("firmware"),
            "via_device": (DOMAIN, main_device.unique_id),
        }

    def _equipment(self) -> dict | None:
        """Return the equipment as last read, None if it was not read."""
        return (self.coordinator.data or {}).get(self._equipment_id)

    @property
    def available(self) -> bool:
        """Tell whether the equipment was read."""
        return super().available and self._equipment() is not None


# Value of each sensor of an equipment, from the equipment read
EQUIPMENT_VALUES = {
    "equipment_power": lambda equipment: equipment["state"].get("power"),
    "equipment_energy": lambda equipment: (equipment.get("day") or {}).get("energy"),
    "equipment_cost": lambda equipment: (equipment.get("day") or {}).get("cost"),
    "equipment_mode": lambda equipment: equipment["state"].get("mode"),
}
# Details of the mode, as attributes
EQUIPMENT_MODE_ATTRIBUTES = ("switch_state", "since", "until", "source")


class EcojokoEquipmentSensor(EcojokoEquipmentEntity, SensorEntity):
    """Sensor of a piloted equipment: power, energy and cost of the day, mode."""

    def __init__(self, main_device, coordinator, equipment, key, state_class,
                 device_class, unit_of_measurement, icon):
        """Initialize the sensor."""
        super().__init__(main_device, coordinator, equipment, key)
        self._attr_state_class = state_class
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_icon = icon
        if key == "equipment_mode":
            self._attr_options = equipment_modes(equipment)

    @property
    def native_value(self):
        """Return the value of the sensor, from the equipment last read."""
        equipment = self._equipment()
        return None if equipment is None else EQUIPMENT_VALUES[self._key](equipment)

    @property
    def extra_state_attributes(self):
        """Return the details of the mode: since and until when, and why."""
        equipment = self._equipment()
        if self._key != "equipment_mode" or equipment is None:
            return None
        return {name: equipment["state"].get(name) for name in EQUIPMENT_MODE_ATTRIBUTES}


# Value of each diagnostic sensor of an equipment
EQUIPMENT_DIAGNOSTIC_VALUES = {
    "equipment_connection": lambda equipment: (
        None if equipment.get("connected") is None
        else "connected" if equipment["connected"] else "disconnected"),
    "equipment_signal": lambda equipment: equipment.get("signal"),
    "equipment_wifi_signal": lambda equipment: equipment.get("wifi_signal"),
    "equipment_battery": lambda equipment: equipment.get("battery"),
}


class EcojokoEquipmentDiagnosticSensor(EcojokoEquipmentEntity, SensorEntity):
    """Diagnostic sensor of an equipment: connection, signal, battery.

    Every equipment of the gateway has them, piloted or not; they come with
    the list of the gateways, read every five minutes.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, main_device, equipment, key, state_class, device_class,
                 unit_of_measurement, icon):
        """Initialize the sensor, updated by the main coordinator."""
        super().__init__(main_device, main_device.coordinator, equipment, key)
        self._attr_state_class = state_class
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_icon = icon
        if key == "equipment_connection":
            self._attr_options = ["connected", "disconnected"]

    def _equipment(self) -> dict | None:
        """Return the equipment as read with the list of the gateways."""
        return ((self.coordinator.data or {}).get("equipments") or {}).get(self._equipment_id)

    @property
    def native_value(self):
        """Return the value of the sensor."""
        equipment = self._equipment()
        return None if equipment is None else EQUIPMENT_DIAGNOSTIC_VALUES[self._key](equipment)
