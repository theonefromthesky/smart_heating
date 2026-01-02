"""Constants for the Smart Heating integration."""
from homeassistant.const import Platform

DOMAIN = "smart_heating"
PLATFORMS = [Platform.CLIMATE]

# Configuration Keys (Setup)
CONF_HEATER = "heater_entity_id"
CONF_SENSOR = "sensor_entity_id"
CONF_SCHEDULE = "schedule_entity_id"

# Option Keys (Settings)
CONF_ENABLE_PREHEAT = "enable_preheat"
CONF_ENABLE_OVERSHOOT = "enable_overshoot"
CONF_ENABLE_LEARNING = "enable_learning"

# Defaults
DEFAULT_NAME = "Central Heating"
DEFAULT_TARGET_TEMP = 20.0
DEFAULT_HEAT_UP_RATE = 0.03
DEFAULT_HEAT_LOSS_RATE = -0.02
DEFAULT_OVERSHOOT = 0.0
DEFAULT_HYSTERESIS = 0.2
