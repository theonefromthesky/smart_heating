import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

class SmartLearningThermostatConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Learning Thermostat."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title="Smart Learning Thermostat", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required("heater_entity_id"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Required("sensor_entity_id"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Helper to get current value, initial value, or a hard default
        def get_opt(key, default):
            return self.config_entry.options.get(key, self.config_entry.data.get(key, default))

        # --- 1. PREPARE CURRENT VALUES ---
        heater_entity = get_opt("heater_entity_id", None)
        sensor_entity = get_opt("sensor_entity_id", None)
        schedule_entity = get_opt("schedule_entity_id", None)
        
        comfort_temp = get_opt("comfort_temp", 20.0)
        setback_temp = get_opt("setback_temp", 16.0)
        hysteresis = get_opt("hysteresis", 0.5)
        
        max_on_time = get_opt("max_on_time", 60)
        max_preheat_time = get_opt("max_preheat_time", 60)
        min_burn_time = get_opt("min_burn_time", 10)
        
        enable_preheat = get_opt("enable_preheat", False)
        enable_overshoot = get_opt("enable_overshoot", False)
        enable_learning = get_opt("enable_learning", False)

        # --- 2. DEFINE THE SCHEMA ---
        schema = {
            # --- Entities ---
            vol.Optional("heater_entity_id", description={"suggested_value": heater_entity}): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch")
            ),
            vol.Optional("sensor_entity_id", description={"suggested_value": sensor_entity}): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional("schedule_entity_id", description={"suggested_value": schedule_entity}): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["switch", "schedule", "calendar"]) # Allow multiple domains if needed
            ),

            # --- Temperatures ---
            vol.Optional("comfort_temp", default=comfort_temp): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=30, step=0.5, unit_of_measurement="°C", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional("setback_temp", default=setback_temp): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=30, step=0.5, unit_of_measurement="°C", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional("hysteresis", default=hysteresis): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.1, max=5.0, step=0.1, unit_of_measurement="°C", mode=selector.NumberSelectorMode.BOX)
            ),

            # --- Time Durations ---
            vol.Optional("max_on_time", default=max_on_time): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=300, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional("max_preheat_time", default=max_preheat_time): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=300, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional("min_burn_time", default=min_burn_time): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=60, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX)
            ),

            # --- Toggles (BooleanSelectors) ---
            vol.Optional("enable_preheat", default=enable_preheat): selector.BooleanSelector(),
            vol.Optional("enable_overshoot", default=enable_overshoot): selector.BooleanSelector(),
            vol.Optional("enable_learning", default=enable_learning): selector.BooleanSelector(),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema)
        )