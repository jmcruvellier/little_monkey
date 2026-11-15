"""Custom integration to integrate little_monkey with Home Assistant.

For more details about this integration, please refer to
https://github.com/jmcruvellier/little_monkey
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import LittleMonkeyApiClient
from .card import async_register_card
from .const import (
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    POLL_INTERVAL,
    CONF_USE_HCHP_FEATURE,
    CONF_USE_TEMPO_FEATURE,
    CONF_USE_TEMPHUM_FEATURE,
    CONF_USE_PROD_FEATURE
)
from .coordinator import LittleMonkeyDataUpdateCoordinator
from .sensor import SENSORS
from .utils import account_unique_id

# Version of the config entries, see EcojokoFlowHandler.VERSION
ENTRY_VERSION = 2

# Configured from the user interface only
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration, once for all its entries."""
    await async_register_card(hass)
    return True


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    # Done before the update listener is registered: it does not reload
    _async_sync_unique_id(hass, entry)
    coordinator = LittleMonkeyDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        client=LittleMonkeyApiClient(
            username=entry.data.get(CONF_USERNAME, ""),
            password=entry.data.get(CONF_PASSWORD, ""),
            poll_interval=entry.data.get(POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
            use_hchp=entry.data.get(CONF_USE_HCHP_FEATURE, False),
            use_tempo=entry.data.get(CONF_USE_TEMPO_FEATURE, False),
            use_temphum=entry.data.get(CONF_USE_TEMPHUM_FEATURE, False),
            use_prod=entry.data.get(CONF_USE_PROD_FEATURE, False),
            # A session of its own, with its own cookies: the ecojoko session
            # cookie is not shared with the other integrations nor with
            # another ecojoko account. Home Assistant releases it when the
            # entry is unloaded.
            session=async_create_clientsession(hass),
        ),
    )
    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Home Assistant removes it when the entry is unloaded
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _async_sync_unique_id(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Identify the entry by its ecojoko account.

    It prevents the same account from being added twice. Entries created
    before 1.2.8 have no unique id, and the username can be changed in the
    options. An account already used by another entry is left as it is.
    """
    unique_id = account_unique_id(entry.data.get(CONF_USERNAME, ""))
    if not unique_id or entry.unique_id == unique_id:
        return
    for other in hass.config_entries.async_entries(DOMAIN):
        if other.entry_id != entry.entry_id and other.unique_id == unique_id:
            return
    hass.config_entries.async_update_entry(entry, unique_id=unique_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate a config entry created by a previous version."""
    if entry.version > ENTRY_VERSION:
        # Created by a more recent version of the integration
        return False
    if entry.version == 1:
        _migrate_unique_ids(hass, entry)
        # The language option was removed in 1.2.8
        data = {key: value for key, value in entry.data.items() if key != "lang"}
        hass.config_entries.async_update_entry(
            entry, data=data, options={}, version=ENTRY_VERSION
        )
        LOGGER.info("Config entry %s migrated to version %s",
                    entry.title, ENTRY_VERSION)
    return True


def _migrate_unique_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Replace the unique ids based on the name by ids based on the entry.

    Until 1.2.7 the entities and the device were identified by the name
    chosen by the user: renaming created new entities and lost the history.
    Entity ids, history and statistics are kept by this migration. Entities
    left behind by a previous renaming do not match the current name and are
    not touched.
    """
    old_base = f"{DOMAIN}_{entry.data.get(CONF_NAME)}"
    new_base = entry.entry_id
    new_unique_ids = {old_base: new_base}
    for key, _kind, _option in SENSORS:
        new_unique_ids[f"{old_base}_{key}"] = f"{new_base}_{key}"

    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        new_unique_id = new_unique_ids.get(entity.unique_id)
        if new_unique_id is None:
            continue
        if entity_registry.async_get_entity_id(
            entity.domain, entity.platform, new_unique_id
        ):
            LOGGER.warning(
                "Entity %s not migrated: its new unique id already exists",
                entity.entity_id)
            continue
        entity_registry.async_update_entity(
            entity.entity_id, new_unique_id=new_unique_id)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, old_base)})
    if (
        device is not None
        and entry.entry_id in device.config_entries
        and device_registry.async_get_device(
            identifiers={(DOMAIN, new_base)}) is None
    ):
        device_registry.async_update_device(
            device.id, new_identifiers={(DOMAIN, new_base)})


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Tell whether a device can be removed from the user interface.

    Until 1.2.7 renaming the integration created a new device and left the
    previous one behind, with unavailable entities. Such a device can be
    removed; the device currently provided by the entry cannot.
    """
    return (DOMAIN, entry.entry_id) not in device_entry.identifiers


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
