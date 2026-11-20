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
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import LittleMonkeyApiClient
from .card import async_register_card
from .const import (
    DEFAULT_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    VERSION,
    LOGGER,
    PLATFORMS,
    POLL_INTERVAL,
    CONF_USE_HCHP_FEATURE,
    CONF_USE_TEMPO_FEATURE,
    CONF_USE_TEMPHUM_FEATURE,
    CONF_USE_PROD_FEATURE,
    CONF_REMOVED_BANDS,
    CONF_TARIFF_BANDS,
    CONF_USE_ACTIVITY_FEATURE,
    CONF_USE_EQUIPMENT_FEATURE,
    CONF_USE_SAVINGS_FEATURE,
    option_enabled,
)
from .coordinator import (
    LittleMonkeyActivityCoordinator,
    LittleMonkeyDataUpdateCoordinator,
    LittleMonkeyEquipmentCoordinator,
    LittleMonkeySavingsCoordinator,
    unknown_bands_issue_id,
)
from .entity import device_entry_ids, equipment_identifier, registry_device
from .sensor import GROUP_SENSOR_KEYS, SENSOR_KEYS
from .services import async_register_services
from .tariff import has_sensor, is_band_key, legacy_bands
from .utils import account_unique_id

# Version of the config entries, see EcojokoFlowHandler.VERSION
ENTRY_VERSION = 3
ENTRY_MINOR_VERSION = 3

# Configured from the user interface only
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration, once for all its entries."""
    await async_register_card(hass)
    async_register_services(hass)
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
            bands=entry.data.get(CONF_TARIFF_BANDS),
            removed_bands=entry.data.get(CONF_REMOVED_BANDS),
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

    # Activity of the account, read apart from the polls: ecojoko is slow to
    # answer, the setup does not wait for it
    coordinator.activity = LittleMonkeyActivityCoordinator(
        hass=hass, entry=entry, client=coordinator.client)
    # Each one is read only when its option is on: no call to ecojoko
    # otherwise
    if option_enabled(entry, CONF_USE_ACTIVITY_FEATURE):
        entry.async_create_background_task(
            hass, coordinator.activity.async_refresh(), "little_monkey activity")
    # Savings of the account, read the same way
    coordinator.savings = LittleMonkeySavingsCoordinator(
        hass=hass, entry=entry, client=coordinator.client)
    if option_enabled(entry, CONF_USE_SAVINGS_FEATURE):
        entry.async_create_background_task(
            hass, coordinator.savings.async_refresh(), "little_monkey savings")
    # Piloted equipments, read the same way
    coordinator.equipment = LittleMonkeyEquipmentCoordinator(
        hass=hass, entry=entry, client=coordinator.client)
    if option_enabled(entry, CONF_USE_EQUIPMENT_FEATURE):
        entry.async_create_background_task(
            hass, coordinator.equipment.async_refresh(), "little_monkey equipment")
    entry.async_on_unload(coordinator.equipment.async_cancel_end_reading)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Home Assistant removes it when the entry is unloaded
    entry.runtime_data = coordinator

    # The Ecojoko device exists before the devices of the equipments, which
    # are linked to it by its id
    main_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data.get(CONF_NAME),
        manufacturer=MANUFACTURER,
        model=MODEL,
        sw_version=VERSION,
        hw_version=coordinator.data.get("gateway_firmware_version"),
    )
    coordinator.main_device_id = main_device.id

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_remove_old_equipment_devices(hass, entry)
    _async_remove_disabled_entities(hass, entry)

    return True


def _async_remove_disabled_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the sensors of the groups whose option is off, and of the bands removed.

    They were created while it was on, or while the band was configured;
    otherwise they would stay unavailable. Turned on again, the option
    creates them again, and so does a band added again.
    """
    keys = set()
    for option, group in GROUP_SENSOR_KEYS.items():
        if not option_enabled(entry, option):
            keys |= set(group)
    configured = {
        band["key"] for band in entry.data.get(CONF_TARIFF_BANDS) or []
        if has_sensor(band)}
    equipment_prefix = f"{entry.entry_id}_"
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        key = entity.unique_id.removeprefix(equipment_prefix)
        # The sensors of the equipments: <entry>_<equipment id>_<key>
        equipment = key.split("_", 1)[0].isdigit()
        removed_band = is_band_key(key) and key not in configured
        if ((key in keys or removed_band) and not equipment) or (
            equipment and not option_enabled(entry, CONF_USE_EQUIPMENT_FEATURE)
        ):
            registry.async_remove(entity.entity_id)


def _equipment_devices(entry: ConfigEntry) -> set:
    """Return the identifiers of the devices of the piloted equipments.

    None without the option of the equipments.
    """
    if not option_enabled(entry, CONF_USE_EQUIPMENT_FEATURE):
        return set()
    return {
        equipment_identifier(entry.entry_id, equipment["id"])
        for equipment in entry.runtime_data.client.equipments
        if equipment["controls"]
    }


def _async_remove_old_equipment_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the devices of the equipments that are no longer piloted.

    Only a piloted equipment has a device. The device of an equipment
    removed from ecojoko, or left empty by a version under development that
    gave one to every equipment, is removed, and every one without the
    option of the equipments. Nothing is removed while the equipments are
    unknown, the option being on.
    """
    if not entry.runtime_data.client.equipments and option_enabled(
            entry, CONF_USE_EQUIPMENT_FEATURE):
        return
    current = _equipment_devices(entry)
    prefix = f"{entry.entry_id}_"
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        equipment = any(
            domain == DOMAIN and identifier.startswith(prefix)
            for domain, identifier in device.identifiers)
        if equipment and not current & device.identifiers:
            registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)


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
            entry, data=data, options={}, version=2
        )
        LOGGER.info("Config entry %s migrated to version 2", entry.title)
    if entry.version == 2:
        # The Tempo option is replaced by the tariff bands. The bands of the
        # HC/HP and Tempo options keep the keys of their sensors, and so
        # their entity ids, history and statistics. No network here: other
        # bands of the contract are counted by their label until the user
        # configures them in the options
        data = dict(entry.data)
        use_tempo = data.pop(CONF_USE_TEMPO_FEATURE, False) is True
        data[CONF_TARIFF_BANDS] = legacy_bands(
            data.get(CONF_USE_HCHP_FEATURE) is True, use_tempo)
        hass.config_entries.async_update_entry(entry, data=data, version=3)
        LOGGER.info("Config entry %s migrated to version 3", entry.title)
    if entry.version == ENTRY_VERSION and entry.minor_version < 2:
        # ecojoko refreshes the realtime of the integration every 30 s: the
        # shorter intervals, 5 s by default until 2.0.0b1, are raised to it.
        # Longer ones chosen by the user are kept
        data = dict(entry.data)
        if data.get(POLL_INTERVAL, DEFAULT_POLL_INTERVAL) < DEFAULT_POLL_INTERVAL:
            data[POLL_INTERVAL] = DEFAULT_POLL_INTERVAL
        hass.config_entries.async_update_entry(entry, data=data, minor_version=2)
        LOGGER.info("Config entry %s migrated to version 3.2", entry.title)
    if entry.version == ENTRY_VERSION and entry.minor_version < 3:
        # The options no longer allow less than MIN_POLL_INTERVAL: a shorter
        # interval chosen since 2.0.0b2 is raised to it
        data = dict(entry.data)
        if data.get(POLL_INTERVAL, DEFAULT_POLL_INTERVAL) < MIN_POLL_INTERVAL:
            data[POLL_INTERVAL] = MIN_POLL_INTERVAL
        hass.config_entries.async_update_entry(entry, data=data, minor_version=3)
        LOGGER.info("Config entry %s migrated to version 3.3", entry.title)
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
    for key in SENSOR_KEYS:
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
    device = registry_device(device_registry, (DOMAIN, old_base), entry.entry_id)
    if (
        device is not None
        and entry.entry_id in device_entry_ids(device)
        and registry_device(device_registry, (DOMAIN, new_base), entry.entry_id) is None
    ):
        device_registry.async_update_device(
            device.id, new_identifiers={(DOMAIN, new_base)})


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and getattr(entry, "runtime_data", None) is not None:
        # No statistics read in the background after the unload
        entry.runtime_data.client.cancel_statistics()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the repair issue of an entry that is removed.

    Nothing reads its tariff bands any more: the issue would stay for ever.
    """
    ir.async_delete_issue(hass, DOMAIN, unknown_bands_issue_id(entry.entry_id))


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Tell whether a device can be removed from the user interface.

    Until 1.2.7 renaming the integration created a new device and left the
    previous one behind, with unavailable entities. Such a device can be
    removed, and so can the device of an equipment removed from ecojoko; the
    devices currently provided by the entry cannot.
    """
    current = {(DOMAIN, entry.entry_id)}
    if getattr(entry, "runtime_data", None) is not None:
        current |= _equipment_devices(entry)
    return not current & device_entry.identifiers


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
