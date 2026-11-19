"""Binary sensor platform for little_monkey: the contactor of the piloted equipments."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import CONF_USE_EQUIPMENT_FEATURE, option_enabled
from .entity import EcojokoEntity, EcojokoEquipmentEntity

# Details of the contactor, as attributes: since when, and why
SWITCH_ATTRIBUTES = ("since", "source")


def has_contactor_sensor(equipment) -> bool:
    """Tell whether an equipment gets a contactor sensor.

    Only with an automatic mode: the mode stays « Automatique » while ecojoko
    switches the equipment on and off. Without it, the mode is on or off,
    the state of the contactor already.
    """
    return "auto" in (equipment.get("controls") or [])


class EcojokoEquipmentContactor(EcojokoEquipmentEntity, BinarySensorEntity):
    """Contactor of a piloted equipment: on or off, whatever its mode.

    A water heater whose water is hot draws no power with its contactor on:
    its thermostat cuts the heating.
    """

    def __init__(self, main_device, coordinator, equipment):
        """Initialize the contactor sensor."""
        super().__init__(main_device, coordinator, equipment, "equipment_switch")

    @property
    def is_on(self) -> bool | None:
        """Tell whether the contactor is on."""
        equipment = self._equipment()
        return None if equipment is None else equipment["state"].get("on")

    @property
    def icon(self) -> str:
        """Return a closed or an open switch."""
        return "mdi:electric-switch-closed" if self.is_on else "mdi:electric-switch"

    @property
    def extra_state_attributes(self):
        """Return since when the contactor is in its state, and why."""
        equipment = self._equipment()
        if equipment is None:
            return None
        return {name: equipment["state"].get(name) for name in SWITCH_ATTRIBUTES}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the contactor of each piloted equipment with an automatic mode."""
    coordinator = config_entry.runtime_data
    if not option_enabled(config_entry, CONF_USE_EQUIPMENT_FEATURE):
        return
    main_device = EcojokoEntity(
        coordinator, config_entry.entry_id, None, coordinator.data["gateway_firmware_version"])
    async_add_entities([
        EcojokoEquipmentContactor(main_device, coordinator.equipment, equipment)
        for equipment in coordinator.equipment.piloted()
        if has_contactor_sensor(equipment)
    ])
