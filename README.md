[![Geek-MD - Battery Devices Monitor](https://img.shields.io/static/v1?label=Geek-MD&message=Battery%20Devices%20Monitor&color=blue&logo=github)](https://github.com/Geek-MD/Battery_Devices_Monitor)
[![Stars](https://img.shields.io/github/stars/Geek-MD/Battery_Devices_Monitor?style=social)](https://github.com/Geek-MD/Battery_Devices_Monitor)
[![Forks](https://img.shields.io/github/forks/Geek-MD/Battery_Devices_Monitor?style=social)](https://github.com/Geek-MD/Battery_Devices_Monitor)

[![GitHub Release](https://img.shields.io/github/release/Geek-MD/Battery_Devices_Monitor?include_prereleases&sort=semver&color=blue)](https://github.com/Geek-MD/Battery_Devices_Monitor/releases)
[![License](https://img.shields.io/badge/License-MIT-blue)](https://github.com/Geek-MD/Battery_Devices_Monitor/blob/main/LICENSE)
[![HACS Custom Repository](https://img.shields.io/badge/HACS-Custom%20Repository-blue)](https://hacs.xyz/)

[![Ruff + Mypy + Hassfest](https://github.com/Geek-MD/Battery_Devices_Monitor/actions/workflows/ci.yaml/badge.svg)](https://github.com/Geek-MD/Battery_Devices_Monitor/actions/workflows/ci.yaml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)

<img width="200" height="200" alt="image" src="https://github.com/Geek-MD/Battery_Devices_Monitor/blob/main/icon.png?raw=true" />

# Battery Devices Monitor
A Home Assistant custom integration that monitors all battery-powered devices and provides a single sensor showing "OK" or "Problem" status.

## Features

- 🔋 Automatically discovers all devices with battery levels
- 🎯 Smart deduplication: each device appears only once, even if it has multiple battery entities
- 📱 Uses proper device names from Home Assistant's device registry
- 📍 Area information: device names include their assigned area for easier identification
- ⚙️ Configurable battery threshold via UI
- 🚫 Exclude specific devices from monitoring
- 📊 Single sensor showing overall battery status ("OK" or "Problem")
- 📝 Detailed attributes showing all monitored devices
- 🔔 Events fired when devices go below threshold
- 🛠️ Service to get formatted list of low battery devices
- 🌐 Multi-language support (English and Spanish)

## Installation

### Manual Installation

1. Copy the `custom_components/battery_devices_monitor` directory to your Home Assistant's `custom_components` folder
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "Battery Devices Monitor"
5. Configure the battery threshold (default: 20%)

### HACS Installation

This integration can be installed through HACS:

1. Add this repository as a custom repository in HACS
2. Search for "Battery Devices Monitor" in HACS
3. Install the integration
4. Restart Home Assistant
5. Add the integration via the UI

## Configuration

The integration can be configured through the Home Assistant UI:

- **Battery Threshold**: The battery level (1-100%) below which a device is considered to have a problem. Default is 20%.
- **Excluded Devices**: Select one or more devices to exclude from monitoring. Devices are displayed with their assigned area (if any) in the format "Device Name (Area)" for easier identification. These can be configured in the integration options after initial setup.

## Usage

After installation and configuration, the integration creates a sensor named `sensor.battery_monitor_status` with:

### States
- **OK**: All monitored devices have battery levels above the threshold
- **Problem**: One or more devices have battery levels below the threshold

### Attributes
- `devices_below_threshold`: List of devices with battery below threshold. Each entry contains `name` (device name), `area` (area name or empty string), and `battery_level` (percentage)
- `devices_above_threshold`: List of devices with battery above threshold. Each entry contains `name` (device name), `area` (area name or empty string), and `battery_level` (percentage)
- `devices_without_battery_info`: List of devices with battery but whose value is unavailable. Each entry contains `name` (device name) and `area` (area name or empty string)
- `devices_without_battery_info_status`: Status showing "OK" when no devices have unavailable battery info, or "Problem" when one or more devices have unavailable battery info
- `excluded_devices`: List of excluded devices. Each entry contains `name` (device name) and `area` (area name or empty string)
- `total_monitored_devices`: Total count of monitored devices (includes devices with available battery info and devices with unavailable battery info)

**Note**: The integration uses device names from the device registry instead of battery entity names, and automatically deduplicates entries when a device has multiple battery entities. Device names and areas are provided as separate fields for easier programmatic access.

**Example attribute structure:**
```json
{
  "devices_below_threshold": [
    {"name": "Temperature Sensor", "area": "Kitchen", "battery_level": 15},
    {"name": "Remote Control", "area": "Living Room", "battery_level": 18}
  ],
  "devices_above_threshold": [
    {"name": "Motion Sensor", "area": "Bedroom", "battery_level": 85},
    {"name": "Door Sensor", "area": "Hallway", "battery_level": 92}
  ],
  "devices_without_battery_info": [
    {"name": "Leak Sensor", "area": "Bathroom"},
    {"name": "Window Sensor", "area": "Bedroom"}
  ],
  "devices_without_battery_info_status": "Problem",
  "excluded_devices": [
    {"name": "Smart Lock", "area": "Front Door"}
  ],
  "total_monitored_devices": 6
}
```

### Example Automation

```yaml
automation:
  - alias: "Notify Low Battery"
    trigger:
      - platform: state
        entity_id: sensor.battery_monitor_status
        to: "Problem"
    action:
      - service: notify.mobile_app
        data:
          title: "Low Battery Alert"
          message: >
            {% set devices = state_attr('sensor.battery_monitor_status', 'devices_below_threshold') %}
            {{ devices | length }} device(s) have low battery:
            {% for device in devices %}
            - {{ device.name }}: {{ device.battery_level }}%
            {% endfor %}

  - alias: "Notify Low Battery Event"
    trigger:
      - platform: event
        event_type: battery_devices_monitor_low_battery
    action:
      - service: notify.mobile_app
        data:
          title: "Low Battery Alert"
          message: >
            Device {{ trigger.event.data.name }} has low battery 
            ({{ trigger.event.data.battery_level }}%)

  - alias: "Notify Devices Without Battery Info"
    trigger:
      - platform: state
        entity_id: sensor.battery_monitor_status
        attribute: devices_without_battery_info_status
        to: "Problem"
    action:
      - service: notify.mobile_app
        data:
          title: "Battery Communication Issue"
          message: >
            {% set devices = state_attr('sensor.battery_monitor_status', 'devices_without_battery_info') %}
            {{ devices | length }} device(s) have unavailable battery info:
            {% for device in devices %}
            - {{ device.name }}{% if device.area %} ({{ device.area }}){% endif %}
            {% endfor %}
```

## Services

### `battery_devices_monitor.get_low_battery_devices`

Returns a formatted list of devices below the battery threshold. This service can be used in automations to get a human-readable list of low battery devices.

**Service Data:**
- `entity_id` (required): The entity ID of the battery monitor sensor (e.g., `sensor.battery_monitor_status`)

**Returns:**
A dictionary with a `result` field containing a formatted string with one device per line in the format: `name (area) - battery_level%`

**Response Variable:**
- **Name**: `result`
- **Type**: String (multi-line)
- **Description**: Formatted list with one device per line. Each line follows the format: "name (area) - battery_level%" where battery_level is an integer.
- **Usage**: Access it in your automation using `{{ response_variable_name.result }}`

**Example Service Call:**
```yaml
service: battery_devices_monitor.get_low_battery_devices
data:
  entity_id: sensor.battery_monitor_status
response_variable: low_battery_list
```

**Example Output (accessed as `low_battery_list.result`):**
```
Temperature Sensor (Kitchen) - 15%
Remote Control (Living Room) - 18%
Door Sensor - 12%
```

**Example Automation Using the Service:**
```yaml
automation:
  - alias: "Send Low Battery Report"
    trigger:
      - platform: state
        entity_id: sensor.battery_monitor_status
        to: "Problem"
    action:
      - service: battery_devices_monitor.get_low_battery_devices
        data:
          entity_id: sensor.battery_monitor_status
        response_variable: battery_report
      - service: notify.mobile_app
        data:
          title: "Low Battery Devices"
          message: "{{ battery_report.result }}"
```

**Advanced Example - Using in Scripts with Conditions:**
```yaml
script:
  check_batteries:
    sequence:
      - service: battery_devices_monitor.get_low_battery_devices
        data:
          entity_id: sensor.battery_monitor_status
        response_variable: battery_list
      - if:
          - condition: template
            value_template: "{{ battery_list.result != '' }}"
        then:
          - service: persistent_notification.create
            data:
              title: "Battery Alert"
              message: |
                The following devices need new batteries:
                {{ battery_list.result }}
```

### `battery_devices_monitor.get_devices_without_battery_info`

Returns a formatted list of devices with battery but whose value is unavailable, unknown, or invalid. This service can be used in automations to get a human-readable list of devices that may be offline or having communication issues.

**Service Data:**
- `entity_id` (required): The entity ID of the battery monitor sensor (e.g., `sensor.battery_monitor_status`)

**Returns:**
A dictionary with a `result` field containing a formatted string with one device per line in the format: `name (area)`

**Response Variable:**
- **Name**: `result`
- **Type**: String (multi-line)
- **Description**: Formatted list with one device per line. Each line follows the format: "name (area)" or just "name" if no area is assigned.
- **Usage**: Access it in your automation using `{{ response_variable_name.result }}`

**Example Service Call:**
```yaml
service: battery_devices_monitor.get_devices_without_battery_info
data:
  entity_id: sensor.battery_monitor_status
response_variable: unavailable_devices
```

**Example Output (accessed as `unavailable_devices.result`):**
```
Leak Sensor (Bathroom)
Window Sensor (Bedroom)
Door Sensor
```

**Example Automation Using the Service:**
```yaml
automation:
  - alias: "Send Unavailable Battery Devices Report"
    trigger:
      - platform: time
        at: "09:00:00"
    action:
      - service: battery_devices_monitor.get_devices_without_battery_info
        data:
          entity_id: sensor.battery_monitor_status
        response_variable: unavailable_report
      - if:
          - condition: template
            value_template: "{{ unavailable_report.result != '' }}"
        then:
          - service: notify.mobile_app
            data:
              title: "Devices with Battery Issues"
              message: |
                The following devices may be offline or have communication issues:
                {{ unavailable_report.result }}
```

**Advanced Example - Combined with Event:**
```yaml
automation:
  - alias: "Track Battery Unavailable Devices"
    trigger:
      - platform: event
        event_type: battery_devices_monitor_battery_unavailable
    action:
      # Wait a bit to let the sensor update
      - delay: "00:00:05"
      - service: battery_devices_monitor.get_devices_without_battery_info
        data:
          entity_id: sensor.battery_monitor_status
        response_variable: all_unavailable
      - service: persistent_notification.create
        data:
          title: "Battery Communication Issue"
          message: |
            Device {{ trigger.event.data.name }} is now unavailable.
            
            All devices with battery issues:
            {{ all_unavailable.result }}
```

## Events

The integration fires the following events:

### `battery_devices_monitor_low_battery`

Fired when a device's battery goes below the configured threshold. The event data includes:

- `entity_id`: The entity ID of the device
- `name`: The friendly name of the device (with area if available)
- `battery_level`: The current battery level
- `threshold`: The configured threshold that was crossed

Example event data:
```json
{
  "entity_id": "sensor.my_device_battery",
  "name": "My Device (Living Room)",
  "battery_level": 15,
  "threshold": 20
}
```

### `battery_devices_monitor_battery_unavailable`

Fired when a device's battery value becomes unavailable (unavailable, unknown, or cannot be read). This is useful for detecting devices that are offline or having communication issues. The event data includes:

- `entity_id`: The entity ID of the device
- `name`: The friendly name of the device (with area if available)

Example event data:
```json
{
  "entity_id": "sensor.my_device_battery",
  "name": "My Device (Living Room)"
}
```

Example automation using the unavailable battery event:
```yaml
automation:
  - alias: "Notify Battery Unavailable"
    trigger:
      - platform: event
        event_type: battery_devices_monitor_battery_unavailable
    action:
      - service: notify.mobile_app
        data:
          title: "Battery Status Unavailable"
          message: >
            Device {{ trigger.event.data.name }} battery status is unavailable.
            The device might be offline or having communication issues.
```

## Development

This integration monitors all entities in Home Assistant that have a `battery_level` attribute or have "battery" in their entity ID. It uses the Home Assistant device and entity registries to properly associate battery entities with their parent devices, ensuring each device appears only once in the list. The integration automatically updates when any device battery level changes.

### Code Quality

This project maintains high code quality standards:

- ✅ **hassfest**: Home Assistant manifest validation
- ✅ **ruff**: Python linting and formatting
- ✅ **mypy**: Static type checking

All checks run automatically via GitHub Actions on every commit.

### Contributing

Contributions are welcome! Please ensure your code passes all CI checks before submitting a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/Geek-MD/Battery_Devices_Monitor/issues).

---

<div align="center">
  
💻 **Proudly developed with GitHub Copilot** 🚀

</div>

