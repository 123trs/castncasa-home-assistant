"""Sensors for CastnCasa household forecasting and presence."""

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
            "Nächste Abfahrt",
        ),
        ResidentTimestampSensor(
            coordinator,
            instance_id,
            resident,
            "expected_home",
            "Erwartete Heimkehr",
        ),
        ResidentTimestampSensor(
            coordinator,
            instance_id,
            resident,
            "last_seen",
            "Zuletzt gesehen",
        ),
        ResidentTextSensor(
            coordinator,
            instance_id,
            resident,
            "plan_deviation",
            "Planabweichung",
        ),
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
    ]
    for resident in residents:
        entities.extend(_resident_entities(coordinator, instance_id, resident))
    async_add_entities(entities)

    def _add_new_residents() -> None:
        new_entities = []
        for resident in coordinator.data.get("residents", []):
            resident_id = str(resident["id"])
            if resident_id not in known:
                known.add(resident_id)
                new_entities.extend(_resident_entities(coordinator, instance_id, resident))
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_add_new_residents))


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


class ResidentTextSensor(CastnCasaResidentEntity, SensorEntity):
    """Resident text state derived from presence and forecast."""

    _attr_icon = "mdi:calendar-alert"

    def __init__(self, coordinator, instance_id: str, resident: dict, key: str, name: str) -> None:
        super().__init__(coordinator, instance_id, resident)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{instance_id}_resident_{self.resident_id}_{key}"

    @property
    def native_value(self) -> str:
        return str((self.resident or {}).get(self._key) or "unbekannt")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        resident = self.resident or {}
        return {
            "presence": resident.get("presence", "unknown"),
            "presence_source": resident.get("presence_source"),
            "planned_away": resident.get("planned_away"),
            "next_departure": resident.get("next_departure"),
            "expected_home": resident.get("expected_home"),
        }


class CastnCasaHeatSensor(CastnCasaHeatEntity, SensorEntity):
    """Base entity for CastnCasa Heat recommendation sensors."""

    def __init__(self, coordinator, instance_id: str, settings: HeatSettings) -> None:
        super().__init__(coordinator, instance_id)
        self._settings = settings

    @property
    def heat(self) -> dict[str, Any]:
        return calculate_heat_forecast(self.coordinator.data.get("household", {}), self._settings)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        heat = self.heat
        return {
            "module": "CastnCasa Heat 1.0",
            "min_empty_minutes": heat["min_empty_minutes"],
            "reheat_lead_minutes": heat["reheat_lead_minutes"],
            "comfort_buffer_minutes": heat["comfort_buffer_minutes"],
            "next_house_empty_from": heat["next_house_empty_from"],
            "next_house_empty_until": heat["next_house_empty_until"],
            "confirmed_home": heat.get("confirmed_home", False),
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
        attrs["note"] = "Bestätigte Anwesenheit hat immer Vorrang vor der Dienstplan-Prognose."
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
