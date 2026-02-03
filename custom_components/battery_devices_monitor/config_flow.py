"""Config flow for Battery Devices Monitor integration."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_BATTERY_THRESHOLD, DEFAULT_BATTERY_THRESHOLD, DOMAIN


class BatteryDevicesMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Battery Devices Monitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, any] | None = None
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
                vol.Optional(
                    CONF_BATTERY_THRESHOLD,
                    default=DEFAULT_BATTERY_THRESHOLD,
                ): vol.All(cv.positive_int, vol.Range(min=1, max=100)),
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

    async def async_step_init(
        self, user_input: dict[str, any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_BATTERY_THRESHOLD,
                        default=self.config_entry.options.get(
                            CONF_BATTERY_THRESHOLD, DEFAULT_BATTERY_THRESHOLD
                        ),
                    ): vol.All(cv.positive_int, vol.Range(min=1, max=100)),
                }
            ),
        )
