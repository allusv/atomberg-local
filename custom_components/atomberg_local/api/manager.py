"""Discovery + registry that reconciles Wi-Fi and BLE sightings by device_id.

Feed it Wi-Fi updates (from the :5625 listener) and BLE adverts (from a scan
loop or Home Assistant's Bluetooth callbacks); it keeps one AtombergDevice per
physical fan and notifies listeners on change.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from logging import getLogger

from bleak.backends.device import BLEDevice

from . import ble as ble_mod
from . import udp as udp_mod
from .device import AtombergDevice
from .state import FanState

_LOGGER = getLogger(__name__)


class AtombergManager:
    """Owns the set of known fans and their transports."""

    def __init__(self) -> None:
        self.devices: dict[str, AtombergDevice] = {}
        self._listeners: list[Callable[[AtombergDevice], None]] = []
        self._udp_transport: asyncio.DatagramTransport | None = None
        self._scan_task: asyncio.Task | None = None

    # ---- listener registration (HA coordinator subscribes here) ----
    def add_update_listener(self, cb: Callable[[AtombergDevice], None]) -> Callable[[], None]:
        self._listeners.append(cb)
        return lambda: self._listeners.remove(cb)

    def _notify(self, device: AtombergDevice) -> None:
        for cb in list(self._listeners):
            try:
                cb(device)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("update listener failed")

    def _get(self, device_id: str, series: str | None) -> AtombergDevice:
        dev = self.devices.get(device_id)
        if dev is None:
            dev = AtombergDevice(device_id, series)
            self.devices[device_id] = dev
            _LOGGER.debug("discovered fan %s (series %s)", device_id, series)
        return dev

    # ---- sighting inputs ----
    def handle_wifi_update(
        self, device_id: str, ip: str, series: str | None, state: FanState | None
    ) -> None:
        dev = self._get(device_id, series)
        dev.update_wifi(ip, series, state)
        self._notify(dev)

    def handle_ble_advert(
        self, device_id: str, series: str | None, ble_device: BLEDevice, rssi: int | None
    ) -> None:
        dev = self._get(device_id, series)
        dev.update_ble(ble_device, series, rssi)
        self._notify(dev)

    # ---- standalone lifecycle (HA wires its own bluetooth callbacks) ----
    async def async_start(self, ble_scan_interval: float = 20.0) -> None:
        self._udp_transport = await udp_mod.start_listener(self.handle_wifi_update)
        self._scan_task = asyncio.ensure_future(self._ble_scan_loop(ble_scan_interval))

    async def async_stop(self) -> None:
        if self._udp_transport:
            self._udp_transport.close()
        if self._scan_task:
            self._scan_task.cancel()

    async def _ble_scan_loop(self, interval: float) -> None:
        while True:
            try:
                results = await ble_mod.async_discover(seconds=min(interval, 8.0))
                for device_id, info in results.items():
                    self.handle_ble_advert(
                        device_id, info.get("series"), info["ble_device"], info.get("rssi")
                    )
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("BLE scan failed: %s", err)
            await asyncio.sleep(interval)

    # ---- convenience ----
    def provisioned(self) -> list[AtombergDevice]:
        return [d for d in self.devices.values() if d.is_provisioned]

    def unprovisioned(self) -> list[AtombergDevice]:
        return [d for d in self.devices.values() if not d.is_provisioned]
