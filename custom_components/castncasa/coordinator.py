"""Local data coordinator for CastnCasa."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .presence import CastnCasaPresenceStore
from .schedule import CastnCasaScheduleStore

_LOGGER = logging.getLogger(__name__)


class CastnCasaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Refresh schedule and real presence data once per minute."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        schedule: CastnCasaScheduleStore,
        presence: CastnCasaPresenceStore,
    ) -> None:
        self.schedule = schedule
        self.presence = presence
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=60),
            always_update=False,
        )

    def _snapshot(self) -> dict[str, Any]:
        return self.presence.enrich_snapshot(self.schedule.state_snapshot())

    async def _async_update_data(self) -> dict[str, Any]:
        return self._snapshot()

    @callback
    def async_source_updated(self) -> None:
        """Refresh immediately after schedule, heartbeat, or HA presence changes."""
        self.async_set_updated_data(self._snapshot())
