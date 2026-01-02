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
)

# --- SAFETY IMPORT BLOCK ---
try:
    from .const import (
        CONF_ENABLE_PREHEAT,
        CONF_ENABLE_OVERSHOOT,
        CONF_ENABLE_LEARNING,
    )
except ImportError:
    CONF_ENABLE_PREHEAT = "enable_preheat"
    CONF_ENABLE_OVERSHOOT = "enable_overshoot"
    CONF_ENABLE_LEARNING = "enable_learning"

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
        """Create the options flow."""
        return SmartHeatingOptionsFlowHandler(config_entry)


class SmartHeatingOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow (Settings -> Configure)."""

    def __init__(self, config_entry):
        # FIX: Do not assign to self.config_entry as it is read-only in newer HA versions.
        # We store it in self._config_entry instead.
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # FIX: Read from self._config_entry
        options = self._config_entry.options
        data = self._config_entry.data
        
        # Helper to safely get current value
        def get_opt(key, default):
            return options.get(key, data.get(key, default))

        schema = vol.Schema({
            vol.Required(CONF_HEATER, default=get_opt(CONF_HEATER, None)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch")
            ),
            vol.Required(CONF_SENSOR, default=get_opt(CONF_SENSOR, None)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Optional(CONF_SCHEDULE, default=get_opt(CONF_SCHEDULE, None)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="schedule")
            ),
            
            # Toggles
            vol.Required(CONF_ENABLE_PREHEAT, default=options.get(CONF_ENABLE_PREHEAT, True)): bool,
            vol.Required(CONF_ENABLE_OVERSHOOT, default=options.get(CONF_ENABLE_OVERSHOOT, True)): bool,
            vol.Required(CONF_ENABLE_LEARNING, default=options.get(CONF_ENABLE_LEARNING, True)): bool,
        })

        return self.async_show_form(step_id="init", data_schema=schema)
