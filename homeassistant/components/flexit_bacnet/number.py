"""The Flexit Nordic (BACnet) integration."""

import asyncio.exceptions
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import override

from flexit_bacnet import FlexitBACnet, Unit
from flexit_bacnet.bacnet import DecodingError

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MAX_TEMP, MIN_TEMP
from .coordinator import FlexitConfigEntry, FlexitCoordinator
from .entity import FlexitEntity

_MAX_FAN_SETPOINT = 100
_MIN_FAN_SETPOINT = 30


def _fan_setpoint_min(device: FlexitBACnet) -> float | None:
    """Return the lowest fan setpoint: 30 % or the unit's minimum air flow."""
    if device.fan_setpoint_unit is Unit.PERCENT:
        return _MIN_FAN_SETPOINT
    return device.air_flow_min


def _fan_setpoint_max(device: FlexitBACnet) -> float | None:
    """Return the highest fan setpoint: 100 % or the unit's nominal air flow."""
    if device.fan_setpoint_unit is Unit.PERCENT:
        return _MAX_FAN_SETPOINT
    return device.air_flow_nominal


_MAX_RUNTIME_DURATION = 360
_MIN_RUNTIME_DURATION = 1


@dataclass(kw_only=True, frozen=True)
class FlexitNumberEntityDescription(NumberEntityDescription):
    """Describes a Flexit number entity."""

    native_value_fn: Callable[[FlexitBACnet], float | None]
    native_max_value_fn: Callable[[FlexitBACnet], float | None]
    native_min_value_fn: Callable[[FlexitBACnet], float | None]
    set_native_value_fn: Callable[[FlexitBACnet, float], Awaitable[None]]
    exists_fn: Callable[[FlexitBACnet], bool] = lambda _: True


# Setpoints for Away, Home and High are dependent of each
# other. Fireplace and Cooker Hood
# have setpoints between 0 (MIN_FAN_SETPOINT) and 100 (MAX_FAN_SETPOINT).
# See the table below for all the setpoints.
#
# | Mode        | Setpoint | Min                   | Max                   |
# |:------------|----------|:----------------------|:----------------------|
# | HOME        | Supply   | AWAY Supply setpoint  | 100                   |
# | HOME        | Extract  | AWAY Extract setpoint | 100                   |
# | AWAY        | Supply   | 30                    | HOME Supply setpoint  |
# | AWAY        | Extract  | 30                    | HOME Extract setpoint |
# | HIGH        | Supply   | HOME Supply setpoint  | 100                   |
# | HIGH        | Extract  | HOME Extract setpoint | 100                   |
# | COOKER_HOOD | Supply   | 30                    | 100                   |
# | COOKER_HOOD | Extract  | 30                    | 100                   |
# | FIREPLACE   | Supply   | 30                    | 100                   |
# | FIREPLACE   | Extract  | 30                    | 100                   |
#
# On flow-controlled units (EcoNordic) the setpoints are air flows in m³/h, and
# 30 and 100 are replaced by the unit's minimum and nominal air flow.


NUMBERS: tuple[FlexitNumberEntityDescription, ...] = (
    FlexitNumberEntityDescription(
        key="away_extract_fan_setpoint",
        translation_key="away_extract_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_extract_air_away,
        set_native_value_fn=lambda device, value: (
            device.set_fan_setpoint_extract_air_away(int(value))
        ),
        native_unit_of_measurement=PERCENTAGE,
        native_max_value_fn=lambda device: device.fan_setpoint_extract_air_home,
        native_min_value_fn=_fan_setpoint_min,
    ),
    FlexitNumberEntityDescription(
        key="away_supply_fan_setpoint",
        translation_key="away_supply_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_supply_air_away,
        set_native_value_fn=lambda device, value: (
            device.set_fan_setpoint_supply_air_away(int(value))
        ),
        native_unit_of_measurement=PERCENTAGE,
        native_max_value_fn=lambda device: device.fan_setpoint_supply_air_home,
        native_min_value_fn=_fan_setpoint_min,
    ),
    FlexitNumberEntityDescription(
        key="cooker_hood_extract_fan_setpoint",
        translation_key="cooker_hood_extract_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_extract_air_cooker,
        set_native_value_fn=lambda device, value: (
            device.set_fan_setpoint_extract_air_cooker(int(value))
        ),
        native_unit_of_measurement=PERCENTAGE,
        native_max_value_fn=_fan_setpoint_max,
        native_min_value_fn=_fan_setpoint_min,
    ),
    FlexitNumberEntityDescription(
        key="cooker_hood_supply_fan_setpoint",
        translation_key="cooker_hood_supply_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_supply_air_cooker,
        set_native_value_fn=lambda device, value: (
            device.set_fan_setpoint_supply_air_cooker(int(value))
        ),
        native_unit_of_measurement=PERCENTAGE,
        native_max_value_fn=_fan_setpoint_max,
        native_min_value_fn=_fan_setpoint_min,
    ),
    FlexitNumberEntityDescription(
        key="fireplace_extract_fan_setpoint",
        translation_key="fireplace_extract_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_extract_air_fire,
        set_native_value_fn=lambda device, value: (
            device.set_fan_setpoint_extract_air_fire(int(value))
        ),
        native_unit_of_measurement=PERCENTAGE,
        native_max_value_fn=_fan_setpoint_max,
        native_min_value_fn=_fan_setpoint_min,
    ),
    FlexitNumberEntityDescription(
        key="fireplace_supply_fan_setpoint",
        translation_key="fireplace_supply_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_supply_air_fire,
        set_native_value_fn=lambda device, value: (
            device.set_fan_setpoint_supply_air_fire(int(value))
        ),
        native_unit_of_measurement=PERCENTAGE,
        native_max_value_fn=_fan_setpoint_max,
        native_min_value_fn=_fan_setpoint_min,
    ),
    FlexitNumberEntityDescription(
        key="high_extract_fan_setpoint",
        translation_key="high_extract_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_extract_air_high,
        set_native_value_fn=lambda device, value: (
            device.set_fan_setpoint_extract_air_high(int(value))
        ),
        native_unit_of_measurement=PERCENTAGE,
        native_max_value_fn=_fan_setpoint_max,
        native_min_value_fn=lambda device: device.fan_setpoint_extract_air_home,
    ),
    FlexitNumberEntityDescription(
        key="high_supply_fan_setpoint",
        translation_key="high_supply_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_supply_air_high,
        set_native_value_fn=lambda device, value: (
            device.set_fan_setpoint_supply_air_high(int(value))
        ),
        native_unit_of_measurement=PERCENTAGE,
        native_max_value_fn=_fan_setpoint_max,
        native_min_value_fn=lambda device: device.fan_setpoint_supply_air_home,
    ),
    FlexitNumberEntityDescription(
        key="home_extract_fan_setpoint",
        translation_key="home_extract_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_extract_air_home,
        set_native_value_fn=lambda device, value: (
            device.set_fan_setpoint_extract_air_home(int(value))
        ),
        native_unit_of_measurement=PERCENTAGE,
        native_max_value_fn=_fan_setpoint_max,
        native_min_value_fn=lambda device: device.fan_setpoint_extract_air_away,
    ),
    FlexitNumberEntityDescription(
        key="home_supply_fan_setpoint",
        translation_key="home_supply_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_supply_air_home,
        set_native_value_fn=lambda device, value: (
            device.set_fan_setpoint_supply_air_home(int(value))
        ),
        native_unit_of_measurement=PERCENTAGE,
        native_max_value_fn=_fan_setpoint_max,
        native_min_value_fn=lambda device: device.fan_setpoint_supply_air_away,
    ),
    FlexitNumberEntityDescription(
        key="fireplace_mode_runtime",
        translation_key="fireplace_mode_runtime",
        device_class=NumberDeviceClass.DURATION,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fireplace_mode_runtime,
        set_native_value_fn=lambda device, value: device.set_fireplace_mode_runtime(
            int(value)
        ),
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_max_value_fn=lambda _: _MAX_RUNTIME_DURATION,
        native_min_value_fn=lambda _: _MIN_RUNTIME_DURATION,
        # read-only and not reported on EcoNordic units
        exists_fn=lambda device: device.fireplace_mode_runtime is not None,
    ),
    FlexitNumberEntityDescription(
        key="space_heating_setpoint",
        translation_key="space_heating_setpoint",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_step=0.5,
        mode=NumberMode.BOX,
        native_value_fn=lambda device: device.space_heating_setpoint,
        set_native_value_fn=lambda device, value: device.set_space_heating_setpoint(
            value
        ),
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_max_value_fn=lambda _: MAX_TEMP,
        native_min_value_fn=lambda _: MIN_TEMP,
        exists_fn=lambda device: device.space_heating_setpoint is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FlexitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Flexit (bacnet) number from a config entry."""
    coordinator = config_entry.runtime_data
    descriptions = NUMBERS
    # flow-controlled units take fan setpoints as air flows instead of percentages
    if coordinator.data.fan_setpoint_unit is Unit.CUBIC_METERS_PER_HOUR:
        descriptions = tuple(
            replace(
                description,
                device_class=NumberDeviceClass.VOLUME_FLOW_RATE,
                native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
            )
            if description.native_unit_of_measurement == PERCENTAGE
            else description
            for description in NUMBERS
        )

    async_add_entities(
        FlexitNumber(coordinator, description)
        for description in descriptions
        if description.exists_fn(coordinator.data)
    )


PARALLEL_UPDATES = 1


class FlexitNumber(FlexitEntity, NumberEntity):
    """Representation of a Flexit Number."""

    entity_description: FlexitNumberEntityDescription

    def __init__(
        self,
        coordinator: FlexitCoordinator,
        entity_description: FlexitNumberEntityDescription,
    ) -> None:
        """Initialize Flexit (bacnet) number."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.device.serial_number}-{entity_description.key}"
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the value and its limits are available."""
        return (
            super().available
            and self.native_value is not None
            and self.entity_description.native_min_value_fn(self.coordinator.device)
            is not None
            and self.entity_description.native_max_value_fn(self.coordinator.device)
            is not None
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the state of the number."""
        return self.entity_description.native_value_fn(self.coordinator.device)

    @property
    @override
    def native_max_value(self) -> float:
        """Return the native max value of the number."""
        if (
            value := self.entity_description.native_max_value_fn(
                self.coordinator.device
            )
        ) is None:
            return super().native_max_value
        return value

    @property
    @override
    def native_min_value(self) -> float:
        """Return the native min value of the number."""
        if (
            value := self.entity_description.native_min_value_fn(
                self.coordinator.device
            )
        ) is None:
            return super().native_min_value
        return value

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        try:
            await self.entity_description.set_native_value_fn(
                self.coordinator.device, value
            )
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_value_error",
                translation_placeholders={
                    "value": str(value),
                },
            ) from exc
        finally:
            await self.coordinator.async_refresh()
