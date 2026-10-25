"""Binary sensors for CastnCasa household forecasting."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CastnCasaConfigEntry
from .entity import CastnCasaEntity, CastnCasaHeatEntity, CastnCasaResidentEntity
from .heat import HeatSettings, calculate_heat_forecast


def _resident_entities(coordinator, instance_id: str, resident: dict):
    return [
        ResidentAwaySensor(coordinator, instance_id, resident),
        ResidentPresenceSensor(coordinator, instance_id, resident),
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CastnCasaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    instance_id = coordinator.data["instance_id"]
    residents = coordinator.data.get("residents", [])
    known = {str(resident["id"]) for resident in residents}
    heat_settings = HeatSettings.from_options(entry.options)
    entities: list[BinarySensorEntity] = [
        HouseholdEmptySensor(coordinator, instance_id),
        HouseholdEffectiveEmptySensor(coordinator, instance_id),
        HeatRecommendationBinarySensor(coordinator, instance_id, heat_settings, "lowering_recommended", "Absenkung empfohlen", "mdi:thermometer-chevron-down"),
        HeatRecommendationBinarySensor(coordinator, instance_id, heat_settings, "hold_reduction_recommended", "Absenkung halten", "mdi:thermometer-lock"),
        HeatRecommendationBinarySensor(coordinator, instance_id, heat_settings, "reheating", "Wiederaufheizen", "mdi:radiator"),
    ]
    for resident in residents:
        entities.extend(_resident_entities(coordinator, instance_id, resident))
    async_add_entities(entities)

    def _sync_residents() -> None:
        current_residents = coordinator.data.get("residents", [])
        current_ids = {str(resident["id"]) for resident in current_residents}
        # A removed resident may later pair again with the same device ID.
        known.intersection_update(current_ids)
        new_entities = []
        for resident in current_residents:
            resident_id = str(resident["id"])
            if resident_id not in known:
                known.add(resident_id)
                new_entities.extend(_resident_entities(coordinator, instance_id, resident))
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_sync_residents))


class HouseholdEmptySensor(CastnCasaEntity, BinarySensorEntity):
    """True only when all active residents are forecast away now."""

    _attr_name = "Haushalt geplant leer"
    _attr_icon = "mdi:home-export-outline"

    def __init__(self, coordinator, instance_id: str) -> None:
        super().__init__(coordinator, instance_id)
        self._attr_unique_id = f"{instance_id}_planned_house_empty"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("household", {}).get("planned_house_empty"))

    @property
    def extra_state_attributes(self):
        household = self.coordinator.data.get("household", {})
        return {
            "next_house_empty_from": household.get("next_house_empty_from"),
            "next_house_empty_until": household.get("next_house_empty_until"),
            "planned_away_names": household.get("planned_away_names", []),
            "priority": household.get("priority", "forecast_only"),
            "note": household.get("priority_note"),
        }


class HouseholdEffectiveEmptySensor(CastnCasaEntity, BinarySensorEntity):
    """Effective household vacancy with actual presence taking priority."""

    _attr_name = "Haushalt effektiv leer"
    _attr_icon = "mdi:home-account"

    def __init__(self, coordinator, instance_id: str) -> None:
        super().__init__(coordinator, instance_id)
        self._attr_unique_id = f"{instance_id}_effective_house_empty"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("household", {}).get("effective_house_empty"))

    @property
    def extra_state_attributes(self):
        household = self.coordinator.data.get("household", {})
        return {
            "source": household.get("effective_presence_source"),
            "planned_house_empty": household.get("planned_house_empty"),
            "actual_house_empty": household.get("actual_house_empty"),
            "actual_home_names": household.get("actual_home_names", []),
            "actual_away_names": household.get("actual_away_names", []),
            "presence_unknown_names": household.get("presence_unknown_names", []),
            "presence_complete": household.get("presence_complete"),
            "priority": "actual_presence_first",
        }


class ResidentAwaySensor(CastnCasaResidentEntity, BinarySensorEntity):
    """Resident planned-away status."""

    _attr_name = "Geplant abwesend"
    _attr_icon = "mdi:account-clock-outline"

    def __init__(self, coordinator, instance_id: str, resident: dict) -> None:
        super().__init__(coordinator, instance_id, resident)
        self._attr_unique_id = f"{instance_id}_resident_{self.resident_id}_planned_away"

    @property
    def is_on(self) -> bool:
        return bool((self.resident or {}).get("planned_away"))

    @property
    def extra_state_attributes(self):
        resident = self.resident or {}
        return {
            "next_planned_absence": resident.get("next_planned_absence"),
            "expected_home": resident.get("expected_home"),
            "priority": "forecast_only",
        }


class ResidentPresenceSensor(CastnCasaResidentEntity, BinarySensorEntity):
    """Actual resident presence, independent from schedule sync."""

    _attr_name = "Anwesend"
    _attr_icon = "mdi:account-check-outline"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, coordinator, instance_id: str, resident: dict) -> None:
        super().__init__(coordinator, instance_id, resident)
        self._attr_unique_id = f"{instance_id}_resident_{self.resident_id}_presence"

    @property
    def available(self) -> bool:
        resident = self.resident
        return resident is not None and resident.get("presence") in {"home", "away"}

    @property
    def is_on(self) -> bool:
        return (self.resident or {}).get("presence") == "home"

    @property
    def extra_state_attributes(self):
        resident = self.resident or {}
        return {
            "presence_source": resident.get("presence_source"),
            "presence_entity_id": resident.get("presence_entity_id"),
            "presence_raw_state": resident.get("presence_raw_state"),
            "presence_age_seconds": resident.get("presence_age_seconds"),
            "last_seen": resident.get("last_seen"),
            "planned_away": resident.get("planned_away"),
            "plan_deviation": resident.get("plan_deviation"),
            "priority": "actual_presence_first",
        }


class HeatRecommendationBinarySensor(CastnCasaHeatEntity, BinarySensorEntity):
    """Recommendation only; never switches heating equipment."""

    def __init__(self, coordinator, instance_id: str, settings: HeatSettings, key: str, name: str, icon: str) -> None:
        super().__init__(coordinator, instance_id)
        self._settings = settings
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{instance_id}_heat_{key}"

    @property
    def heat(self):
        return calculate_heat_forecast(self.coordinator.data.get("household", {}), self._settings)

    @property
    def is_on(self) -> bool:
        return bool(self.heat[self._key])

    @property
    def extra_state_attributes(self):
        heat = self.heat
        return {
            "module": "CastnCasa Heat 1.0",
            "recommended_mode": heat["recommended_mode"],
            "reheat_from": heat["reheat_from"].isoformat() if heat["reheat_from"] else None,
            "time_until_empty_minutes": heat["time_until_empty_minutes"],
            "min_empty_minutes": heat["min_empty_minutes"],
            "min_comfort_minutes": heat["min_comfort_minutes"],
            "reheat_lead_minutes": heat["reheat_lead_minutes"],
            "comfort_buffer_minutes": heat["comfort_buffer_minutes"],
            "priority": heat["priority"],
            "note": "Nur Empfehlung; CastnCasa schaltet keine Heizung selbst.",
        }
