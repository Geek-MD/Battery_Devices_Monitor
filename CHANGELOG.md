# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
