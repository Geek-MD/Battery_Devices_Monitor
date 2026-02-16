# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.9.0] - 2026-02-16

### Changed
- **Complete rewrite of config_flow.py from scratch** to eliminate 500 Internal Server Error issues during integration reconfiguration. The new implementation incorporates all lessons learned from previous versions:
  - Eliminated mixin pattern in favor of module-level helper functions with explicit `hass` parameter, improving type safety and reducing complexity
  - Centralized battery device fetching logic in `_get_battery_devices_safe()` function with comprehensive error handling that always returns a valid dict (never None)
  - Centralized schema creation in `_create_threshold_schema()` and `_create_devices_schema()` functions to eliminate code duplication
  - Improved device filtering in `_create_devices_schema()` to prevent validation errors when excluded devices no longer exist in Home Assistant
  - Enhanced error handling with granular try-except blocks that catch and log all exceptions with full stack traces
  - All error paths return functional forms with user-friendly error messages instead of causing 500 errors
  - Simplified OptionsFlowHandler to remove redundant code and improve maintainability
  - Proper async/await patterns throughout to ensure correct operation within Home Assistant's event loop
  - Better logging with debug and info level messages to facilitate troubleshooting
  - Code structure optimized for readability and future maintenance

### Fixed
- HTTP 500 error when reconfiguring the integration through the UI. The previous v1.8.11 fixes were incomplete. This complete rewrite addresses all edge cases that could cause 500 errors:
  - Schema creation failures now have proper fallbacks
  - Device fetching errors are caught and return empty dict instead of propagating
  - Config entry access is properly protected with safe defaults
  - All form rendering paths are guaranteed to succeed even in error conditions

## [1.8.11] - 2026-02-16

### Fixed
- **Critical fix for AttributeError in OptionsFlowHandler**. The `OptionsFlowHandler.__init__` method was attempting to set `self.config_entry = config_entry`, but `config_entry` is a read-only property inherited from `config_entries.OptionsFlow` without a setter. This caused an `AttributeError: property 'config_entry' of 'OptionsFlowHandler' object has no setter` when users tried to access the integration's options flow.
  - Removed the custom `__init__` method from `OptionsFlowHandler`
  - The parent class `config_entries.OptionsFlow` automatically handles the `config_entry` parameter passed from `async_get_options_flow()`
  - The `config_entry` property is now properly accessible via the parent class's property getter
  - This follows the standard Home Assistant pattern where OptionsFlow subclasses don't need to override `__init__`

## [1.8.10] - 2026-02-16

### Fixed
- **Critical fix for 500 Internal Server Error during integration configuration**. Home Assistant's config flow system expects specific class names: `FlowHandler` for ConfigFlow and `OptionsFlowHandler` for OptionsFlow. The integration was using custom names (`BatteryDevicesMonitorConfigFlow` and `BatteryDevicesMonitorOptionsFlow`), causing 500 errors when users attempted to configure or modify the integration.
  - Renamed `BatteryDevicesMonitorConfigFlow` → `FlowHandler`
  - Renamed `BatteryDevicesMonitorOptionsFlow` → `OptionsFlowHandler`
  - Updated return type annotation in `async_get_options_flow()` to match Home Assistant conventions
  - The implementation now follows the standard pattern used by Home Assistant integrations like SonoffLAN

## [1.8.9] - 2026-02-16

### Fixed
- **Critical fix for persistent 500 Internal Server Error during integration reconfiguration**. Following the proven pattern from the Midea AC LAN integration, the options flow now filters the excluded devices list to only include devices that currently exist in Home Assistant. Previously, if a device was excluded and then removed from Home Assistant, the options flow would fail with a 500 error when trying to display the form because `cv.multi_select()` received a default value containing device IDs that no longer existed in the available devices dictionary.
  - Implemented device filtering using set intersection: `set(battery_devices.keys()) & set(current_excluded)` following the midea_ac_lan pattern (lines 957-963)
  - The filtered list (`valid_excluded`) is now used as the default value in the form schema instead of the raw `current_excluded`
  - Added debug logging to track how many devices were filtered
  - Added explanatory comments referencing the midea_ac_lan pattern
  - This ensures the multi-select validator always receives valid device IDs, preventing validation errors and 500 responses

## [1.8.8] - 2026-02-15

### Fixed
- **Resolved persistent 500 Internal Server Error during integration reconfiguration**. The options flow now has robust, granular error handling that prevents cascading failures. Previously, if any exception occurred (e.g., fetching devices, reading config), the error handler itself could fail when trying to access `self.config_entry.options`, causing a 500 error with no logging.
  - Split error handling into separate try-catch blocks for each operation (read config, fetch devices, build schema, save)
  - Added safe fallbacks: defaults for config values, empty dict for device list, minimal schema on failure
  - Each error path logs with `exc_info=True` and returns a functional form with user-friendly error messages
  - Error messages now properly displayed in both config and options flows with translations (English and Spanish)

### Added
- **Diagnostics support** following Home Assistant best practices for easier troubleshooting
  - Implements `async_get_config_entry_diagnostics` as per Home Assistant specification
  - Provides comprehensive diagnostic data: configuration details, battery devices with exclusion status, devices without battery info, current sensor state
  - Home Assistant automatically detects diagnostics support through the diagnostics.py file
  - Includes error handling to prevent diagnostics from failing
- **Enhanced error messages** for better user experience
  - Added "unknown" error: Generic error for unexpected issues
  - Added "cannot_connect" error: Specific error for device fetching issues
  - Error messages available in English and Spanish translations

### Changed
- Reviewed TuyaLocal integration patterns to ensure robust error handling follows Home Assistant best practices

## [1.8.7] - 2026-02-15

### Fixed
- **Enhanced error logging for configuration flow 500 errors**. Despite the fixes in v1.8.6 addressing async/sync issues, the 500 Internal Server Error could still occur for other reasons but was not being logged. This update adds comprehensive try-except blocks with full error logging to all configuration flow step functions (`async_step_user`, `async_step_exclude_devices`, `async_step_init`) and to `async_setup_entry`. Now any exception that occurs during configuration or setup will be logged with full stack traces (`exc_info=True`), making it possible to diagnose the root cause of 500 errors.
  - Added try-except blocks with error logging to all async step functions in config flow
  - Added try-except block with error logging to async_setup_entry
  - Error handlers return user-friendly error forms instead of causing 500 errors
  - Added debug logging at entry points of each step function to trace execution flow
  - All exceptions are now caught and logged, enabling proper diagnosis of configuration issues

## [1.8.6] - 2026-02-15

### Fixed
- **Critical fix for HTTP 500 Internal Server Error** that persisted despite previous attempts. The root cause was a sync/async mismatch where synchronous utility functions were calling Home Assistant's async registry methods (`er.async_get()`, `dr.async_get()`, `ar.async_get()`) without proper async context. This caused the event loop to fail silently, resulting in 500 errors when loading the configuration flow.
  - Converted `get_all_battery_devices()`, `get_device_info()`, and `get_devices_without_battery_info()` to async functions
  - Updated all call sites in `config_flow.py` and `sensor.py` to properly await these async functions
  - The integration now correctly operates within Home Assistant's async event loop

### Added
- Comprehensive debug logging throughout the integration to help diagnose future issues:
  - Debug logs in config flow steps showing when device selection is initiated
  - Debug logs in utility functions showing number of devices found
  - Error logs with full exception traces for all error conditions
  - All logs properly initialized at module level for optimal performance

## [1.8.5] - 2026-02-15

### Fixed
- HTTP 500 error when reconfiguring the integration through the UI. Added comprehensive error handling and logging in config flow to catch and log exceptions, preventing the integration from crashing when trying to retrieve battery devices. The config flow now gracefully handles errors and returns an empty device list instead of failing with a 500 error.

## [1.8.2] - 2026-02-13

### Fixed
- Entities with "Battery Devices Monitor" in their name are now completely excluded from all monitoring processes. This resolves issues where devices or entities named "Battery Devices Monitor" were incorrectly appearing in the `devices_without_battery_info` list.

## [1.8.1] - 2026-02-13

### Fixed
- Battery Devices Monitor integration and other non-device entities (automations, scenes, scripts) are no longer incorrectly included in `devices_without_battery_info` attribute. The heuristic detection that checks for "battery" in entity_id now properly excludes automation, scene, and script entities even if they contain "battery" in their name.

### Changed
- Battery levels in sensor attributes (`devices_above_threshold` and `devices_below_threshold`) and events are now rounded to integers instead of showing decimal values.
- README documentation clarified that `devices_above_threshold` uses `battery >= threshold` and `devices_below_threshold` uses `battery < threshold`. Code logic has always been correct.

## [1.8.0] - 2026-02-13

### Added
- New service `get_devices_without_battery_info` that returns a formatted list of devices with battery but whose value is unavailable, unknown, or invalid
- Service output format: "name (area)\n" with one device per line
- Service can be used in automations with response_variable to get information about devices without battery info
- Event `battery_devices_monitor_battery_unavailable` (already exists from v1.7.0) can be used alongside this service for automation
- New sensor attribute `devices_without_battery_info_status` that shows "OK" when no devices have unavailable battery info, or "Problem" when one or more devices have unavailable battery info

## [1.7.2] - 2026-02-12

### Fixed
- Battery Devices Monitor device itself is no longer incorrectly included in `devices_without_battery_info` attribute. The previous fix in v1.7.1 only excluded entities from the integration, but the device itself (created by the integration) was still being picked up. Now devices belonging to the battery_devices_monitor integration are properly excluded at the device registry level.

## [1.7.1] - 2026-02-12

### Fixed
- Battery Devices Monitor sensor itself is no longer incorrectly included in `devices_without_battery_info` attribute. The sensor was being flagged because its entity_id contains "battery", triggering the heuristic detection logic. Now all entities from the battery_devices_monitor domain are properly excluded from monitoring.

## [1.7.0] - 2026-02-11

### Added
- New sensor attribute `devices_without_battery_info` that lists devices with battery but whose value cannot be obtained (unavailable, unknown, or invalid)
- New event `battery_devices_monitor_battery_unavailable` fired when a device's battery value becomes unavailable
- Event includes `entity_id` and `name` (with area if available) for use in automations
- Devices without battery info are now included in `total_monitored_devices` count
- Format follows same structure as excluded_devices: each entry contains `name` and `area` fields

## [1.6.0] - 2026-02-10

### Added
- New service `get_low_battery_devices` that returns a formatted list of devices below the battery threshold
- Service output format: "name (area) - battery_level%\n" with rounded battery_level values
- Service can be used in automations to get device information as an output variable

## [1.5.4] - 2026-02-09

### Fixed
- AttributeError when sorting devices with None area values in sensor attributes - now properly handles devices without assigned areas
- AttributeError when sorting devices with None area values in config flow - now properly handles devices without assigned areas in device selection

## [1.5.3] - 2026-02-08

### Fixed
- Case-insensitive sorting for `excluded_devices` list to ensure proper alphabetical order (e.g., "iPhone" now correctly appears before "MacBook Pro")
- Case-insensitive sorting for device selection list in configuration flow to ensure proper alphabetical order
- Case-insensitive sorting for `devices_above_threshold` and `devices_below_threshold` lists

## [1.5.2] - 2026-02-08

### Changed
- Sensor attribute `total_devices` renamed to `total_monitored_devices` for clarity
- `excluded_devices` list is now sorted alphabetically by friendly name (A-Z), then by area (A-Z)
- `devices_above_threshold` and `devices_below_threshold` lists are now sorted by battery_level (ascending), then by friendly name (A-Z), then by area (A-Z)
- Device selection list in configuration flow (step 2) is now sorted by friendly name (A-Z), then by area (A-Z)

## [1.5.0] - 2026-02-04

### Added
- `excluded_devices` sensor attribute that lists excluded devices with their names and areas
- `area` field added to all device list attributes for consistency

### Changed
- Device attribute structure now consistently includes separate `name` and `area` fields
- `devices_below_threshold` entries now include: `name` (device name only), `area` (area name), and `battery_level`
- `devices_above_threshold` entries now include: `name` (device name only), `area` (area name), and `battery_level`
- `excluded_devices` entries include: `name` (device name only) and `area` (area name)
- Device names in attributes no longer include area in parentheses format - area is provided as separate field

### Fixed
- Error 500 when reconfiguring integration due to incorrect area registry access

## [1.4.0] - 2026-02-04

### Fixed
- Configuration flow 500 Internal Server Error when reconfiguring the integration
- Exclusion list now uses the same device names as sensor attributes (from device registry)
- All monitored devices now appear in the exclusion list (including Robovac, PIR sensors, etc.)

### Added
- Area information in sensor attributes for easier device identification
- Area information in device exclusion list (displayed as "Device Name (Area)")
- Shared utility module (`utils.py`) for consistent battery device detection across the integration

### Changed
- Refactored battery device detection logic into shared utilities
- Config flow and sensor now use the same device identification method
- Device display names now include area information when available (format: "Device Name (Area)")

## [1.3.0] - 2026-02-04

### Fixed
- Duplicate device entries: devices with battery entities are now properly deduplicated using device registry
- Device names: now using device name from device registry instead of battery entity's friendly name
- Multiple battery entities per device: when a device has multiple battery entities, the highest battery level is used

### Changed
- Integration now uses Home Assistant's device and entity registries to properly associate battery entities with their parent devices
- Device deduplication logic ensures each physical device is only listed once in the monitoring list

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
