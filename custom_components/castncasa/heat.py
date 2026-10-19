"""CastnCasa Heat 1.0 recommendation model.

The Heat layer only publishes recommendations. It never controls heating
equipment or other Home Assistant entities by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from typing import Any, Mapping

from .const import (
    CONF_HEAT_COMFORT_BUFFER_MINUTES,
    CONF_HEAT_MIN_EMPTY_MINUTES,
    CONF_HEAT_REHEAT_LEAD_MINUTES,
    DEFAULT_HEAT_COMFORT_BUFFER_MINUTES,
    DEFAULT_HEAT_MIN_EMPTY_MINUTES,
    DEFAULT_HEAT_REHEAT_LEAD_MINUTES,
)


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@dataclass(frozen=True, slots=True)
class HeatSettings:
    """User-adjustable CastnCasa Heat 1.0 thresholds."""

    min_empty_minutes: int = DEFAULT_HEAT_MIN_EMPTY_MINUTES
    reheat_lead_minutes: int = DEFAULT_HEAT_REHEAT_LEAD_MINUTES
    comfort_buffer_minutes: int = DEFAULT_HEAT_COMFORT_BUFFER_MINUTES

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> "HeatSettings":
        """Build settings from a Home Assistant config entry."""
        return cls(
            min_empty_minutes=int(
                options.get(CONF_HEAT_MIN_EMPTY_MINUTES, DEFAULT_HEAT_MIN_EMPTY_MINUTES)
            ),
            reheat_lead_minutes=int(
                options.get(CONF_HEAT_REHEAT_LEAD_MINUTES, DEFAULT_HEAT_REHEAT_LEAD_MINUTES)
            ),
            comfort_buffer_minutes=int(
                options.get(
                    CONF_HEAT_COMFORT_BUFFER_MINUTES,
                    DEFAULT_HEAT_COMFORT_BUFFER_MINUTES,
                )
            ),
        )

    @property
    def total_reheat_lead_minutes(self) -> int:
        """Return preheat lead including the comfort safety buffer."""
        return self.reheat_lead_minutes + self.comfort_buffer_minutes


def calculate_heat_forecast(
    household: Mapping[str, Any],
    settings: HeatSettings,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Calculate heating recommendations from the household forecast."""
    generated_at = _parse_dt(household.get("generated_at"))
    now = now or generated_at or datetime.now().astimezone()
    empty_from = _parse_dt(household.get("next_house_empty_from"))
    empty_until = _parse_dt(household.get("next_house_empty_until"))
    actual_home_now = int(household.get("actual_home_now", 0) or 0)
    presence_override_home = actual_home_now > 0
    current_empty = bool(household.get("planned_house_empty")) and not presence_override_home

    duration_minutes: int | None = None
    if empty_from is not None and empty_until is not None and empty_until > empty_from:
        duration_minutes = int(round((empty_until - empty_from).total_seconds() / 60))

    reheat_from: datetime | None = None
    reduction_window_usable = False
    if duration_minutes is not None and empty_from is not None and empty_until is not None:
        candidate = empty_until - timedelta(minutes=settings.total_reheat_lead_minutes)
        reduction_window_usable = (
            duration_minutes >= settings.min_empty_minutes and candidate > empty_from
        )
        if reduction_window_usable:
            reheat_from = candidate

    time_until_home_minutes: int | None = None
    if current_empty and empty_until is not None:
        seconds = max(0.0, (empty_until - now).total_seconds())
        time_until_home_minutes = int(math.ceil(seconds / 60))

    if not current_empty or not reduction_window_usable:
        recommended_mode = "komfort"
    elif reheat_from is not None and now >= reheat_from:
        recommended_mode = "wiederaufheizen"
    else:
        recommended_mode = "reduziert"

    confidence = int(household.get("forecast_confidence_pct", 0) or 0)
    forecast_status = str(household.get("forecast_status", "unvollständig"))

    return {
        "empty_duration_minutes": duration_minutes,
        "time_until_home_minutes": time_until_home_minutes,
        "recommended_mode": recommended_mode,
        "lowering_recommended": recommended_mode == "reduziert",
        "reheat_from": reheat_from,
        "reheating": recommended_mode == "wiederaufheizen",
        "forecast_status": forecast_status,
        "forecast_confidence_pct": confidence,
        "reduction_window_usable": reduction_window_usable,
        "min_empty_minutes": settings.min_empty_minutes,
        "reheat_lead_minutes": settings.reheat_lead_minutes,
        "comfort_buffer_minutes": settings.comfort_buffer_minutes,
        "next_house_empty_from": household.get("next_house_empty_from"),
        "next_house_empty_until": household.get("next_house_empty_until"),
        "presence_override_home": presence_override_home,
        "actual_home_now": actual_home_now,
        "effective_presence_source": household.get("effective_presence_source"),
        "priority": "actual_presence_first",
    }
