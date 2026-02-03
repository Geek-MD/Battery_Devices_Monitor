"""Constants for the Battery Devices Monitor integration."""
from typing import Final

DOMAIN: Final = "battery_devices_monitor"

# Configuration keys
CONF_BATTERY_THRESHOLD: Final = "battery_threshold"

# Default values
DEFAULT_BATTERY_THRESHOLD: Final = 20

# Sensor attributes
ATTR_DEVICES_ABOVE_THRESHOLD: Final = "devices_above_threshold"
ATTR_DEVICES_BELOW_THRESHOLD: Final = "devices_below_threshold"
ATTR_TOTAL_DEVICES: Final = "total_devices"

# Sensor states
STATE_OK: Final = "OK"
STATE_PROBLEM: Final = "Problem"

# Sensor name
SENSOR_NAME: Final = "Battery Monitor Status"
