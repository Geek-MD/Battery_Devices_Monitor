# Battery Devices Monitor

A Home Assistant custom integration that monitors all battery-powered devices and provides a single sensor showing "OK" or "Problem" status.

## Features

- 🔋 Automatically discovers all devices with battery levels
- ⚙️ Configurable battery threshold via UI
- 📊 Single sensor showing overall battery status ("OK" or "Problem")
- 📝 Detailed attributes showing all monitored devices
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

## Usage

After installation and configuration, the integration creates a sensor named `sensor.battery_monitor_status` with:

### States
- **OK**: All monitored devices have battery levels above the threshold
- **Problem**: One or more devices have battery levels below the threshold

### Attributes
- `devices_below_threshold`: List of device friendly names with battery below threshold
- `devices_above_threshold`: List of device friendly names with battery above threshold
- `total_devices`: Total count of monitored devices

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
          message: "One or more devices have low battery!"
```

## Development

This integration monitors all entities in Home Assistant that have a `battery_level` attribute. It automatically updates when any device battery level changes.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/Geek-MD/Battery_Devices_Monitor/issues).
