"""Constants for the Battery Devices Monitor integration."""

from typing import Final

DOMAIN: Final = "battery_devices_monitor"

# Configuration keys
CONF_BATTERY_THRESHOLD: Final = "battery_threshold"
CONF_EXCLUDED_DEVICES: Final = "excluded_devices"

# Default values
DEFAULT_BATTERY_THRESHOLD: Final = 20
DEFAULT_EXCLUDED_DEVICES: Final[list[str]] = []

# Battery attribute names to check (in order of preference)
BATTERY_ATTRS: Final[list[str]] = [
    "battery_level",  # Home Assistant standard
    "battery",  # Common in Zigbee devices
    "Battery",  # Some integrations use capitalized
]

# Sensor attributes
ATTR_DEVICES_ABOVE_THRESHOLD: Final = "devices_above_threshold"
ATTR_DEVICES_BELOW_THRESHOLD: Final = "devices_below_threshold"
ATTR_TOTAL_MONITORED_DEVICES: Final = "total_monitored_devices"
ATTR_EXCLUDED_DEVICES: Final = "excluded_devices"
ATTR_DEVICES_WITHOUT_BATTERY_INFO: Final = "devices_without_battery_info"

# Sensor states
STATE_OK: Final = "OK"
STATE_PROBLEM: Final = "Problem"

# Sensor name
SENSOR_NAME: Final = "Battery Monitor Status"

# Events
EVENT_BATTERY_LOW: Final = "battery_devices_monitor_low_battery"
EVENT_BATTERY_UNAVAILABLE: Final = "battery_devices_monitor_battery_unavailable"
