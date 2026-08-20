"""End-to-end tests inside Home Assistant."""

from __future__ import annotations

from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.battery_devices_monitor.const import (
    ATTR_DEVICES_ABOVE_THRESHOLD,
    ATTR_DEVICES_BELOW_THRESHOLD,
    ATTR_TOTAL_MONITORED_DEVICES,
    CONF_BATTERY_THRESHOLD,
    CONF_EXCLUDED_DEVICES,
    DOMAIN,
    EVENT_BATTERY_LOW,
)


async def test_setup_deduplication_and_reactive_update(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Set up, deduplicate cross-integration sources, and react to changes."""
    area_registry = ar.async_get(hass)
    area = area_registry.async_create("Entrance")

    august_entry = MockConfigEntry(domain="august")
    august_entry.add_to_hass(hass)
    legrand_entry = MockConfigEntry(domain="legrand")
    legrand_entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    august_device = device_registry.async_get_or_create(
        config_entry_id=august_entry.entry_id,
        identifiers={("august", "LOCK-12345")},
        name="Front door lock",
    )
    legrand_device = device_registry.async_get_or_create(
        config_entry_id=legrand_entry.entry_id,
        identifiers={("legrand", "LOCK-12345")},
        name="Front door lock",
    )
    device_registry.async_update_device(august_device.id, area_id=area.id)
    device_registry.async_update_device(legrand_device.id, area_id=area.id)

    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        "sensor",
        "august",
        "august-lock-battery",
        suggested_object_id="front_door_lock_battery",
        device_id=august_device.id,
    )
    entity_registry.async_get_or_create(
        "binary_sensor",
        "legrand",
        "legrand-lock-battery-low",
        suggested_object_id="front_door_lock_battery_low",
        device_id=legrand_device.id,
    )
    hass.states.async_set(
        "sensor.front_door_lock_battery",
        "64",
        {
            "device_class": "battery",
            "unit_of_measurement": PERCENTAGE,
            "friendly_name": "August battery",
        },
    )
    hass.states.async_set(
        "binary_sensor.front_door_lock_battery_low",
        "off",
        {"device_class": "battery", "friendly_name": "August battery low"},
    )

    events = []
    hass.bus.async_listen(EVENT_BATTERY_LOW, events.append)
    monitor_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        options={CONF_BATTERY_THRESHOLD: 20, CONF_EXCLUDED_DEVICES: []},
    )
    monitor_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(monitor_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.battery_monitor_status")
    assert state is not None
    assert state.state == "OK"
    assert state.attributes[ATTR_DEVICES_ABOVE_THRESHOLD] == [
        {"name": "Front door lock", "area": "Entrance", "battery_level": 64}
    ]
    assert state.attributes[ATTR_DEVICES_BELOW_THRESHOLD] == []
    assert events == []

    ring_entry = MockConfigEntry(domain="ring")
    ring_entry.add_to_hass(hass)
    ring_device = device_registry.async_get_or_create(
        config_entry_id=ring_entry.entry_id,
        identifiers={("ring", "CAMERA-98765")},
        name="Garden camera",
    )
    entity_registry.async_get_or_create(
        "sensor",
        "ring",
        "garden-camera-battery",
        suggested_object_id="garden_camera_battery",
        device_id=ring_device.id,
    )
    hass.states.async_set(
        "sensor.garden_camera_battery",
        "90",
        {"device_class": "battery", "unit_of_measurement": PERCENTAGE},
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.battery_monitor_status")
    assert state is not None
    assert state.attributes[ATTR_TOTAL_MONITORED_DEVICES] == 2

    hass.states.async_set(
        "sensor.front_door_lock_battery",
        "10",
        {
            "device_class": "battery",
            "unit_of_measurement": PERCENTAGE,
            "friendly_name": "August battery",
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.battery_monitor_status")
    assert state is not None
    assert state.state == "Problem"
    assert state.attributes[ATTR_DEVICES_BELOW_THRESHOLD][0]["battery_level"] == 10
    assert len(events) == 1
