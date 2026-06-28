# tests/test_switch.py
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from custom_components.pecron_local.const import CONF_CONTROLS
from custom_components.pecron_local.switch import (
    PecronSwitch,
    SWITCH_DESCRIPTIONS,
    _has_writable_control,
)


def test_switch_descriptions_include_ac():
    keys = [s.key for s in SWITCH_DESCRIPTIONS]
    assert "ac_switch_hm" in keys


def test_switch_descriptions_include_dc_and_ups():
    keys = [s.key for s in SWITCH_DESCRIPTIONS]
    assert "dc_switch_hm" in keys
    assert "ups_status_hm" in keys


def _entry(controls: dict):
    return SimpleNamespace(
        entry_id="entry-1",
        title="Pecron Test",
        data={CONF_CONTROLS: controls},
    )


def _coordinator(data: dict):
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.active_transport = MagicMock()
    coordinator.active_transport.write = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


def _switch_description(key: str):
    return next(desc for desc in SWITCH_DESCRIPTIONS if desc.key == key)


async def test_touch_lock_uses_f3000_false_touch_code_for_state_and_write():
    controls = {"false_touch_us": {"id": 86, "type": "BOOL", "access": "RW"}}
    coordinator = _coordinator({"false_touch_us": True})
    entity = PecronSwitch(coordinator, _entry(controls), _switch_description("device_touch_locking_as"))

    assert entity.is_on is True

    await entity.async_turn_off()

    coordinator.active_transport.write.assert_awaited_once_with(86, False, "BOOL")


async def test_eco_mode_uses_f3000_eco_onoff_code_for_state_and_write():
    controls = {"eco_onoff_us": {"id": 84, "type": "BOOL", "access": "RW"}}
    coordinator = _coordinator({"eco_onoff_us": "false"})
    entity = PecronSwitch(coordinator, _entry(controls), _switch_description("eco_quite_mode_as"))

    assert entity.is_on is False

    await entity.async_turn_on()

    coordinator.active_transport.write.assert_awaited_once_with(84, True, "BOOL")


def test_read_only_tsl_control_is_not_exposed_as_switch():
    desc = _switch_description("ups_status_hm")

    assert _has_writable_control(desc, {"ups_status_hm": {"id": 27, "access": "R"}}) is False
