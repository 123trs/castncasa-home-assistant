"""Household schedule storage and forecast model for CastnCasa."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time, timedelta
import re
from typing import Any
import uuid
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .holidays import FEDERAL_STATES, special_days_between

STORE_VERSION = 1
STORE_KEY = "castncasa.schedule"
DEFAULT_COLOR = "#4263eb"
CODE_RE = re.compile(r"^[A-Za-zÄÖÜäöü0-9_-]{1,8}$")
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
KINDS = {"work", "free", "leave", "sick", "other"}
MAX_PROFILES = 50
MAX_ASSIGNMENTS = 800
MAX_WEEKLY_DEFAULTS = 7


class ScheduleValidationError(Exception):
    """Raised when a schedule payload is invalid."""


class ScheduleConflictError(Exception):
    """Raised when an optional base revision does not match."""


def _parse_hm(value: str | None) -> time | None:
    if value in (None, ""):
        return None
    try:
        return datetime.strptime(str(value), "%H:%M").time()
    except ValueError as err:
        raise ScheduleValidationError("invalid_time") from err


def _validate_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as err:
        raise ScheduleValidationError("invalid_date") from err


def _normalize_profile(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ScheduleValidationError("invalid_profile")
    code = str(raw.get("code", "")).strip().upper()
    name = str(raw.get("name", raw.get("label", ""))).strip()
    kind = str(raw.get("kind", "work")).strip().lower()
    away = bool(raw.get("away", kind == "work"))
    start_value = raw.get("start_time") or None
    end_value = raw.get("end_time") or None
    if not CODE_RE.fullmatch(code):
        raise ScheduleValidationError("invalid_profile_code")
    if not name or len(name) > 60:
        raise ScheduleValidationError("invalid_profile_name")
    if kind not in KINDS:
        raise ScheduleValidationError("invalid_profile_kind")
    if bool(start_value) != bool(end_value):
        raise ScheduleValidationError("incomplete_profile_time")
    if start_value:
        _parse_hm(str(start_value))
        _parse_hm(str(end_value))
        start_value = str(start_value)
        end_value = str(end_value)
    try:
        leave_before = max(0, min(240, int(raw.get("leave_before_min", 0) or 0)))
        home_after = max(0, min(240, int(raw.get("home_after_min", 0) or 0)))
    except (TypeError, ValueError) as err:
        raise ScheduleValidationError("invalid_profile_offset") from err
    if not away:
        leave_before = 0
        home_after = 0
    return {
        "code": code,
        "name": name,
        "kind": kind,
        "away": away,
        "start_time": start_value,
        "end_time": end_value,
        "leave_before_min": leave_before,
        "home_after_min": home_after,
    }


def _absence_interval(
    day_str: str,
    profile: dict[str, Any],
    resident: dict[str, Any],
    tz: ZoneInfo,
) -> dict[str, Any] | None:
    if not bool(profile.get("away")):
        return None
    day = date.fromisoformat(day_str)
    start_time = _parse_hm(profile.get("start_time"))
    end_time = _parse_hm(profile.get("end_time"))
    all_day = start_time is None and end_time is None
    if all_day:
        # A work profile without times is intentionally not interpreted as a
        # full-day absence. Missing input must never reduce comfort.
        if profile.get("kind") == "work":
            return None
        start = datetime.combine(day, time.min, tzinfo=tz)
        end = start + timedelta(days=1)
        overnight = False
    else:
        if start_time is None or end_time is None:
            return None
        raw_start = datetime.combine(day, start_time, tzinfo=tz)
        raw_end = datetime.combine(day, end_time, tzinfo=tz)
        overnight = raw_end <= raw_start
        if overnight:
            raw_end += timedelta(days=1)
        start = raw_start - timedelta(minutes=int(profile.get("leave_before_min", 0) or 0))
        end = raw_end + timedelta(minutes=int(profile.get("home_after_min", 0) or 0))

    result: dict[str, Any] = {
        "day": day_str,
        "profile_id": profile["code"],
        "code": profile["code"],
        "name": profile["name"],
        "kind": profile["kind"],
        "away": True,
        "planned_absence_from": start.isoformat(timespec="minutes"),
        "expected_home": end.isoformat(timespec="minutes"),
        "overnight": overnight,
        "all_day": all_day,
        "resident_id": resident["id"],
        "resident_name": resident["name"],
        "resident_color": resident["color"],
    }
    if start_time is not None and end_time is not None:
        raw_start = datetime.combine(day, start_time, tzinfo=tz)
        raw_end = datetime.combine(day, end_time, tzinfo=tz)
        if raw_end <= raw_start:
            raw_end += timedelta(days=1)
        result["shift_start"] = raw_start.isoformat(timespec="minutes")
        result["shift_end"] = raw_end.isoformat(timespec="minutes")
    return result


def _assignment_for_day(resident: dict[str, Any], day_str: str, tz: ZoneInfo) -> dict[str, Any] | None:
    profiles = resident.get("profiles", {})
    code = resident.get("assignments", {}).get(day_str)
    source = "explicit"
    if code is None:
        weekday = str(date.fromisoformat(day_str).weekday())
        code = resident.get("weekly_defaults", {}).get(weekday)
        source = "weekly_default"
    if not code:
        return None
    profile = profiles.get(code)
    if not profile:
        return None
    item: dict[str, Any] = {
        "day": day_str,
        "resident_id": resident["id"],
        "profile_id": code,
        **profile,
        "assignment_source": source,
    }
    interval = _absence_interval(day_str, profile, resident, tz)
    if interval:
        item.update(interval)
        item["assignment_source"] = source
    return item


def _resident_forecast(
    resident: dict[str, Any],
    tz: ZoneInfo,
    now: datetime,
    days: int = 45,
) -> dict[str, Any]:
    first_day = now.date() - timedelta(days=1)
    timeline: list[dict[str, Any]] = []
    for offset in range(days + 2):
        day_str = (first_day + timedelta(days=offset)).isoformat()
        assignment = _assignment_for_day(resident, day_str, tz)
        if not assignment:
            continue
        event = _absence_interval(day_str, assignment, resident, tz)
        if event:
            event["assignment_source"] = assignment.get("assignment_source", "explicit")
            timeline.append(event)
    current = None
    upcoming = None
    for event in timeline:
        start = datetime.fromisoformat(event["planned_absence_from"])
        end = datetime.fromisoformat(event["expected_home"])
        if start <= now < end:
            current = event
        elif start > now and upcoming is None:
            upcoming = event
    return {
        "resident_id": resident["id"],
        "resident_name": resident["name"],
        "current_planned_absence": current,
        "next_planned_absence_event": upcoming,
        "planned_away": current is not None,
        "next_planned_absence": upcoming["planned_absence_from"] if upcoming else None,
        "expected_home": (current or upcoming or {}).get("expected_home") if (current or upcoming) else None,
        "timeline": timeline[:40],
    }


def _merge_segments(segments: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    merged: list[tuple[datetime, datetime]] = []
    for start, end in segments:
        if merged and merged[-1][1] == start:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def _household_forecast(
    residents: list[dict[str, Any]],
    tz: ZoneInfo,
    now: datetime,
    days: int = 45,
) -> dict[str, Any]:
    forecasts = [_resident_forecast(resident, tz, now, days) for resident in residents]
    intervals: dict[str, list[tuple[datetime, datetime]]] = {}
    boundaries: set[datetime] = set()
    for resident, forecast in zip(residents, forecasts, strict=True):
        items: list[tuple[datetime, datetime]] = []
        for event in forecast["timeline"]:
            start = datetime.fromisoformat(event["planned_absence_from"])
            end = datetime.fromisoformat(event["expected_home"])
            items.append((start, end))
            boundaries.add(start)
            boundaries.add(end)
        intervals[resident["id"]] = items

    empty_segments: list[tuple[datetime, datetime]] = []
    ordered = sorted(boundaries)
    if residents and len(ordered) > 1:
        for start, end in zip(ordered, ordered[1:]):
            if end <= start:
                continue
            midpoint = start + (end - start) / 2
            everyone_away = all(
                any(a <= midpoint < b for a, b in intervals[resident["id"]])
                for resident in residents
            )
            if everyone_away:
                empty_segments.append((start, end))
    empty_segments = _merge_segments(empty_segments)

    current_empty = None
    next_empty = None
    for start, end in empty_segments:
        if start <= now < end:
            current_empty = (start, end)
            break
        if start > now and next_empty is None:
            next_empty = (start, end)
    target = current_empty or next_empty
    away_now = [forecast["resident_name"] for forecast in forecasts if forecast["planned_away"]]

    return_candidates: list[datetime] = []
    for forecast in forecasts:
        event = forecast.get("current_planned_absence") or forecast.get("next_planned_absence_event")
        if not event or not event.get("expected_home"):
            continue
        candidate = datetime.fromisoformat(event["expected_home"])
        if candidate > now:
            return_candidates.append(candidate)
    next_return = min(return_candidates) if return_candidates else None

    coverage_days = 7
    coverage_total_slots = len(residents) * coverage_days
    coverage_filled_slots = 0
    for offset in range(coverage_days):
        day_str = (now.date() + timedelta(days=offset)).isoformat()
        coverage_filled_slots += sum(
            _assignment_for_day(resident, day_str, tz) is not None for resident in residents
        )
    confidence = (
        int(round(coverage_filled_slots / coverage_total_slots * 100))
        if coverage_total_slots
        else 0
    )
    if not residents:
        forecast_status = "keine_bewohner"
    elif confidence == 100:
        forecast_status = "vollständig"
    elif confidence > 0:
        forecast_status = "teilweise"
    else:
        forecast_status = "ohne_plan"

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "active_residents": len(residents),
        "residents": forecasts,
        "planned_away_now": len(away_now),
        "planned_away_names": away_now,
        "planned_house_empty": current_empty is not None,
        "next_house_empty_from": target[0].isoformat(timespec="minutes") if target else None,
        "next_house_empty_until": target[1].isoformat(timespec="minutes") if target else None,
        "next_expected_return": next_return.isoformat(timespec="minutes") if next_return else None,
        "forecast_status": forecast_status,
        "forecast_confidence_pct": confidence,
        "forecast_coverage_days": coverage_days,
        "forecast_covered_slots": coverage_filled_slots,
        "forecast_total_slots": coverage_total_slots,
        "empty_periods": [
            {"from": start.isoformat(timespec="minutes"), "until": end.isoformat(timespec="minutes")}
            for start, end in empty_segments[:20]
        ],
        "forecast_rule": "Haus leer wird nur prognostiziert, wenn für alle aktiven Bewohner gleichzeitig eine geplante Abwesenheit vorliegt.",
        "priority": "forecast_only",
        "priority_note": "CastnCasa liefert Prognosen. Reale Anwesenheit in Home Assistant hat immer Vorrang.",
    }


class CastnCasaScheduleStore:
    """Persist and calculate the household schedule inside Home Assistant."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, STORE_KEY)
        self._data: dict[str, Any] = {}
        self._listeners: set[Callable[[], None]] = set()

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.hass.config.time_zone)

    @property
    def instance_id(self) -> str:
        return str(self._data["instance_id"])

    async def async_load(self) -> None:
        loaded = await self._store.async_load() or {}
        self._data = {
            "instance_id": str(loaded.get("instance_id") or uuid.uuid4()),
            "federal_state": str(loaded.get("federal_state") or ""),
            "residents": loaded.get("residents", {}) if isinstance(loaded.get("residents", {}), dict) else {},
        }
        await self._async_save()

    async def _async_save(self) -> None:
        await self._store.async_save(self._data)

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    @callback
    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    async def async_replace_resident(self, device_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        resident_raw = payload.get("resident")
        if not isinstance(resident_raw, dict):
            raise ScheduleValidationError("resident_required")
        name = str(resident_raw.get("name", "")).strip()
        color = str(resident_raw.get("color", DEFAULT_COLOR)).strip()
        if not name or len(name) > 40:
            raise ScheduleValidationError("invalid_resident_name")
        if not COLOR_RE.fullmatch(color):
            raise ScheduleValidationError("invalid_resident_color")

        raw_profiles = payload.get("profiles")
        if not isinstance(raw_profiles, list) or not raw_profiles or len(raw_profiles) > MAX_PROFILES:
            raise ScheduleValidationError("invalid_profiles")
        profiles: dict[str, dict[str, Any]] = {}
        for raw in raw_profiles:
            profile = _normalize_profile(raw)
            if profile["code"] in profiles:
                raise ScheduleValidationError("duplicate_profile_code")
            profiles[profile["code"]] = profile

        raw_assignments = payload.get("assignments", {})
        if not isinstance(raw_assignments, dict) or len(raw_assignments) > MAX_ASSIGNMENTS:
            raise ScheduleValidationError("invalid_assignments")
        assignments: dict[str, str] = {}
        for raw_day, raw_code in raw_assignments.items():
            day = _validate_date(str(raw_day))
            code = str(raw_code).strip().upper()
            if code not in profiles:
                raise ScheduleValidationError("assignment_profile_missing")
            assignments[day] = code

        raw_weekly = payload.get("weekly_defaults", {})
        if not isinstance(raw_weekly, dict) or len(raw_weekly) > MAX_WEEKLY_DEFAULTS:
            raise ScheduleValidationError("invalid_weekly_defaults")
        weekly_defaults: dict[str, str] = {}
        for raw_weekday, raw_code in raw_weekly.items():
            weekday = str(raw_weekday)
            if weekday not in {str(value) for value in range(7)}:
                raise ScheduleValidationError("invalid_weekday")
            code = str(raw_code).strip().upper()
            if code not in profiles:
                raise ScheduleValidationError("weekly_profile_missing")
            weekly_defaults[weekday] = code

        federal_state = payload.get("federal_state")
        if federal_state is not None:
            federal_state = str(federal_state).strip().upper()
            if federal_state not in FEDERAL_STATES:
                raise ScheduleValidationError("invalid_federal_state")

        current = self._data["residents"].get(device_id, {})
        base_revision = payload.get("base_revision")
        if base_revision is not None:
            try:
                supplied_revision = int(base_revision)
            except (TypeError, ValueError) as err:
                raise ScheduleValidationError("invalid_revision") from err
            if current and supplied_revision != int(current.get("revision", 0)):
                raise ScheduleConflictError("revision_conflict")

        revision = int(current.get("revision", 0)) + 1
        now = datetime.now(self.timezone).isoformat(timespec="seconds")
        resident = {
            "id": device_id,
            "device_id": device_id,
            "name": name,
            "color": color,
            "active": bool(resident_raw.get("active", True)),
            "profiles": profiles,
            "assignments": assignments,
            "weekly_defaults": weekly_defaults,
            "revision": revision,
            "updated_at": now,
        }
        self._data["residents"][device_id] = resident
        if federal_state is not None:
            self._data["federal_state"] = federal_state
        await self._async_save()
        self._notify()
        return self.resident_payload(device_id)

    async def async_remove_resident(self, device_id: str) -> bool:
        """Remove one resident schedule and notify all live HA entities."""
        if self._data.get("residents", {}).pop(device_id, None) is None:
            return False
        await self._async_save()
        self._notify()
        return True

    def resident_payload(self, device_id: str) -> dict[str, Any]:
        resident = self._data["residents"].get(device_id)
        if not resident:
            return {
                "resident": None,
                "profiles": [],
                "assignments": {},
                "weekly_defaults": {},
                "revision": 0,
                "federal_state": self._data.get("federal_state", ""),
            }
        return {
            "resident": {
                "id": resident["id"],
                "name": resident["name"],
                "color": resident["color"],
                "active": bool(resident.get("active", True)),
            },
            "profiles": list(resident.get("profiles", {}).values()),
            "assignments": dict(resident.get("assignments", {})),
            "weekly_defaults": dict(resident.get("weekly_defaults", {})),
            "revision": int(resident.get("revision", 0)),
            "federal_state": self._data.get("federal_state", ""),
        }

    def residents(self) -> list[dict[str, Any]]:
        return [
            resident
            for resident in self._data.get("residents", {}).values()
            if bool(resident.get("active", True))
        ]

    def state_snapshot(self, now: datetime | None = None) -> dict[str, Any]:
        tz = self.timezone
        now = now or datetime.now(tz)
        residents = self.residents()
        household = _household_forecast(residents, tz, now)
        today = now.date().isoformat()
        tomorrow = (now.date() + timedelta(days=1)).isoformat()
        state_residents: list[dict[str, Any]] = []
        for resident in residents:
            forecast = _resident_forecast(resident, tz, now)
            state_residents.append(
                {
                    "id": resident["id"],
                    "name": resident["name"],
                    "color": resident["color"],
                    "revision": resident.get("revision", 0),
                    "today": _assignment_for_day(resident, today, tz),
                    "tomorrow": _assignment_for_day(resident, tomorrow, tz),
                    **forecast,
                }
            )
        state_code = str(self._data.get("federal_state", ""))
        return {
            "ok": True,
            "api_version": 1,
            "product": "CastnCasa",
            "instance_id": self.instance_id,
            "timezone": str(tz),
            "generated_at": now.isoformat(timespec="seconds"),
            "household": household,
            "residents": state_residents,
            "settings": {
                "federal_state": state_code,
                "federal_state_name": FEDERAL_STATES.get(state_code, "Nicht gewählt"),
                "holiday_scope": "statewide",
                "holiday_note": "Es werden landesweit geltende gesetzliche Feiertage angezeigt.",
            },
            "special_days": self.special_days(
                date(now.year - 1, 1, 1),
                date(now.year + 2, 1, 1) - timedelta(days=1),
            ),
            "priority": "forecast_only",
            "priority_note": household["priority_note"],
        }

    def events_for_resident(self, resident_id: str, start: date, end: date) -> list[dict[str, Any]]:
        resident = self._data.get("residents", {}).get(resident_id)
        if not resident or not bool(resident.get("active", True)):
            return []
        result: list[dict[str, Any]] = []
        cursor = start
        while cursor < end:
            item = _assignment_for_day(resident, cursor.isoformat(), self.timezone)
            if item:
                result.append(item)
            cursor += timedelta(days=1)
        return result

    def special_days(self, start: date, end: date) -> dict[str, list[dict[str, str]]]:
        return special_days_between(start, end, str(self._data.get("federal_state", "")))
