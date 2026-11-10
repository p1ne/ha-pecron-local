# custom_components/pecron_local/select.py
from __future__ import annotations
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    AC_CHARGING_POWER_OPTIONS,
    AC_FREQUENCY_OPTIONS,
    AC_VOLTAGE_OPTIONS,
    AUTO_OFF_OPTIONS,
    CONF_CONTROLS,
    CONTROLS,
    DOMAIN,
    KEY_BRIGHTNESS_OPTIONS,
    SCREEN_BRIGHTNESS_OPTIONS,
    SCREEN_ENERGY_DISPLAY_OPTIONS,
    STANDBY_TIMEOUT_OPTIONS,
    enum_labels_for,
    enum_options,
)
from .coordinator import PecronCoordinator
from .entity import PecronControlEntity, async_remove_unreported, reported
from .sensor import _get_field


@dataclass(frozen=True, kw_only=True)
class PecronSelectDescription(SelectEntityDescription):
    key: str
    data_point_id: int
    options: list[str]
    # Labels from the user manual, used instead of the TSL's when both define
    # exactly the same values (so a different model's enum is never relabelled).
    display_labels: dict[int, str] | None = None


SELECT_DESCRIPTIONS: list[PecronSelectDescription] = [
    PecronSelectDescription(key="ac_charging_power_ios", name="AC Charging Power", data_point_id=50, options=AC_CHARGING_POWER_OPTIONS),
    PecronSelectDescription(key="machine_screen_light_as", name="Screen Brightness", data_point_id=45, options=SCREEN_BRIGHTNESS_OPTIONS),
    PecronSelectDescription(key="device_standy_times_as", name="Standby Timeout", data_point_id=51, options=STANDBY_TIMEOUT_OPTIONS),
    PecronSelectDescription(key="ac_output_voltage_io", name="AC Output Voltage", data_point_id=32, options=AC_VOLTAGE_OPTIONS),
    PecronSelectDescription(key="ac_output_frequency_io", name="AC Output Frequency", data_point_id=33, options=AC_FREQUENCY_OPTIONS),
    PecronSelectDescription(key="noastime_io", name="Auto-Off Time", data_point_id=34, options=AUTO_OFF_OPTIONS),
    PecronSelectDescription(key="key_light_us", name="Button Brightness", data_point_id=88, options=KEY_BRIGHTNESS_OPTIONS, display_labels=dict(enumerate(KEY_BRIGHTNESS_OPTIONS))),
    PecronSelectDescription(key="screen_power_statistics_mode_us", name="Statistics Display", data_point_id=85, options=SCREEN_ENERGY_DISPLAY_OPTIONS, display_labels=dict(enumerate(SCREEN_ENERGY_DISPLAY_OPTIONS))),
]


def _labels_for_description(description: PecronSelectDescription, controls: dict | None) -> dict:
    info = (controls or {}).get(description.key, {})
    labels = enum_labels_for(description.key, info, description.options)
    if description.display_labels:
        try:
            values = {int(v) for v in labels}
        except (TypeError, ValueError):
            values = set()
        if values == set(description.display_labels):
            return dict(description.display_labels)
    return labels


def _option_value_maps(labels: dict) -> tuple[dict[object, str], dict[str, object]]:
    value_to_option = dict(labels)
    option_to_value = {option: value for value, option in labels.items()}
    return value_to_option, option_to_value


class PecronSelect(PecronControlEntity, SelectEntity):
    entity_description: PecronSelectDescription

    def __init__(self, coordinator: PecronCoordinator, entry: ConfigEntry, description: PecronSelectDescription) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description
        self._controls = entry.data.get(CONF_CONTROLS) or CONTROLS
        info = self._controls.get(description.key, {})
        self._data_point_id = int(info.get("id", description.data_point_id))
        labels = _labels_for_description(description, self._controls)
        self._value_to_option, self._option_to_value = _option_value_maps(labels)
        self._attr_options = enum_options(labels)

    def _device_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        val = _get_field(self.coordinator.data, [(self.entity_description.key,)])
        if val is None:
            return None
        try:
            lookup_value = int(val)
        except (TypeError, ValueError):
            lookup_value = val
        return self._value_to_option.get(lookup_value)

    @property
    def current_option(self) -> str | None:
        return self._displayed_value()

    async def async_select_option(self, option: str) -> None:
        value = self._option_to_value[option]
        await self._async_write(option, self._data_point_id, value, "ENUM")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: PecronCoordinator = hass.data[DOMAIN][entry.entry_id]
    controls = entry.data.get(CONF_CONTROLS) or {}
    entities = [
        PecronSelect(coordinator, entry, desc)
        for desc in SELECT_DESCRIPTIONS
        # With a cloud TSL, the model must define the control; either way the
        # device must actually report it.
        if (not controls or desc.key in controls)
        and reported(coordinator.data, [(desc.key,)])
    ]
    async_remove_unreported(hass, entry, "select", {e.unique_id for e in entities})
    async_add_entities(entities)
