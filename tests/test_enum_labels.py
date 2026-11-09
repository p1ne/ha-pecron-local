from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from custom_components.pecron_local.const import CONF_CONTROLS, enum_labels_from_specs, enum_labels_for
from custom_components.pecron_local.select import PecronSelect, SELECT_DESCRIPTIONS
from custom_components.pecron_local.sensor import PecronSensor, SENSOR_DESCRIPTIONS


F3000_AC_CHARGE_LABELS = {
    0: "20%",
    1: "40%",
    2: "60%",
    3: "80%",
    4: "100%",
}


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


def test_enum_labels_from_cloud_specs():
    specs = [
        {"dataType": "ENUM", "name": "20%", "value": "0"},
        {"dataType": "ENUM", "name": "100%", "value": "4"},
    ]

    assert enum_labels_from_specs(specs) == {0: "20%", 4: "100%"}


def test_enum_labels_for_prefers_cloud_labels_over_fallback():
    info = {"enum_labels": F3000_AC_CHARGE_LABELS}

    labels = enum_labels_for("ac_charging_power_ios", info, ["0%", "10%"])

    assert labels[4] == "100%"


async def test_select_uses_cloud_enum_values_for_options_and_writes():
    desc = next(d for d in SELECT_DESCRIPTIONS if d.key == "ac_charging_power_ios")
    controls = {
        "ac_charging_power_ios": {
            "id": 89,
            "type": "ENUM",
            "enum_labels": F3000_AC_CHARGE_LABELS,
        }
    }
    coordinator = _coordinator({"ac_charging_power_ios": 4})
    entity = _detached(PecronSelect(coordinator, _entry(controls), desc))

    assert entity.options == ["20%", "40%", "60%", "80%", "100%"]
    assert entity.current_option == "100%"

    await entity.async_select_option("100%")

    coordinator.async_write.assert_awaited_once_with(89, 4, "ENUM")


def test_ac_charging_power_sensor_decodes_cloud_enum_to_percentage():
    desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "ac_charging_power")
    controls = {
        "ac_charging_power_ios": {
            "id": 89,
            "type": "ENUM",
            "enum_labels": F3000_AC_CHARGE_LABELS,
        }
    }
    coordinator = _coordinator({"ac_charging_power_ios": 4})
    entity = PecronSensor(coordinator, _entry(controls), desc)

    assert entity.native_value == 100
