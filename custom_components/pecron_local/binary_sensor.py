# custom_components/pecron_local/binary_sensor.py
from __future__ import annotations
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SENSOR_FIELDS
from .coordinator import PecronCoordinator
from .entity import PecronEntity, async_remove_unreported, reported
from .sensor import _get_field


@dataclass(frozen=True, kw_only=True)
class PecronBinarySensorDescription(BinarySensorEntityDescription):
    key: str


BINARY_SENSOR_DESCRIPTIONS: list[PecronBinarySensorDescription] = [
    PecronBinarySensorDescription(key="power_pack_attached", name="Power Pack Attached"),
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
        return bool(val) if val is not None else None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: PecronCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        PecronBinarySensor(coordinator, entry, desc)
        for desc in BINARY_SENSOR_DESCRIPTIONS
        if reported(coordinator.data, SENSOR_FIELDS.get(desc.key, []))
    ]
    async_remove_unreported(hass, entry, "binary_sensor", {e.unique_id for e in entities})
    async_add_entities(entities)
