"""CastnCasa Home Assistant integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import probatio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    network,
)
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from .const import (
    DATA_COORDINATOR,
    DATA_MANAGER,
    DATA_SCHEDULE,
    DOMAIN,
    PLATFORMS,
    SERVICE_CREATE_PAIRING,
    SERVICE_LIST_DEVICES,
    SERVICE_REVOKE_DEVICE,
)
from .coordinator import CastnCasaCoordinator
from .http import (
    CastnCasaPairClaimView,
    CastnCasaPairingPageView,
    CastnCasaPairingQrView,
    CastnCasaPresenceView,
    CastnCasaScheduleView,
    CastnCasaStateView,
    CastnCasaStatusView,
)
from .pairing import CastnCasaPairingManager
from .schedule import CastnCasaScheduleStore

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass(slots=True)
class CastnCasaRuntimeData:
    """Runtime data for the single CastnCasa config entry."""

    coordinator: CastnCasaCoordinator
    schedule: CastnCasaScheduleStore


type CastnCasaConfigEntry = ConfigEntry[CastnCasaRuntimeData]


CREATE_PAIRING_SCHEMA = probatio.Schema(
    {
        probatio.Optional("base_url"): cv.string,
        probatio.Optional("prefer_external", default=False): cv.boolean,
    }
)
REVOKE_DEVICE_SCHEMA = probatio.Schema({probatio.Required("device_id"): cv.string})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up CastnCasa pairing, storage and local API."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if DATA_MANAGER in domain_data:
        return True

    manager = CastnCasaPairingManager(hass)
    schedule = CastnCasaScheduleStore(hass)
    await manager.async_load()
    await schedule.async_load()
    domain_data[DATA_MANAGER] = manager
    domain_data[DATA_SCHEDULE] = schedule

    hass.http.register_view(CastnCasaPairingPageView(manager))
    hass.http.register_view(CastnCasaPairingQrView(manager))
    hass.http.register_view(CastnCasaPairClaimView(manager))
    hass.http.register_view(CastnCasaStatusView(hass, manager))
    hass.http.register_view(CastnCasaScheduleView(manager, schedule))
    hass.http.register_view(CastnCasaPresenceView(manager))
    hass.http.register_view(CastnCasaStateView(hass, manager, schedule))

    async def async_create_pairing(call: ServiceCall) -> ServiceResponse:
        base_url = str(call.data.get("base_url") or "").strip().rstrip("/")
        if not base_url:
            base_url = network.get_url(
                hass,
                allow_internal=True,
                allow_external=True,
                allow_cloud=True,
                prefer_external=bool(call.data.get("prefer_external", False)),
            ).rstrip("/")

        session = manager.create_pairing(base_url)
        return {
            "pairing_url": session.pairing_page_url,
            "expires_at": session.expires_at.isoformat(),
            "pairing_id": session.pairing_id,
        }

    async def async_list_devices(call: ServiceCall) -> ServiceResponse:
        return {"devices": manager.list_devices()}

    async def async_revoke_device(call: ServiceCall) -> ServiceResponse:
        device_id = str(call.data["device_id"])
        resident_removed = await schedule.async_remove_resident(device_id)
        revoked = await manager.revoke_device(device_id)
        return {
            "device_id": device_id,
            "revoked": revoked,
            "resident_removed": resident_removed,
        }

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_CREATE_PAIRING,
        async_create_pairing,
        schema=CREATE_PAIRING_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_LIST_DEVICES,
        async_list_devices,
        schema=probatio.Schema({}),
        supports_response=SupportsResponse.ONLY,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_REVOKE_DEVICE,
        async_revoke_device,
        schema=REVOKE_DEVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: CastnCasaConfigEntry) -> None:
    """Reload CastnCasa when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: CastnCasaConfigEntry) -> bool:
    """Set up CastnCasa native entities.

    CastnCasa is a single-household integration. Older development builds could
    create more than one config entry before the flow gained a fixed unique ID.
    Keep the oldest entry canonical so legacy duplicates cannot create a second
    set of entities or register competing coordinators.
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    canonical = min(entries, key=lambda item: (item.created_at, item.entry_id))
    if canonical.entry_id != entry.entry_id:
        _LOGGER.warning(
            "Ignoring legacy duplicate CastnCasa config entry %s; canonical entry is %s",
            entry.entry_id,
            canonical.entry_id,
        )
        return True

    if entry.unique_id != DOMAIN and not any(
        item.entry_id != entry.entry_id and item.unique_id == DOMAIN for item in entries
    ):
        hass.config_entries.async_update_entry(entry, unique_id=DOMAIN)

    schedule: CastnCasaScheduleStore = hass.data[DOMAIN][DATA_SCHEDULE]
    manager: CastnCasaPairingManager = hass.data[DOMAIN][DATA_MANAGER]
    coordinator = CastnCasaCoordinator(hass, entry, schedule, manager)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][DATA_COORDINATOR] = coordinator
    entry.runtime_data = CastnCasaRuntimeData(coordinator=coordinator, schedule=schedule)
    entry.async_on_unload(schedule.async_add_listener(coordinator.async_schedule_updated))
    entry.async_on_unload(manager.async_add_listener(coordinator.async_presence_updated))
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    @callback
    def _presence_state_changed(event: Event) -> None:
        entity_id = str(event.data.get("entity_id", ""))
        if entity_id in coordinator.presence_entity_ids():
            coordinator.async_presence_updated()

    entry.async_on_unload(hass.bus.async_listen(EVENT_STATE_CHANGED, _presence_state_changed))

    def _remove_departed_resident_devices() -> None:
        active = {str(resident["id"]) for resident in schedule.residents()}
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
        prefix = f"{schedule.instance_id}:resident:"
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
            resident_id = None
            for domain, identifier in device.identifiers:
                if domain == DOMAIN and identifier.startswith(prefix):
                    resident_id = identifier.removeprefix(prefix)
                    break
            if resident_id is None or resident_id in active:
                continue
            for entity_entry in er.async_entries_for_device(
                entity_registry, device.id, include_disabled_entities=True
            ):
                entity_registry.async_remove(entity_entry.entity_id)
            device_registry.async_remove_device(device.id)

    entry.async_on_unload(schedule.async_add_listener(_remove_departed_resident_devices))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _remove_departed_resident_devices()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CastnCasaConfigEntry) -> bool:
    """Unload CastnCasa entities."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(DATA_COORDINATOR, None)
    return unloaded


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: CastnCasaConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Remove a resident device together with its CastnCasa data."""
    schedule = entry.runtime_data.schedule
    prefix = f"{schedule.instance_id}:resident:"
    resident_id = None
    for domain, identifier in device_entry.identifiers:
        if domain == DOMAIN and identifier.startswith(prefix):
            resident_id = identifier.removeprefix(prefix)
            break

    # Household and Heat are integration-owned aggregate devices. They disappear
    # only when the config entry is removed; only resident devices are user-removable.
    if resident_id is None:
        return False

    manager: CastnCasaPairingManager = hass.data[DOMAIN][DATA_MANAGER]
    await schedule.async_remove_resident(resident_id)
    await manager.revoke_device(resident_id)

    # Removing the resident normally triggers _remove_departed_resident_devices.
    # Explicitly clear any remaining registry entities too so stale/orphaned
    # resident devices can always be deleted from the HA device page.
    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_device(
        entity_registry, device_entry.id, include_disabled_entities=True
    ):
        entity_registry.async_remove(entity_entry.entity_id)
    return True
