"""Base entities for CastnCasa."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, INTEGRATION_VERSION
from .coordinator import CastnCasaCoordinator


class CastnCasaEntity(CoordinatorEntity[CastnCasaCoordinator]):
    """Base household entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CastnCasaCoordinator, instance_id: str) -> None:
        super().__init__(coordinator)
        self._instance_id = instance_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, instance_id)},
            name="CastnCasa",
            manufacturer="CastnCasa",
            model="Household Schedule",
            sw_version=INTEGRATION_VERSION,
        )


class CastnCasaResidentEntity(CoordinatorEntity[CastnCasaCoordinator]):
    """Base entity associated with one household resident."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CastnCasaCoordinator,
        instance_id: str,
        resident: dict,
    ) -> None:
        super().__init__(coordinator)
        self._instance_id = instance_id
        self.resident_id = str(resident["id"])
        self.resident_name = str(resident["name"])
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{instance_id}:resident:{self.resident_id}")},
            name=f"CastnCasa · {self.resident_name}",
            manufacturer="CastnCasa",
            model="Resident Schedule",
            sw_version=INTEGRATION_VERSION,
        )

    @property
    def resident(self) -> dict | None:
        for item in self.coordinator.data.get("residents", []):
            if str(item.get("id", "")) == self.resident_id:
                return item
        return None

    @property
    def available(self) -> bool:
        # Disappearing residents become unavailable immediately; the integration
        # then removes their registry entities and resident device completely.
        return self.coordinator.last_update_success and self.resident is not None


class CastnCasaHeatEntity(CoordinatorEntity[CastnCasaCoordinator]):
    """Base entity for the separate CastnCasa Heat recommendation device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CastnCasaCoordinator, instance_id: str) -> None:
        super().__init__(coordinator)
        self._instance_id = instance_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{instance_id}:heat")},
            name="CastnCasa Heat",
            manufacturer="CastnCasa",
            model="Heat Forecast",
            sw_version=INTEGRATION_VERSION,
        )
