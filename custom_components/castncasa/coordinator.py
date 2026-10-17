"""Local data coordinator for CastnCasa."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .schedule import CastnCasaScheduleStore

_LOGGER = logging.getLogger(__name__)


class CastnCasaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Refresh locally calculated forecast data once per minute."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        schedule: CastnCasaScheduleStore,
    ) -> None:
        self.schedule = schedule
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=60),
            always_update=False,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        return self.schedule.state_snapshot()

    @callback
    def async_schedule_updated(self) -> None:
        self.async_set_updated_data(self.schedule.state_snapshot())
