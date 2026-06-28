# tests/test_sensor.py
from types import SimpleNamespace
from unittest.mock import MagicMock
from custom_components.pecron_local.sensor import PecronSensor, _get_field, SENSOR_DESCRIPTIONS
from custom_components.pecron_local.const import CONF_CONTROLS, SENSOR_FIELDS


def test_get_field_top_level():
    kv = {"battery_percentage": 75}
    val = _get_field(kv, SENSOR_FIELDS["battery_percent"])
    assert val == 75


def test_get_field_nested():
    kv = {"host_packet_data_jdb": {"host_packet_electric_percentage": 80}}
    val = _get_field(kv, SENSOR_FIELDS["battery_percent"])
    assert val == 80


def test_get_field_missing_returns_none():
    val = _get_field({}, SENSOR_FIELDS["battery_percent"])
    assert val is None


def test_get_field_ac_output_power():
    kv = {"ac_data_output_hm": {"ac_output_power": 500}}
    val = _get_field(kv, SENSOR_FIELDS["ac_output_power"])
    assert val == 500


def test_sensor_descriptions_include_battery():
    codes = [d.key for d in SENSOR_DESCRIPTIONS]
    assert "battery_percent" in codes


def test_sensor_descriptions_include_solar_ports():
    codes = [d.key for d in SENSOR_DESCRIPTIONS]
    assert "dc5521_input_power" in codes
    assert "gx16mf1_input_power" in codes
    assert "gx16mf2_input_power" in codes


def _entry(controls: dict | None = None):
    return SimpleNamespace(
        entry_id="entry-1",
        title="Pecron Test",
        data={CONF_CONTROLS: controls or {}},
    )


def _coordinator(data: dict):
    coordinator = MagicMock()
    coordinator.data = data
    return coordinator


def _sensor_description(key: str):
    return next(desc for desc in SENSOR_DESCRIPTIONS if desc.key == key)


def test_device_status_reports_cloud_enum_label_exactly_even_when_power_flows():
    controls = {"device_status_hm": {"enum_labels": {0: "Shutdown"}}}
    entity = PecronSensor(
        _coordinator({"device_status_hm": 0, "ac_data_output_hm": {"ac_output_power": 250}}),
        _entry(controls),
        _sensor_description("device_status_hm"),
    )

    assert entity.native_value == "Shutdown"


def test_device_status_uses_builtin_label_when_cloud_enum_missing():
    entity = PecronSensor(
        _coordinator({"device_status_hm": 0}),
        _entry(),
        _sensor_description("device_status_hm"),
    )

    assert entity.native_value == "Shut Down"


def test_device_status_uses_cloud_enum_label_when_not_overridden():
    controls = {"device_status_hm": {"enum_labels": {4: "Standby Status"}}}
    entity = PecronSensor(
        _coordinator({"device_status_hm": 4}),
        _entry(controls),
        _sensor_description("device_status_hm"),
    )

    assert entity.native_value == "Standby Status"
