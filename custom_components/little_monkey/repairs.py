"""Repairs for little_monkey."""
from __future__ import annotations

from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant

from .const import CONF_TARIFF_BANDS
from .tariff import new_band


class AddBandsFlow(RepairsFlow):
    """Add the tariff bands found in the statistics to the entry."""

    def __init__(self, entry_id: str, bands: dict[str, str]) -> None:
        """Initialize with the entry and the bands {id: label} to add."""
        super().__init__()
        self._entry_id = entry_id
        self._bands = bands

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ):
        """Ask for the confirmation."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ):
        """Add the bands with their default settings once confirmed."""
        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(self._entry_id)
            if entry is not None:
                configured = list(entry.data.get(CONF_TARIFF_BANDS) or [])
                known = {band["id"] for band in configured}
                configured += [
                    new_band(int(band_id), label)
                    for band_id, label in self._bands.items()
                    if int(band_id) not in known
                ]
                # The update listener reloads the entry
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_TARIFF_BANDS: configured})
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "bands": ", ".join(sorted(self._bands.values()))},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create the flow fixing an issue."""
    data = data or {}
    return AddBandsFlow(data.get("entry_id", ""), data.get("bands") or {})
