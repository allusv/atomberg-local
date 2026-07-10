"""BLE transport: control + state over GATT. Works with no Wi-Fi at all.

Accepts a bleak ``BLEDevice`` (Home Assistant supplies these from its Bluetooth
integration; standalone we get them from ``BleakScanner``). Commands are the
same JSON as the Wi-Fi path, written to the command characteristic.
"""

from __future__ import annotations

import json
from logging import getLogger

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from .const import (
    BLE_APLIST_CHAR,
    BLE_CMD_CHAR,
    BLE_NAME_PREFIXES,
    BLE_STATE_CHAR,
)
from .state import FanState, decode_state

_LOGGER = getLogger(__name__)

try:  # HA ships bleak-retry-connector; use it for robust connects when present.
    from bleak_retry_connector import establish_connection

    async def _connect(device: BLEDevice) -> BleakClient:
        return await establish_connection(BleakClient, device, device.address)
except ImportError:  # pragma: no cover - standalone fallback

    async def _connect(device: BLEDevice) -> BleakClient:
        client = BleakClient(device)
        await client.connect()
        return client


def parse_ble_name(name: str | None) -> tuple[str, str | None] | None:
    """``atomberg_S2_a1b2c3d4e5f6_3`` -> (device_id, series). Case-insensitive."""
    if not name:
        return None
    low = name.lower()
    if not any(low.startswith(p.lower()) for p in BLE_NAME_PREFIXES):
        return None
    parts = name.split("_")
    if len(parts) >= 3:
        return parts[2], parts[1]
    return None


def is_atomberg_advert(name: str | None, service_uuids: list[str] | None = None) -> bool:
    if parse_ble_name(name):
        return True
    return bool(service_uuids) and any("e29ee02c" in u.lower() for u in service_uuids)


class BleTransport:
    """A short-lived BLE control session to one fan."""

    def __init__(self, device: BLEDevice) -> None:
        self._device = device
        self._client: BleakClient | None = None

    async def __aenter__(self) -> "BleTransport":
        self._client = await _connect(self._device)
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:  # noqa: BLE001
                pass

    async def send_command(self, command: dict) -> None:
        assert self._client
        await self._client.write_gatt_char(BLE_CMD_CHAR, json.dumps(command).encode(), response=True)

    async def read_state(self) -> FanState | None:
        assert self._client
        raw = await self._client.read_gatt_char(BLE_STATE_CHAR)
        return decode_state(bytes(raw).decode(errors="ignore"))

    async def read_ap_list(self) -> list[tuple[str, int]]:
        """Return [(ssid, rssi)] the fan currently sees (for provisioning UIs)."""
        assert self._client
        raw = await self._client.read_gatt_char(BLE_APLIST_CHAR)
        out: list[tuple[str, int]] = []
        for line in bytes(raw).decode(errors="ignore").splitlines():
            line = line.strip()
            if line.endswith(")") and "(" in line:
                ssid, _, rssi = line.rpartition("(")
                try:
                    out.append((ssid.strip(), int(rssi.strip(" )"))))
                except ValueError:
                    out.append((ssid.strip(), 0))
        return out


async def async_discover(seconds: float = 8.0) -> dict[str, dict]:
    """Scan for Atomberg fans over BLE -> {device_id: {address, series, rssi, name}}."""
    found: dict[str, dict] = {}
    devices = await BleakScanner.discover(timeout=seconds, return_adv=True)
    for address, (dev, adv) in devices.items():
        name = adv.local_name or dev.name
        parsed = parse_ble_name(name)
        if not parsed and not is_atomberg_advert(name, adv.service_uuids):
            continue
        device_id, series = parsed if parsed else (None, None)
        if not device_id:
            continue
        found[device_id] = {
            "address": address,
            "series": series,
            "rssi": adv.rssi,
            "name": name,
            "ble_device": dev,
        }
    return found
