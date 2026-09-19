[![Geek-MD - Battery Devices Monitor](https://img.shields.io/static/v1?label=Geek-MD&message=Battery%20Devices%20Monitor&color=blue&logo=github)](https://github.com/Geek-MD/Battery_Devices_Monitor)
[![Stars](https://img.shields.io/github/stars/Geek-MD/Battery_Devices_Monitor?style=social)](https://github.com/Geek-MD/Battery_Devices_Monitor)
[![Forks](https://img.shields.io/github/forks/Geek-MD/Battery_Devices_Monitor?style=social)](https://github.com/Geek-MD/Battery_Devices_Monitor)

[![GitHub Release](https://img.shields.io/github/release/Geek-MD/Battery_Devices_Monitor?include_prereleases&sort=semver&color=blue)](https://github.com/Geek-MD/Battery_Devices_Monitor/releases)
[![License](https://img.shields.io/badge/License-MIT-blue)](https://github.com/Geek-MD/Battery_Devices_Monitor/blob/main/LICENSE)
[![HACS Custom Repository](https://img.shields.io/badge/HACS-Custom%20Repository-blue)](https://hacs.xyz/)

[![Ruff + Mypy + Hassfest](https://github.com/Geek-MD/Battery_Devices_Monitor/actions/workflows/ci.yaml/badge.svg)](https://github.com/Geek-MD/Battery_Devices_Monitor/actions/workflows/ci.yaml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)

<img width="200" height="200" alt="image" src="https://github.com/Geek-MD/Battery_Devices_Monitor/blob/main/custom_components/battery_devices_monitor/brand/logo.png?raw=true" />

# Battery Devices Monitor
A Home Assistant custom integration that monitors battery-powered devices, provides an overall "OK", "Warning", or "Problem" status, and tracks the lifetime and type of each device's battery.

## Features

- 🔋 Automatically discovers all battery-powered devices using a reliable, language-independent hybrid strategy: `device_class: battery` (primary), well-known battery attributes (fallback 1), and entity-ID heuristic (fallback 2)
- 🎯 Physical-device deduplication within one integration and across integrations such as August/Legrand or Ring/MQTT
- ✅ Percentage-first source selection: a `%` battery sensor is preferred over `battery_low`, status, voltage, and legacy heuristic entities
- 📱 Uses proper device names from Home Assistant's device registry
- 📍 Area information: device names include their assigned area for easier identification
- ⚙️ Configurable battery threshold via UI
- 🚫 Exclude specific devices from monitoring
- 📊 Overall sensor showing battery status ("OK", "Warning", or "Problem")
- 📝 Detailed attributes showing all monitored devices
- 🔔 Events fired when devices go below threshold
- 🛠️ Services to get formatted lists of low battery / unavailable devices and to force a rescan
- 🔄 On-demand rescan service to immediately re-discover battery entities after a device is reconfigured
- 🔘 **Rescan button** on the device control page: a one-click button in the *Configuration* subsection that triggers an immediate rescan without leaving the UI
- 📅 **Last battery change** timestamp for every deduplicated physical device
- ♻️ **Battery changed button** that records the current replacement date and time
- 🔽 **Battery type and quantity detection**: reads common device metadata automatically and provides dropdowns for the battery format and the required number of batteries
- 💾 Battery lifetime and type metadata persist across Home Assistant restarts and battery-source changes
- 🌐 Multi-language support (English, Spanish, French, Portuguese, and German)

## Installation

Requires Home Assistant 2024.4.0 or newer.

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

After installation and configuration, the integration creates the overall sensor `sensor.battery_monitor_status` (kept stable for both upgrades and clean installations) plus the per-device tracking entities described below.

### States
- **OK**: All monitored devices have battery levels at or above the threshold and all have available battery info
- **Warning**: No devices have battery below threshold, but one or more devices have unavailable battery info
- **Problem**: One or more devices have battery levels below the threshold (battery < threshold)

### Attributes
- `devices_below_threshold`: List of devices with battery **below** threshold (battery < threshold). Each entry contains `name`, `area`, and `battery_level`
- `devices_above_threshold`: List of devices with battery **at or above** threshold (battery >= threshold). Each entry contains `name`, `area`, and `battery_level`
- `devices_without_battery_info`: List of devices with battery but whose value is unavailable. Each entry contains `name`, `area`, and `battery_level` (`null` when unavailable)
- `devices_without_battery_info_status`: Status showing "OK" when no devices have unavailable battery info, or "Warning" when one or more devices have unavailable battery info
- `excluded_devices`: List of excluded devices. Each entry contains `name` (device name) and `area` (area name or empty string)
- `total_monitored_devices`: Total count of monitored devices (includes devices with available battery info and devices with unavailable battery info)

### Deduplication and source priority

The integration first groups entities that share a Home Assistant `device_id`. It then detects the same physical device exposed by different integrations using matching normalized hardware connections/identifiers. As a conservative fallback, devices from distinct integrations are grouped when their device name and assigned area match exactly and the match is unambiguous.

Within each physical-device group, the selected source order is:

1. A `sensor` with `device_class: battery` and unit `%`.
2. Another valid `device_class: battery` percentage.
3. A valid percentage from a known battery attribute.
4. A valid legacy battery entity-ID heuristic.
5. A binary `battery_low`/status entity only when no percentage exists; it is listed as unavailable because it cannot be compared with the configured threshold.

All percentages must be finite and between 0 and 100. If equally reliable percentage sources disagree, the lowest value is used so that a low battery is not hidden. Source entities and integrations are included in downloaded diagnostics, while the public sensor attributes continue to show one entry per physical device.

### Battery lifetime and type tracking

For every deduplicated physical device, Battery Devices Monitor attaches its tracking entities directly to the corresponding Home Assistant device (or uses a fallback tracking device when the source has no registry device):

- **Last battery change** (`sensor`): date and time when the current battery was first tracked or its replacement was last recorded.
- **Battery changed** (`button`): press this after physically replacing the battery. The sensor immediately records the current date and time.
- **Battery type** (`select`): a dropdown of common formats. The integration first imports a value exposed through `battery_type`, `battery_size`, `battery_model`, or `battery_format` metadata (including dedicated type/size/model entities); otherwise the user can select it manually.
- **Battery number** (`select`): the number of batteries required by the device, from 1 to 16. The integration detects `battery_number`, `battery_count`, `battery_quantity`, or `number_of_batteries` metadata and dedicated entities; otherwise the user can choose it manually.

The replacement timestamp, battery type, and known source aliases are stored persistently by Home Assistant. They survive restarts and remain linked when a device changes its selected battery entity or is deduplicated through another integration. Tracking entities are created for every discovered battery device, including devices excluded from threshold alerts.

The initial timestamp is recorded when version 2.1.0 or later first discovers a device; the integration cannot infer when an already-installed battery was physically inserted. Press **Battery changed** after installing a fresh battery to establish an accurate date.

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
    {"name": "Leak Sensor", "area": "Bathroom", "battery_level": null},
    {"name": "Window Sensor", "area": "Bedroom", "battery_level": null}
  ],
  "devices_without_battery_info_status": "Warning",
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
        to: "Warning"
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

### `battery_devices_monitor.rescan_battery_devices`

Forces an immediate rescan of all battery entities. This is useful after reconfiguring a device whose battery entity ID has changed, causing the sensor to remain in "Warning" state. Instead of waiting for the next automatic update, calling this service triggers a fresh discovery right away.

**Service Data:** None required.

**Example Service Call:**
```yaml
service: battery_devices_monitor.rescan_battery_devices
```

**Example Automation — rescan after a device is reconfigured:**
```yaml
automation:
  - alias: "Rescan Battery Devices After Config Change"
    trigger:
      - platform: state
        entity_id: sensor.battery_monitor_status
        to: "Warning"
        for: "00:01:00"
    action:
      - service: battery_devices_monitor.rescan_battery_devices
```

**Example Script — manual rescan button:**
```yaml
script:
  force_battery_rescan:
    alias: "Force Battery Rescan"
    sequence:
      - service: battery_devices_monitor.rescan_battery_devices
```

## Events

The integration fires the following events:

### `battery_devices_monitor_low_battery`

Fired when a device's battery goes below the configured threshold. The event data includes:

- `entity_id`: The entity ID of the device
- `id` / `device_id`: Home Assistant device ID (or entity_id fallback)
- `name`: The friendly name of the device (with area if available)
- `battery_level`: The current battery level
- `threshold`: The configured threshold that was crossed

Example event data:
```json
{
  "id": "abc123",
  "device_id": "abc123",
  "entity_id": "sensor.my_device_battery",
  "name": "My Device (Living Room)",
  "battery_level": 15,
  "threshold": 20
}
```

### `battery_devices_monitor_battery_unavailable`

Fired when a device's battery value becomes unavailable (unavailable, unknown, or cannot be read). This is useful for detecting devices that are offline or having communication issues. The event data includes:

- `entity_id`: The entity ID of the device
- `id` / `device_id`: Home Assistant device ID (or entity_id fallback)
- `name`: The friendly name of the device (with area if available)

Example event data:
```json
{
  "id": "abc123",
  "device_id": "abc123",
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

### `battery_devices_monitor_zigbee_battery_unavailable`

Fired when a Zigbee device appears in `devices_without_battery_info`. This event is intended for automations like rejoin/recovery flows (e.g., ZHA Toolkit). The event data includes:

- `entity_id`: The entity ID associated with the unavailable battery state
- `id` / `device_id`: Home Assistant device ID (or entity_id fallback)
- `name`: The friendly name of the device (with area if available)
- `zigbee_identifier`: Zigbee identifier when available (for example IEEE)

## Development

The event-driven coordinator performs one discovery pass at startup and refreshes when a battery source or the entity/device registry changes. It stores runtime state in `ConfigEntry.runtime_data`, groups physical devices before classifying their battery level, and does not poll Home Assistant periodically. Per-device battery replacement dates, battery types, and source aliases are persisted in Home Assistant's `.storage` directory.

### Known limitations

- Cross-integration grouping is only automatic when Home Assistant exposes a shared hardware identifier/connection or an unambiguous exact name-and-area match.
- Devices without registry metadata and with different entity names cannot be safely identified as the same physical device. They remain separate to avoid merging two real devices accidentally.
- Binary low/normal battery entities do not provide a percentage and therefore cannot be evaluated against a numeric threshold when they are the only source.

### Code Quality

This project maintains high code quality standards:

- ✅ **hassfest**: Home Assistant manifest validation
- ✅ **ruff**: Python linting and formatting
- ✅ **mypy**: Static type checking
- ✅ **pytest**: Source selection, cross-integration deduplication, setup, and reactive update tests

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
