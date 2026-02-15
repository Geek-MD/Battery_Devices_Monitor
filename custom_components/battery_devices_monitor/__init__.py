"""The Battery Devices Monitor integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.core import ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError

from .const import (
    ATTR_DEVICES_BELOW_THRESHOLD,
    ATTR_DEVICES_WITHOUT_BATTERY_INFO,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Battery Devices Monitor from a config entry."""
    _LOGGER.debug("Setting up Battery Devices Monitor entry: %s", entry.entry_id)
    try:
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = entry.data

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        entry.async_on_unload(entry.add_update_listener(async_reload_entry))

        # Register service
        async def get_low_battery_devices(call: ServiceCall) -> ServiceResponse:
            """Get formatted list of low battery devices."""
            entity_id = call.data.get("entity_id")

            if not entity_id:
                raise HomeAssistantError("entity_id is required")

            state = hass.states.get(entity_id)
            if not state:
                raise HomeAssistantError(f"Entity {entity_id} not found")

            devices_below = state.attributes.get(ATTR_DEVICES_BELOW_THRESHOLD, [])

            # Format output: "name (area) - battery_level%\n"
            output_lines = []
            for device in devices_below:
                name = device.get("name", "Unknown")
                area = device.get("area", "")
                battery_level = device.get("battery_level", 0)

                # Round battery level to integer
                battery_level_int = round(battery_level)

                # Format line
                if area:
                    line = f"{name} ({area}) - {battery_level_int}%"
                else:
                    line = f"{name} - {battery_level_int}%"

                output_lines.append(line)

            # Join with newlines
            formatted_output = "\n".join(output_lines)

            return {"result": formatted_output}

        hass.services.async_register(
            DOMAIN,
            "get_low_battery_devices",
            get_low_battery_devices,
            supports_response=SupportsResponse.ONLY,
        )

        # Register service for devices without battery info
        async def get_devices_without_battery_info(call: ServiceCall) -> ServiceResponse:
            """Get formatted list of devices without battery info."""
            entity_id = call.data.get("entity_id")

            if not entity_id:
                raise HomeAssistantError("entity_id is required")

            state = hass.states.get(entity_id)
            if not state:
                raise HomeAssistantError(f"Entity {entity_id} not found")

            devices_without_info = state.attributes.get(ATTR_DEVICES_WITHOUT_BATTERY_INFO, [])

            # Format output: "name (area)\n"
            output_lines = []
            for device in devices_without_info:
                name = device.get("name", "Unknown")
                area = device.get("area", "")

                # Format line
                if area:
                    line = f"{name} ({area})"
                else:
                    line = name

                output_lines.append(line)

            # Join with newlines
            formatted_output = "\n".join(output_lines)

            return {"result": formatted_output}

        hass.services.async_register(
            DOMAIN,
            "get_devices_without_battery_info",
            get_devices_without_battery_info,
            supports_response=SupportsResponse.ONLY,
        )

        _LOGGER.debug("Battery Devices Monitor entry setup completed successfully")
        return True
    except Exception as err:
        _LOGGER.error(
            "Failed to set up Battery Devices Monitor: %s",
            err,
            exc_info=True,
        )
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        # Unregister services when last entry is unloaded
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "get_low_battery_devices")
            hass.services.async_remove(DOMAIN, "get_devices_without_battery_info")

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
