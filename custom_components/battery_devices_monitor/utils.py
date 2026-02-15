"""Utility functions for Battery Devices Monitor integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er

from .const import BATTERY_ATTRS, DOMAIN, EXCLUDED_ENTITY_DOMAINS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State

# Name pattern to exclude from monitoring
EXCLUDED_NAME_PATTERN = "Battery Devices Monitor"

_LOGGER = logging.getLogger(__name__)


def should_exclude_entity(state: State) -> bool:
    """Check if an entity should be excluded from battery monitoring.
    
    Returns True if the entity should be excluded, False otherwise.
    Excludes:
    - Entities from the battery_devices_monitor domain itself
    - Entities from excluded domains (automation, scene, script)
    """
    # Exclude entities from battery_devices_monitor domain (the monitor itself)
    if state.entity_id.startswith(f"sensor.{DOMAIN}"):
        return True
    
    # Exclude entities from specific domains
    entity_domain = state.entity_id.split(".")[0] if "." in state.entity_id else ""
    if entity_domain in EXCLUDED_ENTITY_DOMAINS:
        return True
    
    return False


def get_battery_level(state: State) -> float | None:
    """Get battery level from entity state or attributes.

    Checks multiple attribute names commonly used for battery level,
    and also checks the state value if entity_id contains "battery".
    Returns the battery level as a float, or None if not found.
    """
    # Exclude entities that should not be monitored
    if should_exclude_entity(state):
        return None
    
    # First check for any battery attribute
    for attr_name in BATTERY_ATTRS:
        battery_value = state.attributes.get(attr_name)
        if battery_value is not None:
            try:
                return float(battery_value)
            except (ValueError, TypeError):
                continue

    # Heuristic: If entity_id contains "battery", try to use the state value
    if "battery" in state.entity_id.lower():
        try:
            potential_level = float(state.state)
            # Validate range - battery levels should be between 0 and 100
            if 0 <= potential_level <= 100:
                return potential_level
        except (ValueError, TypeError):
            pass

    return None


def has_battery_attribute(state: State) -> bool:
    """Check if a state has battery attributes or is a battery entity.

    Returns True if the entity has any battery attribute or if entity_id
    contains "battery".
    """
    # Exclude entities that should not be monitored
    if should_exclude_entity(state):
        return False
    
    # Check if any battery attribute exists
    for attr_name in BATTERY_ATTRS:
        if attr_name in state.attributes:
            return True
    
    # Heuristic: If entity_id contains "battery"
    if "battery" in state.entity_id.lower():
        return True
    
    return False


def is_battery_device(state: State) -> bool:
    """Check if a state object represents a battery device.

    Uses both attribute checking and heuristic to identify battery devices.
    Returns True if the entity has battery attributes or if it has 'battery'
    in its entity_id and a valid numeric state in the range 0-100.
    """
    return get_battery_level(state) is not None


def has_battery_but_unavailable(state: State) -> bool:
    """Check if a state has battery attributes but value is unavailable.

    Returns True if the entity has battery attributes but the value cannot
    be obtained (unavailable, unknown, or cannot be converted to float).
    """
    # First check if this entity has battery attributes
    if not has_battery_attribute(state):
        return False
    
    # If battery level can be obtained, it's available (not what we're looking for)
    if get_battery_level(state) is not None:
        return False
    
    # Has battery attribute but value cannot be obtained
    return True


async def get_device_info(
    hass: HomeAssistant, state: State
) -> tuple[str | None, str | None, str | None]:
    """Get device information for a battery entity.

    Returns a tuple of (display_name, device_id, area_name).
    - display_name: The name to display (device name from registry or friendly_name), or None if device belongs to battery_devices_monitor
    - device_id: The device ID if available, or None
    - area_name: The area name if device is assigned to an area, or None
    """
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)

    device_name = None
    device_id = None
    area_name = None

    # Look up entity in the entity registry
    entity_entry = entity_reg.async_get(state.entity_id)
    if entity_entry and entity_entry.device_id:
        device_id = entity_entry.device_id
        device_entry = device_reg.async_get(device_id)
        if device_entry:
            # Check if this device belongs to battery_devices_monitor integration
            # If so, skip it (the monitor itself should not be monitored)
            for identifier in device_entry.identifiers:
                if identifier[0] == DOMAIN:
                    # This device belongs to our integration, return None for all values
                    return None, None, None

            # Use device name or name_by_user if available
            device_name = device_entry.name_by_user or device_entry.name
            
            # Exclude devices with "Battery Devices Monitor" in their name
            if device_name and EXCLUDED_NAME_PATTERN in device_name:
                return None, None, None

            # Get area name if device is assigned to an area
            if device_entry.area_id:
                area_entry = area_reg.async_get_area(device_entry.area_id)
                if area_entry:
                    area_name = area_entry.name

    # If we couldn't get the device name, fall back to the entity's friendly name
    if not device_name:
        device_name = state.attributes.get("friendly_name", state.entity_id)
    
    # Also check the fallback name for "Battery Devices Monitor"
    if device_name and EXCLUDED_NAME_PATTERN in device_name:
        return None, None, None

    return device_name, device_id, area_name


async def get_all_battery_devices(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """Get all battery devices with their information.

    Returns a dictionary where:
    - Key: device_id (or entity_id if device_id not available)
    - Value: dict with 'name', 'entity_id', 'area', 'battery_level'
    """
    _LOGGER.debug("Starting get_all_battery_devices")
    battery_devices: dict[str, dict[str, Any]] = {}

    all_states = hass.states.async_all()
    _LOGGER.debug("Retrieved %d total states from Home Assistant", len(all_states))

    for state in all_states:
        if not is_battery_device(state):
            continue

        battery_level = get_battery_level(state)
        if battery_level is None:
            continue

        try:
            device_name, device_id, area_name = await get_device_info(hass, state)
        except Exception as err:
            _LOGGER.error(
                "Error getting device info for %s: %s",
                state.entity_id,
                err,
                exc_info=True,
            )
            continue

        # Skip if device belongs to battery_devices_monitor integration
        if device_name is None:
            continue

        # Use device_id if available, otherwise use entity_id as unique key
        unique_key = device_id if device_id else state.entity_id

        # Check if we've already processed this device
        # Keep the entry with the highest battery level if duplicate
        if unique_key in battery_devices:
            existing_level = battery_devices[unique_key]["battery_level"]
            if battery_level > existing_level:
                battery_devices[unique_key] = {
                    "name": device_name,
                    "entity_id": state.entity_id,
                    "area": area_name,
                    "battery_level": battery_level,
                }
        else:
            battery_devices[unique_key] = {
                "name": device_name,
                "entity_id": state.entity_id,
                "area": area_name,
                "battery_level": battery_level,
            }

    _LOGGER.debug("Found %d battery devices", len(battery_devices))
    return battery_devices


async def get_devices_without_battery_info(hass: HomeAssistant) -> dict[str, dict[str, str | None]]:
    """Get devices that have battery but value is unavailable.

    Returns a dictionary where:
    - Key: device_id (or entity_id if device_id not available)
    - Value: dict with 'name', 'area', and 'entity_id'
    """
    _LOGGER.debug("Starting get_devices_without_battery_info")
    devices_without_info: dict[str, dict[str, str | None]] = {}

    all_states = hass.states.async_all()

    for state in all_states:
        # Check if this device has battery attributes but value is unavailable
        if not has_battery_but_unavailable(state):
            continue

        try:
            device_name, device_id, area_name = await get_device_info(hass, state)
        except Exception as err:
            _LOGGER.error(
                "Error getting device info for %s: %s",
                state.entity_id,
                err,
                exc_info=True,
            )
            continue

        # Skip if device belongs to battery_devices_monitor integration
        if device_name is None:
            continue

        # Use device_id if available, otherwise use entity_id as unique key
        unique_key = device_id if device_id else state.entity_id

        # Only add if we haven't already processed this device
        if unique_key not in devices_without_info:
            devices_without_info[unique_key] = {
                "name": device_name,
                "area": area_name,
                "entity_id": state.entity_id,
            }

    _LOGGER.debug("Found %d devices without battery info", len(devices_without_info))
    return devices_without_info
