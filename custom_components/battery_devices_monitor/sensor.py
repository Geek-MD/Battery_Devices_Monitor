"""Sensor platform for Battery Devices Monitor integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    ATTR_DEVICES_ABOVE_THRESHOLD,
    ATTR_DEVICES_BELOW_THRESHOLD,
    ATTR_TOTAL_DEVICES,
    BATTERY_ATTRS,
    CONF_BATTERY_THRESHOLD,
    CONF_EXCLUDED_DEVICES,
    DEFAULT_BATTERY_THRESHOLD,
    DEFAULT_EXCLUDED_DEVICES,
    DOMAIN,
    EVENT_BATTERY_LOW,
    SENSOR_NAME,
    STATE_OK,
    STATE_PROBLEM,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Battery Devices Monitor sensor."""
    async_add_entities(
        [BatteryMonitorSensor(hass, config_entry)], update_before_add=True
    )


class BatteryMonitorSensor(SensorEntity):
    """Representation of a Battery Monitor sensor."""

    _attr_has_entity_name = True
    _attr_name = SENSOR_NAME

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._attr_unique_id = f"{DOMAIN}_sensor"
        self._state = STATE_OK
        self._devices_below_threshold: list[dict[str, Any]] = []
        self._devices_above_threshold: list[dict[str, Any]] = []
        self._total_devices = 0
        self._previous_low_devices: set[str] = set()

        # Device info to allow area assignment
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="Battery Devices Monitor",
            manufacturer="Geek-MD",
            model="Battery Monitor",
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            ATTR_DEVICES_BELOW_THRESHOLD: self._devices_below_threshold,
            ATTR_DEVICES_ABOVE_THRESHOLD: self._devices_above_threshold,
            ATTR_TOTAL_DEVICES: self._total_devices,
        }

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        if self._state == STATE_PROBLEM:
            return "mdi:battery-alert"
        return "mdi:battery-check"

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        await super().async_added_to_hass()

        # Track all state changes to detect battery entities
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                "*",
                self._handle_state_change,
            ),
        )

        # Initial update
        await self.async_update()

    @callback
    def _handle_state_change(self, event: Event) -> None:
        """Handle state changes of battery entities."""
        # Schedule an update when any state changes
        self.async_schedule_update_ha_state(force_refresh=True)

    def _get_battery_level(self, attributes: dict[str, Any]) -> float | None:
        """Get battery level from entity attributes.

        Checks multiple attribute names commonly used for battery level.
        Returns the battery level as a float, or None if not found.
        """
        for attr_name in BATTERY_ATTRS:
            battery_value = attributes.get(attr_name)
            if battery_value is not None:
                try:
                    return float(battery_value)
                except (ValueError, TypeError):
                    continue
        return None

    def _is_battery_entity(self, entity_id: str) -> bool:
        """Check if entity ID suggests it's a battery-related entity.

        Uses heuristic to identify battery entities by checking if
        'battery' appears in the entity ID (case-insensitive).
        """
        return "battery" in entity_id.lower()

    async def async_update(self) -> None:
        """Update the sensor state."""
        threshold = self._config_entry.options.get(
            CONF_BATTERY_THRESHOLD,
            DEFAULT_BATTERY_THRESHOLD,
        )
        excluded_devices = self._config_entry.options.get(
            CONF_EXCLUDED_DEVICES,
            DEFAULT_EXCLUDED_DEVICES,
        )

        devices_below_threshold = []
        devices_above_threshold = []
        devices_below_info = {}

        # Get registries to look up device information
        entity_reg = er.async_get(self.hass)
        device_reg = dr.async_get(self.hass)

        # Track devices we've already processed to avoid duplicates
        processed_devices: dict[str, dict[str, Any]] = {}

        # Scan all entities for battery level attributes
        for state in self.hass.states.async_all():
            # Skip excluded devices
            if state.entity_id in excluded_devices:
                continue

            # Check if entity has any battery attribute
            battery_level = self._get_battery_level(state.attributes)

            # Heuristic: If entity_id contains "battery" and we haven't found
            # a battery level yet, try to use the state value
            if battery_level is None and self._is_battery_entity(state.entity_id):
                try:
                    potential_level = float(state.state)
                    # Validate range - battery levels should be between 0 and 100
                    if 0 <= potential_level <= 100:
                        battery_level = potential_level
                except (ValueError, TypeError):
                    battery_level = None

            if battery_level is not None:
                # Get the device name from the device registry
                device_name = None
                device_id = None

                # Look up entity in the entity registry
                entity_entry = entity_reg.async_get(state.entity_id)
                if entity_entry and entity_entry.device_id:
                    device_id = entity_entry.device_id
                    device_entry = device_reg.async_get(device_id)
                    if device_entry:
                        # Use device name or name_by_user if available
                        device_name = device_entry.name_by_user or device_entry.name

                # If we couldn't get the device name, fall back to the entity's friendly name
                if not device_name:
                    device_name = state.attributes.get("friendly_name", state.entity_id)

                # Use device_id if available, otherwise use entity_id as a unique key
                unique_key = device_id if device_id else state.entity_id

                # Check if we've already processed this device
                # Keep the entry with the highest battery level if duplicate
                if unique_key in processed_devices:
                    existing_level = processed_devices[unique_key]["battery_level"]
                    # Keep the higher battery level (some devices report multiple battery entities)
                    if battery_level > existing_level:
                        processed_devices[unique_key] = {
                            "name": device_name,
                            "battery_level": battery_level,
                            "entity_id": state.entity_id,
                        }
                else:
                    processed_devices[unique_key] = {
                        "name": device_name,
                        "battery_level": battery_level,
                        "entity_id": state.entity_id,
                    }

        # Now categorize devices by threshold
        for device_id, device_data in processed_devices.items():
            device_info = {
                "name": device_data["name"],
                "battery_level": device_data["battery_level"],
            }

            if device_data["battery_level"] < threshold:
                devices_below_threshold.append(device_info)
                devices_below_info[device_data["entity_id"]] = {
                    "name": device_data["name"],
                    "battery_level": device_data["battery_level"],
                    "entity_id": device_data["entity_id"],
                }
            else:
                devices_above_threshold.append(device_info)

        # Sort by name
        self._devices_below_threshold = sorted(
            devices_below_threshold, key=lambda x: x["name"]
        )
        self._devices_above_threshold = sorted(
            devices_above_threshold, key=lambda x: x["name"]
        )
        self._total_devices = len(devices_below_threshold) + len(
            devices_above_threshold
        )

        # Fire events for newly detected low battery devices
        current_low_devices = set(devices_below_info.keys())
        new_low_devices = current_low_devices - self._previous_low_devices

        for entity_id in new_low_devices:
            device_info = devices_below_info[entity_id]
            self.hass.bus.async_fire(
                EVENT_BATTERY_LOW,
                {
                    "entity_id": entity_id,
                    "name": device_info["name"],
                    "battery_level": device_info["battery_level"],
                    "threshold": threshold,
                },
            )

        self._previous_low_devices = current_low_devices

        # Update state based on whether any devices have low battery
        if devices_below_threshold:
            self._state = STATE_PROBLEM
        else:
            self._state = STATE_OK
