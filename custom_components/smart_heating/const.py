"""Constants for the Smart Heating integration."""
from homeassistant.const import Platform

DOMAIN = "smart_heating"
PLATFORMS = [Platform.CLIMATE]

# Configuration Keys
CONF_HEATER = "heater_entity_id"
CONF_SENSOR = "sensor_entity_id"
CONF_SCHEDULE = "schedule_entity_id"

# Defaults
DEFAULT_NAME = "Central Heating"
DEFAULT_TARGET_TEMP = 20.0
DEFAULT_MIN_TEMP = 5.0
DEFAULT_MAX_TEMP = 25.0
DEFAULT_PRECISION = 0.1
DEFAULT_HYSTERESIS = 0.2

# Learning Defaults (Initial values before learning kicks in)
DEFAULT_HEAT_UP_RATE = 0.05    # °C per minute
DEFAULT_HEAT_LOSS_RATE = -0.02 # °C per minute
DEFAULT_OVERSHOOT = 0.0        # °C