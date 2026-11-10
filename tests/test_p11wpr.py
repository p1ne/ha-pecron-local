"""Entity set and values for a real p11wPr device (controls + poll from diagnostics)."""
import json
import pathlib
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.pecron_local import binary_sensor as BS
from custom_components.pecron_local import select as SEL
from custom_components.pecron_local import sensor as SEN
from custom_components.pecron_local import switch as SW
from custom_components.pecron_local.const import CONF_CONTROLS, DOMAIN

FIXTURE = json.loads((pathlib.Path(__file__).parent / "fixtures" / "p11wpr.json").read_text())


def _setup(data=None):
    coordinator = MagicMock()
    coordinator.data = data if data is not None else json.loads(json.dumps(FIXTURE["coordinator_data"]))
    entry = SimpleNamespace(entry_id="E1", title="Pecron @ test", data={CONF_CONTROLS: FIXTURE["controls"]})
    hass = SimpleNamespace(data={DOMAIN: {"E1": coordinator}})
    return hass, entry, coordinator


async def _entities(module, data=None):
    hass, entry, coordinator = _setup(data)
    added = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(module, "async_remove_unreported", lambda *a, **k: None)
        await module.async_setup_entry(hass, entry, added.extend)
    return {e._key: e for e in added}, coordinator


async def test_p11wpr_switches():
    ents, _ = await _entities(SW)
    assert set(ents) == {
        "ac_switch_hm", "dc_switch_hm", "ups_status_hm", "device_touch_locking_as",
        "auto_light_flag_as", "eco_quite_mode_as", "beep_voice_us",
    }
    assert ents["device_touch_locking_as"]._data_point_id == 86
    assert ents["eco_quite_mode_as"]._data_point_id == 84
    assert ents["beep_voice_us"]._data_point_id == 87
    assert ents["ups_status_hm"]._writable is False


async def test_p11wpr_selects_use_model_labels():
    ents, _ = await _entities(SEL)
    assert set(ents) == {"ac_charging_power_ios", "device_standy_times_as", "key_light_us", "screen_power_statistics_mode_us"}
    assert ents["ac_charging_power_ios"]._data_point_id == 89
    assert ents["ac_charging_power_ios"].current_option == "100%"
    # Manual labels replace the TSL's (OFF/10%/50%/100%) for the same values.
    assert ents["key_light_us"]._attr_options == ["Off", "L1", "L2", "L3"]
    assert ents["key_light_us"].current_option == "L3"
    assert ents["screen_power_statistics_mode_us"].current_option == "Solar Input"
    # Writes still send the device's numeric value.
    assert ents["key_light_us"]._option_to_value["L1"] == 1


def test_manual_labels_not_applied_to_a_different_enum():
    from custom_components.pecron_local.select import SELECT_DESCRIPTIONS, _labels_for_description

    desc = next(d for d in SELECT_DESCRIPTIONS if d.key == "key_light_us")
    other = {"key_light_us": {"enum_labels": {"0": "Low", "1": "High"}}}
    assert _labels_for_description(desc, other) == {0: "Low", 1: "High"}


async def test_p11wpr_sensors():
    ents, _ = await _entities(SEN)
    for key in ("pv_energy_total", "ac_charge_energy_total", "ac_output_energy_total", "dc_output_energy_session"):
        assert key in ents
    for key in ("battery_temp", "inverter_temp", "dc5521_input_power", "gx16mf1_input_power"):
        assert key not in ents
    assert ents["ac_charge_energy_total"].native_value == 1.73
    assert ents["battery_percent"].native_value == 100


async def test_activity_follows_power_flow_and_status_stays_raw():
    ents, coordinator = await _entities(SEN)
    activity = ents["activity"]
    assert activity.native_value == "Idle"
    # Device Status stays exactly what the firmware reports.
    assert ents["device_status_hm"].native_value == "Shutdown"

    coordinator.data["total_input_power"] = 120
    assert activity.native_value == "Charging"

    coordinator.data["total_input_power"] = 0
    coordinator.data["ac_data_output_hm"]["ac_output_power"] = 80
    assert activity.native_value == "Discharging"

    coordinator.data["ac_data_output_hm"]["ac_output_power"] = 0
    coordinator.data["dc_data_output_hm"]["dc_output_power"] = 12
    assert activity.native_value == "Discharging"


async def test_time_to_empty_unknown_without_load():
    ents, coordinator = await _entities(SEN)
    tte = ents["remain_time"]
    assert tte.native_value is None  # 6000 placeholder, no load

    coordinator.data["total_output_power"] = 150
    coordinator.data["remain_time"] = 420
    assert tte.native_value == 420


async def test_power_pack_and_alarm_binary_sensors():
    ents, coordinator = await _entities(BS)
    assert set(ents) == {"power_pack_attached", "alarm_active"}
    assert ents["power_pack_attached"].is_on is False
    # p11wPr omits the alarm field from normal polls; its TSL defines it.
    assert "FAULT_ALARM_ENUM" not in coordinator.data
    assert ents["alarm_active"].is_on is False
    coordinator.data["FAULT_ALARM_ENUM"] = 0
    assert ents["alarm_active"].is_on is False
    coordinator.data["FAULT_ALARM_ENUM"] = 21
    assert ents["alarm_active"].is_on is True


async def test_alarm_sensor_uses_manual_codes():
    ents, coordinator = await _entities(SEN)
    alarm = ents["alarm"]
    assert alarm.native_value == "None"
    assert alarm.extra_state_attributes == {"code": 0}
    coordinator.data["FAULT_ALARM_ENUM"] = 0
    assert alarm.native_value == "None"

    coordinator.data["FAULT_ALARM_ENUM"] = 21
    assert alarm.native_value == "E21 Inverter overtemperature"
    coordinator.data["FAULT_ALARM_ENUM"] = 2
    assert alarm.native_value == "E02 Battery pack undervoltage"
    coordinator.data["FAULT_ALARM_ENUM"] = 99
    assert alarm.native_value == "E99"
    assert alarm.extra_state_attributes == {"code": 99}


async def test_alarm_entities_not_created_without_tsl_or_field():
    hass, entry, coordinator = _setup({"battery_percentage": 50, "total_input_power": 0})
    entry.data = {}
    added = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(BS, "async_remove_unreported", lambda *a, **k: None)
        await BS.async_setup_entry(hass, entry, added.extend)
    assert added == []
