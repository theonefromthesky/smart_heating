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

# Default Values
DEFAULT_HEAT_UP_RATE = 0.1
DEFAULT_HEAT_LOSS_RATE = 0.1
DEFAULT_OVERSHOOT = 0.0

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
        
        # --- NEW: Manual Mode Logic Flags ---
        self._manual_mode = False        # True if user touched the dial
        self._last_schedule_state = None # To track ON/OFF transitions
        
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
        """Read settings safely: Options -> Data -> Default."""
        options = self._config_entry.options
        data = self._config_entry.data

        def get_val(key, default=None):
            return options.get(key, data.get(key, default))

        # --- Entities ---
        self._heater_entity_id = get_val("heater_entity_id")
        self._sensor_entity_id = get_val("sensor_entity_id")
        self._schedule_entity_id = get_val("schedule_entity_id")
        
        # --- Toggles ---
        self._enable_preheat = get_val("enable_preheat", False)
        self._enable_overshoot = get_val("enable_overshoot", False)
        self._enable_learning = get_val("enable_learning", False)
        
        # --- Numeric Settings ---
        self._hysteresis = get_val("hysteresis", 0.5)
        self._max_on_time = get_val("max_on_time", 60) * 60 
        self._max_preheat_time = get_val("max_preheat_time", 60)
        self._min_burn_time = get_val("min_burn_time", 10)
        
        # --- Temperatures ---
        self._comfort_temp = get_val("comfort_temp", 20.0)
        self._setback_temp = get_val("setback_temp", 16.0)

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
            "next_fire_timestamp": self._calculate_next_fire_time(),
        }

    # --- CONTROL METHODS ---

    async def async_set_temperature(self, **kwargs):
        """User manually sets temp (Override)."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._target_temp = temp
            self._manual_mode = True  # <--- LOCK MANUAL MODE
            self.async_write_ha_state()
            await self._run_control_logic()

    async def async_set_hvac_mode(self, hvac_mode):
        self._hvac_mode = hvac_mode
        if hvac_mode == HVACMode.OFF:
            await self._set_boiler(False)
        self.async_write_ha_state()
        await self._run_control_logic()

    async def async_set_preset_mode(self, preset_mode):
        """Handle manual preset mode changes."""
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
        """Triggered ONLY when schedule changes state."""
        # Logic is handled inside _run_control_logic to ensure single truth
        await self._run_control_logic()

    async def _async_control_loop(self, now=None): 
        await self._run_control_logic()

    async def _run_control_logic(self):
        """The brain of the thermostat (Single Source of Truth)."""
        if self._current_temp is None or self._hvac_mode == HVACMode.OFF:
            await self._set_boiler(False)
            return

        now = dt_util.now()

        # --- 1. DETECT SCHEDULE CHANGES (Reset Manual Mode) ---
        if self._schedule_entity_id:
            sched_state = self.hass.states.get(self._schedule_entity_id)
            current_state = sched_state.state if sched_state else STATE_OFF
            
            # If schedule flipped (ON->OFF or OFF->ON), release Manual Mode
            if self._last_schedule_state and current_state != self._last_schedule_state:
                _LOGGER.info(f"Schedule changed to {current_state}. Resetting to Auto Mode.")
                self._manual_mode = False 
            
            self._last_schedule_state = current_state

        # --- 2. CALCULATE "AUTO" TARGET (Only if NOT in Manual Mode) ---
        if not self._manual_mode:
            # Default to Setback (Economy)
            new_target = self._setback_temp
            self._attr_preset_mode = "none"

            # A. Schedule is ON
            if self._schedule_entity_id and self._last_schedule_state == STATE_ON:
                new_target = self._comfort_temp
            
            # B. Schedule is OFF (Check Preheat)
            elif self._enable_preheat and self._schedule_entity_id:
                next_start = self._get_next_schedule_start()
                if next_start:
                    diff = self._comfort_temp - self._current_temp
                    if diff > 0:
                        minutes_needed = diff / self._heat_up_rate
                        minutes_needed = min(minutes_needed, self._max_preheat_time)
                        
                        # If we are within the preheat window, raise the target NOW
                        if now >= (next_start - timedelta(minutes=minutes_needed)):
                            new_target = self._comfort_temp
                            self._attr_preset_mode = "preheat"
            
            # Commit the calculated target
            self._target_temp = new_target

        # --- 3. BOILER CONTROL (The Reaction) ---
        # The boiler blindly follows self._target_temp
        
        overshoot = self._overshoot_temp if self._enable_overshoot else 0.0
        off_point = self._target_temp - overshoot
        on_point = self._target_temp - self._hysteresis

        if self._is_active_heating:
            # Turn OFF if we hit the target
            if self._current_temp >= off_point:
                _LOGGER.info(f"Target reached ({self._current_temp} >= {off_point}). Boiler OFF.")
                await self._set_boiler(False)
            
            # Safety Check
            elif self._last_on_time and (now.timestamp() - self._last_on_time) > self._max_on_time:
                _LOGGER.warning("Safety: Max boiler runtime exceeded. Forcing OFF.")
                await self._set_boiler(False)
        else:
            # Turn ON if we drop below hysteresis
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
        if not self._last_on_time or not self._heat_start_temp or not self._current_temp: return
        now_ts = dt_util.now().timestamp()
        duration_mins = (now_ts - self._last_on_time) / 60.0
        if duration_mins < self._min_burn_time: return 
        
        delta_temp = self._current_temp - self._heat_start_temp
        
        # FIX: Ignore if the jump is impossibly high (Sensor Error)
        if delta_temp > 1.5: 
             _LOGGER.warning("Ignoring learning data: Temperature jumped > 1.5C (Possible sensor error).")
             return
        if delta_temp < 0.2: return

        calculated_rate = delta_temp / duration_mins
        new_rate = (self._heat_up_rate * 0.8) + (calculated_rate * 0.2)
        self._heat_up_rate = max(0.01, min(1.0, new_rate))

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
        """Estimate when the boiler will next fire."""
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
