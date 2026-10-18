"""Presence tracking and heartbeat API for CastnCasa."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import json
from typing import Any

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import EVENT_STATE_CHANGED, STATE_HOME, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import PRESENCE_PATH
from .http import _authenticate, _decrypt_request_body, _encrypted_json_response
from .pairing import CastnCasaPairingManager, DeviceAuthError

STORE_VERSION = 1
STORE_KEY = "castncasa.presence"
PRESENCE_TTL_SECONDS = 600
MAX_PRESENCE_BODY = 8 * 1024
VALID_SOURCES = {"home_network", "remote", "companion", "app"}
VALID_SYNC_MODES = {"home_network", "remote"}


class PresenceValidationError(Exception):
    """Raised when a presence heartbeat payload is invalid."""


class CastnCasaPresenceStore:
    """Persist app heartbeats and combine them with native HA presence."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, STORE_KEY)
        self._data: dict[str, Any] = {"devices": {}}
        self._listeners: set[Callable[[], None]] = set()
        self._ha_listener_remove: Callable[[], None] | None = None

    async def async_load(self) -> None:
        loaded = await self._store.async_load() or {}
        devices = loaded.get("devices", {})
        self._data = {"devices": devices if isinstance(devices, dict) else {}}

    @callback
    def async_start(self) -> None:
        """Watch native HA presence sources independently from calendar sync."""
        if self._ha_listener_remove is not None:
            return
        self._ha_listener_remove = self.hass.bus.async_listen(
            EVENT_STATE_CHANGED, self._async_ha_state_changed
        )

    @callback
    def _async_ha_state_changed(self, event: Event) -> None:
        entity_id = str(event.data.get("entity_id", ""))
        if entity_id.startswith("person.") or entity_id.startswith("device_tracker."):
            self._notify()

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

    async def async_update_presence(
        self, device_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Store one authenticated heartbeat from the app."""
        home = payload.get("home")
        if not isinstance(home, bool):
            raise PresenceValidationError("home_required")

        source = str(payload.get("source") or "home_network").strip().lower()
        if source not in VALID_SOURCES:
            raise PresenceValidationError("invalid_source")
        sync_mode = str(payload.get("sync_mode") or source).strip().lower()
        if sync_mode not in VALID_SYNC_MODES:
            sync_mode = "home_network" if source == "home_network" else "remote"

        now = dt_util.now()
        record = {
            "home": home,
            "last_seen": now.isoformat(timespec="seconds"),
            "source": source,
            "sync_mode": sync_mode,
        }
        client_timestamp = payload.get("client_timestamp")
        if isinstance(client_timestamp, str) and len(client_timestamp) <= 64:
            record["client_timestamp"] = client_timestamp

        self._data["devices"][device_id] = record
        await self._async_save()
        self._notify()
        return dict(record)

    async def async_remove(self, device_id: str) -> bool:
        if self._data.get("devices", {}).pop(device_id, None) is None:
            return False
        await self._async_save()
        self._notify()
        return True

    def _heartbeat(self, device_id: str) -> dict[str, Any] | None:
        record = self._data.get("devices", {}).get(device_id)
        return record if isinstance(record, dict) else None

    def _ha_candidates(self, resident_name: str) -> list[str]:
        object_id = slugify(resident_name)
        return [f"person.{object_id}", f"device_tracker.{object_id}"]

    def _native_presence(self, resident_name: str) -> list[dict[str, Any]]:
        signals: list[dict[str, Any]] = []
        for entity_id in self._ha_candidates(resident_name):
            state = self.hass.states.get(entity_id)
            if state is None or state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
                continue
            signals.append(
                {
                    "entity_id": entity_id,
                    "home": state.state == STATE_HOME,
                    "state": state.state,
                    "last_seen": state.last_updated.isoformat(timespec="seconds"),
                }
            )
        return signals

    @staticmethod
    def _seconds_since(value: str | None, now: datetime) -> int | None:
        if not value:
            return None
        try:
            timestamp = datetime.fromisoformat(value)
        except ValueError:
            return None
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=now.tzinfo)
        return max(0, int((now - timestamp).total_seconds()))

    def resolve_resident(self, resident: dict[str, Any], now: datetime) -> dict[str, Any]:
        """Resolve actual presence. Any confirmed-home signal wins for comfort."""
        resident_id = str(resident.get("id", ""))
        resident_name = str(resident.get("name", ""))
        heartbeat = self._heartbeat(resident_id)
        native = self._native_presence(resident_name)

        heartbeat_age = self._seconds_since(
            str(heartbeat.get("last_seen")) if heartbeat else None, now
        )
        heartbeat_fresh = heartbeat_age is not None and heartbeat_age <= PRESENCE_TTL_SECONDS
        heartbeat_home = bool(heartbeat and heartbeat.get("home"))

        native_home = next((item for item in native if item["home"]), None)
        native_away = next((item for item in native if not item["home"]), None)

        if native_home is not None:
            presence = "home"
            source = native_home["entity_id"]
        elif heartbeat_fresh and heartbeat_home:
            presence = "home"
            source = str(heartbeat.get("source") or "app")
        elif native_away is not None:
            presence = "away"
            source = native_away["entity_id"]
        elif heartbeat_fresh:
            presence = "away"
            source = str(heartbeat.get("source") or "app")
        elif heartbeat and heartbeat_home and heartbeat.get("source") == "home_network":
            presence = "away"
            source = "home_network_timeout"
        else:
            presence = "unknown"
            source = "none"

        last_seen_candidates: list[str] = []
        if heartbeat and isinstance(heartbeat.get("last_seen"), str):
            last_seen_candidates.append(heartbeat["last_seen"])
        last_seen_candidates.extend(
            item["last_seen"] for item in native if isinstance(item.get("last_seen"), str)
        )
        last_seen = max(last_seen_candidates) if last_seen_candidates else None

        planned_away = bool(resident.get("planned_away"))
        if presence == "unknown":
            plan_deviation = "unbekannt"
        elif presence == "home" and planned_away:
            plan_deviation = "zuhause_trotz_plan"
        elif presence == "away" and not planned_away:
            plan_deviation = "abwesend_trotz_plan"
        else:
            plan_deviation = "im_plan"

        return {
            "presence": presence,
            "presence_source": source,
            "last_seen": last_seen,
            "heartbeat_age_seconds": heartbeat_age,
            "heartbeat_fresh": heartbeat_fresh,
            "person_entity_id": native[0]["entity_id"] if native else None,
            "plan_deviation": plan_deviation,
            "next_departure": resident.get("next_planned_absence"),
        }

    def enrich_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Apply actual presence to a fresh schedule snapshot."""
        now = dt_util.now()
        residents = snapshot.get("residents", [])
        confirmed_home_names: list[str] = []
        confirmed_away_names: list[str] = []
        unknown_names: list[str] = []

        for resident in residents:
            presence = self.resolve_resident(resident, now)
            resident.update(presence)
            if presence["presence"] == "home":
                confirmed_home_names.append(str(resident.get("name", resident.get("id", ""))))
            elif presence["presence"] == "away":
                confirmed_away_names.append(str(resident.get("name", resident.get("id", ""))))
            else:
                unknown_names.append(str(resident.get("name", resident.get("id", ""))))

        household = snapshot.setdefault("household", {})
        planned_empty = bool(household.get("planned_house_empty"))
        confirmed_home = bool(confirmed_home_names)
        household.update(
            {
                "confirmed_home": confirmed_home,
                "confirmed_home_names": confirmed_home_names,
                "confirmed_away_names": confirmed_away_names,
                "presence_unknown_names": unknown_names,
                "actual_presence_available": bool(confirmed_home_names or confirmed_away_names),
                "effective_house_empty": planned_empty and not confirmed_home,
                "presence_status": (
                    "home"
                    if confirmed_home
                    else "away"
                    if residents and not unknown_names
                    else "unknown"
                ),
                "priority": "actual_presence_over_forecast",
                "priority_note": (
                    "Bestätigte Anwesenheit hat Vorrang vor der Dienstplan-Prognose. "
                    "Ohne bestätigte Anwesenheit bleibt der Dienstplan die Heizungsprognose."
                ),
            }
        )
        snapshot["priority"] = "actual_presence_over_forecast"
        snapshot["priority_note"] = household["priority_note"]
        return snapshot


class CastnCasaPresenceView(HomeAssistantView):
    """Receive encrypted presence heartbeats independently from schedule sync."""

    url = PRESENCE_PATH
    name = "api:castncasa:presence"
    requires_auth = False

    def __init__(
        self, manager: CastnCasaPairingManager, presence: CastnCasaPresenceStore
    ) -> None:
        self.manager = manager
        self.presence = presence

    async def post(self, request: web.Request) -> web.Response:
        envelope = await request.read()
        if len(envelope) > MAX_PRESENCE_BODY:
            return web.json_response({"error": "request_too_large"}, status=413)
        try:
            device_id, record = await _authenticate(
                self.manager, request, PRESENCE_PATH, envelope
            )
        except DeviceAuthError:
            return web.json_response({"error": "invalid_auth"}, status=401)

        try:
            plaintext = _decrypt_request_body(record, request, PRESENCE_PATH, envelope)
            data = json.loads(plaintext)
        except Exception:
            return _encrypted_json_response(
                record,
                request,
                PRESENCE_PATH,
                {"error": "invalid_encrypted_body"},
                status=400,
            )
        if not isinstance(data, dict):
            return _encrypted_json_response(
                record,
                request,
                PRESENCE_PATH,
                {"error": "invalid_request"},
                status=400,
            )
        try:
            result = await self.presence.async_update_presence(device_id, data)
        except PresenceValidationError as err:
            return _encrypted_json_response(
                record,
                request,
                PRESENCE_PATH,
                {"error": str(err)},
                status=400,
            )
        return _encrypted_json_response(
            record,
            request,
            PRESENCE_PATH,
            {
                "ok": True,
                "api_version": 1,
                "presence_timeout_seconds": PRESENCE_TTL_SECONDS,
                "presence": result,
            },
        )
