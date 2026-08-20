"""Event-driven coordinator for Battery Devices Monitor."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import CALLBACK_TYPE, Event, EventStateChangedData, callback
from homeassistant.helpers.device_registry import (
    EVENT_DEVICE_REGISTRY_UPDATED,
    EventDeviceRegistryUpdatedData,
)
from homeassistant.helpers.entity_registry import (
    EVENT_ENTITY_REGISTRY_UPDATED,
    EventEntityRegistryUpdatedData,
)
from homeassistant.helpers.event import (
    async_track_state_added_domain,
    async_track_state_change_event,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .utils import discover_battery_devices, has_battery_attribute

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, State

type BatteryDeviceData = dict[str, dict[str, Any]]

_LOGGER = logging.getLogger(__name__)


class BatteryMonitorCoordinator(DataUpdateCoordinator[BatteryDeviceData]):
    """Coordinate discovery and updates for all battery sources."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the event-driven coordinator."""
        super().__init__(hass, logger=_LOGGER, name=DOMAIN)
        self.entry = entry
        self._event_refresh_task: asyncio.Task[None] | None = None
        self._battery_state_unsub: CALLBACK_TYPE | None = None

    async def _async_update_data(self) -> BatteryDeviceData:
        """Discover and deduplicate all battery-powered devices."""
        data = await discover_battery_devices(self.hass)
        self._replace_battery_state_listener(
            {
                entity_id
                for device in data.values()
                for entity_id in device.get("source_entity_ids", [])
            }
        )
        return data

    def async_start(self) -> None:
        """Listen for battery state and registry changes."""
        self.entry.async_on_unload(self._remove_battery_state_listener)
        self.entry.async_on_unload(
            async_track_state_added_domain(
                self.hass,
                {"binary_sensor", "sensor"},
                self._async_state_changed,
            )
        )
        self.entry.async_on_unload(
            self.hass.bus.async_listen(
                EVENT_ENTITY_REGISTRY_UPDATED,
                self._async_entity_registry_changed,
            )
        )
        self.entry.async_on_unload(
            self.hass.bus.async_listen(
                EVENT_DEVICE_REGISTRY_UPDATED,
                self._async_device_registry_changed,
            )
        )

    @staticmethod
    def _is_battery_state(state: State | None) -> bool:
        """Return whether an event state is a battery source."""
        return state is not None and has_battery_attribute(state)

    @callback
    def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        """Request a refresh only when a battery source changes."""
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if not (self._is_battery_state(old_state) or self._is_battery_state(new_state)):
            return
        self._schedule_event_refresh()

    @callback
    def _replace_battery_state_listener(self, entity_ids: set[str]) -> None:
        """Track only entities that contributed to the latest snapshot."""
        self._remove_battery_state_listener()
        if entity_ids:
            self._battery_state_unsub = async_track_state_change_event(
                self.hass,
                entity_ids,
                self._async_state_changed,
            )

    @callback
    def _remove_battery_state_listener(self) -> None:
        """Remove the current dynamic battery listener."""
        if self._battery_state_unsub:
            self._battery_state_unsub()
            self._battery_state_unsub = None

    @callback
    def _async_entity_registry_changed(
        self, _event: Event[EventEntityRegistryUpdatedData]
    ) -> None:
        """Refresh after an entity registry change."""
        self._schedule_event_refresh()

    @callback
    def _async_device_registry_changed(
        self, _event: Event[EventDeviceRegistryUpdatedData]
    ) -> None:
        """Refresh after a device registry change."""
        self._schedule_event_refresh()

    @callback
    def _schedule_event_refresh(self) -> None:
        """Coalesce same-loop events without the coordinator polling debounce."""
        if self._event_refresh_task and not self._event_refresh_task.done():
            return
        self._event_refresh_task = self.hass.async_create_task(self.async_refresh())
