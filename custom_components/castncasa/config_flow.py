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
    CONF_HEAT_COMFORT_BUFFER_MINUTES,
    CONF_HEAT_LEARNING_AUTO_APPLY,
    CONF_HEAT_LEARNING_BURNER_ENTITY,
    CONF_HEAT_LEARNING_ENABLED,
    CONF_HEAT_LEARNING_OUTDOOR_TEMP_ENTITY,
    CONF_HEAT_LEARNING_ROOM_TEMP_ENTITY,
    CONF_HEAT_LEARNING_TARGET_TEMP,
    CONF_HEAT_LEARNING_TARGET_TEMP_ENTITY,
    CONF_HEAT_REDUCED_TARGET_TEMP_ENTITY,
    CONF_HEAT_MIN_COMFORT_MINUTES,
    CONF_HEAT_MIN_EMPTY_MINUTES,
    CONF_HEAT_REHEAT_LEAD_MINUTES,
    CONF_PRESENCE_ENTITIES,
    DATA_MANAGER,
    DATA_SCHEDULE,
    DEFAULT_HEAT_COMFORT_BUFFER_MINUTES,
    DEFAULT_HEAT_LEARNING_AUTO_APPLY,
    DEFAULT_HEAT_LEARNING_ENABLED,
    DEFAULT_HEAT_LEARNING_TARGET_TEMP,
    DEFAULT_HEAT_MIN_COMFORT_MINUTES,
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
        active_resident_ids = {str(resident["id"]) for resident in residents}
        mappings = {
            resident_id: entity_id
            for resident_id, entity_id in mappings.items()
            if resident_id in active_resident_ids
        }

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
        """Configure CastnCasa Heat recommendation and learning settings."""
        current = dict(self.config_entry.options)
        if user_input is not None:
            current.update(user_input)
            for entity_key in (
                CONF_HEAT_LEARNING_ROOM_TEMP_ENTITY,
                CONF_HEAT_LEARNING_OUTDOOR_TEMP_ENTITY,
                CONF_HEAT_LEARNING_BURNER_ENTITY,
                CONF_HEAT_LEARNING_TARGET_TEMP_ENTITY,
                CONF_HEAT_REDUCED_TARGET_TEMP_ENTITY,
            ):
                if entity_key in user_input and not user_input.get(entity_key):
                    current.pop(entity_key, None)
            return self.async_create_entry(data=current)

        schema: dict[Any, Any] = {
            probatio.Required(
                CONF_HEAT_MIN_EMPTY_MINUTES,
                default=int(
                    current.get(
                        CONF_HEAT_MIN_EMPTY_MINUTES, DEFAULT_HEAT_MIN_EMPTY_MINUTES
                    )
                ),
            ): probatio.All(probatio.Coerce(int), probatio.Range(min=30, max=1440)),
            probatio.Required(
                CONF_HEAT_REHEAT_LEAD_MINUTES,
                default=int(
                    current.get(
                        CONF_HEAT_REHEAT_LEAD_MINUTES,
                        DEFAULT_HEAT_REHEAT_LEAD_MINUTES,
                    )
                ),
            ): probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=360)),
            probatio.Required(
                CONF_HEAT_COMFORT_BUFFER_MINUTES,
                default=int(
                    current.get(
                        CONF_HEAT_COMFORT_BUFFER_MINUTES,
                        DEFAULT_HEAT_COMFORT_BUFFER_MINUTES,
                    )
                ),
            ): probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=120)),
            probatio.Required(
                CONF_HEAT_MIN_COMFORT_MINUTES,
                default=int(
                    current.get(
                        CONF_HEAT_MIN_COMFORT_MINUTES,
                        DEFAULT_HEAT_MIN_COMFORT_MINUTES,
                    )
                ),
            ): probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=720)),
            probatio.Required(
                CONF_HEAT_LEARNING_ENABLED,
                default=bool(
                    current.get(
                        CONF_HEAT_LEARNING_ENABLED,
                        DEFAULT_HEAT_LEARNING_ENABLED,
                    )
                ),
            ): selector.BooleanSelector(),
            probatio.Required(
                CONF_HEAT_LEARNING_AUTO_APPLY,
                default=bool(
                    current.get(
                        CONF_HEAT_LEARNING_AUTO_APPLY,
                        DEFAULT_HEAT_LEARNING_AUTO_APPLY,
                    )
                ),
            ): selector.BooleanSelector(),
            probatio.Required(
                CONF_HEAT_LEARNING_TARGET_TEMP,
                default=float(
                    current.get(
                        CONF_HEAT_LEARNING_TARGET_TEMP,
                        DEFAULT_HEAT_LEARNING_TARGET_TEMP,
                    )
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=15.0,
                    max=30.0,
                    step=0.1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="°C",
                )
            ),
        }

        room_default = str(current.get(CONF_HEAT_LEARNING_ROOM_TEMP_ENTITY, "") or "")
        outdoor_default = str(
            current.get(CONF_HEAT_LEARNING_OUTDOOR_TEMP_ENTITY, "") or ""
        )
        burner_default = str(current.get(CONF_HEAT_LEARNING_BURNER_ENTITY, "") or "")
        target_default = str(current.get(CONF_HEAT_LEARNING_TARGET_TEMP_ENTITY, "") or "")
        reduced_default = str(current.get(CONF_HEAT_REDUCED_TARGET_TEMP_ENTITY, "") or "")
        if room_default:
            schema[
                probatio.Optional(
                    CONF_HEAT_LEARNING_ROOM_TEMP_ENTITY, default=room_default
                )
            ] = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
        else:
            schema[probatio.Optional(CONF_HEAT_LEARNING_ROOM_TEMP_ENTITY)] = (
                selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
            )
        if outdoor_default:
            schema[
                probatio.Optional(
                    CONF_HEAT_LEARNING_OUTDOOR_TEMP_ENTITY, default=outdoor_default
                )
            ] = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
        else:
            schema[probatio.Optional(CONF_HEAT_LEARNING_OUTDOOR_TEMP_ENTITY)] = (
                selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
            )
        if burner_default:
            schema[
                probatio.Optional(CONF_HEAT_LEARNING_BURNER_ENTITY, default=burner_default)
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor")
            )
        else:
            schema[probatio.Optional(CONF_HEAT_LEARNING_BURNER_ENTITY)] = (
                selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                )
            )

        if target_default:
            schema[probatio.Optional(CONF_HEAT_LEARNING_TARGET_TEMP_ENTITY, default=target_default)] = (
                selector.EntitySelector(selector.EntitySelectorConfig(domain="number"))
            )
        else:
            schema[probatio.Optional(CONF_HEAT_LEARNING_TARGET_TEMP_ENTITY)] = (
                selector.EntitySelector(selector.EntitySelectorConfig(domain="number"))
            )
        if reduced_default:
            schema[probatio.Optional(CONF_HEAT_REDUCED_TARGET_TEMP_ENTITY, default=reduced_default)] = (
                selector.EntitySelector(selector.EntitySelectorConfig(domain="number"))
            )
        else:
            schema[probatio.Optional(CONF_HEAT_REDUCED_TARGET_TEMP_ENTITY)] = (
                selector.EntitySelector(selector.EntitySelectorConfig(domain="number"))
            )

        return self.async_show_form(
            step_id="heat_settings",
            data_schema=probatio.Schema(schema),
        )

    async def async_step_pair_resident(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose whether to add a new resident or relink an existing one."""
        schedule = self.hass.data[DOMAIN][DATA_SCHEDULE]
        residents = schedule.residents()

        if user_input is not None:
            selected = str(user_input.get("resident_id", "__new__"))
            resident_id = None if selected == "__new__" else selected
            if resident_id is not None and not any(
                str(resident["id"]) == resident_id for resident in residents
            ):
                return self.async_abort(reason="resident_not_found")

            manager: CastnCasaPairingManager = self.hass.data[DOMAIN][DATA_MANAGER]
            base_url = network.get_url(
                self.hass,
                allow_internal=True,
                allow_external=True,
                allow_cloud=True,
                prefer_external=True,
            ).rstrip("/")
            self._castncasa_pairing_session = manager.create_pairing(base_url, resident_id)
            return await self.async_step_pair_resident_qr()

        resident_options = [
            selector.SelectOptionDict(value="__new__", label="Neuer Bewohner")
        ] + [
            selector.SelectOptionDict(
                value=str(resident["id"]),
                label=f"{resident['name']} wieder verbinden",
            )
            for resident in residents
        ]
        return self.async_show_form(
            step_id="pair_resident",
            data_schema=probatio.Schema(
                {
                    probatio.Required("resident_id", default="__new__"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=resident_options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_pair_resident_qr(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the one-time resident pairing link after the target was chosen."""
        if user_input is not None:
            return self.async_create_entry(data=dict(self.config_entry.options))

        session = getattr(self, "_castncasa_pairing_session", None)
        if session is None:
            return await self.async_step_pair_resident()
        return self.async_show_form(
            step_id="pair_resident_qr",
            data_schema=probatio.Schema({}),
            description_placeholders={
                "pairing_url": session.pairing_page_url,
                "pairing_qr_url": session.pairing_qr_url,
            },
        )
