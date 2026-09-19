"""Tests for battery source classification and deduplication."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT, PERCENTAGE
from homeassistant.core import State

from custom_components.battery_devices_monitor.utils import (
    BatterySource,
    deduplicate_sources,
    get_battery_level,
    has_battery_but_unavailable,
)


def _source(
    entity_id: str,
    *,
    device_id: str,
    integration: str,
    level: float | None,
    priority: int,
    name: str = "Front door lock",
    area: str | None = "Entrance",
    hardware_keys: frozenset[str] = frozenset(),
) -> BatterySource:
    """Create a battery source for a deduplication test."""
    return BatterySource(
        entity_id=entity_id,
        device_id=device_id,
        name=name,
        area=area,
        integration=integration,
        level=level,
        priority=priority,
        is_zigbee=False,
        zigbee_identifier=None,
        hardware_keys=hardware_keys,
    )


def test_percentage_wins_over_low_entity_on_same_device() -> None:
    """A percentage source must replace a low/normal duplicate."""
    devices = deduplicate_sources(
        [
            _source(
                "binary_sensor.august_battery_low",
                device_id="lock",
                integration="legrand",
                level=None,
                priority=10,
            ),
            _source(
                "sensor.august_battery",
                device_id="lock",
                integration="august",
                level=64,
                priority=500,
            ),
        ]
    )

    assert list(devices) == ["lock"]
    assert devices["lock"]["battery_level"] == 64
    assert devices["lock"]["entity_id"] == "sensor.august_battery"
    assert devices["lock"]["source_entity_ids"] == [
        "binary_sensor.august_battery_low",
        "sensor.august_battery",
    ]


def test_battery_type_and_device_identity_are_preserved() -> None:
    """Deduplicated data exposes metadata needed by tracking entities."""
    source = _source(
        "sensor.lock_battery",
        device_id="lock",
        integration="august",
        level=64,
        priority=500,
    )
    source = replace(
        source,
        battery_type="CR123A",
        battery_number=2,
        device_identifiers=frozenset({("august", "LOCK-1")}),
    )

    device = deduplicate_sources([source])["lock"]

    assert device["battery_type"] == "CR123A"
    assert device["battery_number"] == 2
    assert device["device_identifiers"] == {("august", "LOCK-1")}


def test_shared_hardware_identifier_merges_cross_integration_devices() -> None:
    """Different registry devices sharing hardware identity are one device."""
    hardware_key = frozenset({"identifier:aabbccddeeff"})
    devices = deduplicate_sources(
        [
            _source(
                "sensor.ring_battery",
                device_id="ring-device",
                integration="ring",
                level=71,
                priority=500,
                hardware_keys=hardware_key,
            ),
            _source(
                "sensor.ring_mqtt_battery",
                device_id="mqtt-device",
                integration="mqtt",
                level=69,
                priority=500,
                hardware_keys=hardware_key,
            ),
        ]
    )

    assert len(devices) == 1
    assert next(iter(devices.values()))["battery_level"] == 69
    assert next(iter(devices.values()))["source_integrations"] == ["mqtt", "ring"]


def test_exact_name_and_area_merge_unambiguous_integrations() -> None:
    """Exact name+area can join devices exposed by different integrations."""
    devices = deduplicate_sources(
        [
            _source(
                "sensor.august_battery",
                device_id="august-device",
                integration="august",
                level=55,
                priority=500,
            ),
            _source(
                "sensor.legrand_lock_battery",
                device_id="legrand-device",
                integration="legrand",
                level=55,
                priority=500,
            ),
        ]
    )

    assert len(devices) == 1


def test_same_integration_devices_are_not_merged_by_label() -> None:
    """Weak matching must not combine ambiguous devices from one integration."""
    devices = deduplicate_sources(
        [
            _source(
                "sensor.camera_one_battery",
                device_id="camera-one",
                integration="ring",
                level=80,
                priority=500,
            ),
            _source(
                "sensor.camera_two_battery",
                device_id="camera-two",
                integration="ring",
                level=75,
                priority=500,
            ),
        ]
    )

    assert len(devices) == 2


def test_higher_quality_source_wins_before_lower_value() -> None:
    """Source semantics take priority over an arbitrary lower numeric value."""
    devices = deduplicate_sources(
        [
            _source(
                "sensor.lock_battery_attribute",
                device_id="lock",
                integration="mqtt",
                level=5,
                priority=150,
            ),
            _source(
                "sensor.lock_battery",
                device_id="lock",
                integration="august",
                level=40,
                priority=500,
            ),
        ]
    )

    assert devices["lock"]["battery_level"] == 40


@pytest.mark.parametrize(
    "value", [False, True, -1, 101, float("inf"), float("nan"), "invalid"]
)
def test_invalid_percentages_are_rejected(value: Any) -> None:
    """Out-of-range and non-finite readings must not become battery levels."""
    state = State(
        "sensor.lock_battery",
        value,
        {
            ATTR_DEVICE_CLASS: "battery",
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        },
    )

    assert get_battery_level(state) is None
    assert has_battery_but_unavailable(state)


def test_numeric_low_flag_is_not_treated_as_one_percent() -> None:
    """A numeric battery_low flag is status information, not a percentage."""
    state = State("sensor.lock_battery_low", "1")

    assert get_battery_level(state) is None
    assert has_battery_but_unavailable(state)


def test_battery_sensor_percentage_is_accepted() -> None:
    """A standards-compliant battery sensor provides the preferred reading."""
    state = State(
        "sensor.lock_battery",
        "63",
        {
            ATTR_DEVICE_CLASS: "battery",
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        },
    )

    assert get_battery_level(state) == 63
