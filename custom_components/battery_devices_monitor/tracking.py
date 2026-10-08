"""Shared entities for persistent per-device battery tracking."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import BatteryMonitorCoordinator


class BatteryTrackingEntity(CoordinatorEntity[BatteryMonitorCoordinator]):
    """Base entity bound to one deduplicated physical device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: BatteryMonitorCoordinator, tracking_id: str
    ) -> None:
        """Initialize a stable per-device tracking entity."""
        super().__init__(coordinator)
        self.tracking_id = tracking_id

    @property
    def tracked_device(self) -> dict[str, Any] | None:
        """Return the current deduplicated device represented by this entity."""
        return self.coordinator.device_for_tracking_id(self.tracking_id)

    @property
    def available(self) -> bool:
        """Return whether the physical device is currently discovered."""
        return super().available and self.tracked_device is not None

    async def async_added_to_hass(self) -> None:
        """Assign this entity to the already existing physical device.

        ``DeviceInfo`` is intentionally not used here.  Returning another
        integration's identifiers from ``device_info`` makes the device
        registry add this config entry to that device and, in some real-world
        registries, can manufacture a duplicate device.  Updating the entity
        registry's ``device_id`` is the same direct-assignment pattern used by
        integrations which add helper entities to existing devices.
        """
        await super().async_added_to_hass()
        device = self.tracked_device
        source_device_id = device.get("device_id") if device else None
        if source_device_id is None:
            return

        entity_registry = er.async_get(self.hass)
        registry_entry = entity_registry.async_get(self.entity_id)
        if registry_entry and registry_entry.device_id != source_device_id:
            entity_registry.async_update_entity(
                self.entity_id, device_id=source_device_id
            )
