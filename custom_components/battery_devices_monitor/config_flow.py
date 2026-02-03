"""Config flow for Battery Devices Monitor integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import selector

from .const import (
    BATTERY_ATTRS,
    CONF_BATTERY_THRESHOLD,
    CONF_EXCLUDED_DEVICES,
    DEFAULT_BATTERY_THRESHOLD,
    DEFAULT_EXCLUDED_DEVICES,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class BatteryDevicesMonitorConfigFlow(
    config_entries.ConfigFlow, domain=DOMAIN  # type: ignore[call-arg]
):
    """Handle a config flow for Battery Devices Monitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check if already configured
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="Battery Devices Monitor",
                data={},
                options=user_input,
            )

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

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
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

    def _get_battery_devices(self) -> dict[str, str]:
        """Get all devices with battery level attribute."""
        battery_devices = {}
        for state in self.hass.states.async_all():
            # Check for any battery attribute
            has_battery = False
            for attr_name in BATTERY_ATTRS:
                if state.attributes.get(attr_name) is not None:
                    has_battery = True
                    break
            
            if has_battery:
                # Use friendly_name if available, otherwise entity_id
                device_name = state.attributes.get("friendly_name", state.entity_id)
                battery_devices[state.entity_id] = device_name
        return battery_devices

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        battery_devices = self._get_battery_devices()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_BATTERY_THRESHOLD,
                        default=self.config_entry.options.get(
                            CONF_BATTERY_THRESHOLD, DEFAULT_BATTERY_THRESHOLD
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=100,
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Optional(
                        CONF_EXCLUDED_DEVICES,
                        default=self.config_entry.options.get(
                            CONF_EXCLUDED_DEVICES, DEFAULT_EXCLUDED_DEVICES
                        ),
                    ): cv.multi_select(battery_devices),
                }
            ),
        )
