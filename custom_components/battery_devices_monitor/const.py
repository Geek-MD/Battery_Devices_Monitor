"""Constants for the Battery Devices Monitor integration."""

from typing import Final

DOMAIN: Final = "battery_devices_monitor"

# Persistent per-device battery tracking
STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = f"{DOMAIN}.battery_tracking"
MAX_BATTERY_TYPE_LENGTH: Final = 100
UNKNOWN_BATTERY_TYPE: Final = "unknown"
BATTERY_TYPE_OPTIONS: Final[tuple[str, ...]] = (
    UNKNOWN_BATTERY_TYPE,
    "AAA",
    "AA",
    "AAAA",
    "9V",
    "A23",
    "CR123A",
    "CR2",
    "CR2032",
    "CR2025",
    "CR2016",
    "LR44",
    "Li-ion",
    "Rechargeable",
)

# Attributes commonly published by device integrations for battery chemistry/size.
BATTERY_TYPE_ATTRS: Final[tuple[str, ...]] = (
    "battery_type",
    "battery_size",
    "battery_model",
    "battery_format",
)
BATTERY_NUMBER_ATTRS: Final[tuple[str, ...]] = (
    "battery_number",
    "battery_count",
    "battery_quantity",
    "number_of_batteries",
)
BATTERY_NUMBER_OPTIONS: Final[tuple[str, ...]] = (
    UNKNOWN_BATTERY_TYPE,
    *(str(number) for number in range(1, 17)),
)

# Configuration keys
CONF_BATTERY_THRESHOLD: Final = "battery_threshold"
CONF_EXCLUDED_DEVICES: Final = "excluded_devices"

# Default values
DEFAULT_BATTERY_THRESHOLD: Final = 20
DEFAULT_EXCLUDED_DEVICES: Final[list[str]] = []

# Device class value for battery sensors (language-independent HA enum)
BATTERY_DEVICE_CLASS: Final = "battery"

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
ATTR_DEVICES_WITHOUT_BATTERY_INFO_STATUS: Final = "devices_without_battery_info_status"

# Sensor states
STATE_OK: Final = "OK"
STATE_WARNING: Final = "Warning"
STATE_PROBLEM: Final = "Problem"

# Sensor name
SENSOR_NAME: Final = "Battery Monitor Status"

# Events
EVENT_BATTERY_LOW: Final = "battery_devices_monitor_low_battery"
EVENT_BATTERY_UNAVAILABLE: Final = "battery_devices_monitor_battery_unavailable"
EVENT_ZIGBEE_BATTERY_UNAVAILABLE: Final = (
    "battery_devices_monitor_zigbee_battery_unavailable"
)

# Actions
SERVICE_GET_LOW_BATTERY_DEVICES: Final = "get_low_battery_devices"
SERVICE_GET_DEVICES_WITHOUT_BATTERY_INFO: Final = "get_devices_without_battery_info"
SERVICE_RESCAN_BATTERY_DEVICES: Final = "rescan_battery_devices"

# Zigbee integration domains in Home Assistant
ZIGBEE_INTEGRATION_DOMAINS: Final[set[str]] = {"zha", "deconz", "zigbee2mqtt"}

# Entity domains to exclude from battery monitoring
# These entities should not be monitored even if they have "battery" in their entity_id
EXCLUDED_ENTITY_DOMAINS: Final[list[str]] = [
    "automation",  # Automations
    "scene",  # Scenes
    "script",  # Scripts
]
