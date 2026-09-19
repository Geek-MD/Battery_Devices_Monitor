"""Select platform for per-device battery type metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.core import callback

from .const import (
    BATTERY_NUMBER_OPTIONS,
    BATTERY_TYPE_OPTIONS,
    DOMAIN,
    UNKNOWN_BATTERY_TYPE,
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
    """Set up battery type select entities."""
    coordinator = config_entry.runtime_data
    known_tracking_ids: set[str] = set()

    @callback
    def async_add_battery_type_entities() -> None:
        new_tracking_ids = set(coordinator.active_tracking_ids) - known_tracking_ids
        if not new_tracking_ids:
            return
        known_tracking_ids.update(new_tracking_ids)
        async_add_entities(
            entity_class(coordinator, tracking_id)
            for tracking_id in sorted(new_tracking_ids)
            for entity_class in (BatteryTypeSelect, BatteryNumberSelect)
        )

    async_add_battery_type_entities()
    config_entry.async_on_unload(
        coordinator.async_add_listener(async_add_battery_type_entities)
    )


class BatteryTypeSelect(BatteryTrackingEntity, SelectEntity):
    """Expose detected and common battery types as a dropdown."""

    _attr_translation_key = "battery_type"
    _attr_icon = "mdi:battery-edit"

    def __init__(
        self, coordinator: BatteryMonitorCoordinator, tracking_id: str
    ) -> None:
        super().__init__(coordinator, tracking_id)
        self._attr_unique_id = f"{DOMAIN}_{tracking_id}_battery_type_select"

    @property
    def options(self) -> list[str]:
        """Return common types plus a type supplied by the device."""
        current = self.coordinator.battery_type(self.tracking_id)
        options = list(BATTERY_TYPE_OPTIONS)
        if current and current not in options:
            options.append(current)
        return options

    @property
    def current_option(self) -> str:
        """Return the detected or manually selected battery type."""
        return self.coordinator.battery_type(self.tracking_id) or UNKNOWN_BATTERY_TYPE

    async def async_select_option(self, option: str) -> None:
        """Persist the selected type; unknown clears the stored selection."""
        await self.coordinator.async_set_battery_type(
            self.tracking_id, "" if option == UNKNOWN_BATTERY_TYPE else option
        )


class BatteryNumberSelect(BatteryTrackingEntity, SelectEntity):
    """Select how many batteries the physical device requires."""

    _attr_translation_key = "battery_number"
    _attr_icon = "mdi:counter"
    _attr_options = list(BATTERY_NUMBER_OPTIONS)

    def __init__(
        self, coordinator: BatteryMonitorCoordinator, tracking_id: str
    ) -> None:
        super().__init__(coordinator, tracking_id)
        self._attr_unique_id = f"{DOMAIN}_{tracking_id}_battery_number"

    @property
    def current_option(self) -> str:
        """Return the detected or manually selected battery count."""
        number = self.coordinator.battery_number(self.tracking_id)
        return str(number) if number is not None else UNKNOWN_BATTERY_TYPE

    async def async_select_option(self, option: str) -> None:
        """Persist the selected battery count."""
        await self.coordinator.async_set_battery_number(
            self.tracking_id,
            None if option == UNKNOWN_BATTERY_TYPE else int(option),
        )
