"""Event-driven coordinator for Battery Devices Monitor."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import logging
import re
from typing import TYPE_CHECKING, Any, TypedDict
from uuid import uuid4

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
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION
from .utils import discover_battery_devices, has_battery_attribute

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, State

type BatteryDeviceData = dict[str, dict[str, Any]]


class BatteryTrackingRecord(TypedDict):
    """Persistent metadata for one deduplicated physical device."""

    installed_at: str
    battery_type: str
    battery_number: int | None
    source_ids: list[str]


_LOGGER = logging.getLogger(__name__)
_QUANTIFIED_BATTERY_TYPE = re.compile(r"^\s*(\d+)\s*[x×]\s*(.+?)\s*$", re.I)


def _split_battery_type_quantity(value: str) -> tuple[str, int | None]:
    """Separate legacy values such as ``3x AA`` into type and quantity."""
    normalized = value.strip()
    match = _QUANTIFIED_BATTERY_TYPE.fullmatch(normalized)
    if match is None:
        return normalized, None

    quantity = int(match.group(1))
    if not 1 <= quantity <= 16:
        return normalized, None
    return match.group(2).strip(), quantity


class BatteryMonitorCoordinator(DataUpdateCoordinator[BatteryDeviceData]):
    """Coordinate discovery and updates for all battery sources."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the event-driven coordinator."""
        super().__init__(hass, logger=_LOGGER, name=DOMAIN)
        self.entry = entry
        self._event_refresh_task: asyncio.Task[None] | None = None
        self._battery_state_unsub: CALLBACK_TYPE | None = None
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry.entry_id}"
        )
        self._storage_lock = asyncio.Lock()
        self._tracking_records: dict[str, BatteryTrackingRecord] = {}
        self._active_tracking: dict[str, str] = {}

    async def async_initialize_tracking(self) -> None:
        """Load persistent battery replacement dates and battery types."""
        stored = await self._store.async_load()
        records = stored.get("records", {}) if isinstance(stored, dict) else {}
        if not isinstance(records, dict):
            return

        migrated = False
        for tracking_id, value in records.items():
            if not isinstance(tracking_id, str) or not isinstance(value, dict):
                continue
            installed_at = value.get("installed_at")
            battery_type = value.get("battery_type", "")
            battery_number = value.get("battery_number")
            source_ids = value.get("source_ids", [])
            if (
                isinstance(installed_at, str)
                and isinstance(battery_type, str)
                and (
                    battery_number is None
                    or (
                        isinstance(battery_number, int)
                        and not isinstance(battery_number, bool)
                        and 1 <= battery_number <= 16
                    )
                )
                and isinstance(source_ids, list)
                and all(isinstance(source_id, str) for source_id in source_ids)
            ):
                try:
                    datetime.fromisoformat(installed_at)
                except ValueError:
                    continue
                normalized_type, type_quantity = _split_battery_type_quantity(
                    battery_type
                )
                if normalized_type != battery_type:
                    battery_type = normalized_type
                    migrated = True
                if battery_number is None and type_quantity is not None:
                    battery_number = type_quantity
                    migrated = True
                self._tracking_records[tracking_id] = {
                    "installed_at": installed_at,
                    "battery_type": battery_type,
                    "battery_number": battery_number,
                    "source_ids": source_ids,
                }
        if migrated:
            await self._async_save_tracking()

    async def _async_update_data(self) -> BatteryDeviceData:
        """Discover and deduplicate all battery-powered devices."""
        data = await discover_battery_devices(self.hass)
        async with self._storage_lock:
            if self._reconcile_tracking(data):
                await self._async_save_tracking()
        self._replace_battery_state_listener(
            {
                entity_id
                for device in data.values()
                for entity_id in device.get("source_entity_ids", [])
            }
        )
        return data

    @staticmethod
    def _device_aliases(device_id: str, device: dict[str, Any]) -> set[str]:
        """Return all known identities for a deduplicated physical device."""
        return {
            device_id,
            *device.get("source_ids", []),
            *device.get("source_entity_ids", []),
        }

    def _reconcile_tracking(self, data: BatteryDeviceData) -> bool:
        """Match current devices to persisted records across source changes."""
        changed = False
        unused_tracking_ids = set(self._tracking_records)
        active_tracking: dict[str, str] = {}

        for device_id, device in sorted(data.items()):
            aliases = self._device_aliases(device_id, device)
            matches = [
                tracking_id
                for tracking_id in unused_tracking_ids
                if aliases & set(self._tracking_records[tracking_id]["source_ids"])
            ]

            if matches:
                tracking_id = max(
                    matches,
                    key=lambda item: self._tracking_records[item]["installed_at"],
                )
                record = self._tracking_records[tracking_id]
                for duplicate_id in matches:
                    if duplicate_id == tracking_id:
                        continue
                    duplicate = self._tracking_records.pop(duplicate_id)
                    aliases.update(duplicate["source_ids"])
                    if not record["battery_type"] and duplicate["battery_type"]:
                        record["battery_type"] = duplicate["battery_type"]
                    unused_tracking_ids.discard(duplicate_id)
                    changed = True
            else:
                tracking_id = uuid4().hex
                record = {
                    "installed_at": datetime.now(UTC).isoformat(),
                    "battery_type": "",
                    "battery_number": None,
                    "source_ids": [],
                }
                self._tracking_records[tracking_id] = record
                changed = True

            detected_type = device.get("battery_type")
            type_quantity = None
            if not record["battery_type"] and detected_type:
                normalized_type, type_quantity = _split_battery_type_quantity(
                    detected_type
                )
                record["battery_type"] = normalized_type
                changed = True

            detected_number = device.get("battery_number")
            if record["battery_number"] is None and detected_number:
                record["battery_number"] = detected_number
                changed = True
            elif record["battery_number"] is None and type_quantity is not None:
                record["battery_number"] = type_quantity
                changed = True

            normalized_aliases = sorted(aliases | set(record["source_ids"]))
            if record["source_ids"] != normalized_aliases:
                record["source_ids"] = normalized_aliases
                changed = True
            unused_tracking_ids.discard(tracking_id)
            active_tracking[tracking_id] = device_id

        self._active_tracking = active_tracking
        return changed

    async def _async_save_tracking(self) -> None:
        """Persist tracking metadata."""
        await self._store.async_save({"records": self._tracking_records})

    @property
    def active_tracking_ids(self) -> tuple[str, ...]:
        """Return stable tracking IDs for currently discovered devices."""
        return tuple(sorted(self._active_tracking))

    def device_for_tracking_id(self, tracking_id: str) -> dict[str, Any] | None:
        """Return the current physical-device data for a tracking ID."""
        device_id = self._active_tracking.get(tracking_id)
        return self.data.get(device_id) if device_id else None

    def battery_type(self, tracking_id: str) -> str:
        """Return the user-entered battery type."""
        record = self._tracking_records.get(tracking_id)
        return record["battery_type"] if record else ""

    def battery_number(self, tracking_id: str) -> int | None:
        """Return the detected or user-selected battery count."""
        record = self._tracking_records.get(tracking_id)
        return record["battery_number"] if record else None

    def battery_age_days(self, tracking_id: str) -> int | None:
        """Return complete days since the battery counter was started."""
        record = self._tracking_records.get(tracking_id)
        if record is None:
            return None
        installed_at = datetime.fromisoformat(record["installed_at"])
        if installed_at.tzinfo is None:
            installed_at = installed_at.replace(tzinfo=UTC)
        return max(0, (datetime.now(UTC) - installed_at).days)

    def last_battery_change(self, tracking_id: str) -> datetime | None:
        """Return the timestamp of the last recorded battery change."""
        record = self._tracking_records.get(tracking_id)
        if record is None:
            return None
        changed_at = datetime.fromisoformat(record["installed_at"])
        return (
            changed_at.replace(tzinfo=UTC) if changed_at.tzinfo is None else changed_at
        )

    async def async_record_battery_change(self, tracking_id: str) -> None:
        """Record the current time as a device's latest battery change."""
        async with self._storage_lock:
            record = self._tracking_records.get(tracking_id)
            if record is None:
                return
            record["installed_at"] = datetime.now(UTC).isoformat()
            await self._async_save_tracking()
        self.async_update_listeners()

    async def async_set_battery_type(self, tracking_id: str, value: str) -> None:
        """Persist the battery type entered for a device."""
        async with self._storage_lock:
            record = self._tracking_records.get(tracking_id)
            if record is None:
                return
            normalized_type, type_quantity = _split_battery_type_quantity(value)
            record["battery_type"] = normalized_type
            if record["battery_number"] is None and type_quantity is not None:
                record["battery_number"] = type_quantity
            await self._async_save_tracking()
        self.async_update_listeners()

    async def async_set_battery_number(
        self, tracking_id: str, value: int | None
    ) -> None:
        """Persist the number of batteries required by a device."""
        async with self._storage_lock:
            record = self._tracking_records.get(tracking_id)
            if record is None:
                return
            record["battery_number"] = value
            await self._async_save_tracking()
        self.async_update_listeners()

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
