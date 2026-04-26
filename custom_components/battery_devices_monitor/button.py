"""Button platform for Battery Devices Monitor integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Battery Devices Monitor button."""
    async_add_entities([RescanButton(hass, config_entry)])


class RescanButton(ButtonEntity):
    """Button that triggers an immediate rescan of all battery entities."""

    _attr_has_entity_name = True
    _attr_translation_key = "rescan"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:refresh"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the button."""
        self.hass = hass
        self._config_entry = config_entry
        self._attr_unique_id = f"{DOMAIN}_rescan_button"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="Battery Devices Monitor",
            manufacturer="Geek-MD",
            model="Battery Monitor",
        )

    async def async_press(self) -> None:
        """Handle the button press – trigger an immediate rescan of battery entities."""
        ent_reg = er.async_get(self.hass)
        entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_sensor")
        if entity_id:
            await self.hass.services.async_call(
                "homeassistant",
                "update_entity",
                {"entity_id": entity_id},
                blocking=True,
            )
        else:
            raise HomeAssistantError(
                f"Could not find the {DOMAIN} sensor entity to rescan"
            )
