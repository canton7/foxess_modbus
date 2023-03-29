"""Inverter sensor"""
import logging

from custom_components.foxess_modbus.entities.modbus_integration_sensor import (
    ModbusIntegrationSensorDescription,
)
from custom_components.foxess_modbus.entities.validation import Min
from custom_components.foxess_modbus.entities.validation import Range
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import UnitOfTime

from .entity_factory import EntityFactory
from .modbus_sensor import ModbusSensorDescription

_LOGGER: logging.Logger = logging.getLogger(__package__)

H1: list[EntityFactory] = [
    ModbusSensorDescription(
        key="pv1_voltage",
        address=31000,
        name="PV1 Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        validate=[Range(0, 1000)],
    ),
    ModbusSensorDescription(
        key="pv1_current",
        address=31001,
        name="PV1 Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="pv1_power",
        address=31002,
        name="PV1 Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(0, 10000)],
    ),
    ModbusIntegrationSensorDescription(
        key="pv1_energy_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        integration_method="left",
        name="PV1 Power Total",
        round_digits=2,
        source_entity="pv1_power",
        unit_time=UnitOfTime.HOURS,
    ),
    ModbusSensorDescription(
        key="pv2_voltage",
        address=31003,
        name="PV2 Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        validate=[Range(0, 1000)],
    ),
    ModbusSensorDescription(
        key="pv2_current",
        address=31004,
        name="PV2 Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="pv2_power",
        address=31005,
        name="PV2 Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(0, 10000)],
    ),
    ModbusIntegrationSensorDescription(
        key="pv2_energy_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        integration_method="left",
        name="PV2 Power Total",
        round_digits=2,
        source_entity="pv2_power",
        unit_time=UnitOfTime.HOURS,
    ),
]

H1_AC1: list[EntityFactory] = [
    ModbusSensorDescription(
        key="rvolt",
        address=31006,
        name="Grid Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        validate=[Range(0, 300)],
    ),
    ModbusSensorDescription(
        key="rcurrent",
        address=31007,
        name="Grid Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="rfreq",
        address=31009,
        name="Grid Frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Hz",
        scale=0.01,
        validate=[Range(0, 60)],
    ),
    ModbusSensorDescription(
        key="grid_ct",
        address=31014,
        name="Grid CT",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(-100, 100)],
    ),
    ModbusSensorDescription(
        key="feed_in",
        address=31014,
        name="Feed In",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        post_process=lambda v: v if v > 0 else 0,
        validate=[Range(0, 100)],
    ),
    ModbusIntegrationSensorDescription(
        key="feed_in_energy_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        integration_method="left",
        name="Feed-in Total",
        round_digits=2,
        source_entity="feed_in",
        unit_time=UnitOfTime.HOURS,
    ),
    ModbusSensorDescription(
        key="grid_consumption",
        address=31014,
        name="Grid Consumption",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        post_process=lambda v: abs(v) if v < 0 else 0,
        validate=[Range(0, 100)],
    ),
    ModbusIntegrationSensorDescription(
        key="grid_consumption_energy_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        integration_method="left",
        name="Grid Consumption Total",
        round_digits=2,
        source_entity="grid_consumption",
        unit_time=UnitOfTime.HOURS,
    ),
    ModbusSensorDescription(
        key="ct2_meter",
        address=31015,
        name="CT2 Meter",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(-100, 100)],
    ),
    ModbusSensorDescription(
        key="load_power",
        address=31016,
        name="Load Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(-100, 100)],
    ),
    ModbusIntegrationSensorDescription(
        key="load_power_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        integration_method="left",
        name="Load Power Total",
        round_digits=2,
        source_entity="load_power",
        unit_time=UnitOfTime.HOURS,
    ),
    ModbusSensorDescription(
        key="ambtemp",
        address=31018,
        name="Ambient Temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="invtemp",
        address=31019,
        name="Inverter Temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="batvolt",
        address=31020,
        name="Battery Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        validate=[Min(0)],
    ),
    ModbusSensorDescription(
        key="bat_current",
        address=31021,
        name="Battery Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(-100, 100)],
    ),
    ModbusSensorDescription(
        key="battery_discharge",
        address=31022,
        name="Battery Discharge",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        post_process=lambda v: v if v > 0 else 0,
        validate=[Range(0, 100)],
    ),
    ModbusIntegrationSensorDescription(
        key="battery_discharge_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        integration_method="left",
        name="Battery Discharge Total",
        round_digits=2,
        source_entity="battery_discharge",
        unit_time=UnitOfTime.HOURS,
    ),
    ModbusSensorDescription(
        key="battery_charge",
        address=31022,
        name="Battery Charge",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        post_process=lambda v: abs(v) if v < 0 else 0,
        validate=[Range(0, 100)],
    ),
    ModbusIntegrationSensorDescription(
        key="battery_charge_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        integration_method="left",
        name="Battery Charge Total",
        round_digits=2,
        source_entity="battery_charge",
        unit_time=UnitOfTime.HOURS,
    ),
    ModbusSensorDescription(
        key="battery_temp",
        address=31023,
        name="Battery Temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="battery_soc",
        address=31024,
        name="Battery SoC",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        validate=[Range(0, 100)],
    ),
]
