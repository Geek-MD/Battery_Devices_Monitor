"""Button platform for Battery Devices Monitor integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import BatteryMonitorCoordinator
from .tracking import BatteryTrackingEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import BatteryMonitorConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BatteryMonitorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Battery Devices Monitor button."""
    coordinator = config_entry.runtime_data
    known_tracking_ids: set[str] = set()

    @callback
    def async_add_battery_changed_buttons() -> None:
        """Add a battery-changed button for every discovered device."""
        new_tracking_ids = set(coordinator.active_tracking_ids) - known_tracking_ids
        if not new_tracking_ids:
            return
        known_tracking_ids.update(new_tracking_ids)
        async_add_entities(
            BatteryChangedButton(coordinator, tracking_id)
            for tracking_id in sorted(new_tracking_ids)
        )

    async_add_entities([RescanButton(config_entry)])
    async_add_battery_changed_buttons()
    config_entry.async_on_unload(
        coordinator.async_add_listener(async_add_battery_changed_buttons)
    )


class BatteryChangedButton(BatteryTrackingEntity, ButtonEntity):
    """Record that a physical device's battery was changed."""

    _attr_translation_key = "battery_changed"
    _attr_icon = "mdi:battery-sync"

    def __init__(
        self, coordinator: BatteryMonitorCoordinator, tracking_id: str
    ) -> None:
        """Initialize the battery changed button."""
        super().__init__(coordinator, tracking_id)
        self._attr_unique_id = f"{DOMAIN}_{tracking_id}_reset_battery_age"

    async def async_press(self) -> None:
        """Record the current time as the associated battery change."""
        await self.coordinator.async_record_battery_change(self.tracking_id)


class RescanButton(ButtonEntity):
    """Button that triggers an immediate rescan of all battery entities."""

    _attr_has_entity_name = True
    _attr_translation_key = "rescan"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:refresh"

    def __init__(self, config_entry: BatteryMonitorConfigEntry) -> None:
        """Initialize the button."""
        self._coordinator = config_entry.runtime_data
        self._attr_unique_id = f"{DOMAIN}_rescan_button"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="Battery Devices Monitor",
            manufacturer="Geek-MD",
            model="Battery Monitor",
        )

    async def async_press(self) -> None:
        """Handle the button press – trigger an immediate rescan of battery entities."""
        await self._coordinator.async_request_refresh()
