"""The Core Logic for Smart Heating."""
import logging
import math
from datetime import timedelta

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode, HVACAction
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
    STATE_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_HEATER,
    CONF_SENSOR,
    CONF_SCHEDULE,
    CONF_ENABLE_PREHEAT,
    CONF_ENABLE_OVERSHOOT,
    CONF_ENABLE_LEARNING,
    CONF_MAX_ON_TIME,
    CONF_MAX_PREHEAT_TIME,
    CONF_HYSTERESIS,
    CONF_MIN_BURN_TIME,
    CONF_COMFORT_TEMP,
    CONF_SETBACK_TEMP,
    DEFAULT_HEAT_UP_RATE,
    DEFAULT_HEAT_LOSS_RATE,
    DEFAULT_OVERSHOOT,
    DEFAULT_HYSTERESIS,
    DEFAULT_MAX_ON_TIME,
    DEFAULT_MAX_PREHEAT_TIME,
    DEFAULT_MIN_BURN_TIME,
    DEFAULT_COMFORT_TEMP,
    DEFAULT_SETBACK_TEMP,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smart Heating platform."""
    config = config_entry.data
    name = config.get("name", "Smart Heating")
    unique_id = config_entry.entry_id
    async_add_entities([SmartThermostat(hass, name, unique_id, config_entry)])

class SmartThermostat(ClimateEntity, RestoreEntity):
    """Representation of a Smart Learning Thermostat."""

    def __init__(self, hass, name, unique_id, config_entry):
        self.hass = hass
        self._config_entry = config_entry
        self._attr_name = name
        self._attr_unique_id = unique_id
        
        # Load Initial Config
        self._load_config_options()

        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        self._attr_preset_modes = ["none", "preheat"]
        self._attr_preset_mode = "none"

        # Operational State
        self._hvac_mode = HVACMode.OFF
        self._target_temp = self._comfort_temp # Default start
        self._current_temp = None
        self._is_active_heating = False 
        
        # Learned Values (Persistent)
        self._heat_up_rate = DEFAULT_HEAT_UP_RATE
        self._heat_loss_rate = DEFAULT_HEAT_LOSS_RATE
        self._overshoot_temp = DEFAULT_OVERSHOOT
        
        # Cycle Tracking
        self._last_on_time = None
        self._heat_start_temp = None
        self._last_off_time = None
        self._peak_tracking_start_temp = None
        self._peak_temp_observed = None

    def _load_config_options(self):
        """Read settings from config_entry."""
        opts = self._config_entry.options
        data = self._config_entry.data
        
        self._heater_entity_id = opts.get(CONF_HEATER, data.get(CONF_HEATER))
        self._sensor_entity_id = opts.get(CONF_SENSOR, data.get(CONF_SENSOR))
        self._schedule_entity_id = opts.get(CONF_SCHEDULE, data.get(CONF_SCHEDULE))
        
        self._enable_preheat = opts.get(CONF_ENABLE_PREHEAT, True)
        self._enable_overshoot = opts.get(CONF_ENABLE_OVERSHOOT, True)
        self._enable_learning = opts.get(CONF_ENABLE_LEARNING, True)
        
        # Numeric Tunables
        self._hysteresis = opts.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)
        self._max_on_time = opts.get(CONF_MAX_ON_TIME, DEFAULT_MAX_ON_TIME) * 60 
        self._max_preheat_time = opts.get(CONF_MAX_PREHEAT_TIME, DEFAULT_MAX_PREHEAT_TIME)
        self._min_burn_time = opts.get(CONF_MIN_BURN_TIME, DEFAULT_MIN_BURN_TIME)
        
        # Temps
        self._comfort_temp = opts.get(CONF_COMFORT_TEMP, DEFAULT_COMFORT_TEMP)
        self._setback_temp = opts.get(CONF_SETBACK_TEMP, DEFAULT_SETBACK_TEMP)

    async def async_added_to_hass(self):
        """Run when entity is added."""
        await super().async_added_to_hass()
        
        # Restore State
        last_state = await self.async_get_last_state()
        if last_state:
            self._hvac_mode = last_state.state if last_state.state in self._attr_hvac_modes else HVACMode.OFF
            self._target_temp = last_state.attributes.get("target_temp", self._comfort_temp)
            self._heat_up_rate = last_state.attributes.get("learned_heat_up_rate", DEFAULT_HEAT_UP_RATE)
            self._heat_loss_rate = last_state.attributes.get("learned_heat_loss_rate", DEFAULT_HEAT_LOSS_RATE)
            self._overshoot_temp = last_state.attributes.get("learned_overshoot", DEFAULT_OVERSHOOT)

        # Listeners
        async_track_state_change_event(self.hass, [self._sensor_entity_id], self._async_sensor_changed)
        if self._schedule_entity_id:
             async_track_state_change_event(self.hass, [self._schedule_entity_id], self._async_control_loop_event)
        
        self.async_on_remove(self._config_entry.add_update_listener(self.async_update_options))
        async_track_time_interval(self.hass, self._async_control_loop, timedelta(minutes=1))

    async def async_update_options(self, hass, entry):
        """Handle options update from UI."""
        self._load_config_options()
        await self._run_control_logic()

    # --- Properties ---
    @property
    def heat_up_rate(self): return self._heat_up_rate
    @property
    def heat_loss_rate(self): return self._heat_loss_rate
    @property
    def overshoot_temp(self): return self._overshoot_temp

    @property
    def hvac_action(self):
        if self._hvac_mode == HVACMode.OFF: return HVACAction.OFF
        return HVACAction.HEATING if self._is_active_heating else HVACAction.IDLE

    @property
