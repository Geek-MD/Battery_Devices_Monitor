"""Tests for persistent battery tracking metadata."""

from __future__ import annotations

import pytest

from custom_components.battery_devices_monitor.coordinator import (
    _split_battery_type_quantity,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("3x AA", ("AA", 3)),
        ("2 × AAA", ("AAA", 2)),
        ("CR2032", ("CR2032", None)),
        ("20x AA", ("20x AA", None)),
    ],
)
def test_split_battery_type_quantity(
    value: str, expected: tuple[str, int | None]
) -> None:
    """Legacy combined values are split only for valid quantities."""
    assert _split_battery_type_quantity(value) == expected
