"""The Battery Devices Monitor integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_DEVICES_BELOW_THRESHOLD,
    ATTR_DEVICES_WITHOUT_BATTERY_INFO,
    DOMAIN,
    SERVICE_GET_DEVICES_WITHOUT_BATTERY_INFO,
    SERVICE_GET_LOW_BATTERY_DEVICES,
    SERVICE_RESCAN_BATTERY_DEVICES,
)
from .coordinator import BatteryMonitorCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State

type BatteryMonitorConfigEntry = ConfigEntry[BatteryMonitorCoordinator]

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.TEXT,
]
_ENTITY_SERVICE_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_id})


def _monitor_state(hass: HomeAssistant, call: ServiceCall) -> State:
    """Return and validate the monitor sensor selected by an action call."""
    entity_id = call.data[ATTR_ENTITY_ID]
    state = hass.states.get(entity_id)
    if state is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_not_found",
            translation_placeholders={"entity_id": entity_id},
        )
    return state


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Register integration actions independently of config entries."""

    async def get_low_battery_devices(call: ServiceCall) -> ServiceResponse:
        """Return a formatted list of devices below the threshold."""
        devices = _monitor_state(hass, call).attributes.get(
            ATTR_DEVICES_BELOW_THRESHOLD, []
        )
        output = []
        for device in devices:
            name = device.get("name", "Unknown")
            area = device.get("area")
            level = round(device.get("battery_level", 0))
            label = f"{name} ({area})" if area else name
            output.append(f"{label} - {level}%")
        return {"result": "\n".join(output)}

    async def get_devices_without_battery_info(
        call: ServiceCall,
    ) -> ServiceResponse:
        """Return a formatted list of devices without a percentage."""
        devices = _monitor_state(hass, call).attributes.get(
            ATTR_DEVICES_WITHOUT_BATTERY_INFO, []
        )
        output = []
        for device in devices:
            name = device.get("name", "Unknown")
            area = device.get("area")
            output.append(f"{name} ({area})" if area else name)
        return {"result": "\n".join(output)}

    async def rescan_battery_devices(_call: ServiceCall) -> None:
        """Force all loaded entries to discover battery sources again."""
        entries = [
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.state is ConfigEntryState.LOADED
        ]
        if not entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_configured",
            )
        for entry in entries:
            await entry.runtime_data.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_LOW_BATTERY_DEVICES,
        get_low_battery_devices,
        schema=_ENTITY_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_DEVICES_WITHOUT_BATTERY_INFO,
        get_devices_without_battery_info,
        schema=_ENTITY_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESCAN_BATTERY_DEVICES,
        rescan_battery_devices,
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: BatteryMonitorConfigEntry
) -> bool:
    """Set up Battery Devices Monitor from a config entry."""
    coordinator = BatteryMonitorCoordinator(hass, entry)
    await coordinator.async_initialize_tracking()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    coordinator.async_start()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: BatteryMonitorConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant, entry: BatteryMonitorConfigEntry
) -> None:
    """Reload a config entry after its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
