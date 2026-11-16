"""Diagnostics support for little_monkey."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import VERSION

# The title and the unique id of the entry are the ecojoko username. The name
# is a free text chosen by the user, which may be personal.
TO_REDACT = {CONF_NAME, CONF_USERNAME, CONF_PASSWORD, "title", "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry, without the credentials."""
    diagnostics: dict[str, Any] = {
        "integration_version": VERSION,
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
    }
    # The coordinator is missing when the setup of the entry failed
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        return diagnostics

    update_interval = coordinator.update_interval
    last_exception = coordinator.last_exception
    diagnostics["coordinator"] = {
        "last_update_success": coordinator.last_update_success,
        "update_interval_seconds": (
            None if update_interval is None else update_interval.total_seconds()
        ),
        "last_exception": None if last_exception is None else str(last_exception),
    }
    diagnostics["data"] = coordinator.data
    activity = getattr(coordinator, "activity", None)
    if activity is not None:
        diagnostics["activity"] = {
            "last_update_success": activity.last_update_success,
            "last_exception": (
                None if activity.last_exception is None
                else str(activity.last_exception)),
            "data": activity.data,
        }
    diagnostics["client"] = coordinator.client.diagnostics()
    return diagnostics
