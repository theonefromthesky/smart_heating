"""Sensors to expose internal learned values of Smart Heating."""
from homeassistant.components.sensor import SensorEntity, SensorStateClass, SensorDeviceClass
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the diagnostic sensors."""
    # We need to find the thermostat entity to read data from it
    # For now, we attach sensors that pull from the climate entity
    
    # NOTE: In a cleaner architecture, we'd use a DataUpdateCoordinator.
    # But for simplicity, we will just read the attributes of the climate entity
    # or attach these sensors to the same class instance.
    
    # Actually, simpler method: The Climate entity holds the data. 
    # These sensors will just represent the attributes of the main entity.
    
    async_add_entities([
        HeatingDiagnosticSensor(config_entry, "Heat Up Rate", "learned_heat_up_rate", "°C/min"),
        HeatingDiagnosticSensor(config_entry, "Overshoot", "learned_overshoot", "°C", SensorDeviceClass.TEMPERATURE),
        HeatingDiagnosticSensor(config_entry, "Heat Loss Rate", "learned_heat_loss_rate", "°C/min"),
    ])

class HeatingDiagnosticSensor(SensorEntity):
    """Sensor that reads attributes from the main Climate entity."""

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
        """Subscribe to updates."""
        # Find the climate entity ID based on the config entry
        # This is a bit of a lookup, but works reliably
        entity_registry = self.hass.helpers.entity_registry.async_get(self.hass)
        entries = homeassistant.helpers.entity_registry.async_entries_for_config_entry(
            entity_registry, self._config_entry.entry_id
        )
        
        # Find the climate entity
        for entry in entries:
            if entry.domain == "climate":
                self._climate_entity_id = entry.entity_id
                break
        
        # Listen for changes on the climate entity
        if self._climate_entity_id:
             self.async_on_remove(
                self.hass.helpers.event.async_track_state_change_event(
                    self._climate_entity_id, self._handle_climate_update
                )
            )

    @property
    def native_value(self):
        """Return the value from the climate entity attributes."""
        if not self._climate_entity_id: return None
        state = self.hass.states.get(self._climate_entity_id)
        if state and self._attribute in state.attributes:
            return state.attributes[self._attribute]
        return None

    def _handle_climate_update(self, event):
        """Update this sensor when climate updates."""
        self.async_write_ha_state()

import homeassistant.helpers.entity_registry
