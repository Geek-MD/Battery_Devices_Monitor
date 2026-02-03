"""Sensor platform for Battery Devices Monitor integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_BATTERY_LEVEL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    ATTR_DEVICES_ABOVE_THRESHOLD,
    ATTR_DEVICES_BELOW_THRESHOLD,
    ATTR_TOTAL_DEVICES,
    CONF_BATTERY_THRESHOLD,
    DEFAULT_BATTERY_THRESHOLD,
    DOMAIN,
    SENSOR_NAME,
    STATE_OK,
    STATE_PROBLEM,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Battery Devices Monitor sensor."""
    async_add_entities([BatteryMonitorSensor(hass, config_entry)], True)


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
        self._devices_below_threshold: list[str] = []
        self._devices_above_threshold: list[str] = []
        self._total_devices = 0

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, any]:
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
            )
        )
        
        # Initial update
        await self.async_update()

    @callback
    def _handle_state_change(self, event) -> None:
        """Handle state changes of battery entities."""
        # Schedule an update when any state changes
        self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        """Update the sensor state."""
        threshold = self._config_entry.options.get(
            CONF_BATTERY_THRESHOLD, DEFAULT_BATTERY_THRESHOLD
        )

        devices_below_threshold = []
        devices_above_threshold = []

        # Scan all entities for battery level attributes
        for state in self.hass.states.async_all():
            # Check if entity has battery_level attribute
            battery_level = state.attributes.get(ATTR_BATTERY_LEVEL)
            
            if battery_level is not None:
                try:
                    battery_value = float(battery_level)
                    
                    # Use friendly_name if available, otherwise use entity_id
                    device_name = state.attributes.get("friendly_name", state.entity_id)
                    
                    if battery_value < threshold:
                        devices_below_threshold.append(device_name)
                    else:
                        devices_above_threshold.append(device_name)
                        
                except (ValueError, TypeError):
                    # Skip if battery_level is not a valid number
                    continue

        self._devices_below_threshold = sorted(devices_below_threshold)
        self._devices_above_threshold = sorted(devices_above_threshold)
        self._total_devices = len(devices_below_threshold) + len(devices_above_threshold)
        
        # Update state based on whether any devices have low battery
        if devices_below_threshold:
            self._state = STATE_PROBLEM
        else:
            self._state = STATE_OK
