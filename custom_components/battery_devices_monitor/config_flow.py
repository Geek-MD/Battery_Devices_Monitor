"""Config flow for Battery Devices Monitor integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
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


async def _get_battery_devices_safe(hass: HomeAssistant) -> dict[str, str]:
    """Get all battery devices with comprehensive error handling.

    Returns a dictionary where:
    - Key: device_id or entity_id (unique identifier)
    - Value: display name with area (if available)

    Returns empty dict on any error to prevent 500 errors.
    """
    try:
        all_devices = await get_all_battery_devices(hass)
        _LOGGER.debug("Retrieved %d battery devices", len(all_devices))

        # Sort by name (case-insensitive), then by area (case-insensitive)
        device_list = sorted(
            all_devices.items(),
            key=lambda x: (
                x[1]["name"].lower(),
                (x[1].get("area") or "").lower(),
            ),
        )

        # Create display dict for the multi-select
        battery_devices = {}
        for device_key, device_data in device_list:
            display_name = device_data["name"]
            if device_data.get("area"):
                display_name = f"{device_data['name']} ({device_data['area']})"
            battery_devices[device_key] = display_name

        return battery_devices

    except Exception as err:
        _LOGGER.error(
            "Error getting battery devices: %s",
            err,
            exc_info=True,
        )
        # Return empty dict to prevent 500 error
        return {}


def _create_threshold_schema(default_value: int) -> vol.Schema:
    """Create schema for battery threshold configuration.

    Args:
        default_value: Default threshold value (0-100)

    Returns:
        A voluptuous Schema object for threshold configuration
    """
    return vol.Schema(
        {
            vol.Required(
                CONF_BATTERY_THRESHOLD,
                default=default_value,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=100,
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
        }
    )


def _create_devices_schema(
    devices: dict[str, str],
    default_excluded: list[str],
) -> vol.Schema:
    """Create schema for device exclusion configuration.

    Args:
        devices: Dictionary of available battery devices
        default_excluded: List of currently excluded device IDs

    Returns:
        A voluptuous Schema object for device selection
    """
    # Filter excluded devices to only include those that still exist
    # This prevents 500 errors when devices have been removed from HA
    valid_excluded = list(set(devices.keys()) & set(default_excluded))

    _LOGGER.debug(
        "Filtered excluded devices from %d to %d valid entries",
        len(default_excluded),
        len(valid_excluded),
    )

    return vol.Schema(
        {
            vol.Optional(
                CONF_EXCLUDED_DEVICES,
                default=valid_excluded,
            ): cv.multi_select(devices),
        }
    )


class FlowHandler(
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
        _LOGGER.debug("Config flow step 'user' started")
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Validate and store threshold
                self._threshold = user_input[CONF_BATTERY_THRESHOLD]
                _LOGGER.debug("Threshold set to %s", self._threshold)
                return await self.async_step_exclude_devices()

            except Exception as err:
                _LOGGER.error(
                    "Error in user step: %s",
                    err,
                    exc_info=True,
                )
                errors["base"] = "unknown"

        # Show the form
        try:
            data_schema = _create_threshold_schema(DEFAULT_BATTERY_THRESHOLD)
        except Exception as err:
            _LOGGER.error(
                "Error creating threshold schema: %s",
                err,
                exc_info=True,
            )
            errors["base"] = "unknown"
            data_schema = _create_threshold_schema(DEFAULT_BATTERY_THRESHOLD)

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_exclude_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the second step - select devices to exclude."""
        _LOGGER.debug("Config flow step 'exclude_devices' started")
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Check if already configured
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()

                # Create config entry with options
                config_data = {
                    CONF_BATTERY_THRESHOLD: self._threshold,
                    CONF_EXCLUDED_DEVICES: user_input.get(
                        CONF_EXCLUDED_DEVICES, []
                    ),
                }

                _LOGGER.info(
                    "Creating config entry: threshold=%s, excluded_count=%d",
                    self._threshold,
                    len(config_data[CONF_EXCLUDED_DEVICES]),
                )

                return self.async_create_entry(
                    title="Battery Devices Monitor",
                    data={},
                    options=config_data,
                )

            except Exception as err:
                _LOGGER.error(
                    "Error creating config entry: %s",
                    err,
                    exc_info=True,
                )
                errors["base"] = "unknown"

        # Fetch battery devices for the form
        battery_devices = await _get_battery_devices_safe(self.hass)

        if not battery_devices and not errors:
            _LOGGER.warning("No battery devices found")
            errors["base"] = "cannot_connect"

        # Build the form schema
        try:
            data_schema = _create_devices_schema(
                battery_devices,
                DEFAULT_EXCLUDED_DEVICES,
            )
        except Exception as err:
            _LOGGER.error(
                "Error creating devices schema: %s",
                err,
                exc_info=True,
            )
            errors["base"] = "unknown"
            # Fallback to empty schema
            data_schema = _create_devices_schema(
                {},
                DEFAULT_EXCLUDED_DEVICES,
            )

        return self.async_show_form(
            step_id="exclude_devices",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Battery Devices Monitor."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        _LOGGER.debug("Options flow step 'init' started")
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                _LOGGER.info("Updating options: %s", user_input)
                return self.async_create_entry(title="", data=user_input)

            except Exception as err:
                _LOGGER.error(
                    "Error saving options: %s",
                    err,
                    exc_info=True,
                )
                errors["base"] = "unknown"

        # Get current configuration values with safe fallbacks
        current_threshold = self.config_entry.options.get(
            CONF_BATTERY_THRESHOLD, DEFAULT_BATTERY_THRESHOLD
        )
        current_excluded = self.config_entry.options.get(
            CONF_EXCLUDED_DEVICES, DEFAULT_EXCLUDED_DEVICES
        )

        # Fetch battery devices
        battery_devices = await _get_battery_devices_safe(self.hass)

        if not battery_devices and not errors:
            _LOGGER.warning("No battery devices found in options flow")
            errors["base"] = "cannot_connect"

        # Build the form schema with current values
        try:
            # Create threshold schema
            threshold_schema = _create_threshold_schema(current_threshold)
            # Create devices schema
            devices_schema = _create_devices_schema(
                battery_devices,
                current_excluded,
            )

            # Combine schemas
            data_schema = vol.Schema(
                {
                    **threshold_schema.schema,
                    **devices_schema.schema,
                }
            )

        except Exception as err:
            _LOGGER.error(
                "Error building options form schema: %s",
                err,
                exc_info=True,
            )
            errors["base"] = "unknown"
            # Fallback to minimal schema
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

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )
