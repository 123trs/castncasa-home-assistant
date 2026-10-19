"""Config flow for CastnCasa."""

from __future__ import annotations

from typing import Any, override

import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import network, selector

from .const import (
    CONF_PRESENCE_ENTITIES,
    CONF_HEAT_COMFORT_BUFFER_MINUTES,
    CONF_HEAT_MIN_EMPTY_MINUTES,
    CONF_HEAT_REHEAT_LEAD_MINUTES,
    DATA_MANAGER,
    DATA_SCHEDULE,
    DEFAULT_HEAT_COMFORT_BUFFER_MINUTES,
    DEFAULT_HEAT_MIN_EMPTY_MINUTES,
    DEFAULT_HEAT_REHEAT_LEAD_MINUTES,
    DOMAIN,
)
from .pairing import CastnCasaPairingManager


class CastnCasaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a CastnCasa config flow."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> CastnCasaOptionsFlow:
        """Create the CastnCasa options flow."""
        return CastnCasaOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up CastnCasa from the UI."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="CastnCasa", data={})

        return self.async_show_form(step_id="user")


class CastnCasaOptionsFlow(OptionsFlow):
    """Handle CastnCasa actions from the integration page."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show CastnCasa management actions."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["pair_resident", "presence_settings", "heat_settings"],
        )

    async def async_step_presence_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Map a CastnCasa resident to a real HA presence entity."""
        schedule = self.hass.data[DOMAIN][DATA_SCHEDULE]
        residents = schedule.residents()
        if not residents:
            return self.async_abort(reason="no_residents")

        current = dict(self.config_entry.options)
        mappings_value = current.get(CONF_PRESENCE_ENTITIES, {})
        mappings = dict(mappings_value) if isinstance(mappings_value, dict) else {}

        if user_input is not None:
            resident_id = str(user_input["resident_id"])
            presence_entity = str(user_input.get("presence_entity", "") or "").strip()
            if presence_entity:
                mappings[resident_id] = presence_entity
            else:
                mappings.pop(resident_id, None)
            current[CONF_PRESENCE_ENTITIES] = mappings
            return self.async_create_entry(data=current)

        resident_options = [
            selector.SelectOptionDict(value=str(resident["id"]), label=str(resident["name"]))
            for resident in residents
        ]
        first_resident_id = str(residents[0]["id"])
        schema: dict[Any, Any] = {
            probatio.Required("resident_id", default=first_resident_id): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=resident_options, mode=selector.SelectSelectorMode.DROPDOWN
                )
            )
        }
        schema[probatio.Optional("presence_entity")] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["person", "device_tracker"])
        )
        return self.async_show_form(
            step_id="presence_settings",
            data_schema=probatio.Schema(schema),
        )

    async def async_step_heat_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure CastnCasa Heat 1.0 recommendation thresholds."""
        current = dict(self.config_entry.options)
        if user_input is not None:
            current.update(user_input)
            return self.async_create_entry(data=current)

        return self.async_show_form(
            step_id="heat_settings",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_HEAT_MIN_EMPTY_MINUTES, default=int(current.get(CONF_HEAT_MIN_EMPTY_MINUTES, DEFAULT_HEAT_MIN_EMPTY_MINUTES))): probatio.All(probatio.Coerce(int), probatio.Range(min=30, max=1440)),
                    probatio.Required(CONF_HEAT_REHEAT_LEAD_MINUTES, default=int(current.get(CONF_HEAT_REHEAT_LEAD_MINUTES, DEFAULT_HEAT_REHEAT_LEAD_MINUTES))): probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=360)),
                    probatio.Required(CONF_HEAT_COMFORT_BUFFER_MINUTES, default=int(current.get(CONF_HEAT_COMFORT_BUFFER_MINUTES, DEFAULT_HEAT_COMFORT_BUFFER_MINUTES))): probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=120)),
                }
            ),
        )

    async def async_step_pair_resident(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create and show a one-time resident pairing link."""
        if user_input is not None:
            return self.async_create_entry(data=dict(self.config_entry.options))

        manager: CastnCasaPairingManager = self.hass.data[DOMAIN][DATA_MANAGER]
        base_url = network.get_url(
            self.hass,
            allow_internal=True,
            allow_external=True,
            allow_cloud=True,
            prefer_external=True,
        ).rstrip("/")
        session = manager.create_pairing(base_url)

        return self.async_show_form(
            step_id="pair_resident",
            data_schema=probatio.Schema({}),
            description_placeholders={
                "pairing_url": session.pairing_page_url,
                "pairing_qr_url": session.pairing_qr_url,
            },
        )