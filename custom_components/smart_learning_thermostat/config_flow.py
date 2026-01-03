"""Config flow for Smart Heating integration."""
import logging
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
    DEFAULT_NAME,
    CONF_ENABLE_PREHEAT,
    CONF_ENABLE_OVERSHOOT,
    CONF_ENABLE_LEARNING,
    CONF_MAX_ON_TIME,
    CONF_MAX_PREHEAT_TIME,
    CONF_HYSTERESIS,
    CONF_MIN_BURN_TIME,
    CONF_COMFORT_TEMP,
    CONF_SETBACK_TEMP,
    DEFAULT_MAX_ON_TIME,
    DEFAULT_MAX_PREHEAT_TIME,
    DEFAULT_HYSTERESIS,
    DEFAULT_MIN_BURN_TIME,
    DEFAULT_COMFORT_TEMP,
    DEFAULT_SETBACK_TEMP,
)

_LOGGER = logging.getLogger(__name__)

class SmartHeatingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Heating."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(title=user_input.get("name", DEFAULT_NAME), data=user_input)

        data_schema = vol.Schema({
            vol.Required("name", default=DEFAULT_NAME): str,
            vol.Required(CONF_HEATER): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch")
            ),
            vol.Required(CONF_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Optional(CONF_SCHEDULE): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="schedule")
            ),
        })

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SmartHeatingOptionsFlowHandler(config_entry)


class SmartHeatingOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow (Settings -> Configure)."""

    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self._config_entry.options
        data = self._config_entry.data
        
        # Helper to get current value, falling back to data, then default
        def get_opt(key, default):
            return options.get(key, data.get(key, default))

        # --- DYNAMIC SCHEMA CONSTRUCTION ---
        # We build the schema dictionary piece by piece.
        # This prevents passing "default=None" to selectors, which crashes the UI.
        
        schema_dict = {}

        # 1. Temperature Settings
        schema_dict[vol.Required(CONF_COMFORT_TEMP, default=get_opt(CONF_COMFORT_TEMP, DEFAULT_COMFORT_TEMP))] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=10, max=30, step=0.5, unit_of_measurement="°C")
        )
        schema_dict[vol.Required(CONF_SETBACK_TEMP, default=get_opt(CONF_SETBACK_TEMP, DEFAULT_SETBACK_TEMP))] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=5, max=25, step=0.5, unit_of_measurement="°C")
        )

        # 2. Entities (The Crash Fix)
        # Check if we actually have a stored value. If None, do NOT pass 'default'.
        
        # Heater (Required)
        current_heater = get_opt(CONF_HEATER, None)
        if current_heater:
            schema_dict[vol.Required(CONF_HEATER, default=current_heater)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch")
            )
        else:
            schema_dict[vol.Required(CONF_HEATER)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch")
            )

        # Sensor (Required)
        current_sensor = get_opt(CONF_SENSOR, None)
        if current_sensor:
            schema_dict[vol.Required(CONF_SENSOR, default=current_sensor)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            )
        else:
            schema_dict[vol.Required(CONF_SENSOR)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            )

        # Schedule (Optional)
        current_schedule = get_opt(CONF_SCHEDULE, None)
        if current_schedule:
            schema_dict[vol.Optional(CONF_SCHEDULE, default=current_schedule)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="schedule")
            )
        else:
            # If no schedule is set, just show an empty optional field. Passing default=None here would crash it.
            schema_dict[vol.Optional(CONF_SCHEDULE)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="schedule")
            )

        # 3. Numeric Settings (Tunables)
        schema_dict[vol.Required(CONF_HYSTERESIS, default=get_opt(CONF_HYSTERESIS, DEFAULT_HYSTERESIS))] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.1, max=2.0, step=0.1, unit_of_measurement="°C")
        )
        schema_dict[vol.Required(CONF_MAX_ON_TIME, default=get_opt(CONF_MAX_ON_TIME, DEFAULT_MAX_ON_TIME))] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=30, max=600, step=10, unit_of_measurement="min")
        )
        schema_dict[vol.Required(CONF_MAX_PREHEAT_TIME, default=get_opt(CONF_MAX_PREHEAT_TIME, DEFAULT_MAX_PREHEAT_TIME))] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=300, step=10, unit_of_measurement="min")
        )
        schema_dict[vol.Required(CONF_MIN_BURN_TIME, default=get_opt(CONF_MIN_BURN_TIME, DEFAULT_MIN_BURN_TIME))] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=5, max=60, step=1, unit_of_measurement="min")
        )

        # 4. Toggles
        schema_dict[vol.Required(CONF_ENABLE_PREHEAT, default=get_opt(CONF_ENABLE_PREHEAT, True))] = bool
        schema_dict[vol.Required(CONF_ENABLE_OVERSHOOT, default=get_opt(CONF_ENABLE_OVERSHOOT, True))] = bool
        schema_dict[vol.Required(CONF_ENABLE_LEARNING, default=get_opt(CONF_ENABLE_LEARNING, True))] = bool

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema_dict))