"""The Core Logic for Smart Heating."""
import logging
import math
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode, HVACAction
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_UNIQUE_ID,
    UnitOfTemperature,
    STATE_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
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
    DEFAULT_HEAT_UP_RATE,
    DEFAULT_HEAT_LOSS_RATE,
    DEFAULT_OVERSHOOT,
    DEFAULT_HYSTERESIS,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smart Heating platform via Config Flow."""
    
    # Get data from the config entry
    config = config_entry.data
    name = config.get("name", "Smart Heating")
    unique_id = config_entry.entry_id

    # Pass the full config_entry to the entity so it can read options
    async_add_entities([
        SmartThermostat(hass, name, unique_id, config_entry)
    ])

class SmartThermostat(ClimateEntity, RestoreEntity):
    """Representation of a Smart Learning Thermostat."""

    def __init__(self, hass, name, unique_id, config_entry):
        self.hass = hass
        self._config_entry = config_entry
        self._attr_name = name
        self._attr_unique_id = unique_id
        
        # Load Entities from Options (or Data if options not set yet)
        self._heater_entity_id = config_entry.options.get(CONF_HEATER, config_entry.data.get(CONF_HEATER))
        self._sensor_entity_id = config_entry.options.get(CONF_SENSOR, config_entry.data.get(CONF_SENSOR))
        self._schedule_entity_id = config_entry.options.get(CONF_SCHEDULE, config_entry.data.get(CONF_SCHEDULE))
        
        # Load Logic Toggles (Default to True)
        self._enable_preheat = config_entry.options.get(CONF_ENABLE_PREHEAT, True)
        self._enable_overshoot = config_entry.options.get(CONF_ENABLE_OVERSHOOT, True)
        self._enable_learning = config_entry.options.get(CONF_ENABLE_LEARNING, True)

        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        self._attr_preset_modes = ["none", "preheat"]
        self._attr_preset_mode = "none"

        # Operational State
        self._hvac_mode = HVACMode.OFF
        self._target_temp = 20.0
        self._current_temp = None
        self._is_active_heating = False # Actual boiler state
        
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

        # Watchdogs
        self._max_on_time = 300 * 60  # 5 hours safety
        self._min_burn_time = 10 * 60 # Minimum 10 mins to be considered a valid learn cycle

    async def async_added_to_hass(self):
        """Run when entity is added."""
        await super().async_added_to_hass()
        
        # 1. Restore State
        last_state = await self.async_get_last_state()
        if last_state:
            self._hvac_mode = last_state.state if last_state.state in self._attr_hvac_modes else HVACMode.OFF
            self._target_temp = last_state.attributes.get("target_temp", 20.0)
            
            # Restore learned values
            self._heat_up_rate = last_state.attributes.get("learned_heat_up_rate", DEFAULT_HEAT_UP_RATE)
            self._heat_loss_rate = last_state.attributes.get("learned_heat_loss_rate", DEFAULT_HEAT_LOSS_RATE)
            self._overshoot_temp = last_state.attributes.get("learned_overshoot", DEFAULT_OVERSHOOT)

        # 2. Subscribe to Sensor Updates
        async_track_state_change_event(
            self.hass, [self._sensor_entity_id], self._async_sensor_changed
        )
        
        # 3. Subscribe to Schedule Updates
        if self._schedule_entity_id:
             async_track_state_change_event(
                self.hass, [self._schedule_entity_id], self._async_control_loop_event
            )

        # 4. Subscribe to Config Option Updates (Live Settings Change)
        self.async_on_remove(
            self._config_entry.add_update_listener(self.async_update_options)
        )

        # 5. Start Control Loop (Every 1 minute)
        async_track_time_interval(
            self.hass, self._async_control_loop, timedelta(minutes=1)
        )

    async def async_update_options(self, hass, entry):
        """Handle options update from UI Configure menu."""
        _LOGGER.info("Reloading Smart Heating configuration options")
        self._enable_preheat = entry.options.get(CONF_ENABLE_PREHEAT, True)
        self._enable_overshoot = entry.options.get(CONF_ENABLE_OVERSHOOT, True)
        self._enable_learning = entry.options.get(CONF_ENABLE_LEARNING, True)
        
        # Update entities if changed
        self._heater_entity_id = entry.options.get(CONF_HEATER, self._heater_entity_id)
        self._sensor_entity_id = entry.options.get(CONF_SENSOR, self._sensor_entity_id)
        self._schedule_entity_id = entry.options.get(CONF_SCHEDULE, self._schedule_entity_id)
        
        await self._run_control_logic()

    @property
    def hvac_action(self):
        """Return the current running action."""
        if self._hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if self._is_active_heating:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def current_temperature(self):
        return self._current_temp

    @property
    def target_temperature(self):
        return self._target_temp
        
    @property
    def hvac_mode(self):
        return self._hvac_mode

    @property
    def extra_state_attributes(self):
        """Expose learned values and diagnostics."""
        return {
            "learned_heat_up_rate": round(self._heat_up_rate, 4),
            "learned_heat_loss_rate": round(self._heat_loss_rate, 4),
            "learned_overshoot": round(self._overshoot_temp, 2),
            "boiler_active": self._is_active_heating,
            "time_to_target_mins": self._calculate_time_to_target(),
            "next_schedule_on": self._get_next_schedule_start_str(),
            "preheat_enabled": self._enable_preheat,
            "overshoot_enabled": self._enable_overshoot,
            "learning_enabled": self._enable_learning
        }

    async def async_set_temperature(self, **kwargs):
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
        """Handle temperature sensor changes."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        try:
            self._current_temp = float(new_state.state)
            
            # Post-cycle Overshoot Tracking (Only if learning is enabled)
            if self._enable_learning and not self._is_active_heating and self._peak_tracking_start_temp is not None:
                self._track_overshoot_peak()
                
            await self._run_control_logic()
        except ValueError:
            pass

    @callback
    async def _async_control_loop_event(self, event):
        """Triggered by schedule change."""
        await self._run_control_logic()

    async def _async_control_loop(self, now=None):
        """Timed heartbeat."""
        await self._run_control_logic()

    async def _run_control_logic(self):
        """The Main Brain."""
        if self._current_temp is None or self._hvac_mode == HVACMode.OFF:
            await self._set_boiler(False)
            return

        now = dt_util.now()
        target = self._target_temp
        
        # 1. PREHEAT LOGIC
        # If enabled and schedule exists, check if we need to start early
        preheat_active = False
        if self._enable_preheat and self._schedule_entity_id:
            sched_state = self.hass.states.get(self._schedule_entity_id)
            if sched_state and sched_state.state == STATE_OFF:
                # We are currently OFF schedule, check if we need to pre-heat
                next_start = self._get_next_schedule_start()
                if next_start:
                    # Look up comfort temp (assuming 20C or configurable later)
                    comfort_target = 20.0 
                    
                    diff = comfort_target - self._current_temp
                    if diff > 0:
                        minutes_needed = diff / self._heat_up_rate
                        # Cap max preheat time (e.g. 3 hours)
                        minutes_needed = min(minutes_needed, 180)
                        
                        start_time = next_start - timedelta(minutes=minutes_needed)
                        
                        if now >= start_time:
                            target = comfort_target
                            preheat_active = True
                            self._attr_preset_mode = "preheat"

        if not preheat_active:
             self._attr_preset_mode = "none"

        # 2. HYSTERESIS & OVERSHOOT CONTROL
        # If overshoot compensation is enabled, lower the cut-off point
        overshoot_adj = self._overshoot_temp if self._enable_overshoot else 0.0
        effective_cutoff = target - overshoot_adj
        
        if self._is_active_heating:
            # We are ON. Should we turn OFF?
            # Turn off if we hit effective target OR safety limit
            if self._current_temp >= effective_cutoff:
                _LOGGER.info(f"Target {target}C (adj: {effective_cutoff}C) reached. Turning OFF.")
                await self._set_boiler(False)
            elif (now.timestamp() - self._last_on_time) > self._max_on_time:
                 _LOGGER.warning("Watchdog: Boiler ON too long. Force OFF.")
                 await self._set_boiler(False)
        else:
            # We are OFF. Should we turn ON?
            # Standard hysteresis (e.g., target - 0.2)
            on_point = target - DEFAULT_HYSTERESIS
            if self._current_temp <= on_point:
                 _LOGGER.info(f"Temp {self._current_temp}C below {on_point}C. Turning ON.")
                 await self._set_boiler(True)

        self.async_write_ha_state()

    async def _set_boiler(self, turn_on):
        """Physical Switch Control & Learning Triggers."""
        if turn_on and not self._is_active_heating:
            # Turning ON
            self._is_active_heating = True
            self._last_on_time = dt_util.now().timestamp()
            self._heat_start_temp = self._current_temp
            self._peak_tracking_start_temp = None # Reset overshoot tracker
            
            # Fire command
            await self.hass.services.async_call("switch", "turn_on", {"entity_id": self._heater_entity_id})
            
        elif not turn_on and self._is_active_heating:
            # Turning OFF
            self._is_active_heating = False
            self._last_off_time = dt_util.now().timestamp()
            
            # Fire command
            await self.hass.services.async_call("switch", "turn_off", {"entity_id": self._heater_entity_id})
            
            # Trigger Learning (if enabled)
            if self._enable_learning:
                self._learn_heat_up_rate()
                # Start Overshoot Tracking
                self._peak_tracking_start_temp = self._current_temp
                self._peak_temp_observed = self._current_temp

    def _learn_heat_up_rate(self):
        """Update heat_up_rate based on the cycle just finished."""
        if not self._last_on_time or not self._heat_start_temp:
            return

        now_ts = dt_util.now().timestamp()
        duration_mins = (now_ts - self._last_on_time) / 60.0
        
        # Filter: Ignore short cycles or tiny temp changes
        if duration_mins < 10: return
        delta_temp = self._current_temp - self._heat_start_temp
        if delta_temp < 0.2: return

        calculated_rate = delta_temp / duration_mins
        
        # Weighted Average: 80% old, 20% new
        new_rate = (self._heat_up_rate * 0.8) + (calculated_rate * 0.2)
        
        # Clamp values (min 0.01, max 1.0)
        self._heat_up_rate = max(0.01, min(1.0, new_rate))
        _LOGGER.info(f"Learned Heat Up Rate: {self._heat_up_rate}")

    def _track_overshoot_peak(self):
        """Called while OFF to find how high temp goes after boiler stop."""
        if self._current_temp > self._peak_temp_observed:
            self._peak_temp_observed = self._current_temp
        
        # Check if we have peaked and started falling (or 30 mins passed)
        time_since_off = dt_util.now().timestamp() - self._last_off_time
        
        if time_since_off > 1800: # 30 mins post-off
            # Calculate Overshoot
            overshoot = self._peak_temp_observed - self._peak_tracking_start_temp
            if overshoot > 0:
                # Update learned overshoot (80/20 split)
                new_overshoot = (self._overshoot_temp * 0.8) + (overshoot * 0.2)
                self._overshoot_temp = max(0.0, min(1.0, new_overshoot))
                _LOGGER.info(f"Learned Overshoot: {self._overshoot_temp}")
            
            # Stop tracking
            self._peak_tracking_start_temp = None

    # --- Helpers ---
    def _calculate_time_to_target(self):
        if self._current_temp is None or self._heat_up_rate <= 0:
            return 0
        diff = self._target_temp - self._current_temp
        if diff <= 0: return 0
        return round(diff / self._heat_up_rate, 1)

    def _get_next_schedule_start(self):
        """Retrieve next 'on' event from schedule entity."""
        if not self._schedule_entity_id: return None
        
        state = self.hass.states.get(self._schedule_entity_id)
        if not state: return None
        
        next_event = state.attributes.get("next_event")
        if next_event:
            return dt_util.parse_datetime(str(next_event))
        return None

    def _get_next_schedule_start_str(self):
        ns = self._get_next_schedule_start()
        return ns.isoformat() if ns else "None"
