"""Wi-Fi (UDP) transport: command send on :5600, state/presence listen on :5625."""

from __future__ import annotations

import asyncio
import json
import socket
from collections.abc import Callable
from logging import getLogger

from .const import BROADCAST_PORT, CMD_PORT
from .state import FanState, decode_state

_LOGGER = getLogger(__name__)

# callback(device_id, ip, series, state_or_none)
UpdateCallback = Callable[[str, str, "str | None", "FanState | None"], None]


def parse_datagram(data: bytes, src_ip: str) -> tuple[str, str | None, FanState | None] | None:
    """Return (device_id, series, state) from a :5625 datagram, or None."""
    msg = data.decode(errors="ignore").strip()
    if msg.startswith("PROXY "):
        parts = msg.split()
        if len(parts) >= 6 and parts[1] == "TCP4":
            msg = " ".join(parts[6:]).strip()

    payload = None
    if msg.startswith("{") and msg.endswith("}"):
        try:
            payload = json.loads(msg)
        except (ValueError, TypeError):
            payload = None

    if payload is None:
        try:
            payload = json.loads(bytes.fromhex(msg))
        except (ValueError, TypeError):
            payload = None

    if isinstance(payload, dict) and "device_id" in payload:
        state = decode_state(payload["state_string"]) if "state_string" in payload else None
        series = state.series if state else payload.get("series")
        return str(payload["device_id"]).lower(), series, state

    # Presence beacon: "<device_id>_<series>"
    if "_" in msg and not msg.startswith("{"):
        did, _, series_part = msg.partition("_")
        did = did.strip().lower()
        if did and all(c in "0123456789abcdef" for c in did) and 8 <= len(did) <= 16:
            series = series_part.split("_")[0].strip() if series_part else None
            return did, series or None, None

    return None


def send_command(ip: str, command: dict, timeout: float = 0.4) -> FanState | None:
    """Send JSON command datagram to :5600 and return direct state reply if present."""
    data = json.dumps(command).encode()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.sendto(data, (ip, CMD_PORT))
        except OSError as err:
            _LOGGER.debug("UDP send error to %s:%d: %s", ip, CMD_PORT, err)
            raise

        try:
            resp_data, _ = sock.recvfrom(2048)
            resp_msg = resp_data.decode(errors="ignore").strip()
            state = None
            if "," in resp_msg:
                state = decode_state(resp_msg)
            if state is None and resp_msg.startswith("{"):
                try:
                    payload = json.loads(resp_msg)
                    if isinstance(payload, dict) and "state_string" in payload:
                        state = decode_state(payload["state_string"])
                except Exception:
                    pass
            if state is None:
                try:
                    payload = json.loads(bytes.fromhex(resp_msg))
                    if isinstance(payload, dict) and "state_string" in payload:
                        state = decode_state(payload["state_string"])
                except Exception:
                    pass
            return state
        except (socket.timeout, OSError):
            return None


class UdpListener(asyncio.DatagramProtocol):
    """Listens on :5625 and reports device presence + state."""

    def __init__(self, on_update: UpdateCallback) -> None:
        self._on_update = on_update
        self._transport: asyncio.BaseTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self._transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            parsed = parse_datagram(data, addr[0])
        except Exception as err:  # noqa: BLE001 - a malformed packet must not kill the listener
            _LOGGER.debug("Ignored malformed :5625 datagram from %s: %s", addr[0], err)
            return
        if parsed:
            device_id, series, state = parsed
            _LOGGER.debug(
                "Wi-Fi sighting: %s from %s (series=%s, has_state=%s)",
                device_id, addr[0], series, state is not None,
            )
            self._on_update(device_id, addr[0], series, state)
        else:
            _LOGGER.debug("Unparsed :5625 datagram from %s: %r", addr[0], data[:48])

    def error_received(self, exc: Exception) -> None:  # pragma: no cover
        _LOGGER.debug("UDP error: %s", exc)


async def start_listener(on_update: UpdateCallback) -> asyncio.DatagramTransport:
    """Bind the :5625 listener and return its transport (call .close() to stop)."""
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: UdpListener(on_update),
        local_addr=("0.0.0.0", BROADCAST_PORT),
        reuse_port=hasattr(socket, "SO_REUSEPORT"),
    )
    _LOGGER.debug("Listening for Atomberg fans on UDP :%d", BROADCAST_PORT)
    return transport


async def async_discover(seconds: float = 5.0) -> dict[str, dict]:
    """Passively collect fans announcing on :5625 -> {device_id: {ip, series}}."""
    found: dict[str, dict] = {}

    def collect(device_id: str, ip: str, series: str | None, _state: FanState | None) -> None:
        entry = found.setdefault(device_id, {})
        entry["ip"] = ip
        if series:
            entry["series"] = series

    transport = await start_listener(collect)
    try:
        await asyncio.sleep(seconds)
    finally:
        transport.close()
    return found
