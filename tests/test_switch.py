# tests/test_switch.py
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError

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
    coordinator.async_write = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


def _detached(entity):
    # Not added to hass in these tests; state writes are no-ops.
    entity.async_write_ha_state = MagicMock()
    return entity


def _switch_description(key: str):
    return next(desc for desc in SWITCH_DESCRIPTIONS if desc.key == key)


async def test_touch_lock_uses_f3000_false_touch_code_for_state_and_write():
    controls = {"false_touch_us": {"id": 86, "type": "BOOL", "access": "RW"}}
    coordinator = _coordinator({"false_touch_us": True})
    entity = _detached(PecronSwitch(coordinator, _entry(controls), _switch_description("device_touch_locking_as")))

    assert entity.is_on is True

    await entity.async_turn_off()

    coordinator.async_write.assert_awaited_once_with(86, False, "BOOL")


async def test_eco_mode_uses_f3000_eco_onoff_code_for_state_and_write():
    controls = {"eco_onoff_us": {"id": 84, "type": "BOOL", "access": "RW"}}
    coordinator = _coordinator({"eco_onoff_us": "false"})
    entity = _detached(PecronSwitch(coordinator, _entry(controls), _switch_description("eco_quite_mode_as")))

    assert entity.is_on is False

    await entity.async_turn_on()

    coordinator.async_write.assert_awaited_once_with(84, True, "BOOL")


def test_read_only_ups_mode_stays_visible():
    desc = _switch_description("ups_status_hm")

    assert _has_writable_control(desc, {"ups_status_hm": {"id": 27, "access": "R"}}) is True


async def test_read_only_ups_mode_does_not_send_write():
    controls = {"ups_status_hm": {"id": 27, "type": "BOOL", "access": "R"}}
    coordinator = _coordinator({"ups_status_hm": True})
    entity = _detached(PecronSwitch(coordinator, _entry(controls), _switch_description("ups_status_hm")))

    assert entity.is_on is True

    with pytest.raises(HomeAssistantError):
        await entity.async_turn_off()

    coordinator.async_write.assert_not_awaited()
    coordinator.async_request_refresh.assert_awaited_once()


def test_read_only_non_status_control_is_not_exposed_as_switch():
    desc = _switch_description("auto_light_flag_as")

    assert _has_writable_control(desc, {"auto_light_flag_as": {"id": 43, "access": "R"}}) is False


async def test_switch_shows_written_value_until_device_confirms():
    coordinator = _coordinator({"ac_switch_hm": False})
    entity = _detached(PecronSwitch(coordinator, _entry({}), _switch_description("ac_switch_hm")))

    await entity.async_turn_on()
    assert entity.is_on is True

    # Device still reports the old value right after the command.
    entity._handle_coordinator_update()
    assert entity.is_on is True

    coordinator.data = {"ac_switch_hm": True}
    entity._handle_coordinator_update()
    assert entity._pending_value is None

    # A later change on the device itself is shown.
    coordinator.data = {"ac_switch_hm": False}
    assert entity.is_on is False


async def test_failed_write_keeps_device_state():
    coordinator = _coordinator({"ac_switch_hm": False})
    coordinator.async_write = AsyncMock(side_effect=HomeAssistantError("nope"))
    entity = _detached(PecronSwitch(coordinator, _entry({}), _switch_description("ac_switch_hm")))

    with pytest.raises(HomeAssistantError):
        await entity.async_turn_on()

    assert entity.is_on is False
