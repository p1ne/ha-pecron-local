# custom_components/pecron_local/sensor.py
from __future__ import annotations
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    AC_CHARGING_POWER_OPTIONS,
    CONF_CONTROLS,
    CONTROLS,
    DOMAIN,
    SENSOR_FIELDS,
    DEVICE_STATUS_LABELS,
    CHARGE_STATUS_LABELS,
    REMAIN_TIME_NO_LOAD,
    ALARM_CODES,
    ALARM_NONE,
    enum_labels_for,
)
from .coordinator import PecronCoordinator
from .entity import PecronEntity, alarm_defined, async_remove_unreported, reported


@dataclass(frozen=True, kw_only=True)
class PecronSensorDescription(SensorEntityDescription):
    key: str


def _get_field(kv: dict, paths: list[tuple]) -> object | None:
    for path in paths:
        node = kv
        for part in path:
            if not isinstance(node, dict) or part not in node:
                node = None
                break
            node = node[part]
        if node is not None:
            return node
    return None


def _power(kv: dict, key: str) -> float:
    try:
        return float(_get_field(kv, SENSOR_FIELDS.get(key, [])) or 0)
    except (TypeError, ValueError):
        return 0.0


def _device_status_label(raw: object, controls: dict | None = None) -> str:
    try:
        raw_int = int(raw)
    except (TypeError, ValueError):
        return str(raw)

    labels = enum_labels_for("device_status_hm", (controls or {}).get("device_status_hm", {}))
    return labels.get(raw_int, DEVICE_STATUS_LABELS.get(raw_int, str(raw)))


ACTIVITY_OPTIONS = ["Charging", "Discharging", "Idle"]


def _alarm_code(raw: object) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _alarm_label(raw: object) -> str | None:
    code = _alarm_code(raw)
    if code is None:
        return None
    if code == 0:
        return ALARM_NONE
    return f"E{code:02d} {ALARM_CODES[code]}" if code in ALARM_CODES else f"E{code:02d}"


def _activity(kv: dict) -> str:
    """What the unit is doing, from power flow.

    Device Status reports the firmware's own value, which is 0 ("Shutdown")
    whenever nothing is charging or discharging even though the unit is on.
    """
    if _power(kv, "total_input_power") > 0:
        return "Charging"
    if (
        _power(kv, "total_output_power") > 0
        or _power(kv, "ac_output_power") > 0
        or _power(kv, "dc_output_power") > 0
    ):
        return "Discharging"
    return "Idle"


SENSOR_DESCRIPTIONS: list[PecronSensorDescription] = [
    PecronSensorDescription(key="battery_percent", name="Battery", native_unit_of_measurement=PERCENTAGE, device_class=SensorDeviceClass.BATTERY, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="voltage", name="Voltage", native_unit_of_measurement=UnitOfElectricPotential.VOLT, device_class=SensorDeviceClass.VOLTAGE, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="current", name="Current", native_unit_of_measurement=UnitOfElectricCurrent.AMPERE, device_class=SensorDeviceClass.CURRENT, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="temperature", name="Temperature", native_unit_of_measurement=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="battery_temp", name="Battery Temperature", native_unit_of_measurement=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="charging_plate_temp", name="Charging Plate Temperature", native_unit_of_measurement=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="inverter_temp", name="Inverter Temperature", native_unit_of_measurement=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="total_input_power", name="Total Input Power", native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="total_output_power", name="Total Output Power", native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="ac_input_power", name="AC Input Power", native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="ac_output_power", name="AC Output Power", native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="dc_input_power", name="DC Input Power", native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="dc_output_power", name="DC Output Power", native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="dc5521_input_voltage", name="Solar Port 1 Voltage", native_unit_of_measurement=UnitOfElectricPotential.VOLT, device_class=SensorDeviceClass.VOLTAGE, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="dc5521_input_current", name="Solar Port 1 Current", native_unit_of_measurement=UnitOfElectricCurrent.AMPERE, device_class=SensorDeviceClass.CURRENT, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="dc5521_input_power", name="Solar Port 1 Power", native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="gx16mf1_input_voltage", name="Solar Port 2 Voltage", native_unit_of_measurement=UnitOfElectricPotential.VOLT, device_class=SensorDeviceClass.VOLTAGE, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="gx16mf1_input_current", name="Solar Port 2 Current", native_unit_of_measurement=UnitOfElectricCurrent.AMPERE, device_class=SensorDeviceClass.CURRENT, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="gx16mf1_input_power", name="Solar Port 2 Power", native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="gx16mf2_input_voltage", name="Solar Port 3 Voltage", native_unit_of_measurement=UnitOfElectricPotential.VOLT, device_class=SensorDeviceClass.VOLTAGE, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="gx16mf2_input_current", name="Solar Port 3 Current", native_unit_of_measurement=UnitOfElectricCurrent.AMPERE, device_class=SensorDeviceClass.CURRENT, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="gx16mf2_input_power", name="Solar Port 3 Power", native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="ac_output_voltage", name="AC Output Voltage", native_unit_of_measurement=UnitOfElectricPotential.VOLT, device_class=SensorDeviceClass.VOLTAGE, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="ac_output_hz", name="AC Output Frequency", native_unit_of_measurement="Hz", device_class=SensorDeviceClass.FREQUENCY, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="ac_output_pf", name="AC Power Factor", native_unit_of_measurement=None, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="remain_time", name="Time to Empty", native_unit_of_measurement=UnitOfTime.MINUTES, device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="remain_charging_time", name="Time to Full", native_unit_of_measurement=UnitOfTime.MINUTES, device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="device_status_hm", name="Device Status", native_unit_of_measurement=None),
    PecronSensorDescription(key="activity", name="Activity", device_class=SensorDeviceClass.ENUM, options=ACTIVITY_OPTIONS),
    PecronSensorDescription(key="alarm", name="Alarm"),
    PecronSensorDescription(key="charge_status", name="Charge Status", native_unit_of_measurement=None),
    PecronSensorDescription(key="ac_charging_power", name="AC Charging Power", native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT),
    PecronSensorDescription(key="pv_energy_session", name="PV Energy (Session)", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=2),
    PecronSensorDescription(key="pv_energy_total", name="PV Energy Total", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=2),
    PecronSensorDescription(key="ac_charge_energy_session", name="AC Charge Energy (Session)", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=2),
    PecronSensorDescription(key="ac_charge_energy_total", name="AC Charge Energy Total", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=2),
    PecronSensorDescription(key="dc_output_energy_session", name="DC Output Energy (Session)", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=2),
    PecronSensorDescription(key="dc_output_energy_total", name="DC Output Energy Total", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=2),
    PecronSensorDescription(key="ac_output_energy_session", name="AC Output Energy (Session)", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=2),
    PecronSensorDescription(key="ac_output_energy_total", name="AC Output Energy Total", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=2),
]


class PecronSensor(PecronEntity, SensorEntity):
    entity_description: PecronSensorDescription

    def __init__(self, coordinator: PecronCoordinator, entry: ConfigEntry, description: PecronSensorDescription) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description
        self._controls = entry.data.get(CONF_CONTROLS) or CONTROLS

    def _enum_percentage(self, code: str, raw: object, fallback_options: list[str]) -> object:
        labels = enum_labels_for(code, self._controls.get(code, {}), fallback_options)
        try:
            lookup_value = int(raw)
        except (TypeError, ValueError):
            lookup_value = raw
        label = labels.get(lookup_value)
        if not label:
            return raw
        stripped = label.strip()
        if not stripped.endswith("%"):
            return raw
        try:
            percentage = float(stripped[:-1])
        except ValueError:
            return raw
        return int(percentage) if percentage.is_integer() else percentage

    @property
    def native_value(self) -> object:
        if not self.coordinator.data:
            return None
        raw = _get_field(self.coordinator.data, SENSOR_FIELDS.get(self.entity_description.key, []))
        key = self.entity_description.key
        if key == "device_status_hm" and raw is not None:
            return _device_status_label(raw, self._controls)
        if key == "activity":
            return _activity(self.coordinator.data)
        if key == "alarm":
            # Absent while no alarm is active (the field is only in the
            # model's TSL, not in normal polls).
            return ALARM_NONE if raw is None else _alarm_label(raw)
        if key == "remain_time" and raw is not None:
            # No load: the device sends a placeholder, not a real estimate.
            if raw >= REMAIN_TIME_NO_LOAD or _power(self.coordinator.data, "total_output_power") <= 0:
                return None
            return raw
        if self.entity_description.device_class == SensorDeviceClass.ENERGY and raw is not None:
            # Values arrive as float32 (1.73000001907349); trim the noise.
            return round(float(raw), 3)
        if self.entity_description.key == "charge_status" and raw is not None:
            return CHARGE_STATUS_LABELS.get(int(raw), str(raw))
        if self.entity_description.key == "ac_charging_power" and raw is not None:
            return self._enum_percentage(
                "ac_charging_power_ios",
                raw,
                AC_CHARGING_POWER_OPTIONS,
            )
        return raw


    @property
    def extra_state_attributes(self) -> dict | None:
        if self.entity_description.key != "alarm" or not self.coordinator.data:
            return None
        raw = _get_field(self.coordinator.data, SENSOR_FIELDS["alarm"])
        return {"code": 0 if raw is None else _alarm_code(raw)}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: PecronCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        PecronSensor(coordinator, entry, desc)
        for desc in SENSOR_DESCRIPTIONS
        if reported(coordinator.data, SENSOR_FIELDS.get(desc.key, []))
        or (desc.key == "alarm" and alarm_defined(entry))
    ]
    async_remove_unreported(hass, entry, "sensor", {e.unique_id for e in entities})
    async_add_entities(entities)
