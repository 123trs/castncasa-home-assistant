"""Local data coordinator for CastnCasa."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import APP_PRESENCE_TTL_SECONDS, CONF_PRESENCE_ENTITIES, DOMAIN
from .pairing import CastnCasaPairingManager
from .schedule import CastnCasaScheduleStore

_LOGGER = logging.getLogger(__name__)


class CastnCasaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Combine schedule forecast with real Home Assistant/app presence."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        schedule: CastnCasaScheduleStore,
        manager: CastnCasaPairingManager,
    ) -> None:
        self.entry = entry
        self.schedule = schedule
        self.manager = manager
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=60),
            always_update=False,
        )

    def _configured_presence_entities(self) -> dict[str, str]:
        value = self.entry.options.get(CONF_PRESENCE_ENTITIES, {})
        if not isinstance(value, dict):
            return {}
        return {str(key): str(entity_id) for key, entity_id in value.items() if entity_id}

    def _presence_entity(self, resident: dict[str, Any]) -> tuple[str | None, str | None]:
        resident_id = str(resident.get("id", ""))
        configured = self._configured_presence_entities().get(resident_id)
        if configured:
            return configured, "configured"

        resident_name = str(resident.get("name", "")).strip().casefold()
        if not resident_name:
            return None, None
        matches = [
            state.entity_id
            for state in self.hass.states.async_all("person")
            if str(state.attributes.get("friendly_name", "")).strip().casefold()
            == resident_name
        ]
        if len(matches) == 1:
            return matches[0], "auto_person"
        return None, None

    def presence_entity_ids(self) -> set[str]:
        """Return HA presence entities currently relevant to CastnCasa."""
        entity_ids = set(self._configured_presence_entities().values())
        for resident in self.schedule.residents():
            entity_id, _source = self._presence_entity(resident)
            if entity_id:
                entity_ids.add(entity_id)
        return entity_ids

    def _app_presence(self, resident_id: str) -> dict[str, Any] | None:
        metadata = self.manager.device_metadata(resident_id)
        presence_state = str(metadata.get("presence_state") or "unknown")
        updated_at = metadata.get("presence_updated_at")
        if presence_state not in {"home", "away"} or not updated_at:
            return None
        try:
            seen = datetime.fromisoformat(str(updated_at))
            if seen.tzinfo is None:
                seen = seen.replace(tzinfo=UTC)
        except ValueError:
            return None
        age_seconds = max(0, int((datetime.now(UTC) - seen.astimezone(UTC)).total_seconds()))
        if age_seconds > APP_PRESENCE_TTL_SECONDS:
            return None
        return {
            "presence": presence_state,
            "presence_source": str(metadata.get("presence_source") or "app"),
            "presence_entity_id": None,
            "presence_raw_state": presence_state,
            "presence_age_seconds": age_seconds,
        }

    def _resident_presence(self, resident: dict[str, Any]) -> dict[str, Any]:
        resident_id = str(resident.get("id", ""))
        entity_id, source = self._presence_entity(resident)
        if entity_id:
            state = self.hass.states.get(entity_id)
            if state is not None and state.state not in {"unknown", "unavailable"}:
                return {
                    "presence": "home" if state.state == "home" else "away",
                    "presence_source": source,
                    "presence_entity_id": entity_id,
                    "presence_raw_state": state.state,
                    "presence_age_seconds": None,
                }

        app_presence = self._app_presence(resident_id)
        if app_presence is not None:
            return app_presence

        return {
            "presence": "unknown",
            "presence_source": source or "none",
            "presence_entity_id": entity_id,
            "presence_raw_state": None,
            "presence_age_seconds": None,
        }

    @staticmethod
    def _plan_deviation(planned_away: bool, presence: str) -> str:
        if presence == "unknown":
            return "unbekannt"
        if planned_away and presence == "home":
            return "anwesend_trotz_plan"
        if not planned_away and presence == "away":
            return "abwesend_trotz_plan"
        return "im_plan"

    def _snapshot(self) -> dict[str, Any]:
        snapshot = self.schedule.state_snapshot()
        residents = snapshot.get("residents", [])
        home_names: list[str] = []
        away_names: list[str] = []
        unknown_names: list[str] = []

        for resident in residents:
            resident_id = str(resident.get("id", ""))
            metadata = self.manager.device_metadata(resident_id)
            presence = self._resident_presence(resident)
            resident.update(presence)
            resident["last_seen"] = metadata.get("last_seen")
            resident["device_name"] = metadata.get("device_name")
            resident["app_version"] = metadata.get("app_version")
            resident["next_departure"] = resident.get("next_planned_absence")
            resident["plan_deviation"] = self._plan_deviation(
                bool(resident.get("planned_away")), str(presence["presence"])
            )
            resident["plan_matches_actual"] = (
                None
                if presence["presence"] == "unknown"
                else resident["plan_deviation"] == "im_plan"
            )
            if presence["presence"] == "home":
                home_names.append(str(resident.get("name", resident_id)))
            elif presence["presence"] == "away":
                away_names.append(str(resident.get("name", resident_id)))
            else:
                unknown_names.append(str(resident.get("name", resident_id)))

        household = snapshot.get("household", {})
        known_count = len(home_names) + len(away_names)
        all_known = bool(residents) and known_count == len(residents)
        actual_house_empty: bool | None
        if home_names:
            actual_house_empty = False
        elif all_known:
            actual_house_empty = True
        else:
            actual_house_empty = None

        if home_names:
            effective_house_empty = False
            effective_source = "actual_home"
        elif actual_house_empty is True:
            effective_house_empty = True
            effective_source = "actual_away"
        else:
            effective_house_empty = bool(household.get("planned_house_empty"))
            effective_source = "forecast_fallback"

        household.update(
            {
                "actual_home_now": len(home_names),
                "actual_away_now": len(away_names),
                "presence_known_now": known_count,
                "presence_complete": all_known,
                "actual_home_names": home_names,
                "actual_away_names": away_names,
                "presence_unknown_names": unknown_names,
                "actual_house_empty": actual_house_empty,
                "effective_house_empty": effective_house_empty,
                "effective_presence_source": effective_source,
                "priority": "actual_presence_first",
                "priority_note": "Tatsächliche Anwesenheit aus Home Assistant oder frischer CastnCasa-Präsenz hat immer Vorrang vor der Dienstplan-Prognose.",
            }
        )
        snapshot["priority"] = "actual_presence_first"
        snapshot["priority_note"] = household["priority_note"]

        # Heat learning is integration-local runtime state. Keep the most recent
        # snapshot attached while the schedule/presence coordinator replaces its
        # data every 60 seconds, so all Heat entities see one consistent learned
        # lead even if their listeners run before the learner updates this cycle.
        current_data = getattr(self, "data", None)
        if isinstance(current_data, dict) and "heat_learning" in current_data:
            snapshot["heat_learning"] = current_data["heat_learning"]
        return snapshot

    async def _async_update_data(self) -> dict[str, Any]:
        return self._snapshot()

    @callback
    def async_schedule_updated(self) -> None:
        self.async_set_updated_data(self._snapshot())

    @callback
    def async_presence_updated(self) -> None:
        self.async_set_updated_data(self._snapshot())
