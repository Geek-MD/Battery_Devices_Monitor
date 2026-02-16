"""Config flow for Battery Devices Monitor integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_THRESHOLD,
    CONF_EXCLUDED_DEVICES,
    DEFAULT_BATTERY_THRESHOLD,
    DEFAULT_EXCLUDED_DEVICES,
    DOMAIN,
)
from .utils import get_all_battery_devices

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

_LOGGER = logging.getLogger(__name__)


class BatteryDevicesMonitorConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,  # type: ignore[call-arg]
):
    """Handle a config flow for Battery Devices Monitor."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._threshold: int | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - configure threshold."""
        _LOGGER.debug("Config flow: async_step_user started with user_input: %s", user_input is not None)
        errors: dict[str, str] = {}

        try:
            if user_input is not None:
                # Store threshold and move to next step
                self._threshold = user_input[CONF_BATTERY_THRESHOLD]
                _LOGGER.debug("Config flow: Threshold set to %s, proceeding to exclude_devices step", self._threshold)
                return await self.async_step_exclude_devices()

            data_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_BATTERY_THRESHOLD,
                        default=DEFAULT_BATTERY_THRESHOLD,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=100,
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                }
            )

            _LOGGER.debug("Config flow: Showing user form for threshold configuration")
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
                errors=errors,
            )
        except Exception as err:
            _LOGGER.error(
                "Config flow: Unexpected error in async_step_user: %s",
                err,
                exc_info=True,
            )
            errors["base"] = "unknown"
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_BATTERY_THRESHOLD,
                            default=DEFAULT_BATTERY_THRESHOLD,
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=0,
                                max=100,
                                mode=selector.NumberSelectorMode.BOX,
                            ),
                        ),
                    }
                ),
                errors=errors,
            )

    async def _get_battery_devices(self) -> dict[str, str]:
        """Get all devices with battery level attribute.

        Returns a dictionary where:
        - Key: device_id or entity_id (unique identifier)
        - Value: display name with area (if available)
        """
        _LOGGER.debug("Config flow: Getting battery devices for device selection")
        try:
            all_devices = await get_all_battery_devices(self.hass)
            _LOGGER.debug("Config flow: Retrieved %d battery devices", len(all_devices))

            # Create list of tuples (device_key, device_data) for sorting
            device_list = []
            for device_key, device_data in all_devices.items():
                device_list.append((device_key, device_data))

            # Sort by name (A-Z, case-insensitive), then by area (A-Z, case-insensitive)
            device_list.sort(key=lambda x: (x[1]["name"].lower(), (x[1].get("area", "") or "").lower()))

            # Create display dict for the multi-select
            battery_devices = {}
            for device_key, device_data in device_list:
                # Create a descriptive display name
                display_name = device_data["name"]
                if device_data.get("area"):
                    display_name = f"{device_data['name']} ({device_data['area']})"

                battery_devices[device_key] = display_name

            return battery_devices
        except Exception as err:
            _LOGGER.error(
                "Error getting battery devices in config flow: %s",
                err,
                exc_info=True,
            )
            # Return empty dict to prevent 500 error
            return {}

    async def async_step_exclude_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the second step - select devices to exclude."""
        _LOGGER.debug("Config flow: async_step_exclude_devices started with user_input: %s", user_input is not None)

        try:
            if user_input is not None:
                _LOGGER.debug("Config flow: Processing user input for device exclusion")
                # Check if already configured
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()

                # Combine threshold and excluded devices
                config_data = {
                    CONF_BATTERY_THRESHOLD: self._threshold,
                    CONF_EXCLUDED_DEVICES: user_input.get(CONF_EXCLUDED_DEVICES, []),
                }

                _LOGGER.debug("Config flow: Creating config entry with threshold=%s, excluded_devices=%s",
                             self._threshold, len(config_data[CONF_EXCLUDED_DEVICES]))
                return self.async_create_entry(
                    title="Battery Devices Monitor",
                    data={},
                    options=config_data,
                )

            _LOGGER.debug("Config flow: Fetching battery devices for exclusion selection")
            battery_devices = await self._get_battery_devices()
            _LOGGER.debug("Config flow: Found %d battery devices for selection", len(battery_devices))

            data_schema = vol.Schema(
                {
                    vol.Optional(
                        CONF_EXCLUDED_DEVICES,
                        default=DEFAULT_EXCLUDED_DEVICES,
                    ): cv.multi_select(battery_devices),
                }
            )

            _LOGGER.debug("Config flow: Showing exclude_devices form")
            return self.async_show_form(
                step_id="exclude_devices",
                data_schema=data_schema,
            )
        except Exception as err:
            _LOGGER.error(
                "Config flow: Unexpected error in async_step_exclude_devices: %s",
                err,
                exc_info=True,
            )
            # Try to show form with empty device list to avoid 500 error
            errors = {"base": "unknown"}
            return self.async_show_form(
                step_id="exclude_devices",
                data_schema=vol.Schema(
                    {
                        vol.Optional(
                            CONF_EXCLUDED_DEVICES,
                            default=DEFAULT_EXCLUDED_DEVICES,
                        ): cv.multi_select({}),
                    }
                ),
                errors=errors,
            )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BatteryDevicesMonitorOptionsFlow:
        """Get the options flow for this handler."""
        return BatteryDevicesMonitorOptionsFlow(config_entry)


class BatteryDevicesMonitorOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Battery Devices Monitor."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        # Clean up excluded devices that no longer exist
        # This is done in __init__ following the midea_ac_lan pattern
        # to prevent 500 errors when devices are removed from Home Assistant

    async def _get_battery_devices(self) -> dict[str, str]:
        """Get all devices with battery level attribute.

        Returns a dictionary where:
        - Key: device_id or entity_id (unique identifier)
        - Value: display name with area (if available)
        """
        _LOGGER.debug("Options flow: Getting battery devices for device selection")
        try:
            all_devices = await get_all_battery_devices(self.hass)
            _LOGGER.debug("Options flow: Retrieved %d battery devices", len(all_devices))

            # Create list of tuples (device_key, device_data) for sorting
            device_list = []
            for device_key, device_data in all_devices.items():
                device_list.append((device_key, device_data))

            # Sort by name (A-Z, case-insensitive), then by area (A-Z, case-insensitive)
            device_list.sort(key=lambda x: (x[1]["name"].lower(), (x[1].get("area", "") or "").lower()))

            # Create display dict for the multi-select
            battery_devices = {}
            for device_key, device_data in device_list:
                # Create a descriptive display name
                display_name = device_data["name"]
                if device_data.get("area"):
                    display_name = f"{device_data['name']} ({device_data['area']})"

                battery_devices[device_key] = display_name

            return battery_devices
        except Exception as err:
            _LOGGER.error(
                "Error getting battery devices in options flow: %s",
                err,
                exc_info=True,
            )
            # Return empty dict to prevent 500 error
            return {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        _LOGGER.debug("Options flow: async_step_init started with user_input: %s", user_input is not None)
        
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                _LOGGER.debug("Options flow: Updating options with new configuration")
                return self.async_create_entry(title="", data=user_input)
            except Exception as err:
                _LOGGER.error(
                    "Options flow: Error saving configuration: %s",
                    err,
                    exc_info=True,
                )
                errors["base"] = "unknown"

        # Get current configuration values with safe fallbacks
        try:
            current_threshold = self.config_entry.options.get(
                CONF_BATTERY_THRESHOLD, DEFAULT_BATTERY_THRESHOLD
            )
            current_excluded = self.config_entry.options.get(
                CONF_EXCLUDED_DEVICES, DEFAULT_EXCLUDED_DEVICES
            )
        except Exception as err:
            _LOGGER.error(
                "Options flow: Error reading current options: %s",
                err,
                exc_info=True,
            )
            current_threshold = DEFAULT_BATTERY_THRESHOLD
            current_excluded = DEFAULT_EXCLUDED_DEVICES
            errors["base"] = "cannot_connect"

        # Fetch battery devices
        try:
            _LOGGER.debug("Options flow: Fetching battery devices for options form")
            battery_devices = await self._get_battery_devices()
            _LOGGER.debug("Options flow: Found %d battery devices for selection", len(battery_devices))
        except Exception as err:
            _LOGGER.error(
                "Options flow: Error fetching battery devices: %s",
                err,
                exc_info=True,
            )
            battery_devices = {}
            if "base" not in errors:
                errors["base"] = "cannot_connect"

        # Filter excluded devices to only include those that still exist
        # This follows the midea_ac_lan pattern to prevent 500 errors
        # when devices have been removed from Home Assistant
        valid_excluded = list(
            set(battery_devices.keys()) & set(current_excluded)
        )
        _LOGGER.debug(
            "Options flow: Filtered excluded devices from %d to %d valid entries",
            len(current_excluded), len(valid_excluded)
        )

        # Build the form schema
        try:
            data_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_BATTERY_THRESHOLD,
                        default=current_threshold,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=100,
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Optional(
                        CONF_EXCLUDED_DEVICES,
                        default=valid_excluded,
                    ): cv.multi_select(battery_devices),
                }
            )
        except Exception as err:
            _LOGGER.error(
                "Options flow: Error building form schema: %s",
                err,
                exc_info=True,
            )
            # Create a minimal fallback schema
            data_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_BATTERY_THRESHOLD,
                        default=DEFAULT_BATTERY_THRESHOLD,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=100,
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Optional(
                        CONF_EXCLUDED_DEVICES,
                        default=DEFAULT_EXCLUDED_DEVICES,
                    ): cv.multi_select({}),
                }
            )
            errors["base"] = "unknown"

        _LOGGER.debug("Options flow: Showing init form with %d errors", len(errors))
        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )
