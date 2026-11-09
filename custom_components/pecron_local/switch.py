# custom_components/pecron_local/switch.py
from __future__ import annotations
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_CONTROLS, CONTROLS, DOMAIN, SENSOR_FIELDS
from .coordinator import PecronCoordinator
from .entity import PecronControlEntity, async_remove_unreported, reported
from .sensor import _get_field


@dataclass(frozen=True, kw_only=True)
class PecronSwitchDescription(SwitchEntityDescription):
    key: str
    data_point_id: int
    resource_codes: tuple[str, ...] = ()
    allow_read_only: bool = False


SWITCH_DESCRIPTIONS: list[PecronSwitchDescription] = [
    PecronSwitchDescription(key="ac_switch_hm", name="AC Output", data_point_id=40),
    PecronSwitchDescription(key="dc_switch_hm", name="DC Output", data_point_id=38),
    PecronSwitchDescription(
        key="ups_status_hm",
        name="UPS Mode",
        data_point_id=27,
        allow_read_only=True,
    ),
    PecronSwitchDescription(
        key="device_touch_locking_as",
        name="Touch Lock",
        data_point_id=42,
        resource_codes=("device_touch_locking_as", "false_touch_us"),
    ),
    PecronSwitchDescription(key="auto_light_flag_as", name="Auto Screen Light", data_point_id=43),
    PecronSwitchDescription(key="beep_voice_us", name="Buzzer", data_point_id=87),
    PecronSwitchDescription(
        key="eco_quite_mode_as",
        name="Eco/Quiet Mode",
        data_point_id=44,
        resource_codes=("eco_quite_mode_as", "eco_onoff_us"),
    ),
]

_SWITCH_FIELD_MAP = {
    "ac_switch_hm": SENSOR_FIELDS.get("ac_switch", [("ac_switch_hm",)]),
    "dc_switch_hm": SENSOR_FIELDS.get("dc_switch", [("dc_switch_hm",)]),
    "ups_status_hm": SENSOR_FIELDS.get("ups_mode", [("ups_status_hm",)]),
    "device_touch_locking_as": [("device_touch_locking_as",)],
    "auto_light_flag_as": [("auto_light_flag_as",)],
    "eco_quite_mode_as": [("eco_quite_mode_as",)],
    "beep_voice_us": [("beep_voice_us",)],
}


def _truthy(value) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y", "on", "open", "enabled"}
    return bool(value)


def _resource_codes(description: PecronSwitchDescription) -> tuple[str, ...]:
    return description.resource_codes or (description.key,)


def _resolve_control(description: PecronSwitchDescription, controls: dict) -> tuple[str, dict]:
    for code in _resource_codes(description):
        info = controls.get(code)
        if info is not None and "W" in str(info.get("access", "RW")).upper():
            return code, info
    for code in _resource_codes(description):
        info = controls.get(code)
        if info is not None:
            return code, info
    return description.key, controls.get(description.key, {})


def _field_paths(description: PecronSwitchDescription, control_code: str) -> list[tuple]:
    base_paths = _SWITCH_FIELD_MAP.get(description.key, [(description.key,)])
    return [(control_code,)] + [path for path in base_paths if path != (control_code,)]


def _has_writable_control(description: PecronSwitchDescription, controls: dict) -> bool:
    if not controls:
        return True
    for code in _resource_codes(description):
        info = controls.get(code)
        if info and "W" in str(info.get("access", "RW")).upper():
            return True
        if info and description.allow_read_only:
            return True
    return False


class PecronSwitch(PecronControlEntity, SwitchEntity):
    entity_description: PecronSwitchDescription

    def __init__(self, coordinator: PecronCoordinator, entry: ConfigEntry, description: PecronSwitchDescription) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description
        self._controls = entry.data.get(CONF_CONTROLS) or CONTROLS
        self._control_code, info = _resolve_control(description, self._controls)
        self._data_point_id = int(info.get("id", description.data_point_id))
        self._writable = "W" in str(info.get("access", "RW")).upper()
        self._field_paths = _field_paths(description, self._control_code)

    def _device_value(self) -> bool | None:
        if not self.coordinator.data:
            return None
        return _truthy(_get_field(self.coordinator.data, self._field_paths))

    @property
    def is_on(self) -> bool | None:
        return self._displayed_value()

    async def async_turn_on(self, **kwargs) -> None:
        await self._send_write(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._send_write(False)

    async def _send_write(self, value: bool) -> None:
        if not self._writable:
            # Shown for status only on models whose TSL marks it read-only.
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(
                f"{self.entity_description.name} is read-only on this model"
            )
        await self._async_write(value, self._data_point_id, value, "BOOL")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: PecronCoordinator = hass.data[DOMAIN][entry.entry_id]
    controls = entry.data.get(CONF_CONTROLS) or {}
    resolve_from = controls or CONTROLS
    entities = [
        PecronSwitch(coordinator, entry, desc)
        for desc in SWITCH_DESCRIPTIONS
        if _has_writable_control(desc, controls)
        and reported(coordinator.data, _field_paths(desc, _resolve_control(desc, resolve_from)[0]))
    ]
    async_remove_unreported(hass, entry, "switch", {e.unique_id for e in entities})
    async_add_entities(entities)
