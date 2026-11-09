# custom_components/pecron_local/entity.py
from __future__ import annotations

import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
from .coordinator import PecronCoordinator

# How long a control keeps showing the value just written while the device
# catches up. Cleared early as soon as the device reports that value. Longer
# than one poll interval so a slow device is confirmed by the regular poll.
PENDING_TIMEOUT = 45.0


class PecronEntity(CoordinatorEntity[PecronCoordinator]):
    """Base entity. Unavailable when coordinator has no data."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PecronCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Pecron",
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None


class PecronControlEntity(PecronEntity):
    """Switch/select base: shows the written value until the device confirms it.

    Without this, the refresh after a write can return the device's old value
    and the control flips back for a few seconds before settling.
    """

    _pending_value: object | None = None
    _pending_until: float = 0.0

    def _device_value(self) -> object | None:
        """Current value as reported by the device (in the entity's own terms)."""
        raise NotImplementedError

    def _displayed_value(self) -> object | None:
        if self._pending_value is not None:
            if time.monotonic() < self._pending_until:
                return self._pending_value
            self._pending_value = None
        return self._device_value()

    async def _async_write(self, shown_value: object, data_point_id: int, raw_value: object, ctrl_type: str) -> None:
        # Raises HomeAssistantError on failure; the UI then shows the error and
        # the control stays at the device's real state.
        await self.coordinator.async_write(data_point_id, raw_value, ctrl_type)
        self._pending_value = shown_value
        self._pending_until = time.monotonic() + PENDING_TIMEOUT
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._pending_value is not None and self._device_value() == self._pending_value:
            self._pending_value = None
        super()._handle_coordinator_update()

