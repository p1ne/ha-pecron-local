# custom_components/pecron_local/transport/tcp.py
"""Async TCP transport for Pecron devices on port 6607 (AES-CBC encrypted TTLV).

Ported from https://github.com/attractify-logan/pecron-monitor (MIT License).
Uses asyncio streams and the cryptography package (both bundled with HA).
"""
from __future__ import annotations

import asyncio
import base64
import logging
import struct

from ..protocol import (
    build_write_payload,
    _byte_stuff,
    aes_decrypt,
    aes_encrypt,
    build_iv_request,
    build_login_packet,
    build_read_packet,
    derive_iv,
    extract_iv_from_fields,
    fields_to_kv,
    parse_fields,
    parse_packet,
)
from ..const import DEFAULT_PORT
from .base import PecronTransport, TransportError

_LOGGER = logging.getLogger(__name__)


class TcpTransport(PecronTransport):
    """Async TCP transport. Keeps socket open between polls; reconnects on error."""

    def __init__(
        self,
        host: str,
        auth_key_b64: str,
        port: int = DEFAULT_PORT,
        timeout: float = 10.0,
        controls: dict | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.auth_key = base64.b64decode(auth_key_b64)
        self.timeout = timeout
        self.controls = controls

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._iv: bytes | None = None
        self._encrypted = False
        self._packet_id = 0
        self._lock = asyncio.Lock()
        self._first_read_done = False
        # Fields from the last read whose id isn't in the TSL map (diagnostics).
        self.last_unmapped: list = []

    @property
    def connected(self) -> bool:
        return self._encrypted and self._writer is not None

    def _next_pid(self) -> int:
        self._packet_id = (self._packet_id + 1) % 65535
        return self._packet_id

    async def connect(self) -> None:
        await self.disconnect()
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise TransportError(f"TCP connect failed: {exc}") from exc

        try:
            await self._handshake()
        except TransportError:
            await self.disconnect()
            raise

    async def _handshake(self) -> None:
        # Step 1: request random IV
        await self._send_raw(build_iv_request(self._next_pid()))
        resp_raw = await asyncio.wait_for(self._recv_packet(), timeout=self.timeout)
        resp = parse_packet(resp_raw)
        if resp.get("cmd") != 0x7033:
            raise TransportError(f"Expected 0x7033, got 0x{resp.get('cmd', 0):04x}")

        fields = parse_fields(resp["payload"])
        random_str = extract_iv_from_fields(fields)
        if not random_str:
            raise TransportError("No IV in 0x7033 response")

        # Step 2: login
        login_pkt = build_login_packet(self._next_pid(), self.auth_key, random_str)
        await self._send_raw(login_pkt)
        resp_raw = await asyncio.wait_for(self._recv_packet(), timeout=self.timeout)
        resp = parse_packet(resp_raw)
        if resp.get("cmd") != 0x7035:
            raise TransportError(f"Login failed — expected 0x7035, got 0x{resp.get('cmd', 0):04x}")

        fields = parse_fields(resp["payload"])
        for _, ftype, fval in fields:
            if ftype == "NUM" and fval != 0:
                raise TransportError(f"Login rejected (result={fval})")

        self._iv = derive_iv(random_str)
        self._encrypted = True
        _LOGGER.debug("TCP handshake complete for %s:%s", self.host, self.port)

    async def disconnect(self) -> None:
        self._encrypted = False
        self._iv = None
        self._first_read_done = False
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None

    async def _send_raw(self, data: bytes) -> None:
        assert self._writer is not None
        self._writer.write(data)
        await self._writer.drain()

    async def _recv_packet(self) -> bytes:
        """Read one TTLV packet from the stream.

        No asyncio.wait_for inside — callers own the timeout by wrapping this
        coroutine. Nesting wait_for on Python 3.12+ causes CancelledError to
        escape as a BaseException instead of being converted to TimeoutError.
        """
        assert self._reader is not None
        buf = b""
        # Sync to 0xAA 0xAA
        while True:
            b = await self._reader.read(1)
            if not b:
                raise TransportError("Connection closed")
            buf += b
            if len(buf) >= 2 and buf[-2:] == b"\xaa\xaa":
                buf = b"\xaa\xaa"
                break
            if len(buf) > 200:
                raise TransportError("No sync found in stream")

        # Everything after the sync word is byte-stuffed (0x55 inserted after
        # any 0xAA followed by 0x55/0xAA). The length field counts UNSTUFFED
        # bytes, so stuffing bytes must not count towards it, otherwise the
        # frame is cut short and its ciphertext fails to decrypt.
        raw = bytearray(buf)
        unstuffed = bytearray()
        prev: int | None = None
        needed = 2  # length field first, then the rest of the frame
        while len(unstuffed) < needed:
            chunk = await self._reader.read(min(needed - len(unstuffed), 4096))
            if not chunk:
                raise TransportError("Connection closed mid-packet")
            raw += chunk
            for byte in chunk:
                if prev == 0xAA and byte == 0x55:
                    prev = None  # stuffing byte
                    continue
                unstuffed.append(byte)
                prev = byte
            if needed == 2 and len(unstuffed) >= 2:
                needed = 2 + struct.unpack(">H", bytes(unstuffed[:2]))[0]

        return bytes(raw)

    async def read(self) -> dict:
        if not self.connected:
            raise TransportError("Not connected")
        async with self._lock:
            try:
                return await self._do_read()
            except asyncio.CancelledError:
                # HA is shutting down or reloading — clean up and re-raise.
                self._encrypted = False
                self._iv = None
                raise
            except TransportError:
                # Device closes TCP after each response — reconnect next poll.
                self._encrypted = False
                self._iv = None
                raise
            except Exception as exc:
                self._encrypted = False
                self._iv = None
                raise TransportError(f"Read failed: {exc}") from exc

    async def _do_read(self) -> dict:
        # Brief delay after handshake — some firmware drops the connection if a
        # read arrives too fast. Only wait on the first read after each connect.
        if not self._first_read_done:
            await asyncio.sleep(0.5)
            self._first_read_done = True

        await self._send_raw(build_read_packet(self._next_pid()))
        all_fields, peer_closed = await self._collect_data_packets()

        if not all_fields and not peer_closed:
            # Device sometimes needs a moment to prepare data — retry once.
            _LOGGER.debug("No fields on first read from %s, retrying in 1s", self.host)
            await asyncio.sleep(1.0)
            await self._send_raw(build_read_packet(self._next_pid()))
            all_fields, peer_closed = await self._collect_data_packets()

        if peer_closed:
            # Pecron firmware closes the socket after each response. Keep
            # whatever arrived and reconnect on the next poll.
            await self.disconnect()

        if not all_fields:
            # Raise instead of returning {} so the coordinator reconnects and
            # retries, rather than publishing an empty dict (every entity
            # would show "unknown").
            raise TransportError(
                "Device closed the connection before sending data"
                if peer_closed
                else "No data fields in TCP read response (even after retry)"
            )

        _LOGGER.debug("Collected %d fields from %s", len(all_fields), self.host)
        unmapped: list = []
        kv = fields_to_kv(all_fields, controls=self.controls, unmapped=unmapped)
        if unmapped != self.last_unmapped:
            _LOGGER.debug("Unmapped fields from %s: %s", self.host, unmapped)
        self.last_unmapped = unmapped
        return kv

    async def _collect_data_packets(self) -> tuple[list, bool]:
        """Collect 0x0014 response packets after a read command has been sent.

        Returns (fields, peer_closed). A connection closed by the device after
        it has sent its data is normal and must not discard that data.
        """
        all_fields: list = []
        for _ in range(10):
            try:
                # 3.0s per-packet timeout — matches source; signals "no more packets"
                resp_raw = await asyncio.wait_for(self._recv_packet(), timeout=3.0)
            except asyncio.TimeoutError:
                break
            except (TransportError, ConnectionError, OSError) as exc:
                _LOGGER.debug("TCP session to %s ended during read: %s", self.host, exc)
                return all_fields, True
            resp = parse_packet(resp_raw)
            cmd = resp.get("cmd", 0)
            if cmd == 0x0012:
                continue
            if cmd == 0x0014:
                payload = resp.get("payload", b"")
                if payload:
                    try:
                        decrypted = aes_decrypt(self.auth_key, self._iv, payload)
                    except ValueError as exc:
                        _LOGGER.debug("Could not decrypt packet from %s: %s", self.host, exc)
                        continue
                    fields = parse_fields(decrypted)
                    _LOGGER.debug("Packet with %d fields from %s", len(fields), self.host)
                    all_fields.extend(fields)
            else:
                _LOGGER.debug("Unexpected cmd 0x%04x from %s", cmd, self.host)
                break
        return all_fields, False

    async def write(self, data_point_id: int, value: object, ctrl_type: str) -> None:
        if not self.connected:
            raise TransportError("Not connected")
        async with self._lock:
            try:
                await self._do_write(data_point_id, value, ctrl_type)
            except asyncio.CancelledError:
                self._encrypted = False
                self._iv = None
                raise
            except Exception as exc:
                self._encrypted = False
                self._iv = None
                raise TransportError(f"Write failed: {exc}") from exc

    async def _do_write(self, data_point_id: int, value: object, ctrl_type: str) -> None:
        # Same post-handshake pause as reads: some firmware drops a command
        # that arrives right after login.
        if not self._first_read_done:
            await asyncio.sleep(0.5)
            self._first_read_done = True
        raw_payload = build_write_payload(data_point_id, value, ctrl_type)

        enc_payload = aes_encrypt(self.auth_key, self._iv, raw_payload)
        inner = struct.pack(">HH", self._next_pid(), 0x0013) + enc_payload
        crc = sum(inner) & 0xFF
        length = len(inner) + 1
        raw_pkt = b"\xaa\xaa" + struct.pack(">H", length) + bytes([crc]) + inner
        pkt = _byte_stuff(raw_pkt)
        await self._send_raw(pkt)
        resp_raw = await asyncio.wait_for(self._recv_packet(), timeout=self.timeout)
        if _LOGGER.isEnabledFor(logging.DEBUG):
            resp = parse_packet(resp_raw)
            detail = resp.get("payload", b"").hex()
            if resp.get("cmd") == 0x0014 and resp.get("payload"):
                try:
                    detail = str(parse_fields(aes_decrypt(self.auth_key, self._iv, resp["payload"])))
                except ValueError:
                    pass
            _LOGGER.debug(
                "Write %d=%s (%s) sent %s; device replied cmd=0x%04x %s",
                data_point_id, value, ctrl_type, raw_payload.hex(),
                resp.get("cmd", 0), detail,
            )
