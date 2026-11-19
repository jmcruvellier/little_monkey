"""Select platform for little_monkey: the mode of the piloted equipments."""
from __future__ import annotations

import datetime as dt

from homeassistant.components.select import SelectEntity

from .api import TZ
from .const import CONF_USE_EQUIPMENT_FEATURE, option_enabled
from .entity import EcojokoEntity, EcojokoEquipmentEntity, equipment_modes

# Duration of a forced mode chosen in the list: the shortest one of ecojoko
FORCED_SECONDS = 3600


def seconds_until_midnight(now: dt.datetime) -> int:
    """Return the seconds until the next midnight in Paris.

    An absence chosen in the list lasts until then, as the first day offered
    by ecojoko: its web application ends an absence at midnight.
    """
    local = now.astimezone(TZ)
    midnight = dt.datetime.combine(local.date() + dt.timedelta(days=1), dt.time(), TZ)
    # Through the timestamps: a difference of two times of the same time
    # zone ignores the change of the clocks, and the day it changes lasts
    # 23 or 25 hours
    return int(midnight.timestamp() - local.timestamp())


class EcojokoEquipmentSelect(EcojokoEquipmentEntity, SelectEntity):
    """Mode of a piloted equipment: automatic, forced or absence, or on and off.

    A forced mode chosen here lasts an hour and an absence until midnight;
    the service set_equipment_mode chooses any duration.
    """

    _attr_icon = "mdi:remote"

    def __init__(self, main_device, coordinator, equipment):
        """Initialize the list with the modes ecojoko offers."""
        super().__init__(main_device, coordinator, equipment, "equipment_mode")
        self._attr_options = equipment_modes(equipment)

    @property
    def current_option(self) -> str | None:
        """Return the current mode."""
        equipment = self._equipment()
        return None if equipment is None else equipment["state"].get("mode")

    async def async_select_option(self, option: str) -> None:
        """Send the mode to ecojoko."""
        seconds = None
        if option == "forced":
            seconds = FORCED_SECONDS
        elif option == "absence":
            seconds = seconds_until_midnight(dt.datetime.now(TZ))
        await self.coordinator.async_command(self._equipment_id, option, seconds)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the mode of each piloted equipment."""
    coordinator = config_entry.runtime_data
    if not option_enabled(config_entry, CONF_USE_EQUIPMENT_FEATURE):
        return
    main_device = EcojokoEntity(
        coordinator, config_entry.entry_id, None, coordinator.data["gateway_firmware_version"])
    async_add_entities([
        EcojokoEquipmentSelect(main_device, coordinator.equipment, equipment)
        for equipment in coordinator.equipment.piloted()
    ])
