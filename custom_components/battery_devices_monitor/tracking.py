"""Shared entities for persistent per-device battery tracking."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.entity import DeviceInfo
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

    @property
    def device_info(self) -> DeviceInfo | None:
        """Attach tracking controls to the physical device being monitored."""
        device = self.tracked_device
        if device and (device["device_identifiers"] or device["device_connections"]):
            return DeviceInfo(
                identifiers=device["device_identifiers"],
                connections=device["device_connections"],
            )

        # Never manufacture a second device for an entity-only source. Such
        # tracking entities remain unassigned until the source gains a real
        # device-registry association.
        return None
