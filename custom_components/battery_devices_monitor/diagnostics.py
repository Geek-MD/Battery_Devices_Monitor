"""Diagnostics support for Battery Devices Monitor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_BATTERY_THRESHOLD,
    CONF_EXCLUDED_DEVICES,
    DEFAULT_BATTERY_THRESHOLD,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import BatteryMonitorConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BatteryMonitorConfigEntry
) -> dict[str, Any]:
    """Return diagnostics, including cross-integration source grouping."""
    excluded = set(entry.options.get(CONF_EXCLUDED_DEVICES, []))
    devices = []
    for device_id, device in entry.runtime_data.data.items():
        source_ids = set(device.get("source_ids", []))
        devices.append(
            {
                "device_id": device_id,
                "name": device["name"],
                "area": device.get("area"),
                "battery_level": device["battery_level"],
                "selected_entity_id": device["entity_id"],
                "source_entity_ids": device.get("source_entity_ids", []),
                "source_integrations": device.get("source_integrations", []),
                "source_count": len(device.get("source_entity_ids", [])),
                "is_excluded": bool(excluded & ({device_id} | source_ids)),
            }
        )

    entity_registry = er.async_get(hass)
    sensor_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_sensor"
    )
    sensor_state = hass.states.get(sensor_entity_id) if sensor_entity_id else None

    return {
        "config_entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "title": entry.title,
        },
        "configuration": {
            "battery_threshold": entry.options.get(
                CONF_BATTERY_THRESHOLD, DEFAULT_BATTERY_THRESHOLD
            ),
            "excluded_devices_count": len(excluded),
        },
        "physical_devices": {
            "total_count": len(devices),
            "devices": sorted(devices, key=lambda item: item["name"].casefold()),
        },
        "sensor": (
            {
                "entity_id": sensor_entity_id,
                "state": sensor_state.state,
                "attributes": dict(sensor_state.attributes),
            }
            if sensor_state
            else None
        ),
    }
