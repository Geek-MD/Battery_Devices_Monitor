"""Sensor platform for Battery Devices Monitor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    EVENT_ZIGBEE_BATTERY_UNAVAILABLE,
    SENSOR_NAME,
    STATE_OK,
    STATE_PROBLEM,
    STATE_WARNING,
)
from .coordinator import BatteryMonitorCoordinator
from .tracking import BatteryTrackingEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import BatteryMonitorConfigEntry


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: BatteryMonitorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Battery Devices Monitor sensor."""
    coordinator = config_entry.runtime_data
    known_tracking_ids: set[str] = set()

    @callback
    def async_add_last_change_entities() -> None:
        """Add a battery-change timestamp for every discovered device."""
        new_tracking_ids = set(coordinator.active_tracking_ids) - known_tracking_ids
        if not new_tracking_ids:
            return
        known_tracking_ids.update(new_tracking_ids)
        async_add_entities(
            LastBatteryChangeSensor(coordinator, tracking_id)
            for tracking_id in sorted(new_tracking_ids)
        )

    async_add_entities([BatteryMonitorSensor(config_entry)])
    async_add_last_change_entities()
    config_entry.async_on_unload(
        coordinator.async_add_listener(async_add_last_change_entities)
    )


class LastBatteryChangeSensor(BatteryTrackingEntity, SensorEntity):
    """Report when a device's battery was last changed."""

    _attr_translation_key = "last_battery_change"
    _attr_icon = "mdi:battery-clock"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, coordinator: BatteryMonitorCoordinator, tracking_id: str
    ) -> None:
        """Initialize the last battery change sensor."""
        super().__init__(coordinator, tracking_id)
        self._attr_unique_id = f"{DOMAIN}_{tracking_id}_battery_age"

    @property
    def native_value(self) -> datetime | None:
        """Return the timestamp of the last recorded battery replacement."""
        return self.coordinator.last_battery_change(self.tracking_id)


class BatteryMonitorSensor(CoordinatorEntity[BatteryMonitorCoordinator], SensorEntity):
    """Represent the deduplicated overall battery status."""

    # Keep the established sensor.battery_monitor_status entity ID.
    _attr_has_entity_name = False
    _attr_name = SENSOR_NAME

    def __init__(self, config_entry: BatteryMonitorConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry.runtime_data)
        self._config_entry = config_entry
        self._attr_unique_id = f"{DOMAIN}_sensor"
        self._state = STATE_OK
        self._devices_below_threshold: list[dict[str, Any]] = []
        self._devices_above_threshold: list[dict[str, Any]] = []
        self._devices_without_battery_info: list[dict[str, Any]] = []
        self._devices_without_battery_info_status = STATE_OK
        self._total_devices = 0
        self._excluded_devices: list[dict[str, Any]] = []
        self._previous_low_devices: set[str] = set()
        self._previous_unavailable_devices: set[str] = set()
        self._previous_unavailable_zigbee_devices: set[str] = set()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="Battery Devices Monitor",
            manufacturer="Geek-MD",
            model="Battery Monitor",
        )
        self._process_coordinator_data(fire_events=False)

    @property
    def native_value(self) -> str:
        """Return the overall battery state."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return deduplicated device lists."""
        return {
            ATTR_DEVICES_BELOW_THRESHOLD: self._devices_below_threshold,
            ATTR_DEVICES_ABOVE_THRESHOLD: self._devices_above_threshold,
            ATTR_TOTAL_MONITORED_DEVICES: self._total_devices,
            ATTR_EXCLUDED_DEVICES: self._excluded_devices,
            ATTR_DEVICES_WITHOUT_BATTERY_INFO: self._devices_without_battery_info,
            ATTR_DEVICES_WITHOUT_BATTERY_INFO_STATUS: (
                self._devices_without_battery_info_status
            ),
        }

    @property
    def icon(self) -> str:
        """Return an icon matching the overall state."""
        if self._state == STATE_PROBLEM:
            return "mdi:battery-alert"
        if self._state == STATE_WARNING:
            return "mdi:battery-alert-variant-outline"
        return "mdi:battery-check"

    @staticmethod
    def _display_device(device: dict[str, Any]) -> dict[str, Any]:
        """Return the stable public device representation."""
        return {
            "name": device["name"],
            "area": device.get("area") or "",
            "battery_level": (
                round(device["battery_level"])
                if device["battery_level"] is not None
                else None
            ),
        }

    def _is_excluded(self, device: dict[str, Any], excluded: set[str]) -> bool:
        """Support exclusions created before and after cross-source grouping."""
        return bool(
            excluded
            & {
                device["id"],
                *device.get("source_ids", []),
                *device.get("source_entity_ids", []),
            }
        )

    def _fire_events(
        self,
        low_devices: dict[str, dict[str, Any]],
        unavailable_devices: dict[str, dict[str, Any]],
        threshold: int,
    ) -> None:
        """Fire one event per newly problematic physical device."""
        current_low = set(low_devices)
        for device_id in current_low - self._previous_low_devices:
            device = low_devices[device_id]
            self.hass.bus.async_fire(
                EVENT_BATTERY_LOW,
                {
                    "id": device_id,
                    "device_id": device_id,
                    "entity_id": device["entity_id"],
                    "name": device["display_name"],
                    "battery_level": round(device["battery_level"]),
                    "threshold": threshold,
                },
            )
        self._previous_low_devices = current_low

        current_unavailable = set(unavailable_devices)
        for device_id in current_unavailable - self._previous_unavailable_devices:
            device = unavailable_devices[device_id]
            self.hass.bus.async_fire(
                EVENT_BATTERY_UNAVAILABLE,
                {
                    "id": device_id,
                    "device_id": device_id,
                    "entity_id": device["entity_id"],
                    "name": device["display_name"],
                },
            )
        self._previous_unavailable_devices = current_unavailable

        zigbee_devices = {
            device_id: device
            for device_id, device in unavailable_devices.items()
            if device.get("is_zigbee")
        }
        current_zigbee = set(zigbee_devices)
        for device_id in current_zigbee - self._previous_unavailable_zigbee_devices:
            device = zigbee_devices[device_id]
            self.hass.bus.async_fire(
                EVENT_ZIGBEE_BATTERY_UNAVAILABLE,
                {
                    "id": device_id,
                    "device_id": device_id,
                    "entity_id": device["entity_id"],
                    "name": device["display_name"],
                    "zigbee_identifier": device.get("zigbee_identifier"),
                },
            )
        self._previous_unavailable_zigbee_devices = current_zigbee

    def _process_coordinator_data(self, *, fire_events: bool) -> None:
        """Categorize a deduplicated coordinator snapshot."""
        threshold = self._config_entry.options.get(
            CONF_BATTERY_THRESHOLD, DEFAULT_BATTERY_THRESHOLD
        )
        excluded = set(
            self._config_entry.options.get(
                CONF_EXCLUDED_DEVICES, DEFAULT_EXCLUDED_DEVICES
            )
        )
        below: list[dict[str, Any]] = []
        above: list[dict[str, Any]] = []
        unavailable: list[dict[str, Any]] = []
        excluded_devices: list[dict[str, Any]] = []
        low_event_data: dict[str, dict[str, Any]] = {}
        unavailable_event_data: dict[str, dict[str, Any]] = {}

        for device_id, device in self.coordinator.data.items():
            if self._is_excluded(device, excluded):
                excluded_devices.append(
                    {"name": device["name"], "area": device.get("area") or ""}
                )
                continue

            display_name = device["name"]
            if device.get("area"):
                display_name = f"{display_name} ({device['area']})"
            event_device = {**device, "display_name": display_name}

            if device["battery_level"] is None:
                unavailable.append(self._display_device(device))
                unavailable_event_data[device_id] = event_device
            elif device["battery_level"] < threshold:
                below.append(self._display_device(device))
                low_event_data[device_id] = event_device
            else:
                above.append(self._display_device(device))

        def battery_sort(item: dict[str, Any]) -> tuple[float, str, str]:
            return (
                item["battery_level"],
                item["name"].casefold(),
                item["area"].casefold(),
            )

        def name_sort(item: dict[str, Any]) -> tuple[str, str]:
            return item["name"].casefold(), item["area"].casefold()

        self._devices_below_threshold = sorted(below, key=battery_sort)
        self._devices_above_threshold = sorted(above, key=battery_sort)
        self._devices_without_battery_info = sorted(unavailable, key=name_sort)
        self._excluded_devices = sorted(excluded_devices, key=name_sort)
        self._total_devices = len(below) + len(above) + len(unavailable)
        self._devices_without_battery_info_status = (
            STATE_WARNING if unavailable else STATE_OK
        )
        self._state = (
            STATE_PROBLEM if below else STATE_WARNING if unavailable else STATE_OK
        )

        if fire_events:
            self._fire_events(low_event_data, unavailable_event_data, threshold)
        else:
            self._previous_low_devices = set(low_event_data)
            self._previous_unavailable_devices = set(unavailable_event_data)
            self._previous_unavailable_zigbee_devices = {
                device_id
                for device_id, device in unavailable_event_data.items()
                if device.get("is_zigbee")
            }

    def _handle_coordinator_update(self) -> None:
        """Handle a battery-source update."""
        self._process_coordinator_data(fire_events=True)
        super()._handle_coordinator_update()
