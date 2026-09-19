"""Battery discovery, source selection, and physical-device deduplication."""

from __future__ import annotations

from dataclasses import dataclass, replace
import logging
import math
import re
from typing import TYPE_CHECKING, Any

from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT, PERCENTAGE
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from .const import (
    BATTERY_ATTRS,
    BATTERY_DEVICE_CLASS,
    BATTERY_NUMBER_ATTRS,
    BATTERY_TYPE_ATTRS,
    DOMAIN,
    EXCLUDED_ENTITY_DOMAINS,
    ZIGBEE_INTEGRATION_DOMAINS,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant, State

_LOGGER = logging.getLogger(__name__)

_LOW_BATTERY_MARKERS = ("battery_low", "low_battery", "battery_status")
_NON_PERCENTAGE_MARKERS = ("battery_voltage", "battery_volts", "battery_health")
_UNAVAILABLE_STATES = {"", "none", "unknown", "unavailable"}
_BINARY_BATTERY_STATES = {"0", "1", "false", "low", "normal", "off", "on", "true"}
_IDENTIFIER_NORMALIZER = re.compile(r"[^a-z0-9]")
_POWER_SOURCE_ATTRS = ("power_source", "power_supply", "power_type")
_MAINS_POWER_MARKERS = ("ac", "dc", "mains", "line", "wired")


@dataclass(slots=True, frozen=True)
class BatterySource:
    """One entity or attribute that reports battery information."""

    entity_id: str
    device_id: str | None
    name: str
    area: str | None
    integration: str
    level: float | None
    priority: int
    is_zigbee: bool
    zigbee_identifier: str | None
    hardware_keys: frozenset[str]
    battery_type: str | None = None
    battery_number: int | None = None
    device_identifiers: frozenset[tuple[str, str]] = frozenset()
    device_connections: frozenset[tuple[str, str]] = frozenset()

    @property
    def source_id(self) -> str:
        """Return the stable identifier used by exclusions and grouping."""
        return self.device_id or self.entity_id


class _DisjointSet:
    """Small union-find implementation used to group battery sources."""

    def __init__(self, size: int) -> None:
        self._parent = list(range(size))

    def find(self, item: int) -> int:
        """Return the representative for an item."""
        while self._parent[item] != item:
            self._parent[item] = self._parent[self._parent[item]]
            item = self._parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        """Join two groups."""
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self._parent[right_root] = left_root


def should_exclude_entity(state: State) -> bool:
    """Return whether an entity must not be considered a battery source."""
    entity_domain = state.entity_id.partition(".")[0]
    return (
        state.entity_id.startswith(f"sensor.{DOMAIN}")
        or entity_domain in EXCLUDED_ENTITY_DOMAINS
    )


def _declares_mains_power(state: State) -> bool:
    """Return whether entity metadata explicitly says it is not battery powered."""
    battery_powered = state.attributes.get("battery_powered")
    if battery_powered is False or str(battery_powered).strip().casefold() in {
        "0",
        "false",
        "no",
    }:
        return True

    for attribute in _POWER_SOURCE_ATTRS:
        value = state.attributes.get(attribute)
        if value is None:
            continue
        normalized = str(value).strip().casefold()
        if any(
            normalized == marker
            or normalized.startswith(f"{marker} ")
            or normalized.startswith(f"{marker}(")
            for marker in _MAINS_POWER_MARKERS
        ):
            return True
    return False


def _valid_percentage(value: Any) -> float | None:
    """Convert a value to a finite percentage in the inclusive 0..100 range."""
    if isinstance(value, bool):
        return None
    try:
        percentage = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(percentage) or not 0 <= percentage <= 100:
        return None
    return percentage


def _battery_reading(state: State) -> tuple[bool, float | None, int]:
    """Return candidate status, percentage, and semantic source priority."""
    if should_exclude_entity(state):
        return False, None, 0

    entity_domain = state.entity_id.partition(".")[0]
    entity_id_lower = state.entity_id.lower()
    device_class = state.attributes.get(ATTR_DEVICE_CLASS)
    unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

    # A binary battery entity means low/normal, never a percentage.
    if entity_domain == "binary_sensor" and device_class == BATTERY_DEVICE_CLASS:
        return True, None, 10

    if device_class == BATTERY_DEVICE_CLASS:
        level = _valid_percentage(state.state)
        if level is None:
            return True, None, 450
        priority = 500 if entity_domain == "sensor" and unit == PERCENTAGE else 450
        return True, level, priority

    battery_attribute_found = False
    for attribute_name in BATTERY_ATTRS:
        if attribute_name not in state.attributes:
            continue
        battery_attribute_found = True
        level = _valid_percentage(state.attributes[attribute_name])
        if level is not None:
            return True, level, 350

    if battery_attribute_found:
        return True, None, 300

    if "battery" not in entity_id_lower:
        return False, None, 0

    normalized_state = str(state.state).strip().lower()
    if any(marker in entity_id_lower for marker in _LOW_BATTERY_MARKERS):
        return True, None, 10
    if any(marker in entity_id_lower for marker in _NON_PERCENTAGE_MARKERS):
        return False, None, 0
    if normalized_state in _UNAVAILABLE_STATES:
        return True, None, 100
    if normalized_state in _BINARY_BATTERY_STATES and unit != PERCENTAGE:
        return True, None, 10

    level = _valid_percentage(state.state)
    if level is None:
        return True, None, 100
    return True, level, 300 if unit == PERCENTAGE else 150


def get_battery_level(state: State) -> float | None:
    """Return a valid battery percentage, if the state provides one."""
    return _battery_reading(state)[1]


def has_battery_attribute(state: State) -> bool:
    """Return whether a state looks like a battery source."""
    return _battery_reading(state)[0]


def is_battery_device(state: State) -> bool:
    """Return whether a state provides a valid battery percentage."""
    return get_battery_level(state) is not None


def has_battery_but_unavailable(state: State) -> bool:
    """Return whether a battery source has no usable percentage."""
    is_candidate, level, _priority = _battery_reading(state)
    return is_candidate and level is None


def _normalize_identifier(value: object) -> str | None:
    """Normalize a hardware identifier while rejecting weak identifiers."""
    normalized = _IDENTIFIER_NORMALIZER.sub("", str(value).lower())
    if len(normalized) < 8 or normalized in {
        "unknown",
        "unavailable",
        "00000000",
    }:
        return None
    return normalized


def _normalize_label(value: str | None) -> str:
    """Normalize a user-facing label for conservative exact comparisons."""
    if not value:
        return ""
    return " ".join(value.casefold().split())


def _hardware_keys(device_entry: dr.DeviceEntry | None) -> frozenset[str]:
    """Return cross-integration identity keys from the device registry."""
    if device_entry is None:
        return frozenset()

    keys: set[str] = set()
    for connection_type, value in device_entry.connections:
        normalized = _normalize_identifier(value)
        if normalized:
            keys.add(f"connection:{connection_type}:{normalized}")

    # Identifier namespaces are integration-specific. Comparing the normalized
    # value as well allows the same serial/MAC to match across integrations.
    for _domain, value in device_entry.identifiers:
        normalized = _normalize_identifier(value)
        if normalized:
            keys.add(f"identifier:{normalized}")

    return frozenset(keys)


def _zigbee_info(
    hass: HomeAssistant, device_entry: dr.DeviceEntry | None
) -> tuple[bool, str | None]:
    """Return whether a device is Zigbee and its best available identifier."""
    if device_entry is None:
        return False, None

    for domain, value in device_entry.identifiers:
        if domain in ZIGBEE_INTEGRATION_DOMAINS:
            return True, str(value)

    for config_entry_id in device_entry.config_entries:
        config_entry = hass.config_entries.async_get_entry(config_entry_id)
        if config_entry and config_entry.domain in ZIGBEE_INTEGRATION_DOMAINS:
            return True, None

    return False, None


def _battery_type_from_state(state: State) -> str | None:
    """Extract battery type metadata from an attribute or dedicated entity."""
    battery_type = next(
        (
            str(state.attributes[attr]).strip()
            for attr in BATTERY_TYPE_ATTRS
            if state.attributes.get(attr) not in (None, "")
        ),
        None,
    )
    if battery_type is None and any(
        marker in state.entity_id.casefold()
        for marker in ("battery_type", "battery_size", "battery_model")
    ):
        state_type = str(state.state).strip()
        if state_type.casefold() not in _UNAVAILABLE_STATES:
            return state_type
    return battery_type


def _positive_battery_number(value: object) -> int | None:
    """Return a practical positive battery count from device metadata."""
    if isinstance(value, bool):
        return None
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if 1 <= number <= 16 else None


def _battery_number_from_state(state: State) -> int | None:
    """Extract the required number of batteries from an attribute or entity."""
    for attribute in BATTERY_NUMBER_ATTRS:
        if number := _positive_battery_number(state.attributes.get(attribute)):
            return number
    if any(marker in state.entity_id.casefold() for marker in BATTERY_NUMBER_ATTRS):
        return _positive_battery_number(state.state)
    if battery_type := _battery_type_from_state(state):
        if match := re.match(r"^\s*(\d+)\s*[x×]", battery_type, re.IGNORECASE):
            return _positive_battery_number(match.group(1))
    return None


def _source_from_state(
    hass: HomeAssistant,
    state: State,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
) -> BatterySource | None:
    """Build a battery source from one Home Assistant state."""
    is_candidate, level, priority = _battery_reading(state)
    if not is_candidate:
        return None

    entity_entry = entity_registry.async_get(state.entity_id)
    device_id = entity_entry.device_id if entity_entry else None
    device_entry = device_registry.async_get(device_id) if device_id else None

    if device_entry and any(
        identifier[0] == DOMAIN for identifier in device_entry.identifiers
    ):
        return None

    name = state.attributes.get("friendly_name", state.entity_id)
    area_id = entity_entry.area_id if entity_entry else None
    if device_entry:
        name = device_entry.name_by_user or device_entry.name or name
        area_id = area_id or device_entry.area_id

    if DOMAIN.replace("_", " ") in str(name).casefold():
        return None

    area_entry = area_registry.async_get_area(area_id) if area_id else None
    integration = (
        entity_entry.platform if entity_entry else state.entity_id.partition(".")[0]
    )
    is_zigbee, zigbee_identifier = _zigbee_info(hass, device_entry)
    battery_type = _battery_type_from_state(state)
    battery_number = _battery_number_from_state(state)

    return BatterySource(
        entity_id=state.entity_id,
        device_id=device_id,
        name=str(name),
        area=area_entry.name if area_entry else None,
        integration=integration,
        level=level,
        priority=priority,
        is_zigbee=is_zigbee,
        zigbee_identifier=zigbee_identifier,
        hardware_keys=_hardware_keys(device_entry),
        battery_type=battery_type,
        battery_number=battery_number,
        device_identifiers=frozenset(device_entry.identifiers)
        if device_entry
        else frozenset(),
        device_connections=frozenset(device_entry.connections)
        if device_entry
        else frozenset(),
    )


def _union_exact_identities(sources: list[BatterySource], groups: _DisjointSet) -> None:
    """Group sources that share a registry device or hardware identifier."""
    device_ids: dict[str, int] = {}
    hardware_keys: dict[str, int] = {}
    for index, source in enumerate(sources):
        if source.device_id:
            if source.device_id in device_ids:
                groups.union(index, device_ids[source.device_id])
            else:
                device_ids[source.device_id] = index
        for hardware_key in source.hardware_keys:
            if hardware_key in hardware_keys:
                groups.union(index, hardware_keys[hardware_key])
            else:
                hardware_keys[hardware_key] = index


def _components(
    sources: list[BatterySource], groups: _DisjointSet
) -> dict[int, list[int]]:
    """Return current union-find components."""
    result: dict[int, list[int]] = {}
    for index in range(len(sources)):
        result.setdefault(groups.find(index), []).append(index)
    return result


def _union_unambiguous_labels(
    sources: list[BatterySource], groups: _DisjointSet
) -> None:
    """Merge exact name+area matches across distinct integrations.

    This fallback is deliberately conservative: an area is required, every
    component must come from a disjoint set of integrations, and the same
    integration may not contribute two devices to the match.
    """
    signature_groups: dict[tuple[str, str], list[list[int]]] = {}
    for indexes in _components(sources, groups).values():
        representative = max(
            (sources[index] for index in indexes), key=lambda item: item.priority
        )
        signature = (
            _normalize_label(representative.name),
            _normalize_label(representative.area),
        )
        if signature[0] and signature[1]:
            signature_groups.setdefault(signature, []).append(indexes)

    for matching_components in signature_groups.values():
        if len(matching_components) < 2:
            continue
        integration_sets = [
            {sources[index].integration for index in indexes}
            for indexes in matching_components
        ]
        if any(
            left & right
            for position, left in enumerate(integration_sets)
            for right in integration_sets[position + 1 :]
        ):
            continue
        first = matching_components[0][0]
        for indexes in matching_components[1:]:
            groups.union(first, indexes[0])


def _best_source(sources: Iterable[BatterySource]) -> BatterySource:
    """Select the best percentage source, using the lowest equal-quality value."""
    source_list = list(sources)
    available = [source for source in source_list if source.level is not None]
    if available:
        highest_priority = max(source.priority for source in available)
        top_sources = [
            source for source in available if source.priority == highest_priority
        ]
        return min(top_sources, key=lambda item: (item.level or 0, item.entity_id))
    return max(source_list, key=lambda item: (item.priority, item.entity_id))


def _device_data(sources: list[BatterySource]) -> dict[str, Any]:
    """Create the public and diagnostic representation of a physical device."""
    selected = _best_source(sources)
    source_ids = sorted({source.source_id for source in sources})
    source_entity_ids = sorted({source.entity_id for source in sources})
    device_ids = sorted(
        source.device_id for source in sources if source.device_id is not None
    )
    canonical_id = device_ids[0] if device_ids else source_entity_ids[0]
    zigbee_source = next((source for source in sources if source.is_zigbee), selected)
    registry_source = selected
    if (
        not registry_source.device_identifiers
        and not registry_source.device_connections
    ):
        registry_source = next(
            (
                source
                for source in sources
                if source.device_identifiers or source.device_connections
            ),
            selected,
        )
    battery_type = next(
        (source.battery_type for source in sources if source.battery_type), None
    )
    battery_number = next(
        (source.battery_number for source in sources if source.battery_number), None
    )
    return {
        "id": canonical_id,
        "name": selected.name,
        "entity_id": selected.entity_id,
        "area": selected.area,
        "battery_level": selected.level,
        "is_zigbee": zigbee_source.is_zigbee,
        "zigbee_identifier": zigbee_source.zigbee_identifier,
        "source_ids": source_ids,
        "source_entity_ids": source_entity_ids,
        "source_integrations": sorted({source.integration for source in sources}),
        "battery_type": battery_type,
        "battery_number": battery_number,
        "device_identifiers": set(registry_source.device_identifiers),
        "device_connections": set(registry_source.device_connections),
    }


def deduplicate_sources(
    sources: list[BatterySource],
) -> dict[str, dict[str, Any]]:
    """Group battery sources and select one percentage per physical device."""
    if not sources:
        return {}

    groups = _DisjointSet(len(sources))
    _union_exact_identities(sources, groups)
    _union_unambiguous_labels(sources, groups)

    devices: dict[str, dict[str, Any]] = {}
    for indexes in _components(sources, groups).values():
        device_data = _device_data([sources[index] for index in indexes])
        devices[device_data["id"]] = device_data
    return devices


async def discover_battery_devices(
    hass: HomeAssistant,
) -> dict[str, dict[str, Any]]:
    """Discover battery sources and return one record per physical device."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    area_registry = ar.async_get(hass)
    states = hass.states.async_all()
    mains_powered_device_ids = {
        entity_entry.device_id
        for state in states
        if _declares_mains_power(state)
        and (entity_entry := entity_registry.async_get(state.entity_id))
        and entity_entry.device_id
    }
    sources: list[BatterySource] = []
    for state in states:
        entity_entry = entity_registry.async_get(state.entity_id)
        if entity_entry and entity_entry.device_id in mains_powered_device_ids:
            continue
        source = _source_from_state(
            hass,
            state,
            entity_registry,
            device_registry,
            area_registry,
        )
        if source is not None:
            sources.append(source)
    # Type metadata is sometimes exposed on a door/lock entity rather than on
    # its battery sensor. Associate those attributes through the shared device.
    type_by_device: dict[str, str] = {}
    number_by_device: dict[str, int] = {}
    for state in states:
        entity_entry = entity_registry.async_get(state.entity_id)
        battery_type = _battery_type_from_state(state)
        battery_number = _battery_number_from_state(state)
        if entity_entry and entity_entry.device_id and battery_type:
            type_by_device.setdefault(entity_entry.device_id, battery_type)
        if entity_entry and entity_entry.device_id and battery_number:
            number_by_device.setdefault(entity_entry.device_id, battery_number)
    sources = [
        replace(
            source,
            battery_type=source.battery_type
            or (type_by_device.get(source.device_id) if source.device_id else None),
            battery_number=source.battery_number
            or (number_by_device.get(source.device_id) if source.device_id else None),
        )
        for source in sources
    ]
    devices = deduplicate_sources(sources)

    _LOGGER.debug(
        "Discovered %d battery sources grouped into %d physical devices",
        len(sources),
        len(devices),
    )
    return devices


async def get_all_battery_devices(
    hass: HomeAssistant,
) -> dict[str, dict[str, Any]]:
    """Return deduplicated physical devices with a valid percentage."""
    devices = await discover_battery_devices(hass)
    return {
        device_id: data
        for device_id, data in devices.items()
        if data["battery_level"] is not None
    }


async def get_devices_without_battery_info(
    hass: HomeAssistant,
) -> dict[str, dict[str, Any]]:
    """Return deduplicated physical devices without a valid percentage."""
    devices = await discover_battery_devices(hass)
    return {
        device_id: data
        for device_id, data in devices.items()
        if data["battery_level"] is None
    }
