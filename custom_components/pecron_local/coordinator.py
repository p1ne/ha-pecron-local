from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .transport.base import PecronTransport, TransportError

_LOGGER = logging.getLogger(__name__)

# How long after a write to re-read the device. Pecron firmware applies a
# change and reports it back with a short delay, so an immediate read returns
# the old value.
WRITE_REFRESH_DELAY = 3.0


class PecronCoordinator(DataUpdateCoordinator[dict]):
    """Poll device via TCP then BLE fallback. Tracks active transport for writes."""

    def __init__(
        self,
        hass: HomeAssistant,
        tcp: PecronTransport | None,
        ble: PecronTransport | None,
        poll_interval: int = 30,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Pecron Local",
            update_interval=timedelta(seconds=poll_interval),
        )
        self._transports = [t for t in [tcp, ble] if t is not None]
        self.active_transport: PecronTransport | None = None
        # Serialises polls and writes: both share one connection to the device.
        self._io_lock = asyncio.Lock()
        self._unsub_write_refresh: CALLBACK_TYPE | None = None

    def _ordered_transports(self) -> list[PecronTransport]:
        """Last working transport first, then the rest in configured order."""
        if self.active_transport in self._transports:
            return [self.active_transport] + [
                t for t in self._transports if t is not self.active_transport
            ]
        return list(self._transports)

    async def _async_update_data(self) -> dict:
        async with self._io_lock:
            errors: list[str] = []
            for transport in self._transports:
                # Attempt up to 2 tries per transport: once with an existing
                # connection and once after a fresh connect. Pecron firmware
                # closes the TCP socket between polls, so the second attempt
                # handles the reconnect transparently.
                for attempt in range(2):
                    try:
                        if not transport.connected:
                            await transport.connect()
                        data = await transport.read()
                        self.active_transport = transport
                        return data
                    except TransportError as exc:
                        _LOGGER.debug(
                            "Transport %s attempt %d failed: %s",
                            type(transport).__name__, attempt + 1, exc,
                        )
                        try:
                            await transport.disconnect()
                        except Exception:
                            pass
                        if attempt == 1:
                            errors.append(f"{type(transport).__name__}: {exc}")

            self.active_transport = None
            raise UpdateFailed(f"All transports failed — {'; '.join(errors)}")

    async def async_write(self, data_point_id: int, value: object, ctrl_type: str) -> None:
        """Write a data point, reconnecting if the device dropped the session.

        Raises HomeAssistantError so the UI shows a failed command instead of
        silently reverting the control.
        """
        errors: list[str] = []
        async with self._io_lock:
            for transport in self._ordered_transports():
                for attempt in range(2):
                    try:
                        if not transport.connected:
                            await transport.connect()
                        await transport.write(data_point_id, value, ctrl_type)
                        self.active_transport = transport
                        _LOGGER.debug(
                            "Wrote data point %d = %s via %s",
                            data_point_id, value, type(transport).__name__,
                        )
                        self._schedule_write_refresh()
                        return
                    except TransportError as exc:
                        _LOGGER.debug(
                            "Write via %s attempt %d failed: %s",
                            type(transport).__name__, attempt + 1, exc,
                        )
                        try:
                            await transport.disconnect()
                        except Exception:
                            pass
                        if attempt == 1:
                            errors.append(f"{type(transport).__name__}: {exc}")

        raise HomeAssistantError(
            f"Pecron did not accept the command — {'; '.join(errors) or 'no transport configured'}"
        )

    @callback
    def _schedule_write_refresh(self) -> None:
        """Re-read the device shortly after a write (one refresh for a burst of writes)."""
        if self._unsub_write_refresh:
            self._unsub_write_refresh()

        @callback
        def _refresh(_now) -> None:
            self._unsub_write_refresh = None
            self.hass.async_create_task(self.async_refresh())

        self._unsub_write_refresh = async_call_later(
            self.hass, WRITE_REFRESH_DELAY, _refresh
        )

    async def async_shutdown(self) -> None:
        if self._unsub_write_refresh:
            self._unsub_write_refresh()
            self._unsub_write_refresh = None
        await super().async_shutdown()
