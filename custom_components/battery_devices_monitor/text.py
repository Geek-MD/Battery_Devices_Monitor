"""Text platform for per-device battery type metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.core import callback

from .const import DOMAIN, MAX_BATTERY_TYPE_LENGTH
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
    """Set up battery type text entities."""
    coordinator = config_entry.runtime_data
    known_tracking_ids: set[str] = set()

    @callback
    def async_add_battery_type_entities() -> None:
        """Add a battery type field for every newly discovered device."""
        new_tracking_ids = set(coordinator.active_tracking_ids) - known_tracking_ids
        if not new_tracking_ids:
            return
        known_tracking_ids.update(new_tracking_ids)
        async_add_entities(
            BatteryTypeText(coordinator, tracking_id)
            for tracking_id in sorted(new_tracking_ids)
        )

    async_add_battery_type_entities()
    config_entry.async_on_unload(
        coordinator.async_add_listener(async_add_battery_type_entities)
    )


class BatteryTypeText(BatteryTrackingEntity, TextEntity):
    """Allow the user to record the battery model used by a device."""

    _attr_translation_key = "battery_type"
    _attr_icon = "mdi:battery-edit"
    _attr_mode = TextMode.TEXT
    _attr_native_min = 0
    _attr_native_max = MAX_BATTERY_TYPE_LENGTH

    def __init__(
        self, coordinator: BatteryMonitorCoordinator, tracking_id: str
    ) -> None:
        """Initialize the battery type text entity."""
        super().__init__(coordinator, tracking_id)
        self._attr_unique_id = f"{DOMAIN}_{tracking_id}_battery_type"

    @property
    def native_value(self) -> str:
        """Return the persisted battery type."""
        return self.coordinator.battery_type(self.tracking_id)

    async def async_set_value(self, value: str) -> None:
        """Persist a new battery type."""
        await self.coordinator.async_set_battery_type(self.tracking_id, value)
