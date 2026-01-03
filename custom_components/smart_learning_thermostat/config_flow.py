import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_HEATER,
    CONF_SENSOR,
    CONF_SCHEDULE,
    CONF_COMFORT_TEMP,
    CONF_SETBACK_TEMP,
    CONF_HYSTERESIS,
    CONF_MAX_ON_TIME,
    CONF_MAX_PREHEAT_TIME,
    CONF_MIN_BURN_TIME,
    CONF_ENABLE_PREHEAT,
    CONF_ENABLE_OVERSHOOT,
    CONF_ENABLE_LEARNING,
    DEFAULT_COMFORT_TEMP,
    DEFAULT_SETBACK_TEMP,
    DEFAULT_HYSTERESIS,
    DEFAULT_MAX_ON_TIME,
    DEFAULT_MAX_PREHEAT_TIME,
    DEFAULT_MIN_BURN_TIME,
)

class SmartHeatingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Learning Thermostat."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial setup."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title=user_input.get("name", "Smart Thermostat"), data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("name", default="Smart Heating"): str,
                vol.Required(CONF_HEATER): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Required(CONF_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_SCHEDULE): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["schedule", "calendar", "switch"])
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
        # FIXED: Do not manually set self.config_entry. 
        # The parent class manages it automatically as a property.
        pass

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Helper to get current value, initial value, or a hard default
        # self.config_entry is available automatically via the parent class
        def get_opt(key, default):
            return self.config_entry.options.get(key, self.config_entry.data.get(key, default))

        # --- 1. PREPARE CURRENT VALUES ---
        heater_entity = get_opt(CONF_HEATER, None)
        sensor_entity = get_opt(CONF_SENSOR, None)
        schedule_entity = get_opt(CONF_SCHEDULE, None)
        
        comfort_temp = get_opt(CONF_COMFORT_TEMP, DEFAULT_COMFORT_TEMP)
        setback_temp = get_opt(CONF_SETBACK_TEMP, DEFAULT_SETBACK_TEMP)
        hysteresis = get_opt(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)
        
        max_on_time = get_opt(CONF_MAX_ON_TIME, DEFAULT_MAX_ON_TIME)
        max_preheat_time = get_opt(CONF_MAX_PREHEAT_TIME, DEFAULT_MAX_PREHEAT_TIME)
        min_burn_time = get_opt(CONF_MIN_BURN_TIME, DEFAULT_MIN_BURN_TIME)
        
        enable_preheat = get_opt(CONF_ENABLE_PREHEAT, False)
        enable_overshoot = get_opt(CONF_ENABLE_OVERSHOOT, False)
        enable_learning = get_opt(CONF_ENABLE_LEARNING, False)

        # --- 2. DEFINE THE SCHEMA ---
        schema = {
            # --- Entities ---
            vol.Optional(CONF_HEATER, description={"suggested_value": heater_entity}): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch")
            ),
            vol.Optional(CONF_SENSOR, description={"suggested_value": sensor_entity}): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_SCHEDULE, description={"suggested_value": schedule_entity}): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["schedule", "calendar", "switch"]) 
            ),

            # --- Temperatures ---
            vol.Optional(CONF_COMFORT_TEMP, default=comfort_temp): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=30, step=0.5, unit_of_measurement="°C", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_SETBACK_TEMP, default=setback_temp): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=30, step=0.5, unit_of_measurement="°C", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_HYSTERESIS, default=hysteresis): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.1, max=5.0, step=0.1, unit_of_measurement="°C", mode=selector.NumberSelectorMode.BOX)
            ),

            # --- Time Durations ---
            vol.Optional(CONF_MAX_ON_TIME, default=max_on_time): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=300, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_MAX_PREHEAT_TIME, default=max_preheat_time): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=300, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_MIN_BURN_TIME, default=min_burn_time): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=60, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX)
            ),

            # --- Toggles (BooleanSelectors) ---
            vol.Optional(CONF_ENABLE_PREHEAT, default=enable_preheat): selector.BooleanSelector(),
            vol.Optional(CONF_ENABLE_OVERSHOOT, default=enable_overshoot): selector.BooleanSelector(),
            vol.Optional(CONF_ENABLE_LEARNING, default=enable_learning): selector.BooleanSelector(),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema)
        )
