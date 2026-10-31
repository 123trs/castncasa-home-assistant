"""Sensors for CastnCasa household forecasting."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CastnCasaConfigEntry
from .entity import CastnCasaEntity, CastnCasaHeatEntity, CastnCasaResidentEntity
from .heat import HeatSettings, calculate_heat_forecast
from .learning import HeatLearningManager


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _item_attrs(item: dict[str, Any] | None) -> dict[str, Any]:
    if not item:
        return {}
    keys = (
        "name",
        "kind",
        "away",
        "start_time",
        "end_time",
        "shift_start",
        "shift_end",
        "planned_absence_from",
        "expected_home",
        "overnight",
        "all_day",
        "assignment_source",
    )
    return {key: item.get(key) for key in keys if item.get(key) is not None}


def _resident_entities(coordinator, instance_id: str, resident: dict):
    return [
        ResidentDaySensor(coordinator, instance_id, resident, "today", "Abwesenheit heute"),
        ResidentDaySensor(coordinator, instance_id, resident, "tomorrow", "Abwesenheit morgen"),
        ResidentTimestampSensor(
            coordinator,
            instance_id,
            resident,
            "next_planned_absence",
            "Nächste geplante Abwesenheit",
        ),
        ResidentTimestampSensor(
            coordinator,
            instance_id,
            resident,
            "expected_home",
            "Erwartete Heimkehr",
        ),
        ResidentTimestampSensor(
            coordinator, instance_id, resident, "next_departure", "Nächste Abfahrt"
        ),
        ResidentTimestampSensor(
            coordinator, instance_id, resident, "last_seen", "Zuletzt gesehen"
        ),
        ResidentPlanDeviationSensor(coordinator, instance_id, resident),
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

    learning = HeatLearningManager(hass, entry, coordinator, heat_settings)
    await learning.async_load()
    learning.process_update()
    entry.async_on_unload(coordinator.async_add_listener(learning.process_update))

    entities: list[SensorEntity] = [
        HouseholdCountSensor(coordinator, instance_id, "active_residents", "Aktive Bewohner"),
        HouseholdCountSensor(coordinator, instance_id, "planned_away_now", "Geplant abwesend"),
        HouseholdTimestampSensor(
            coordinator, instance_id, "next_house_empty_from", "Nächste Leerphase ab"
        ),
        HouseholdTimestampSensor(
            coordinator, instance_id, "next_house_empty_until", "Nächste Leerphase bis"
        ),
        HouseholdTimestampSensor(
            coordinator, instance_id, "next_expected_return", "Nächste erwartete Heimkehr"
        ),
        HeatDurationSensor(coordinator, instance_id, heat_settings),
        HeatTimeUntilHomeSensor(coordinator, instance_id, heat_settings),
        HeatModeSensor(coordinator, instance_id, heat_settings),
        HeatTimestampSensor(coordinator, instance_id, heat_settings),
        HeatForecastStatusSensor(coordinator, instance_id, heat_settings),
        HeatConfidenceSensor(coordinator, instance_id, heat_settings),
        HeatLearningStatusSensor(coordinator, instance_id),
        HeatLearningCyclesSensor(coordinator, instance_id),
        HeatLearningLeadSensor(coordinator, instance_id),
    ]
    for resident in residents:
        entities.extend(_resident_entities(coordinator, instance_id, resident))
    async_add_entities(entities)

    def _sync_residents() -> None:
        current_residents = coordinator.data.get("residents", [])
        current_ids = {str(resident["id"]) for resident in current_residents}
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


class HouseholdCountSensor(CastnCasaEntity, SensorEntity):
    """Integer household sensor."""

    def __init__(self, coordinator, instance_id: str, key: str, name: str) -> None:
        super().__init__(coordinator, instance_id)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{instance_id}_{key}"
        self._attr_icon = "mdi:account-group-outline"

    @property
    def native_value(self) -> int:
        return int(self.coordinator.data.get("household", {}).get(self._key, 0) or 0)


class HouseholdTimestampSensor(CastnCasaEntity, SensorEntity):
    """Timestamp household sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, instance_id: str, key: str, name: str) -> None:
        super().__init__(coordinator, instance_id)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{instance_id}_{key}"

    @property
    def native_value(self) -> datetime | None:
        return _parse_dt(self.coordinator.data.get("household", {}).get(self._key))


class ResidentDaySensor(CastnCasaResidentEntity, SensorEntity):
    """Today/tomorrow shift-code sensor."""

    def __init__(self, coordinator, instance_id: str, resident: dict, key: str, name: str) -> None:
        super().__init__(coordinator, instance_id, resident)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{instance_id}_resident_{self.resident_id}_{key}"
        self._attr_icon = "mdi:calendar-today" if key == "today" else "mdi:calendar-arrow-right"

    @property
    def native_value(self) -> str:
        item = (self.resident or {}).get(self._key)
        return str(item.get("code")) if item else "—"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return _item_attrs((self.resident or {}).get(self._key))


class ResidentTimestampSensor(CastnCasaResidentEntity, SensorEntity):
    """Resident timestamp sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, instance_id: str, resident: dict, key: str, name: str) -> None:
        super().__init__(coordinator, instance_id, resident)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{instance_id}_resident_{self.resident_id}_{key}"

    @property
    def native_value(self) -> datetime | None:
        return _parse_dt((self.resident or {}).get(self._key))


class ResidentPlanDeviationSensor(CastnCasaResidentEntity, SensorEntity):
    """Difference between actual presence and the planned schedule."""

    _attr_name = "Abweichung vom Plan"
    _attr_icon = "mdi:calendar-alert"

    def __init__(self, coordinator, instance_id: str, resident: dict) -> None:
        super().__init__(coordinator, instance_id, resident)
        self._attr_unique_id = f"{instance_id}_resident_{self.resident_id}_plan_deviation"

    @property
    def native_value(self) -> str:
        return str((self.resident or {}).get("plan_deviation") or "unbekannt")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        resident = self.resident or {}
        return {
            "presence": resident.get("presence"),
            "presence_source": resident.get("presence_source"),
            "presence_entity_id": resident.get("presence_entity_id"),
            "planned_away": resident.get("planned_away"),
            "next_departure": resident.get("next_departure"),
            "expected_home": resident.get("expected_home"),
            "plan_matches_actual": resident.get("plan_matches_actual"),
        }


class CastnCasaHeatSensor(CastnCasaHeatEntity, SensorEntity):
    """Base entity for CastnCasa Heat recommendation sensors."""

    def __init__(self, coordinator, instance_id: str, settings: HeatSettings) -> None:
        super().__init__(coordinator, instance_id)
        self._settings = settings

    @property
    def heat(self) -> dict[str, Any]:
        return calculate_heat_forecast(
            self.coordinator.data.get("household", {}),
            self._settings,
            learning=self.coordinator.data.get("heat_learning", {}),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        heat = self.heat
        return {
            "module": "CastnCasa Heat 1.1",
            "min_empty_minutes": heat["min_empty_minutes"],
            "reheat_lead_minutes": heat["reheat_lead_minutes"],
            "effective_reheat_lead_minutes": heat["effective_reheat_lead_minutes"],
            "learned_reheat_lead_minutes": heat["learned_reheat_lead_minutes"],
            "learning_status": heat["learning_status"],
            "comfort_buffer_minutes": heat["comfort_buffer_minutes"],
            "next_house_empty_from": heat["next_house_empty_from"],
            "next_house_empty_until": heat["next_house_empty_until"],
            "actual_home_now": heat["actual_home_now"],
            "presence_override_home": heat["presence_override_home"],
            "effective_presence_source": heat["effective_presence_source"],
            "priority": heat["priority"],
        }


class HeatDurationSensor(CastnCasaHeatSensor):
    _attr_name = "Leerphase Dauer"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer-sand"

    def __init__(self, coordinator, instance_id: str, settings: HeatSettings) -> None:
        super().__init__(coordinator, instance_id, settings)
        self._attr_unique_id = f"{instance_id}_heat_empty_duration"

    @property
    def native_value(self) -> int | None:
        return self.heat["empty_duration_minutes"]


class HeatTimeUntilHomeSensor(CastnCasaHeatSensor):
    _attr_name = "Zeit bis Heimkehr"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:home-clock-outline"

    def __init__(self, coordinator, instance_id: str, settings: HeatSettings) -> None:
        super().__init__(coordinator, instance_id, settings)
        self._attr_unique_id = f"{instance_id}_heat_time_until_home"

    @property
    def native_value(self) -> int | None:
        return self.heat["time_until_home_minutes"]


class HeatModeSensor(CastnCasaHeatSensor):
    _attr_name = "Empfohlener Modus"
    _attr_icon = "mdi:home-thermometer-outline"

    def __init__(self, coordinator, instance_id: str, settings: HeatSettings) -> None:
        super().__init__(coordinator, instance_id, settings)
        self._attr_unique_id = f"{instance_id}_heat_recommended_mode"

    @property
    def native_value(self) -> str:
        return str(self.heat["recommended_mode"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes
        attrs["reduction_window_usable"] = self.heat["reduction_window_usable"]
        attrs["note"] = "Empfehlung aus Dienstplan-Prognose. Reale Anwesenheit in Home Assistant hat immer Vorrang."
        return attrs


class HeatTimestampSensor(CastnCasaHeatSensor):
    _attr_name = "Wiederaufheizen ab"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:radiator"

    def __init__(self, coordinator, instance_id: str, settings: HeatSettings) -> None:
        super().__init__(coordinator, instance_id, settings)
        self._attr_unique_id = f"{instance_id}_heat_reheat_from"

    @property
    def native_value(self) -> datetime | None:
        return self.heat["reheat_from"]


class HeatForecastStatusSensor(CastnCasaHeatSensor):
    _attr_name = "Prognose Status"
    _attr_icon = "mdi:calendar-check-outline"

    def __init__(self, coordinator, instance_id: str, settings: HeatSettings) -> None:
        super().__init__(coordinator, instance_id, settings)
        self._attr_unique_id = f"{instance_id}_heat_forecast_status"

    @property
    def native_value(self) -> str:
        return str(self.heat["forecast_status"])


class HeatConfidenceSensor(CastnCasaHeatSensor):
    _attr_name = "Prognose Vertrauen"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:shield-check-outline"

    def __init__(self, coordinator, instance_id: str, settings: HeatSettings) -> None:
        super().__init__(coordinator, instance_id, settings)
        self._attr_unique_id = f"{instance_id}_heat_forecast_confidence"

    @property
    def native_value(self) -> int:
        return int(self.heat["forecast_confidence_pct"])


class CastnCasaLearningSensor(CastnCasaHeatEntity, SensorEntity):
    """Base sensor for persistent Heat learning state."""

    @property
    def learning(self) -> dict[str, Any]:
        return self.coordinator.data.get("heat_learning", {})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        learning = self.learning
        return {
            "auto_apply": learning.get("auto_apply"),
            "configured_reheat_lead_minutes": learning.get("configured_reheat_lead_minutes"),
            "effective_reheat_lead_minutes": learning.get("effective_reheat_lead_minutes"),
            "learned_reheat_lead_minutes": learning.get("learned_reheat_lead_minutes"),
            "minimum_cycles_for_suggestion": learning.get("minimum_cycles_for_suggestion"),
            "minimum_cycles_for_auto_apply": learning.get("minimum_cycles_for_auto_apply"),
            "target_temperature": learning.get("target_temperature"),
            "target_temperature_entity": learning.get("target_temperature_entity"),
            "target_temperature_source": learning.get("target_temperature_source"),
            "reduced_target_temperature": learning.get("reduced_target_temperature"),
            "reduced_target_temperature_entity": learning.get("reduced_target_temperature_entity"),
            "reduced_target_temperature_source": learning.get("reduced_target_temperature_source"),
            "room_temperature_entity": learning.get("room_temperature_entity"),
            "outdoor_temperature_entity": learning.get("outdoor_temperature_entity"),
            "burner_entity": learning.get("burner_entity"),
            "active_cycle": learning.get("active_cycle"),
            "last_cycle": learning.get("last_cycle"),
        }


class HeatLearningStatusSensor(CastnCasaLearningSensor):
    _attr_name = "Heat Lernstatus"
    _attr_icon = "mdi:brain"

    def __init__(self, coordinator, instance_id: str) -> None:
        super().__init__(coordinator, instance_id)
        self._attr_unique_id = f"{instance_id}_heat_learning_status"

    @property
    def native_value(self) -> str:
        return str(self.learning.get("status") or "deaktiviert")


class HeatLearningCyclesSensor(CastnCasaLearningSensor):
    _attr_name = "Heat Lernzyklen"
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator, instance_id: str) -> None:
        super().__init__(coordinator, instance_id)
        self._attr_unique_id = f"{instance_id}_heat_learning_cycles"

    @property
    def native_value(self) -> int:
        return int(self.learning.get("valid_cycles", 0) or 0)


class HeatLearningLeadSensor(CastnCasaLearningSensor):
    _attr_name = "Gelernter Wiederaufheiz-Vorlauf"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer-cog-outline"

    def __init__(self, coordinator, instance_id: str) -> None:
        super().__init__(coordinator, instance_id)
        self._attr_unique_id = f"{instance_id}_heat_learning_lead"

    @property
    def native_value(self) -> int | None:
        value = self.learning.get("learned_reheat_lead_minutes")
        return int(value) if value is not None else None
