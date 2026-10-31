"""Adaptive reheating learner for CastnCasa Heat.

The learner observes real reheating cycles and estimates how many minutes the
building needs to reach the configured measured comfort temperature. It never
controls heating equipment directly; it only changes the lead time used by the
CastnCasa Heat recommendation model after enough valid cycles were collected.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import math
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_HEAT_LEARNING_AUTO_APPLY,
    CONF_HEAT_LEARNING_BURNER_ENTITY,
    CONF_HEAT_LEARNING_ENABLED,
    CONF_HEAT_LEARNING_OUTDOOR_TEMP_ENTITY,
    CONF_HEAT_LEARNING_ROOM_TEMP_ENTITY,
    CONF_HEAT_LEARNING_TARGET_TEMP,
    CONF_HEAT_LEARNING_TARGET_TEMP_ENTITY,
    CONF_HEAT_REDUCED_TARGET_TEMP_ENTITY,
    DEFAULT_HEAT_LEARNING_AUTO_APPLY,
    DEFAULT_HEAT_LEARNING_ENABLED,
    DEFAULT_HEAT_LEARNING_TARGET_TEMP,
    DOMAIN,
)
from .heat import HeatSettings, calculate_heat_forecast

LEARNING_STORAGE_VERSION = 1
LEARNING_MIN_CYCLES = 3
LEARNING_AUTO_APPLY_CYCLES = 5
LEARNING_MIN_LEAD_MINUTES = 10
LEARNING_MAX_LEAD_MINUTES = 180
LEARNING_TARGET_TOLERANCE = 0.2
LEARNING_MAX_STORED_CYCLES = 30
LEARNING_EARLY_RETURN_GRACE_MINUTES = 20
LEARNING_MAX_AFTER_RETURN_MINUTES = 90


class HeatLearningManager:
    """Persist and evaluate CastnCasa Heat learning cycles."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator,
        heat_settings: HeatSettings,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.heat_settings = heat_settings
        self._store = Store(
            hass,
            LEARNING_STORAGE_VERSION,
            f"{DOMAIN}.heat_learning.{entry.entry_id}",
        )
        self._cycles: list[dict[str, Any]] = []
        self._active: dict[str, Any] | None = None
        self._last_cycle: dict[str, Any] | None = None
        self._last_target_temp: float | None = None
        self._last_reduced_target_temp: float | None = None

    @property
    def enabled(self) -> bool:
        return bool(
            self.entry.options.get(
                CONF_HEAT_LEARNING_ENABLED, DEFAULT_HEAT_LEARNING_ENABLED
            )
        )

    @property
    def auto_apply(self) -> bool:
        return bool(
            self.entry.options.get(
                CONF_HEAT_LEARNING_AUTO_APPLY,
                DEFAULT_HEAT_LEARNING_AUTO_APPLY,
            )
        )

    @property
    def room_temp_entity(self) -> str:
        return str(self.entry.options.get(CONF_HEAT_LEARNING_ROOM_TEMP_ENTITY, "") or "")

    @property
    def outdoor_temp_entity(self) -> str:
        return str(
            self.entry.options.get(CONF_HEAT_LEARNING_OUTDOOR_TEMP_ENTITY, "") or ""
        )

    @property
    def burner_entity(self) -> str:
        return str(self.entry.options.get(CONF_HEAT_LEARNING_BURNER_ENTITY, "") or "")

    @property
    def target_temp_entity(self) -> str:
        return str(
            self.entry.options.get(CONF_HEAT_LEARNING_TARGET_TEMP_ENTITY, "") or ""
        )

    @property
    def reduced_target_temp_entity(self) -> str:
        return str(
            self.entry.options.get(CONF_HEAT_REDUCED_TARGET_TEMP_ENTITY, "") or ""
        )

    @property
    def configured_target_temp(self) -> float:
        return float(
            self.entry.options.get(
                CONF_HEAT_LEARNING_TARGET_TEMP,
                DEFAULT_HEAT_LEARNING_TARGET_TEMP,
            )
        )

    @property
    def target_temp(self) -> float:
        live = self._state_float(self.target_temp_entity)
        if live is not None:
            return live
        if self._last_target_temp is not None:
            return self._last_target_temp
        return self.configured_target_temp

    @property
    def reduced_target_temp(self) -> float | None:
        live = self._state_float(self.reduced_target_temp_entity)
        if live is not None:
            return live
        return self._last_reduced_target_temp

    @property
    def target_temp_source(self) -> str:
        if self._state_float(self.target_temp_entity) is not None:
            return "heating_entity"
        if self._last_target_temp is not None:
            return "last_valid_heating_value"
        return "configured_fallback"

    @property
    def reduced_target_temp_source(self) -> str | None:
        if self._state_float(self.reduced_target_temp_entity) is not None:
            return "heating_entity"
        if self._last_reduced_target_temp is not None:
            return "last_valid_heating_value"
        return None

    async def async_load(self) -> None:
        """Load persisted learning data."""
        data = await self._store.async_load() or {}
        cycles = data.get("cycles", [])
        if isinstance(cycles, list):
            self._cycles = [item for item in cycles if isinstance(item, dict)][
                -LEARNING_MAX_STORED_CYCLES:
            ]
        active = data.get("active_cycle")
        if isinstance(active, dict):
            self._active = active
        last_cycle = data.get("last_cycle")
        if isinstance(last_cycle, dict):
            self._last_cycle = last_cycle
        last_target_temp = data.get("last_target_temp")
        if isinstance(last_target_temp, (int, float)):
            self._last_target_temp = float(last_target_temp)
        last_reduced_target_temp = data.get("last_reduced_target_temp")
        if isinstance(last_reduced_target_temp, (int, float)):
            self._last_reduced_target_temp = float(last_reduced_target_temp)

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "cycles": self._cycles[-LEARNING_MAX_STORED_CYCLES:],
                "active_cycle": self._active,
                "last_cycle": self._last_cycle,
                "last_target_temp": self._last_target_temp,
                "last_reduced_target_temp": self._last_reduced_target_temp,
            }
        )

    def _state_float(self, entity_id: str) -> float | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable", "none", ""}:
            return None
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return None
        return value if math.isfinite(value) else None

    def _refresh_heating_targets(self) -> bool:
        changed = False
        live_target = self._state_float(self.target_temp_entity)
        if live_target is not None and live_target != self._last_target_temp:
            self._last_target_temp = live_target
            changed = True
        live_reduced = self._state_float(self.reduced_target_temp_entity)
        if live_reduced is not None and live_reduced != self._last_reduced_target_temp:
            self._last_reduced_target_temp = live_reduced
            changed = True
        return changed

    def _burner_on(self) -> bool | None:
        if not self.burner_entity:
            return None
        state = self.hass.states.get(self.burner_entity)
        if state is None or state.state in {"unknown", "unavailable"}:
            return None
        return state.state == "on"

    def _valid_cycles(self) -> list[dict[str, Any]]:
        return [
            cycle
            for cycle in self._cycles
            if isinstance(cycle.get("required_minutes"), (int, float))
            and cycle.get("valid", True)
        ]

    def _prediction(self) -> int | None:
        cycles = self._valid_cycles()
        if len(cycles) < LEARNING_MIN_CYCLES:
            return None

        room_temp = self._state_float(self.room_temp_entity)
        outdoor_temp = self._state_float(self.outdoor_temp_entity)
        current_deficit = (
            max(0.0, self.target_temp - room_temp) if room_temp is not None else None
        )

        weighted_total = 0.0
        weight_sum = 0.0
        newest_index = len(cycles) - 1
        for index, cycle in enumerate(cycles):
            required = float(cycle["required_minutes"])
            weight = 0.9 ** (newest_index - index)

            cycle_outdoor = cycle.get("outdoor_temp")
            if outdoor_temp is not None and isinstance(cycle_outdoor, (int, float)):
                weight /= 1.0 + abs(outdoor_temp - float(cycle_outdoor)) / 5.0

            cycle_deficit = cycle.get("start_deficit")
            if current_deficit is not None and isinstance(cycle_deficit, (int, float)):
                weight /= 1.0 + abs(current_deficit - float(cycle_deficit)) / 0.5

            weighted_total += required * weight
            weight_sum += weight

        if weight_sum <= 0:
            return None
        predicted = weighted_total / weight_sum
        rounded = int(math.ceil(predicted / 5.0) * 5)
        return max(LEARNING_MIN_LEAD_MINUTES, min(LEARNING_MAX_LEAD_MINUTES, rounded))

    @property
    def effective_reheat_lead_minutes(self) -> int:
        prediction = self._prediction()
        if (
            self.enabled
            and self.auto_apply
            and len(self._valid_cycles()) >= LEARNING_AUTO_APPLY_CYCLES
            and prediction is not None
        ):
            return prediction
        return self.heat_settings.reheat_lead_minutes

    def _sources_ready(self) -> bool:
        return bool(
            self.room_temp_entity
            and self.outdoor_temp_entity
            and self._state_float(self.room_temp_entity) is not None
            and self._state_float(self.outdoor_temp_entity) is not None
        )

    @staticmethod
    def _cycle_key(forecast: dict[str, Any]) -> str | None:
        reheat_from = forecast.get("reheat_from")
        empty_until = forecast.get("next_house_empty_until")
        if not isinstance(reheat_from, datetime) or not empty_until:
            return None
        return f"{reheat_from.isoformat()}|{empty_until}"

    def snapshot(self) -> dict[str, Any]:
        """Return the public learning state used by Heat entities."""
        valid_cycles = self._valid_cycles()
        prediction = self._prediction()
        if not self.enabled:
            status = "deaktiviert"
        elif not self._sources_ready():
            status = "sensoren_fehlen"
        elif len(valid_cycles) < LEARNING_MIN_CYCLES:
            status = "sammelt_daten"
        elif len(valid_cycles) < LEARNING_AUTO_APPLY_CYCLES or not self.auto_apply:
            status = "vorschlag"
        else:
            status = "aktiv"

        return {
            "enabled": self.enabled,
            "auto_apply": self.auto_apply,
            "status": status,
            "valid_cycles": len(valid_cycles),
            "minimum_cycles_for_suggestion": LEARNING_MIN_CYCLES,
            "minimum_cycles_for_auto_apply": LEARNING_AUTO_APPLY_CYCLES,
            "configured_reheat_lead_minutes": self.heat_settings.reheat_lead_minutes,
            "learned_reheat_lead_minutes": prediction,
            "effective_reheat_lead_minutes": self.effective_reheat_lead_minutes,
            "target_temperature": self.target_temp,
            "target_temperature_entity": self.target_temp_entity or None,
            "target_temperature_source": self.target_temp_source,
            "reduced_target_temperature": self.reduced_target_temp,
            "reduced_target_temperature_entity": self.reduced_target_temp_entity or None,
            "reduced_target_temperature_source": self.reduced_target_temp_source,
            "room_temperature_entity": self.room_temp_entity or None,
            "outdoor_temperature_entity": self.outdoor_temp_entity or None,
            "burner_entity": self.burner_entity or None,
            "active_cycle": self._active,
            "last_cycle": self._last_cycle,
        }

    def _start_cycle(
        self,
        now: datetime,
        forecast: dict[str, Any],
        room_temp: float,
        outdoor_temp: float,
    ) -> None:
        start_time = forecast.get("reheat_from")
        if not isinstance(start_time, datetime) or start_time > now:
            start_time = now
        expected_home = forecast.get("next_house_empty_until")
        self._active = {
            "cycle_key": self._cycle_key(forecast),
            "started_at": start_time.isoformat(),
            "detected_at": now.isoformat(),
            "expected_home": expected_home,
            "start_room_temp": round(room_temp, 2),
            "outdoor_temp": round(outdoor_temp, 2),
            "target_temp": self.target_temp,
            "start_deficit": round(max(0.0, self.target_temp - room_temp), 2),
            "burner_started_at": None,
            "min_room_temp": round(room_temp, 2),
            "max_room_temp": round(room_temp, 2),
            "last_room_temp": round(room_temp, 2),
        }
        self.hass.async_create_task(self._async_save())

    def _discard_active(self, reason: str, now: datetime) -> None:
        if self._active is None:
            return
        self._last_cycle = {
            **self._active,
            "finished_at": now.isoformat(),
            "valid": False,
            "reason": reason,
        }
        self._active = None
        self.hass.async_create_task(self._async_save())

    def _finish_active(
        self,
        reason: str,
        now: datetime,
        required_minutes: float,
        room_temp: float,
    ) -> None:
        if self._active is None:
            return
        cycle = {
            **self._active,
            "finished_at": now.isoformat(),
            "finish_room_temp": round(room_temp, 2),
            "required_minutes": int(
                max(0, min(LEARNING_MAX_LEAD_MINUTES, math.ceil(required_minutes)))
            ),
            "valid": True,
            "reason": reason,
        }
        self._cycles.append(cycle)
        self._cycles = self._cycles[-LEARNING_MAX_STORED_CYCLES:]
        self._last_cycle = cycle
        self._active = None
        self.hass.async_create_task(self._async_save())

    @callback
    def process_update(self) -> None:
        """Observe one coordinator update and advance the learning state."""
        now = dt_util.now()
        if self._refresh_heating_targets():
            self.hass.async_create_task(self._async_save())
        household = self.coordinator.data.get("household", {})

        if not self.enabled or not self._sources_ready():
            if self._active is not None:
                self._discard_active("learning_not_ready", now)
            self.coordinator.data["heat_learning"] = self.snapshot()
            return

        room_temp = self._state_float(self.room_temp_entity)
        outdoor_temp = self._state_float(self.outdoor_temp_entity)
        if room_temp is None or outdoor_temp is None:
            self.coordinator.data["heat_learning"] = self.snapshot()
            return

        learning_hint = {
            "effective_reheat_lead_minutes": self.effective_reheat_lead_minutes
        }
        forecast = calculate_heat_forecast(
            household,
            self.heat_settings,
            now=now,
            learning=learning_hint,
        )
        cycle_key = self._cycle_key(forecast)

        if self._active is not None:
            active_key = self._active.get("cycle_key")
            if cycle_key is not None and active_key not in {None, cycle_key}:
                self._discard_active("forecast_changed", now)

        if self._active is not None:
            self._active["last_room_temp"] = round(room_temp, 2)
            self._active["min_room_temp"] = round(
                min(float(self._active["min_room_temp"]), room_temp), 2
            )
            self._active["max_room_temp"] = round(
                max(float(self._active["max_room_temp"]), room_temp), 2
            )
            if self._active.get("burner_started_at") is None and self._burner_on() is True:
                self._active["burner_started_at"] = now.isoformat()

            started_at = datetime.fromisoformat(str(self._active["started_at"]))
            elapsed_minutes = max(0.0, (now - started_at).total_seconds() / 60.0)
            expected_home_raw = self._active.get("expected_home")
            expected_home = (
                datetime.fromisoformat(str(expected_home_raw)) if expected_home_raw else None
            )

            if room_temp >= self.target_temp - LEARNING_TARGET_TOLERANCE:
                self._finish_active("target_reached", now, elapsed_minutes, room_temp)
            elif int(household.get("actual_home_now", 0) or 0) > 0:
                if (
                    expected_home is not None
                    and now
                    < expected_home
                    - timedelta(minutes=LEARNING_EARLY_RETURN_GRACE_MINUTES)
                ):
                    self._discard_active("unexpected_early_return", now)
                else:
                    self._finish_active(
                        "arrival_before_target",
                        now,
                        elapsed_minutes + self.heat_settings.comfort_buffer_minutes,
                        room_temp,
                    )
            elif (
                expected_home is not None
                and now
                > expected_home
                + timedelta(minutes=LEARNING_MAX_AFTER_RETURN_MINUTES)
            ):
                self._finish_active(
                    "target_not_reached",
                    now,
                    elapsed_minutes,
                    room_temp,
                )

        last_cycle_key = self._last_cycle.get("cycle_key") if self._last_cycle else None
        if (
            self._active is None
            and forecast["recommended_mode"] == "wiederaufheizen"
            and bool(household.get("planned_house_empty"))
            and cycle_key is not None
            and cycle_key != last_cycle_key
        ):
            self._start_cycle(now, forecast, room_temp, outdoor_temp)
            if room_temp >= self.target_temp - LEARNING_TARGET_TOLERANCE:
                self._finish_active("target_already_reached", now, 0, room_temp)

        self.coordinator.data["heat_learning"] = self.snapshot()
