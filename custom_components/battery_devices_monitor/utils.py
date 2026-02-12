"""Utility functions for Battery Devices Monitor integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er

from .const import BATTERY_ATTRS, DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State


def get_battery_level(state: State) -> float | None:
    """Get battery level from entity state or attributes.

    Checks multiple attribute names commonly used for battery level,
    and also checks the state value if entity_id contains "battery".
    Returns the battery level as a float, or None if not found.
    """
    # Exclude entities from battery_devices_monitor domain (the monitor itself)
    if state.entity_id.startswith(f"sensor.{DOMAIN}"):
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
    # Exclude entities from battery_devices_monitor domain (the monitor itself)
    if state.entity_id.startswith(f"sensor.{DOMAIN}"):
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


def get_device_info(
    hass: HomeAssistant, state: State
) -> tuple[str, str | None, str | None]:
    """Get device information for a battery entity.

    Returns a tuple of (display_name, device_id, area_name).
    - display_name: The name to display (device name from registry or friendly_name)
    - device_id: The device ID if available
    - area_name: The area name if device is assigned to an area
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
            # Use device name or name_by_user if available
            device_name = device_entry.name_by_user or device_entry.name

            # Get area name if device is assigned to an area
            if device_entry.area_id:
                area_entry = area_reg.async_get_area(device_entry.area_id)
                if area_entry:
                    area_name = area_entry.name

    # If we couldn't get the device name, fall back to the entity's friendly name
    if not device_name:
        device_name = state.attributes.get("friendly_name", state.entity_id)

    return device_name, device_id, area_name


def get_all_battery_devices(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """Get all battery devices with their information.

    Returns a dictionary where:
    - Key: device_id (or entity_id if device_id not available)
    - Value: dict with 'name', 'entity_id', 'area', 'battery_level'
    """
    battery_devices: dict[str, dict[str, Any]] = {}

    for state in hass.states.async_all():
        if not is_battery_device(state):
            continue

        battery_level = get_battery_level(state)
        if battery_level is None:
            continue

        device_name, device_id, area_name = get_device_info(hass, state)

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

    return battery_devices


def get_devices_without_battery_info(hass: HomeAssistant) -> dict[str, dict[str, str | None]]:
    """Get devices that have battery but value is unavailable.

    Returns a dictionary where:
    - Key: device_id (or entity_id if device_id not available)
    - Value: dict with 'name', 'area', and 'entity_id'
    """
    devices_without_info: dict[str, dict[str, str | None]] = {}

    for state in hass.states.async_all():
        # Check if this device has battery attributes but value is unavailable
        if not has_battery_but_unavailable(state):
            continue

        device_name, device_id, area_name = get_device_info(hass, state)

        # Use device_id if available, otherwise use entity_id as unique key
        unique_key = device_id if device_id else state.entity_id

        # Only add if we haven't already processed this device
        if unique_key not in devices_without_info:
            devices_without_info[unique_key] = {
                "name": device_name,
                "area": area_name,
                "entity_id": state.entity_id,
            }

    return devices_without_info
