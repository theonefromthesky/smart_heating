"""The Core Logic for Smart Heating."""
import logging
import math
from datetime import timedelta

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode, HVACAction
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    UnitOfTemperature,
    STATE_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
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
    CONF_COMFORT_TEMP,       # NEW
    CONF_SETBACK_TEMP,       # NEW
    DEFAULT_HEAT_UP_RATE,
    DEFAULT_HEAT_LOSS_RATE,
    DEFAULT_OVERSHOOT,
    DEFAULT_HYSTERESIS,
    DEFAULT_MAX_ON_TIME,
    DEFAULT_MAX_PREHEAT_TIME,
    DEFAULT_MIN_BURN_TIME,
    DEFAULT_COMFORT_TEMP,    # NEW
    DEFAULT_SETBACK_TEMP,    # NEW
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
    def current_temperature(self): return self._current_temp
    @property
    def target_temperature(self): return self._target_temp
    @property
    def hvac_mode(self): return self._hvac_mode

    @property
    def extra_state_attributes(self):
        """Expose values."""
        return {
            "learned_heat_up_rate": round(self._heat_up_rate, 4),
            "learned_heat_loss_rate": round(self._heat_loss_rate, 4),
            "learned_overshoot": round(self._overshoot_temp, 2),
            "boiler_active": self._is_active_heating,
            "hysteresis": self._hysteresis,
            "max_on_time_mins": self._max_on_time / 60,
            "next_fire_timestamp": self._calculate_next_fire_time(),
            "comfort_temp": self._comfort_temp,
            "setback_temp": self._setback_temp
        }

    async def async_set_temperature(self, **kwargs):
        """User manually sets temp (Override)."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._target_temp = temp
            self.async_write_ha_state()
            await self._run_control_logic()

    async def async_set_hvac_mode(self, hvac_mode):
        self._hvac_mode = hvac_mode
        if hvac_mode == HVACMode.OFF:
            await self._set_boiler(False)
        self.async_write_ha_state()
        await self._run_control_logic()

    @callback
    async def _async_sensor_changed(self, event):
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN): return
        try:
            self._current_temp = float(new_state.state)
            if self._enable_learning and not self._is_active_heating and self._peak_tracking_start_temp is not None:
                self._track_overshoot_peak()
            await self._run_control_logic()
        except ValueError: pass

    @callback
    async def _async_control_loop_event(self, event):
        """Triggered ONLY when schedule changes state."""
        new_state = event.data.get("new_state")
        if new_state is None: return

        # LOGIC: Reset target temp only on schedule switch
        if new_state.state == STATE_ON:
             _LOGGER.info(f"Schedule ON: Restoring Comfort Temp {self._comfort_temp}")
             self._target_temp = self._comfort_temp
        elif new_state.state == STATE_OFF:
             _LOGGER.info(f"Schedule OFF: Restoring Setback Temp {self._setback_temp}")
             self._target_temp = self._setback_temp
             
        self.async_write_ha_state()
        await self._run_control_logic()

    async def _async_control_loop(self, now=None): 
        # Loop does NOT change target temp (preserves overrides)
        await self._run_control_logic()

    async def _run_control_logic(self):
        if self._current_temp is None or self._hvac_mode == HVACMode.OFF:
            await self._set_boiler(False)
            return

        now = dt_util.now()
        target = self._target_temp
        
        # PREHEAT LOGIC
        # If enabled, schedule is OFF, and we are approaching an ON slot
        preheat_active = False
        if self._enable_preheat and self._schedule_entity_id:
            sched_state = self.hass.states.get(self._schedule_entity_id)
            if sched_state and sched_state.state == STATE_OFF:
                next_start = self._get_next_schedule_start()
                if next_start:
                    # Target the COMFORT temp
                    diff = self._comfort_temp - self._current_temp
                    if diff > 0:
                        minutes_needed = diff / self._heat_up_rate
                        minutes_needed = min(minutes_needed, self._max_preheat_time)
                        start_time = next_start - timedelta(minutes=minutes_needed)
                        
                        if now >= start_time:
                            # Boost target to comfort
                            target = self._comfort_temp
                            preheat_active = True
                            self._attr_preset_mode = "preheat"
        
        if not preheat_active: self._attr_preset_mode = "none"

        # OVERSHOOT LOGIC
        overshoot_adj = self._overshoot_temp if self._enable_overshoot else 0.0
        effective_cutoff = target - overshoot_adj
        
        if self._is_active_heating:
            if self._current_temp >= effective_cutoff:
                _LOGGER.info(f"Target reached. OFF.")
                await self._set_boiler(False)
            elif (now.timestamp() - self._last_on_time) > self._max_on_time:
                 _LOGGER.warning("Watchdog: Max runtime exceeded.")
                 await self._set_boiler(False)
        else:
            on_point = target - self._hysteresis
            if self._current_temp <= on_point:
                 _LOGGER.info(f"Turning ON.")
                 await self._set_boiler(True)

        self.async_write_ha_state()

    async def _set_boiler(self, turn_on):
        if turn_on and not self._is_active_heating:
            self._is_active_heating = True
            self._last_on_time = dt_util.now().timestamp()
            self._heat_start_temp = self._current_temp
            self._peak_tracking_start_temp = None
            await self.hass.services.async_call("switch", "turn_on", {"entity_id": self._heater_entity_id})
        elif not turn_on and self._is_active_heating:
            self._is_active_heating = False
            self._last_off_time = dt_util.now().timestamp()
            await self.hass.services.async_call("switch", "turn_off", {"entity_id": self._heater_entity_id})
            if self._enable_learning:
                self._learn_heat_up_rate()
                self._peak_tracking_start_temp = self._current_temp
                self._peak_temp_observed = self._current_temp

    def _learn_heat_up_rate(self):
        if not self._last_on_time or not self._heat_start_temp: return
        now_ts = dt_util.now().timestamp()
        duration_mins = (now_ts - self._last_on_time) / 60.0
        if duration_mins < self._min_burn_time: return 
        delta_temp = self._current_temp - self._heat_start_temp
        if delta_temp < 0.2: return

        calculated_rate = delta_temp / duration_mins
        new_rate = (self._heat_up_rate * 0.8) + (calculated_rate * 0.2)
        self._heat_up_rate = max(0.01, min(1.0, new_rate))

    def _track_overshoot_peak(self):
        if self._current_temp > self._peak_temp_observed: self._peak_temp_observed = self._current_temp
        time_since_off = dt_util.now().timestamp() - self._last_off_time
        if time_since_off > 1800:
            overshoot = self._peak_temp_observed - self._peak_tracking_start_temp
            if overshoot > 0:
                new_overshoot = (self._overshoot_temp * 0.8) + (overshoot * 0.2)
                self._overshoot_temp = max(0.0, min(1.0, new_overshoot))
            self._peak_tracking_start_temp = None

    def _get_next_schedule_start(self):
        if not self._schedule_entity_id: return None
        state = self.hass.states.get(self._schedule_entity_id)
        if not state: return None
        next_event = state.attributes.get("next_event")
        if next_event: return dt_util.parse_datetime(str(next_event))
        return None

    def _calculate_next_fire_time(self):
        """Estimate when the boiler will next fire."""
        if self._is_active_heating: return dt_util.now().isoformat()
        next_sched = self._get_next_schedule_start()
        if not next_sched: return None
        if not self._enable_preheat: return next_sched.isoformat()
            
        current = self._current_temp if self._current_temp else self._comfort_temp
        diff = self._comfort_temp - current # Use configured Comfort Temp
        
        if diff <= 0: return next_sched.isoformat()
            
        minutes_needed = diff / self._heat_up_rate
        minutes_needed = min(minutes_needed, self._max_preheat_time)
        fire_time = next_sched - timedelta(minutes=minutes_needed)
        
        now = dt_util.now()
        if fire_time < now: return now.isoformat()
        return fire_time.isoformat()
