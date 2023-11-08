"""LittleMonkeyEntity class."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, NAME, MANUFACTURER, VERSION
from .coordinator import LittleMonkeyDataUpdateCoordinator

class LittleMonkeyEntity(CoordinatorEntity):
    """LittleMonkeyEntity class."""

    # _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
            self,
            coordinator: LittleMonkeyDataUpdateCoordinator,
            sensor_type: str) -> None:
            # ,
            #     device_class: str,
            #     state_class: str,
            #     unit_of_measurement: str
        """Initialize."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._sensor_type = sensor_type
        # self._last_reset = '1970-01-01T00:00:00+00:00'
        self._attr_unique_id = coordinator.config_entry.entry_id
        # self._attr_device_class = device_class
        # self._attr_state_class = state_class
        # self._attr_unit_of_measurement = unit_of_measurement
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=NAME,
            model=VERSION,
            manufacturer=MANUFACTURER,
        )
        # self._attr_translation_key = translation_key
        #self._translation_key = translation_key
