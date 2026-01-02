from homeassistant.components.sensor import SensorEntity, SensorStateClass, SensorDeviceClass
from homeassistant.const import UnitOfTemperature, UnitOfTime
import homeassistant.helpers.entity_registry
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util  # <--- NEW IMPORT
from datetime import datetime

from .const import DOMAIN

async def async_setup_entry(hass, config_entry, async_add_entities):
    async_add_entities([
        HeatingDiagnosticSensor(config_entry, "Heat Up Rate", "learned_heat_up_rate", "°C/min"),
        HeatingDiagnosticSensor(config_entry, "Heat Loss Rate", "learned_heat_loss_rate", "°C/min"),
        HeatingDiagnosticSensor(config_entry, "Learned Overshoot", "learned_overshoot", "°C", SensorDeviceClass.TEMPERATURE),
        NextFireSensor(config_entry),
    ])

class HeatingDiagnosticSensor(SensorEntity):
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

    def _handle_climate_update(self, event):
        self.async_write_ha_state()

class NextFireSensor(SensorEntity):
    def __init__(self, config_entry):
        self._config_entry = config_entry
        self._attr_name = "Smart Heating Next Fire Time"
        self._attr_unique_id = f"{config_entry.entry_id}_next_fire_time"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._climate_entity_id = None

    async def async_added_to_hass(self):
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
        
        # LOGIC FIX: Convert string back to datetime object
        if state and "next_fire_timestamp" in state.attributes:
            ts_str = state.attributes["next_fire_timestamp"]
            if ts_str:
                return dt_util.parse_datetime(ts_str)
        return None

    def _handle_climate_update(self, event):
        self.async_write_ha_state()
