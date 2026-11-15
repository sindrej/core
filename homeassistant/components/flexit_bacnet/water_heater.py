"""The Flexit Nordic (BACnet) integration."""

import asyncio.exceptions
from typing import Any, override

from flexit_bacnet import econordic
from flexit_bacnet.bacnet import DecodingError

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_HIGH_DEMAND,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import FlexitConfigEntry, FlexitCoordinator
from .entity import FlexitEntity

STATE_COMFORT = "comfort"

OPERATION_MODE_TO_HA: dict[int | None, str] = {
    econordic.DHW_OPERATION_MODE_COMFORT: STATE_COMFORT,
    econordic.DHW_OPERATION_MODE_ECONOMY: STATE_ECO,
    econordic.DHW_OPERATION_MODE_BOOST: STATE_HIGH_DEMAND,
}
HA_TO_OPERATION_MODE = {
    mode: value for value, mode in OPERATION_MODE_TO_HA.items() if value is not None
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FlexitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Flexit (bacnet) hot water tank from a config entry."""
    coordinator = config_entry.runtime_data

    # Only EcoNordic units have a hot water tank
    if coordinator.data.dhw_operation_mode is not None:
        async_add_entities([FlexitWaterHeater(coordinator)])


PARALLEL_UPDATES = 1


class FlexitWaterHeater(FlexitEntity, WaterHeaterEntity):
    """Representation of the hot water tank of a Flexit EcoNordic unit."""

    _attr_translation_key = "hot_water"
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_WHOLE
    _attr_target_temperature_step = 1
    # The heat pump delivers up to 65 °C
    _attr_min_temp = 40
    _attr_max_temp = 65
    _attr_operation_list = list(OPERATION_MODE_TO_HA.values())
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )

    def __init__(self, coordinator: FlexitCoordinator) -> None:
        """Initialize the hot water tank."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.serial_number}-hot_water"

    @property
    @override
    def current_operation(self) -> str | None:
        """Return the hot water operation mode."""
        return OPERATION_MODE_TO_HA.get(self.device.dhw_operation_mode)

    @property
    @override
    def native_current_temperature(self) -> float | None:
        """Return the temperature at the top of the tank, where hot water is drawn."""
        return self.device.dhw_tank_temperature_top

    @property
    @override
    def native_target_temperature(self) -> float | None:
        """Return the setpoint of the active operation mode."""
        if self.current_operation == STATE_ECO:
            return self.device.dhw_temperature_setpoint_economy
        return self.device.dhw_temperature_setpoint_comfort

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the setpoint of the active operation mode."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        if self.current_operation == STATE_ECO:
            setter = self.device.set_dhw_temperature_setpoint_economy
        else:
            setter = self.device.set_dhw_temperature_setpoint_comfort

        try:
            await setter(temperature)
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_temperature",
                translation_placeholders={"temperature": str(temperature)},
            ) from exc
        finally:
            await self.coordinator.async_refresh()

    @override
    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set the hot water operation mode."""
        try:
            await self.device.set_dhw_operation_mode(
                HA_TO_OPERATION_MODE[operation_mode]
            )
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_operation_mode",
                translation_placeholders={"mode": operation_mode},
            ) from exc
        finally:
            await self.coordinator.async_refresh()
