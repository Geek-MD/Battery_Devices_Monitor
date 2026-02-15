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
    ATTR_DEVICES_WITHOUT_BATTERY_INFO,
    ATTR_DEVICES_WITHOUT_BATTERY_INFO_STATUS,
    ATTR_EXCLUDED_DEVICES,
    ATTR_TOTAL_MONITORED_DEVICES,
    CONF_BATTERY_THRESHOLD,
    CONF_EXCLUDED_DEVICES,
    DEFAULT_BATTERY_THRESHOLD,
    DEFAULT_EXCLUDED_DEVICES,
    DOMAIN,
    EVENT_BATTERY_LOW,
    EVENT_BATTERY_UNAVAILABLE,
    SENSOR_NAME,
    STATE_OK,
    STATE_PROBLEM,
)
from .utils import get_all_battery_devices, get_devices_without_battery_info

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
        self._devices_without_battery_info: list[dict[str, str | None]] = []
        self._devices_without_battery_info_status = STATE_OK
        self._total_devices = 0
        self._excluded_devices: list[dict[str, str]] = []
        self._previous_low_devices: set[str] = set()
        self._previous_unavailable_devices: set[str] = set()

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
            ATTR_TOTAL_MONITORED_DEVICES: self._total_devices,
            ATTR_EXCLUDED_DEVICES: self._excluded_devices,
            ATTR_DEVICES_WITHOUT_BATTERY_INFO: self._devices_without_battery_info,
            ATTR_DEVICES_WITHOUT_BATTERY_INFO_STATUS: self._devices_without_battery_info_status,
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
        import logging
        _LOGGER = logging.getLogger(__name__)
        
        _LOGGER.debug("Sensor: Starting async_update")
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
        devices_without_info = []

        # Get all battery devices using shared utility
        try:
            _LOGGER.debug("Sensor: Getting all battery devices")
            all_devices = await get_all_battery_devices(self.hass)
            _LOGGER.debug("Sensor: Retrieved %d battery devices", len(all_devices))
        except Exception as err:
            _LOGGER.error("Sensor: Error getting battery devices: %s", err, exc_info=True)
            all_devices = {}
        
        # Get devices with battery but unavailable info
        try:
            _LOGGER.debug("Sensor: Getting devices without battery info")
            all_devices_without_info = await get_devices_without_battery_info(self.hass)
            _LOGGER.debug("Sensor: Retrieved %d devices without battery info", len(all_devices_without_info))
        except Exception as err:
            _LOGGER.error("Sensor: Error getting devices without battery info: %s", err, exc_info=True)
            all_devices_without_info = {}

        # Filter out excluded devices and categorize by threshold
        for device_key, device_data in all_devices.items():
            # Check if device is excluded
            if device_key in excluded_devices:
                # Create display info for excluded devices
                excluded_devices_info.append({
                    "name": device_data["name"],
                    "area": device_data.get("area", ""),
                })
                continue

            # Create display info with name, area, and battery level
            device_info = {
                "name": device_data["name"],
                "area": device_data.get("area", ""),
                "battery_level": round(device_data["battery_level"]),
            }

            if device_data["battery_level"] < threshold:
                devices_below_threshold.append(device_info)
                # For event firing, use display name with area
                display_name = device_data["name"]
                if device_data.get("area"):
                    display_name = f"{device_data['name']} ({device_data['area']})"
                devices_below_info[device_data["entity_id"]] = {
                    "name": display_name,
                    "battery_level": round(device_data["battery_level"]),
                    "entity_id": device_data["entity_id"],
                }
            else:
                devices_above_threshold.append(device_info)

        # Process devices without battery info (also filter excluded)
        unavailable_devices_event_data = {}
        for device_key, device_data in all_devices_without_info.items():
            # Skip if device is excluded
            if device_key in excluded_devices:
                continue
            
            # entity_id should always be present
            entity_id = device_data.get("entity_id")
            if not entity_id:
                continue
            
            # For display in attributes (without entity_id)
            devices_without_info.append({
                "name": device_data["name"],
                "area": device_data.get("area", ""),
            })
            
            # For event firing, use display name with area
            display_name = device_data["name"]
            if device_data.get("area"):
                display_name = f"{device_data['name']} ({device_data['area']})"
            unavailable_devices_event_data[entity_id] = {
                "name": display_name,
                "entity_id": entity_id,
            }

        # Sort devices_below_threshold: first by battery_level (ascending), then by name (A-Z, case-insensitive), then by area (A-Z, case-insensitive)
        self._devices_below_threshold = sorted(
            devices_below_threshold, key=lambda x: (x["battery_level"], x["name"].lower(), (x["area"] or "").lower())
        )
        # Sort devices_above_threshold: first by battery_level (ascending), then by name (A-Z, case-insensitive), then by area (A-Z, case-insensitive)
        self._devices_above_threshold = sorted(
            devices_above_threshold, key=lambda x: (x["battery_level"], x["name"].lower(), (x["area"] or "").lower())
        )
        # Sort excluded_devices: first by name (A-Z, case-insensitive), then by area (A-Z, case-insensitive)
        self._excluded_devices = sorted(
            excluded_devices_info, key=lambda x: (x["name"].lower(), (x["area"] or "").lower())
        )
        # Sort devices_without_battery_info: first by name (A-Z, case-insensitive), then by area (A-Z, case-insensitive)
        # Note: name should never be None (has fallback), but type system requires the check
        self._devices_without_battery_info = sorted(
            devices_without_info, key=lambda x: ((x["name"] or "").lower(), (x["area"] or "").lower())
        )
        # Include devices without battery info in total count
        self._total_devices = len(devices_below_threshold) + len(
            devices_above_threshold
        ) + len(devices_without_info)

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

        # Fire events for newly detected unavailable battery devices
        current_unavailable_devices = set(unavailable_devices_event_data.keys())
        new_unavailable_devices = current_unavailable_devices - self._previous_unavailable_devices

        for entity_id in new_unavailable_devices:
            device_info = unavailable_devices_event_data[entity_id]
            self.hass.bus.async_fire(
                EVENT_BATTERY_UNAVAILABLE,
                {
                    "entity_id": entity_id,
                    "name": device_info["name"],
                },
            )

        self._previous_unavailable_devices = current_unavailable_devices

        # Update state based on whether any devices have low battery
        if devices_below_threshold:
            self._state = STATE_PROBLEM
        else:
            self._state = STATE_OK

        # Update devices_without_battery_info_status based on whether there are devices without battery info
        if devices_without_info:
            self._devices_without_battery_info_status = STATE_PROBLEM
        else:
            self._devices_without_battery_info_status = STATE_OK
