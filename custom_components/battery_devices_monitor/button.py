"""Button platform for Battery Devices Monitor integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

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
    async_add_entities([RescanButton(config_entry)])


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
