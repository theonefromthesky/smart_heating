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

_LOGGER = logging.getLogger(__name__)

class SmartHeatingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Heating."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate input if necessary, then create entry
            return self.async_create_entry(title=user_input.get("name", DEFAULT_NAME), data=user_input)

        # The Form Schema
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
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Pre-fill with existing data
        current_config = self.config_entry.data
        
        # Allow users to change entities after setup
        schema = vol.Schema({
            vol.Required(CONF_HEATER, default=current_config.get(CONF_HEATER)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch")
            ),
            vol.Required(CONF_SENSOR, default=current_config.get(CONF_SENSOR)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Optional(CONF_SCHEDULE, default=current_config.get(CONF_SCHEDULE)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="schedule")
            ),
        })

        return self.async_show_form(step_id="init", data_schema=schema)