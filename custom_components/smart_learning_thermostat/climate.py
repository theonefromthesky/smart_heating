"""The Core Logic for Smart Heating."""
import logging
from datetime import timedelta

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)
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

# Import your custom constants to ensure sync
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
    async_add_entities([SmartThermostat(hass, config_entry)])

class SmartThermostat(ClimateEntity, RestoreEntity):
    """Representation of a Smart Learning Thermostat."""

    def __init__(self, hass, config_entry):
        self.hass = hass
        self._config_entry = config_entry
        
        # Identity
        self._attr_name = config_entry.data.get("name", "Smart Heating")
        self._attr_unique_id = config_entry.entry_id
        
        # Load Configuration
        self._load_config_options()

        # Entity Attributes
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        self._attr_preset_modes = ["none", "preheat"]
        self._attr_preset_mode = "none"

        # Operational State
        self._hvac_mode = HVACMode.OFF
        self._target_temp = self._setback_temp 
        self._current_temp = None
        self._is_active_heating = False 
        
        # Logic Flags
        self._manual_mode = False        
        self._last_schedule_state = None 
        self._preheat_latch = False  # <--- NEW: Sticks to True once preheat starts
        
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
        """Read settings safely using constants."""
        options = self._config_entry.options
        data = self._config_entry.data

        def get_val(key, default=None):
            return options.get(key, data.get(key, default))

        # --- Entities ---
        self._heater_entity_id = get_val(CONF_HEATER)
        self._sensor_entity_id = get_val(CONF_SENSOR)
        self._schedule_entity_id = get_val(CONF_SCHEDULE)
        
        # --- Toggles ---
        self._enable_preheat = get_val(CONF_ENABLE_PREHEAT, False)
        self._enable_overshoot = get_val(CONF_ENABLE_OVERSHOOT, False)
        self._enable_learning = get_val(CONF_ENABLE_LEARNING, False)
        
        # --- Numeric Settings ---
        self._hysteresis = get_val(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)
        self._max_on_time = get_val(CONF_MAX_ON_TIME, DEFAULT_MAX_ON_TIME) * 60 
        self._max_preheat_time = get_val(CONF_MAX_PREHEAT_TIME, DEFAULT_MAX_PREHEAT_TIME)
        self._min_burn_time = get_val(CONF_MIN_BURN_TIME, DEFAULT_MIN_BURN_TIME)
        
        # --- Temperatures ---
        self._comfort_temp = get_val(CONF_COMFORT_TEMP, DEFAULT_COMFORT_TEMP)
        self._setback_temp = get_val(CONF_SETBACK_TEMP, DEFAULT_SETBACK_TEMP)

    async def async_added_to_hass(self):
        """Run when entity is added."""
        await super().async_added_to_hass()
        
        # Restore State
        last_state = await self.async_get_last_state()
        if last_state:
            self._hvac_mode = last_state.state if last_state.state in self._attr_hvac_modes else HVACMode.OFF
            self._target_temp = last_state.attributes.get("target_temp", self._setback_temp)
            self._heat_up_rate = last_state.attributes.get("learned_heat_up_rate", DEFAULT_HEAT_UP_RATE)
            self._heat_loss_rate = last_state.attributes.get("learned_heat_loss_rate", DEFAULT_HEAT_LOSS_RATE)
            self._overshoot_temp = last_state.attributes.get("learned_overshoot", DEFAULT_OVERSHOOT)

        # Listeners
        if self._sensor_entity_id:
            self.async_on_remove(
                async_track_state_change_event(self.hass, [self._sensor_entity_id], self._async_sensor_changed)
            )
        
        if self._schedule_entity_id:
             self.async_on_remove(
                async_track_state_change_event(self.hass, [self._schedule_entity_id], self._async_control_loop_event)
             )
        
        self.async_on_remove(
            async_track_time_interval(self.hass, self._async_control_loop, timedelta(minutes=1))
        )

    # --- PROPERTIES ---
    @property
    def min_temp(self): return 5.0
    @property
    def max_temp(self): return 30.0
    @property
    def target_temperature_step(self): return 0.5
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
        return {
            "learned_heat_up_rate": round(self._heat_up_rate, 4),
            "learned_heat_loss_rate": round(self._heat_loss_rate, 4),
            "learned_overshoot": round(self._overshoot_temp, 2),
            "boiler_active": self._is_active_heating,
            "hysteresis": self._hysteresis,
            "manual_mode": self._manual_mode,
            "preheat_latch": self._preheat_latch,
            "next_fire_timestamp": self._calculate_next_fire_time(),
        }

    # --- CONTROL METHODS ---

    async def async_set_temperature(self, **kwargs):
        """User manually sets temp (Override)."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._target_temp = temp
            self._manual_mode = True  # Lock Manual Mode
            self.async_write_ha_state()
            await self._run_control_logic()

    async def async_set_hvac_mode(self, hvac_mode):
        self._hvac_mode = hvac_mode
        if hvac_mode == HVACMode.OFF:
            await self._set_boiler(False)
        self.async_write_ha_state()
        await self._run_control_logic()

    async def async_set_preset_mode(self, preset_mode):
        if preset_mode in self._attr_preset_modes:
            self._attr_preset_mode = preset_mode
            self.async_write_ha_state()

    # --- LOGIC HANDLERS ---

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
        await self._run_control_logic()

    async def _async_control_loop(self, now=None): 
        await self._run_control_logic()

    async def _run_control_logic(self):
        """The brain of the thermostat (Single Source of Truth)."""
        if self._current_temp is None or self._hvac_mode == HVACMode.OFF:
            await self._set_boiler(False)
            return

        now = dt_util.now()

        # --- 1. DETECT SCHEDULE CHANGES (Reset Flags) ---
        if self._schedule_entity_id:
            sched_state = self.hass.states.get(self._schedule_entity_id)
            current_state = sched_state.state if sched_state else STATE_OFF
            
            # If schedule flipped (ON->OFF or OFF->ON)
            if self._last_schedule_state and current_state != self._last_schedule_state:
                _LOGGER.info(f"Schedule changed to {current_state}. Resetting Auto/Manual/Latch.")
                self._manual_mode = False 
                if current_state == STATE_ON:
                    self._preheat_latch = False # Clear preheat when schedule starts
            
            self._last_schedule_state = current_state

        # --- 2. CALCULATE "AUTO" TARGET ---
        if not self._manual_mode:
            new_target = self._setback_temp
            self._attr_preset_mode = "none"

            # A. Schedule is ON
            if self._schedule_entity_id and self._last_schedule_state == STATE_ON:
                new_target = self._comfort_temp
            
            # B. Schedule is OFF (Check Preheat)
            elif self._enable_preheat and self._schedule_entity_id:
                next_start = self._get_next_schedule_start()
                
                # Check for Entry (Calculated Time) or Existence (Latch)
                should_preheat = False
                
                if self._preheat_latch:
                    should_preheat = True # Stick to it if we already started!
                
                elif next_start:
                    diff = self._comfort_temp - self._current_temp
                    if diff > 0:
                        minutes_needed = diff / self._heat_up_rate
                        minutes_needed = min(minutes_needed, self._max_preheat_time)
                        
                        # Trigger Check
                        if now >= (next_start - timedelta(minutes=minutes_needed)):
                            should_preheat = True
                            _LOGGER.info("Preheat Triggered (Latched ON)")
                            self._preheat_latch = True

                if should_preheat:
                    new_target = self._comfort_temp
                    self._attr_preset_mode = "preheat"
            
            self._target_temp = new_target

        # --- 3. BOILER CONTROL ---
        overshoot = self._overshoot_temp if self._enable_overshoot else 0.0
        off_point = self._target_temp - overshoot
        on_point = self._target_temp - self._hysteresis

        if self._is_active_heating:
            if self._current_temp >= off_point:
                _LOGGER.info(f"Target reached ({self._current_temp} >= {off_point}). Boiler OFF.")
                await self._set_boiler(False)
            elif self._last_on_time and (now.timestamp() - self._last_on_time) > self._max_on_time:
                _LOGGER.warning("Safety: Max boiler runtime exceeded. Forcing OFF.")
                await self._set_boiler(False)
        else:
            if self._current_temp <= on_point:
                 _LOGGER.info(f"Demand detected ({self._current_temp} <= {on_point}). Boiler ON.")
                 await self._set_boiler(True)

        self.async_write_ha_state()

    async def _set_boiler(self, turn_on):
        if not self._heater_entity_id: return

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
        """Debug version: Logs exactly why learning happens or fails."""
        if not self._last_on_time or not self._heat_start_temp or not self._current_temp:
            return

        now_ts = dt_util.now().timestamp()
        duration_mins = (now_ts - self._last_on_time) / 60.0
        delta_temp = self._current_temp - self._heat_start_temp
        
        _LOGGER.warning(f"DEBUG: Boiler ran for {round(duration_mins, 1)} min. Temp changed by {round(delta_temp, 2)}C.")

        if duration_mins < self._min_burn_time: 
            _LOGGER.warning(f"Learning Aborted: Burn time {round(duration_mins, 1)}m is less than minimum {self._min_burn_time}m.")
            return 
        
        if delta_temp < 0.2: 
            _LOGGER.warning(f"Learning Aborted: Temp rise {round(delta_temp, 2)}C is too small (min 0.2C).")
            return

        if delta_temp > 2.0: 
             _LOGGER.warning(f"Learning Aborted: Temp jump {round(delta_temp, 2)}C is impossibly high (Sensor Error?).")
             return

        calculated_rate = delta_temp / duration_mins
        new_rate = (self._heat_up_rate * 0.8) + (calculated_rate * 0.2)
        self._heat_up_rate = max(0.01, min(1.0, new_rate))
        _LOGGER.warning(f"LEARNING SUCCESS! New Rate: {round(self._heat_up_rate, 4)}")

    def _track_overshoot_peak(self):
        if self._current_temp > self._peak_temp_observed: 
            self._peak_temp_observed = self._current_temp
        time_since_off = dt_util.now().timestamp() - (self._last_off_time or 0)
        if time_since_off > 1800 and self._peak_tracking_start_temp:
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
        if self._is_active_heating: return dt_util.now().isoformat()
        
        if self._schedule_entity_id:
             sched_state = self.hass.states.get(self._schedule_entity_id)
             if sched_state and sched_state.state == STATE_ON:
                 return dt_util.now().isoformat()

        next_sched = self._get_next_schedule_start()
        if not next_sched: return None
        
        if not self._enable_preheat: return next_sched.isoformat()
            
        current = self._current_temp if self._current_temp is not None else self._setback_temp
        diff = self._comfort_temp - current 
        
        if diff <= 0: return next_sched.isoformat()
        
        minutes_needed = diff / self._heat_up_rate
        minutes_needed = min(minutes_needed, self._max_preheat_time)
        fire_time = next_sched - timedelta(minutes=minutes_needed)
        
        now = dt_util.now()
        if fire_time < now: return now.isoformat()

        return fire_time.isoformat()
