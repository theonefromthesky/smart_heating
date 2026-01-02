from homeassistant.const import Platform

DOMAIN = "smart_heating"
PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]

CONF_HEATER = "heater_entity_id"
CONF_SENSOR = "sensor_entity_id"
CONF_SCHEDULE = "schedule_entity_id"

CONF_ENABLE_PREHEAT = "enable_preheat"
CONF_ENABLE_OVERSHOOT = "enable_overshoot"
CONF_ENABLE_LEARNING = "enable_learning"

CONF_MAX_ON_TIME = "max_on_time"
CONF_MAX_PREHEAT_TIME = "max_preheat_time"
CONF_HYSTERESIS = "hysteresis"
CONF_MIN_BURN_TIME = "min_burn_time"

CONF_COMFORT_TEMP = "comfort_temp"
CONF_SETBACK_TEMP = "setback_temp"

DEFAULT_NAME = "Central Heating"
DEFAULT_TARGET_TEMP = 20.0
DEFAULT_HEAT_UP_RATE = 0.03
DEFAULT_HEAT_LOSS_RATE = -0.02
DEFAULT_OVERSHOOT = 0.0

DEFAULT_HYSTERESIS = 0.2
DEFAULT_MAX_ON_TIME = 300
DEFAULT_MAX_PREHEAT_TIME = 180
DEFAULT_MIN_BURN_TIME = 10
DEFAULT_COMFORT_TEMP = 20.0
DEFAULT_SETBACK_TEMP = 15.0
