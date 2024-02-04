"""Custom integration to integrate little_monkey with Home Assistant.

For more details about this integration, please refer to
https://github.com/jmcruvellier/little_monkey
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LittleMonkeyApiClient
from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_USE_LAST_MEASURE_FEATURE,
    CONF_USE_HCHP_FEATURE,
    CONF_USE_TEMPO_FEATURE,
    CONF_USE_TEMPHUM_FEATURE,
    CONF_USE_PROD_FEATURE
)
from .coordinator import LittleMonkeyDataUpdateCoordinator

def get_boolean(array, index):
    """Read the value with a default of False if the key is not found."""
    return array.get(index, False)

def get_string(array, index):
    """Read the value with a default of empty string if the key is not found."""
    return array.get(index, "")


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    hass.data.setdefault(DOMAIN, {})
    coordinator = LittleMonkeyDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        client=LittleMonkeyApiClient(
            username=get_string(entry.data, CONF_USERNAME),
            password=get_string(entry.data, CONF_PASSWORD),
            use_last_measure=get_boolean(entry.data, CONF_USE_LAST_MEASURE_FEATURE),
            use_hchp=get_boolean(entry.data, CONF_USE_HCHP_FEATURE),
            use_tempo=get_boolean(entry.data, CONF_USE_TEMPO_FEATURE),
            use_temphum=get_boolean(entry.data, CONF_USE_TEMPHUM_FEATURE),
            use_prod=get_boolean(entry.data, CONF_USE_PROD_FEATURE),
            session=async_get_clientsession(hass),
        ),
    )
    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
