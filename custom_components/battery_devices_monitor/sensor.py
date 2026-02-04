"""Sensor platform for Battery Devices Monitor integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    ATTR_DEVICES_ABOVE_THRESHOLD,
    ATTR_DEVICES_BELOW_THRESHOLD,
    ATTR_EXCLUDED_DEVICES,
    ATTR_TOTAL_DEVICES,
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
from .utils import get_all_battery_devices

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
        self._excluded_devices: list[dict[str, str]] = []
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
            ATTR_EXCLUDED_DEVICES: self._excluded_devices,
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
        excluded_devices_info = []

        # Get all battery devices using shared utility
        all_devices = get_all_battery_devices(self.hass)

        # Filter out excluded devices and categorize by threshold
        for device_key, device_data in all_devices.items():
            # Check if device is excluded
            if device_key in excluded_devices:
                # Create display info for excluded devices
                display_name = device_data["name"]
                if device_data.get("area"):
                    display_name = f"{device_data['name']} ({device_data['area']})"

                excluded_devices_info.append({
                    "name": display_name,
                    "area": device_data.get("area", ""),
                })
                continue

            # Create display info with name, area, and battery level
            display_name = device_data["name"]
            if device_data.get("area"):
                display_name = f"{device_data['name']} ({device_data['area']})"

            device_info = {
                "name": display_name,
                "battery_level": device_data["battery_level"],
            }

            if device_data["battery_level"] < threshold:
                devices_below_threshold.append(device_info)
                devices_below_info[device_data["entity_id"]] = {
                    "name": display_name,
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
        self._excluded_devices = sorted(
            excluded_devices_info, key=lambda x: x["name"]
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
