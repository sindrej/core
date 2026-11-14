"""The Flexit Nordic (BACnet) integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from flexit_bacnet import FlexitBACnet, econordic

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import FlexitConfigEntry, FlexitCoordinator
from .entity import FlexitEntity


@dataclass(kw_only=True, frozen=True)
class FlexitSensorEntityDescription(SensorEntityDescription):
    """Describes a Flexit sensor entity."""

    value_fn: Callable[[FlexitBACnet], StateType]
    exists_fn: Callable[[FlexitBACnet], bool] = lambda _: True


HEAT_PUMP_STATES: dict[int | None, str] = {
    econordic.HEAT_PUMP_STATE_STANDBY: "standby",
    econordic.HEAT_PUMP_STATE_AIR_PURGE_PROCESS: "air_purge",
    econordic.HEAT_PUMP_STATE_STARTUP_PROCESS: "starting",
    econordic.HEAT_PUMP_STATE_NORMAL_OPERATION: "running",
    econordic.HEAT_PUMP_STATE_STOP_PROCESS: "stopping",
    econordic.HEAT_PUMP_STATE_DEFROST_OPERATION: "defrosting",
    econordic.HEAT_PUMP_STATE_STANDBY_WHEN_ERROR: "error",
    econordic.HEAT_PUMP_STATE_MANUAL_OPERATION: "manual",
    econordic.HEAT_PUMP_STATE_FORCED_FAN_OPERATION: "forced_fan",
    econordic.HEAT_PUMP_STATE_FORCED_PUMP_OPERATION: "forced_pump",
}

DHW_STATES: dict[int | None, str] = {
    econordic.DHW_STATE_COMFORT: "comfort",
    econordic.DHW_STATE_ECONOMY: "economy",
    econordic.DHW_STATE_BOOST: "boost",
    econordic.DHW_STATE_TEMPORARY_BOOST: "temporary_boost",
    econordic.DHW_STATE_FORCED_CHARGE: "forced_charge",
    econordic.DHW_STATE_ECONOMY_DELAY: "economy_delay",
    econordic.DHW_STATE_LEGIONELLA_PREVENTION: "legionella_prevention",
}


SENSOR_TYPES: tuple[FlexitSensorEntityDescription, ...] = (
    FlexitSensorEntityDescription(
        key="outside_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key="outside_air_temperature",
        value_fn=lambda data: data.outside_air_temperature,
    ),
    FlexitSensorEntityDescription(
        key="supply_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key="supply_air_temperature",
        value_fn=lambda data: data.supply_air_temperature,
    ),
    FlexitSensorEntityDescription(
        key="exhaust_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key="exhaust_air_temperature",
        value_fn=lambda data: data.exhaust_air_temperature,
    ),
    FlexitSensorEntityDescription(
        key="extract_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key="extract_air_temperature",
        value_fn=lambda data: data.extract_air_temperature,
    ),
    FlexitSensorEntityDescription(
        key="extract_air_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        translation_key="extract_air_humidity",
        value_fn=lambda data: data.extract_air_humidity,
        # Units without a humidity sensor report None or 0.
        exists_fn=lambda data: (
            (humidity := data.extract_air_humidity) is not None and humidity > 0
        ),
    ),
    FlexitSensorEntityDescription(
        key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key="room_temperature",
        value_fn=lambda data: data.room_temperature,
    ),
    FlexitSensorEntityDescription(
        key="fireplace_ventilation_remaining_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        translation_key="fireplace_ventilation_remaining_duration",
        value_fn=lambda data: data.fireplace_ventilation_remaining_duration,
        suggested_display_precision=0,
    ),
    FlexitSensorEntityDescription(
        key="rapid_ventilation_remaining_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        translation_key="rapid_ventilation_remaining_duration",
        value_fn=lambda data: data.rapid_ventilation_remaining_duration,
        suggested_display_precision=0,
    ),
    FlexitSensorEntityDescription(
        key="supply_air_fan_control_signal",
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="supply_air_fan_control_signal",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.supply_air_fan_control_signal,
    ),
    FlexitSensorEntityDescription(
        key="supply_air_fan_rpm",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        translation_key="supply_air_fan_rpm",
        value_fn=lambda data: data.supply_air_fan_rpm,
    ),
    FlexitSensorEntityDescription(
        key="exhaust_air_fan_control_signal",
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="exhaust_air_fan_control_signal",
        value_fn=lambda data: data.exhaust_air_fan_control_signal,
        native_unit_of_measurement=PERCENTAGE,
    ),
    FlexitSensorEntityDescription(
        key="exhaust_air_fan_rpm",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        translation_key="exhaust_air_fan_rpm",
        value_fn=lambda data: data.exhaust_air_fan_rpm,
    ),
    FlexitSensorEntityDescription(
        key="electric_heater_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        translation_key="electric_heater_power",
        value_fn=lambda data: data.electric_heater_power,
        suggested_display_precision=3,
    ),
    FlexitSensorEntityDescription(
        key="air_filter_operating_time",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        native_unit_of_measurement=UnitOfTime.HOURS,
        translation_key="air_filter_operating_time",
        value_fn=lambda data: data.air_filter_operating_time,
    ),
    FlexitSensorEntityDescription(
        key="heat_exchanger_efficiency",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        translation_key="heat_exchanger_efficiency",
        value_fn=lambda data: data.heat_exchanger_efficiency,
    ),
    FlexitSensorEntityDescription(
        key="heat_exchanger_speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        translation_key="heat_exchanger_speed",
        value_fn=lambda data: data.heat_exchanger_speed,
    ),
    FlexitSensorEntityDescription(
        key="dhw_tank_temperature_top",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key="dhw_tank_temperature_top",
        value_fn=lambda data: data.dhw_tank_temperature_top,
        exists_fn=lambda data: data.dhw_tank_temperature_top is not None,
    ),
    FlexitSensorEntityDescription(
        key="dhw_tank_temperature_middle",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key="dhw_tank_temperature_middle",
        value_fn=lambda data: data.dhw_tank_temperature_middle,
        exists_fn=lambda data: data.dhw_tank_temperature_middle is not None,
    ),
    FlexitSensorEntityDescription(
        key="dhw_tank_temperature_bottom",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key="dhw_tank_temperature_bottom",
        value_fn=lambda data: data.dhw_tank_temperature_bottom,
        exists_fn=lambda data: data.dhw_tank_temperature_bottom is not None,
    ),
    FlexitSensorEntityDescription(
        key="dhw_electric_heater_status",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        translation_key="dhw_electric_heater_status",
        value_fn=lambda data: data.dhw_electric_heater_status,
        exists_fn=lambda data: data.dhw_electric_heater_status is not None,
    ),
    FlexitSensorEntityDescription(
        key="dhw_state",
        device_class=SensorDeviceClass.ENUM,
        options=list(DHW_STATES.values()),
        translation_key="dhw_state",
        value_fn=lambda data: DHW_STATES.get(data.dhw_state),
        exists_fn=lambda data: data.dhw_state is not None,
    ),
    FlexitSensorEntityDescription(
        key="heat_pump_state",
        device_class=SensorDeviceClass.ENUM,
        options=list(HEAT_PUMP_STATES.values()),
        translation_key="heat_pump_state",
        value_fn=lambda data: HEAT_PUMP_STATES.get(data.heat_pump_state),
        exists_fn=lambda data: data.heat_pump_state is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FlexitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Flexit (bacnet) sensor from a config entry."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        FlexitSensor(coordinator, description)
        for description in SENSOR_TYPES
        if description.exists_fn(coordinator.data)
    )


# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


class FlexitSensor(FlexitEntity, SensorEntity):
    """Representation of a Flexit (bacnet) Sensor."""

    entity_description: FlexitSensorEntityDescription

    def __init__(
        self,
        coordinator: FlexitCoordinator,
        entity_description: FlexitSensorEntityDescription,
    ) -> None:
        """Initialize Flexit (bacnet) sensor."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.device.serial_number}-{entity_description.key}"
        )

    @property
    @override
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
