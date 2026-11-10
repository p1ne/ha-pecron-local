# custom_components/pecron_local/binary_sensor.py
from __future__ import annotations
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SENSOR_FIELDS
from .coordinator import PecronCoordinator
from .entity import PecronEntity, alarm_defined, async_remove_unreported, reported
from .sensor import _get_field


@dataclass(frozen=True, kw_only=True)
class PecronBinarySensorDescription(BinarySensorEntityDescription):
    key: str
    # Value that means "off"; anything else is "on".
    off_value: object = False
    # Treat a missing field as "off" (alarm fields are only sent while active).
    missing_is_off: bool = False


BINARY_SENSOR_DESCRIPTIONS: list[PecronBinarySensorDescription] = [
    PecronBinarySensorDescription(key="power_pack_attached", name="Power Pack Attached"),
    PecronBinarySensorDescription(
        key="alarm_active",
        name="Alarm Active",
        device_class=BinarySensorDeviceClass.PROBLEM,
        off_value=0,
        missing_is_off=True,
    ),
]


class PecronBinarySensor(PecronEntity, BinarySensorEntity):
    entity_description: PecronBinarySensorDescription

    def __init__(self, coordinator: PecronCoordinator, entry: ConfigEntry, description: PecronBinarySensorDescription) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.data:
            return None
        val = _get_field(self.coordinator.data, SENSOR_FIELDS.get(self.entity_description.key, []))
        if val is None:
            return False if self.entity_description.missing_is_off else None
        if self.entity_description.off_value is False:
            return bool(val)
        try:
            return int(val) != int(self.entity_description.off_value)
        except (TypeError, ValueError):
            return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: PecronCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        PecronBinarySensor(coordinator, entry, desc)
        for desc in BINARY_SENSOR_DESCRIPTIONS
        if reported(coordinator.data, SENSOR_FIELDS.get(desc.key, []))
        or (desc.key == "alarm_active" and alarm_defined(entry))
    ]
    async_remove_unreported(hass, entry, "binary_sensor", {e.unique_id for e in entities})
    async_add_entities(entities)
