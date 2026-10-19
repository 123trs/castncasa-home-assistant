"""Calendar entities for CastnCasa."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import CastnCasaConfigEntry
from .entity import CastnCasaEntity, CastnCasaResidentEntity


def _event_from_item(item: dict[str, Any] | None) -> CalendarEvent | None:
    if not item:
        return None
    code = str(item.get("code", "Plan"))
    name = str(item.get("name", code))
    if item.get("shift_start") and item.get("shift_end"):
        start = datetime.fromisoformat(str(item["shift_start"]))
        end = datetime.fromisoformat(str(item["shift_end"]))
        start_time = item.get("start_time") or start.strftime("%H:%M")
        end_time = item.get("end_time") or end.strftime("%H:%M")
        summary = f"{code} {start_time}–{end_time}"
    else:
        start = date.fromisoformat(str(item["day"]))
        end = start + timedelta(days=1)
        summary = f"{code} {name}"
    return CalendarEvent(start=start, end=end, summary=summary)


def _month_event_from_item(item: dict[str, Any] | None) -> CalendarEvent | None:
    # One-day all-day presentation event for the month grid.
    if not item:
        return None
    code = str(item.get("code", "Plan"))
    name = str(item.get("name", code))
    day = date.fromisoformat(str(item["day"]))
    if item.get("shift_start") and item.get("shift_end"):
        start = datetime.fromisoformat(str(item["shift_start"]))
        end = datetime.fromisoformat(str(item["shift_end"]))
        start_time = item.get("start_time") or start.strftime("%H:%M")
        end_time = item.get("end_time") or end.strftime("%H:%M")
        summary = f"{code} {start_time}–{end_time}"
    else:
        summary = f"{code} {name}"
    return CalendarEvent(start=day, end=day + timedelta(days=1), summary=summary)


def _holiday_event(item: dict[str, Any], state_name: str) -> CalendarEvent:
    start = date.fromisoformat(str(item["day"]))
    return CalendarEvent(
        start=start,
        end=start + timedelta(days=1),
        summary=str(item.get("name") or "Feiertag"),
        description=f"Gesetzlicher Feiertag · {state_name}",
    )


def _weekend_event(item: dict[str, Any]) -> CalendarEvent:
    start = date.fromisoformat(str(item["day"]))
    summary = "Samstag" if item.get("weekday") == "sa" else "Sonntag"
    return CalendarEvent(start=start, end=start + timedelta(days=1), summary=summary)


def _next_special(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    today = dt_util.now().date()
    for item in items:
        try:
            if date.fromisoformat(str(item["day"])) >= today:
                return item
        except (KeyError, ValueError, TypeError):
            continue
    return None


def _sync_calendar_registry_color(entity: CalendarEntity) -> None:
    """Keep Home Assistant's persisted calendar color aligned with CastnCasa."""
    if not entity.entity_id:
        return
    registry = er.async_get(entity.hass)
    entry = registry.async_get(entity.entity_id)
    if entry is None:
        return
    color = entity.initial_color
    if color is None:
        return
    options = dict(entry.options.get("calendar", {}))
    if options.get("color") == color:
        return
    options["color"] = color
    registry.async_update_entity_options(entity.entity_id, "calendar", options)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CastnCasaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    schedule = entry.runtime_data.schedule
    instance_id = coordinator.data["instance_id"]
    residents = coordinator.data.get("residents", [])
    known = {str(resident["id"]) for resident in residents}
    entities: list[CalendarEntity] = [
        HolidayCalendar(coordinator, instance_id, schedule),
        WeekendCalendar(coordinator, instance_id, schedule),
    ]
    for resident in residents:
        entities.extend([
            ResidentCalendar(coordinator, instance_id, resident, schedule),
            ResidentMonthCalendar(coordinator, instance_id, resident, schedule),
        ])
    async_add_entities(entities)

    def _add_new_residents() -> None:
        new_entities = []
        for resident in coordinator.data.get("residents", []):
            resident_id = str(resident["id"])
            if resident_id not in known:
                known.add(resident_id)
                new_entities.extend([
                    ResidentCalendar(coordinator, instance_id, resident, schedule),
                    ResidentMonthCalendar(coordinator, instance_id, resident, schedule),
                ])
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_add_new_residents))


class ResidentCalendar(CastnCasaResidentEntity, CalendarEntity):
    """Calendar for one resident."""

    _attr_name = "Abwesenheit"
    _attr_icon = "mdi:calendar-account-outline"

    def __init__(self, coordinator, instance_id: str, resident: dict, schedule) -> None:
        super().__init__(coordinator, instance_id, resident)
        self._schedule = schedule
        self._attr_unique_id = f"{instance_id}_resident_{self.resident_id}_calendar"

    @property
    def initial_color(self) -> str:
        resident = self.resident or {}
        return str(resident.get("color") or "#4263eb")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        _sync_calendar_registry_color(self)

    @callback
    def _handle_coordinator_update(self) -> None:
        _sync_calendar_registry_color(self)
        super()._handle_coordinator_update()

    @property
    def event(self) -> CalendarEvent | None:
        resident = self.resident or {}
        item = resident.get("current_planned_absence") or resident.get(
            "next_planned_absence_event"
        )
        return _event_from_item(item)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        rows = self._schedule.events_for_resident(
            self.resident_id,
            start_date.date(),
            end_date.date(),
        )
        events = [_event_from_item(row) for row in rows]
        return [event for event in events if event is not None]


class ResidentMonthCalendar(CastnCasaResidentEntity, CalendarEntity):
    # Compact one-day events for the Home Assistant month grid.

    _attr_name = "Abwesenheit Monat"
    _attr_icon = "mdi:calendar-month-outline"

    def __init__(self, coordinator, instance_id: str, resident: dict, schedule) -> None:
        super().__init__(coordinator, instance_id, resident)
        self._schedule = schedule
        self._attr_unique_id = f"{instance_id}_resident_{self.resident_id}_month_calendar"

    @property
    def initial_color(self) -> str:
        resident = self.resident or {}
        return str(resident.get("color") or "#4263eb")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        _sync_calendar_registry_color(self)

    @callback
    def _handle_coordinator_update(self) -> None:
        _sync_calendar_registry_color(self)
        super()._handle_coordinator_update()

    @property
    def event(self) -> CalendarEvent | None:
        resident = self.resident or {}
        item = resident.get("current_planned_absence") or resident.get(
            "next_planned_absence_event"
        )
        return _month_event_from_item(item)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        rows = self._schedule.events_for_resident(
            self.resident_id,
            start_date.date(),
            end_date.date(),
        )
        events = [_month_event_from_item(row) for row in rows]
        return [event for event in events if event is not None]


class HolidayCalendar(CastnCasaEntity, CalendarEntity):
    """State-wide German public-holiday calendar."""

    _attr_name = "Feiertage"
    _attr_icon = "mdi:calendar-star"

    def __init__(self, coordinator, instance_id: str, schedule) -> None:
        super().__init__(coordinator, instance_id)
        self._schedule = schedule
        self._attr_unique_id = f"{instance_id}_holidays_calendar"

    @property
    def initial_color(self) -> str:
        return "#E76F51"

    @property
    def event(self) -> CalendarEvent | None:
        data = self.coordinator.data
        item = _next_special(data.get("special_days", {}).get("holidays", []))
        if not item:
            return None
        state_name = data.get("settings", {}).get("federal_state_name", "Deutschland")
        return _holiday_event(item, state_name)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        holidays = data.get("special_days", {}).get("holidays", [])
        return {
            "holiday_dates": [str(item.get("day")) for item in holidays if item.get("day")],
            "federal_state": data.get("settings", {}).get("federal_state"),
            "federal_state_name": data.get("settings", {}).get("federal_state_name"),
        }

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        start = start_date.date()
        end = end_date.date()
        data = self._schedule.special_days(start, end)
        state_name = self.coordinator.data.get("settings", {}).get(
            "federal_state_name", "Deutschland"
        )
        events = []
        for item in data.get("holidays", []):
            day = date.fromisoformat(str(item["day"]))
            if start <= day < end:
                events.append(_holiday_event(item, state_name))
        return events


class WeekendCalendar(CastnCasaEntity, CalendarEntity):
    """Weekend calendar used for visual highlighting."""

    _attr_name = "Wochenenden"
    _attr_icon = "mdi:calendar-weekend-outline"

    def __init__(self, coordinator, instance_id: str, schedule) -> None:
        super().__init__(coordinator, instance_id)
        self._schedule = schedule
        self._attr_unique_id = f"{instance_id}_weekends_calendar"

    @property
    def initial_color(self) -> str:
        return "#7895B2"

    @property
    def event(self) -> CalendarEvent | None:
        item = _next_special(
            self.coordinator.data.get("special_days", {}).get("weekends", [])
        )
        return _weekend_event(item) if item else None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        start = start_date.date()
        end = end_date.date()
        data = self._schedule.special_days(start, end)
        events = []
        for item in data.get("weekends", []):
            day = date.fromisoformat(str(item["day"]))
            if start <= day < end:
                events.append(_weekend_event(item))
        return events
