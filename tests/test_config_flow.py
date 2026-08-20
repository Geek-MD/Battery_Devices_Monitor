"""Tests for the Battery Devices Monitor config flow."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.battery_devices_monitor.const import (
    CONF_BATTERY_THRESHOLD,
    CONF_EXCLUDED_DEVICES,
    DOMAIN,
)


async def test_config_flow_allows_setup_without_existing_batteries(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """An empty Home Assistant installation is valid and discovers later."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_BATTERY_THRESHOLD: 20}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "exclude_devices"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EXCLUDED_DEVICES: []}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        CONF_BATTERY_THRESHOLD: 20,
        CONF_EXCLUDED_DEVICES: [],
    }


async def test_second_config_flow_aborts_as_already_configured(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """A duplicate setup attempt must not become an unknown error."""
    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    first = await hass.config_entries.flow.async_configure(
        first["flow_id"], {CONF_BATTERY_THRESHOLD: 20}
    )
    await hass.config_entries.flow.async_configure(
        first["flow_id"], {CONF_EXCLUDED_DEVICES: []}
    )

    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    second = await hass.config_entries.flow.async_configure(
        second["flow_id"], {CONF_BATTERY_THRESHOLD: 20}
    )
    second = await hass.config_entries.flow.async_configure(
        second["flow_id"], {CONF_EXCLUDED_DEVICES: []}
    )

    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == "already_configured"
