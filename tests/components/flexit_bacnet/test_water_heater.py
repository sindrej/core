"""Tests for the Flexit Nordic (BACnet) water heater entity."""

from unittest.mock import AsyncMock

from flexit_bacnet import DecodingError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.flexit_bacnet.const import DOMAIN
from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    STATE_ECO,
    STATE_HIGH_DEMAND,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

ENTITY_ID = "water_heater.device_name_hot_water"


async def test_water_heater(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_flexit_bacnet_econordic: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the hot water tank of an EcoNordic unit."""

    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_water_heater_not_on_nordic(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_flexit_bacnet: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Nordic units without a hot water tank get no water heater."""

    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    assert not entity_registry.async_get_entity_id(
        Platform.WATER_HEATER, DOMAIN, "0000-0001-hot_water"
    )


@pytest.mark.parametrize(
    ("operation_mode", "setter", "target"),
    [
        (1, "set_dhw_temperature_setpoint_comfort", 49.0),
        (2, "set_dhw_temperature_setpoint_economy", 45.0),
        (3, "set_dhw_temperature_setpoint_comfort", 49.0),
    ],
)
async def test_set_temperature_of_active_mode(
    hass: HomeAssistant,
    mock_flexit_bacnet_econordic: AsyncMock,
    mock_config_entry: MockConfigEntry,
    operation_mode: int,
    setter: str,
    target: float,
) -> None:
    """Test the target temperature is the setpoint of the active mode."""
    mock_flexit_bacnet_econordic.dhw_operation_mode = operation_mode

    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )
    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == target

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 52},
        blocking=True,
    )

    getattr(mock_flexit_bacnet_econordic, setter).assert_awaited_once_with(52)


@pytest.mark.parametrize(
    ("operation_mode", "value"), [(STATE_ECO, 2), (STATE_HIGH_DEMAND, 3)]
)
async def test_set_operation_mode(
    hass: HomeAssistant,
    mock_flexit_bacnet_econordic: AsyncMock,
    mock_config_entry: MockConfigEntry,
    operation_mode: str,
    value: int,
) -> None:
    """Test changing the hot water operation mode."""

    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPERATION_MODE: operation_mode},
        blocking=True,
    )

    mock_flexit_bacnet_econordic.set_dhw_operation_mode.assert_awaited_once_with(value)


async def test_set_operation_mode_error(
    hass: HomeAssistant,
    mock_flexit_bacnet_econordic: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a failed write raises a translated error."""
    mock_flexit_bacnet_econordic.set_dhw_operation_mode.side_effect = DecodingError

    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    with pytest.raises(HomeAssistantError, match="Failed to set operation mode eco"):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_OPERATION_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPERATION_MODE: STATE_ECO},
            blocking=True,
        )
