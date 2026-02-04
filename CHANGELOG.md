# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2026-02-04

### Added
- Heuristic method to identify battery-powered devices by entity ID
- Support for battery entities that have "battery" in their entity_id (case-insensitive)
- Battery level validation (0-100 range) for heuristically detected devices
- Helper function `_is_battery_device()` in config_flow to reduce code duplication

### Changed
- Enhanced device discovery to detect entities like `sensor.device_battery` where the state represents the battery level
- Improved config flow to include heuristically detected battery devices in device selection

### Fixed
- Missing battery devices that don't have battery attributes but have "battery" in their entity_id

## [1.1.0] - 2026-02-03

### Added
- Two-step initial configuration flow: configure threshold first, then optionally select devices to exclude from a filtered list
- Device registration support to allow the sensor to be assigned to an area in Home Assistant
- Multi-attribute battery detection: now checks `battery_level`, `battery`, and `Battery` attributes to discover more devices (especially Zigbee devices)

### Changed
- Battery threshold field changed from optional to required in configuration
- Battery threshold input changed from slider to number box for better control
- Battery threshold validation range updated from 1-100% to 0-100%
- Configuration UI now shows excluded device selection as second step during initial setup with filtered battery device list
- Improved device discovery to detect 20+ battery-powered devices instead of only 5

### Fixed
- Missing Zigbee and other battery devices that use alternate attribute names (`battery` instead of `battery_level`)

## [1.0.0] - 2026-02-03

### Added
- Initial release of Battery Devices Monitor integration
- Automatic discovery of all devices with battery levels
- Configurable battery threshold via UI (default: 20%)
- Device exclusion feature - select specific devices to exclude from monitoring
- Single sensor showing overall battery status ("OK" or "Problem")
- Two attributes showing devices above and below threshold as lists
- Events fired when devices go below threshold (`battery_devices_monitor_low_battery`)
- Multi-language support (English and Spanish)
- Full compliance with hassfest, ruff, and mypy
- Comprehensive documentation and examples
- HACS compatibility

### Changed
- Attributes `devices_below_threshold` and `devices_above_threshold` now include both device name and battery level as dictionaries instead of just device names
- Updated README with new attribute structure and improved automation examples
