"""Sensors to expose internal learned values of Smart Heating."""
from homeassistant.components.sensor import SensorEntity, SensorStateClass, SensorDeviceClass
from homeassistant.const import UnitOfTemperature, UnitOfTime, STATE_ON
from homeassistant.core import callback
import homeassistant.helpers.entity_registry
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util
from datetime import datetime

from .const import DOMAIN

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the diagnostic sensors."""
    async_add_entities([
        HeatingDiagnosticSensor(config_entry, "Heat Up Rate", "learned_heat_up_rate", "°C/min"),
        HeatingDiagnosticSensor(config_entry, "Heat Loss Rate", "learned_heat_loss_rate", "°C/min"),
        HeatingDiagnosticSensor(config_entry, "Learned Overshoot", "learned_overshoot", "°C", SensorDeviceClass.TEMPERATURE),
        NextFireSensor(config_entry),
    ])

class HeatingDiagnosticSensor(SensorEntity):
    """Sensor that reads simple attributes from the main Climate entity."""

    def __init__(self, config_entry, name_suffix, attribute, unit, device_class=None):
        self._config_entry = config_entry
        self._attr_name = f"Smart Heating {name_suffix}"
        self._attr_unique_id = f"{config_entry.entry_id}_{attribute}"
        self._attribute = attribute
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._climate_entity_id = None

    async def async_added_to_hass(self):
        """Find parent climate entity and subscribe."""
        registry = homeassistant.helpers.entity_registry.async_get(self.hass)
        entries = homeassistant.helpers.entity_registry.async_entries_for_config_entry(
            registry, self._config_entry.entry_id
        )
        for entry in entries:
            if entry.domain == "climate":
                self._climate_entity_id = entry.entity_id
                break
        
        if self._climate_entity_id:
             self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._climate_entity_id], self._handle_climate_update
                )
            )

    @property
    def native_value(self):
        if not self._climate_entity_id: return None
        state = self.hass.states.get(self._climate_entity_id)
        if state and self._attribute in state.attributes:
            return state.attributes[self._attribute]
        return None

    @callback
    def _handle_climate_update(self, event):
        self.async_write_ha_state()


class NextFireSensor(SensorEntity):
    """Predicts exactly when the boiler will fire next."""

    def __init__(self, config_entry):
        self._config_entry = config_entry
        self._attr_name = "Smart Heating Next Fire Time"
        self._attr_unique_id = f"{config_entry.entry_id}_next_fire_time"
        self._attr_device_class = None 
        self._attr_icon = "mdi:clock-start"
        self._climate_entity_id = None
        
        # Determine schedule entity from config to check for "Window Active"
        self._schedule_entity_id = config_entry.options.get(
            "schedule_entity_id", config_entry.data.get("schedule_entity_id")
        )

    async def async_added_to_hass(self):
        """Link to climate entity."""
        registry = homeassistant.helpers.entity_registry.async_get(self.hass)
        entries = homeassistant.helpers.entity_registry.async_entries_for_config_entry(
            registry, self._config_entry.entry_id
        )
        for entry in entries:
            if entry.domain == "climate":
                self._climate_entity_id = entry.entity_id
                break
        
        # Track Climate Entity
        if self._climate_entity_id:
             self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._climate_entity_id], self._handle_update
                )
            )
        
        # Track Schedule Entity (to update "Now" status instantly)
        if self._schedule_entity_id:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._schedule_entity_id], self._handle_update
                )
            )

    @property
    def native_value(self):
        if not self._climate_entity_id: return None
        state = self.hass.states.get(self._climate_entity_id)
        if not state: return None

        # 1. Check for Preheating
        # If preset_mode is 'preheat', we are definitely preheating right now
        if state.attributes.get("preset_mode") == "preheat":
            return "Preheating"

        # 2. Check if we are inside the Schedule Window ("Now")
        # We check the actual schedule entity state
        if self._schedule_entity_id:
            sched_state = self.hass.states.get(self._schedule_entity_id)
            if sched_state and sched_state.state == STATE_ON:
                return "Now"

        # 3. Check for Manual Activation ("Now")
        # If boiler is burning but schedule is off/missing, it's a manual override
        if state.attributes.get("boiler_active") is True:
            return "Now"

        # 4. Future Prediction
        if "next_fire_timestamp" in state.attributes:
            ts_str = state.attributes["next_fire_timestamp"]
            if ts_str:
                next_fire = dt_util.parse_datetime(ts_str)
                if next_fire:
                    now = dt_util.now()
                    
                    # Logic: If today -> "HH:MM", Else -> "Day HH:MM"
                    if next_fire.date() == now.date():
                        return next_fire.strftime("%H:%M")
                    else:
                        # %a = Mon, Tue, Wed...
                        return next_fire.strftime("%a %H:%M")
        
        return "Unknown"

    @callback
    def _handle_update(self, event):
        """Refresh sensor state when Climate or Schedule changes."""
        self.async_write_ha_state()