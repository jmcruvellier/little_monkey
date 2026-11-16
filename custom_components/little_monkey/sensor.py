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

from .entity import (
    EcojokoActivitySensor,
    EcojokoEntity,
    EcojokoPeriodSensor,
    EcojokoSensor,
)
from .tariff import KNOWN_BANDS, TEMPO_BANDS, band_key, has_sensor
from .const import (
    CONF_USE_HCHP_FEATURE,
    CONF_TARIFF_BANDS,
    CONF_USE_TEMPHUM_FEATURE,
    CONF_USE_PROD_FEATURE,
    tariff_periods,
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

PERIOD = (
    None,
    SensorDeviceClass.ENUM,
    None,
    "mdi:clock-time-four-outline",
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
    # Current tariff period sensor, with the HC/HP totals or a Tempo
    # contract (see tariff_periods)
    ("current_tariff_period", PERIOD, None),
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

SAVINGS = (
    SensorStateClass.MEASUREMENT,
    None,
    PERCENTAGE,
    "mdi:piggy-bank-outline",
)
# Totals over a sliding period: neither a measurement nor an increasing total
ENERGY_7_DAYS = (None, SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, "mdi:lightning-bolt")
COST = (None, SensorDeviceClass.MONETARY, "EUR", "mdi:currency-eur")
MAX_POWER = (None, SensorDeviceClass.POWER, UnitOfPower.WATT, "mdi:flash-alert")

# Sensors of the activity of the account, read apart from the polls
ACTIVITY_SENSORS = (
    ("savings_7_days", SAVINGS),
    ("consumption_7_days", ENERGY_7_DAYS),
    ("cost_7_days", COST),
    ("total_savings", COST),
    ("max_power_month", MAX_POWER),
    ("max_power_year", MAX_POWER),
    ("max_power_alltime", MAX_POWER),
)

# Option that enables a sensor: None (always), one option, or several (any)


def _enabled(option, data):
    """Tell whether a sensor is enabled by the options of a config entry."""
    if option is None:
        return True
    options = option if isinstance(option, tuple) else (option,)
    return any(data.get(name) is True for name in options)


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
        if not _enabled(option, config_entry.data):
            continue
        if kind is PERIOD:
            periods = tariff_periods(config_entry.data)
            if periods is None:
                continue
            sensor = EcojokoPeriodSensor(main_device, key, *kind, periods)
        else:
            sensor = EcojokoSensor(main_device, key, *kind)
        main_device.add_child_entity(sensor)
    # One sensor per tariff band of the contract
    for band in config_entry.data.get(CONF_TARIFF_BANDS) or []:
        if has_sensor(band):
            # A known sensor without a chosen name keeps its translated name
            name = band.get("name")
            if not name and band["id"] not in KNOWN_BANDS:
                name = band.get("label")
            main_device.add_child_entity(EcojokoSensor(
                main_device, band["key"], *ENERGY, name=name))

    for key, kind in ACTIVITY_SENSORS:
        main_device.add_child_entity(
            EcojokoActivitySensor(main_device, coordinator.activity, key, *kind))

    async_add_entities([main_device] + main_device.child_entities)
