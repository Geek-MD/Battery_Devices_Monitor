"""Diagnostics support for Battery Devices Monitor."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .const import (
    CONF_BATTERY_THRESHOLD,
    CONF_EXCLUDED_DEVICES,
    DEFAULT_BATTERY_THRESHOLD,
    DOMAIN,
)
from .utils import get_all_battery_devices, get_devices_without_battery_info

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    _LOGGER.debug("Generating diagnostics for entry: %s", entry.entry_id)

    try:
        # Get configuration
        threshold = entry.options.get(CONF_BATTERY_THRESHOLD, DEFAULT_BATTERY_THRESHOLD)
        excluded_devices = entry.options.get(CONF_EXCLUDED_DEVICES, [])
        
        # Get all battery devices
        try:
            battery_devices = await get_all_battery_devices(hass)
            battery_devices_count = len(battery_devices)
            battery_devices_info = []
            
            for device_id, device_data in battery_devices.items():
                battery_devices_info.append({
                    "device_id": device_id,
                    "name": device_data.get("name"),
                    "area": device_data.get("area"),
                    "battery_level": device_data.get("battery_level"),
                    "entity_id": device_data.get("entity_id"),
                    "is_excluded": device_id in excluded_devices,
                })
        except Exception as err:
            _LOGGER.error("Error getting battery devices for diagnostics: %s", err, exc_info=True)
            battery_devices_count = 0
            battery_devices_info = []
        
        # Get devices without battery info
        try:
            devices_without_info = await get_devices_without_battery_info(hass)
            devices_without_info_count = len(devices_without_info)
            devices_without_info_list = []
            
            for device_id, device_data in devices_without_info.items():
                devices_without_info_list.append({
                    "device_id": device_id,
                    "name": device_data.get("name"),
                    "area": device_data.get("area"),
                    "entity_id": device_data.get("entity_id"),
                })
        except Exception as err:
            _LOGGER.error("Error getting devices without battery info for diagnostics: %s", err, exc_info=True)
            devices_without_info_count = 0
            devices_without_info_list = []
        
        # Get sensor state if available
        sensor_entity_id = f"sensor.{DOMAIN}_status"
        sensor_state = hass.states.get(sensor_entity_id)
        sensor_info = None
        
        if sensor_state:
            sensor_info = {
                "state": sensor_state.state,
                "attributes": dict(sensor_state.attributes),
            }
        
        diagnostics_data = {
            "config_entry": {
                "entry_id": entry.entry_id,
                "version": entry.version,
                "title": entry.title,
            },
            "configuration": {
                "battery_threshold": threshold,
                "excluded_devices_count": len(excluded_devices),
                "excluded_devices": excluded_devices,
            },
            "battery_devices": {
                "total_count": battery_devices_count,
                "devices": battery_devices_info,
            },
            "devices_without_battery_info": {
                "total_count": devices_without_info_count,
                "devices": devices_without_info_list,
            },
            "sensor": sensor_info,
        }
        
        _LOGGER.debug("Diagnostics generated successfully with %d battery devices", battery_devices_count)
        return diagnostics_data
        
    except Exception as err:
        _LOGGER.error("Error generating diagnostics: %s", err, exc_info=True)
        return {
            "error": "Failed to generate diagnostics",
            "error_message": str(err),
        }
