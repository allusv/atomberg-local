"""A logical fan, reachable over Wi-Fi and/or BLE, keyed by its device_id.

Reconciliation: the same ``device_id`` seen over BLE (unprovisioned) and later
over Wi-Fi (provisioned) is one ``AtombergDevice`` that simply gains a transport.

Fallback: commands prefer Wi-Fi when it is healthy (a recent :5625 beacon), and
fall back to BLE when Wi-Fi is stale, unreachable, or unconfirmed - satisfying
"if the Wi-Fi connection is weak or disconnected, use BLE".
"""

from __future__ import annotations

import asyncio
import time
from logging import getLogger

from bleak.backends.device import BLEDevice

from . import ble as ble_mod
from . import udp as udp_mod
from .const import READ_COMMAND, WIFI_STALE_AFTER
from .models import ModelProfile, profile_for_series
from .state import FanState

_LOGGER = getLogger(__name__)


class NoTransportAvailable(RuntimeError):
    """Neither Wi-Fi nor BLE is currently usable for this fan."""


class AtombergDevice:
    """One physical fan and everything we know about how to reach it."""

    def __init__(self, device_id: str, series: str | None = None) -> None:
        self.device_id = device_id
        self.series = series
        # Wi-Fi transport
        self.wifi_ip: str | None = None
        self._last_wifi = 0.0
        self._ever_wifi = False
        # BLE transport
        self.ble_device: BLEDevice | None = None
        self.ble_rssi: int | None = None
        self._last_ble = 0.0
        # state + prefs
        self.state: FanState | None = None
        self.prefer_ble = False          # user opted for BLE-only control
        self._state_event = asyncio.Event()

    # ---- identity / capabilities ----
    @property
    def model(self) -> ModelProfile:
        return profile_for_series(self.series)

    @property
    def name(self) -> str:
        return f"{self.model.name} {self.device_id[-4:]}"

    # ---- transport health ----
    @property
    def wifi_available(self) -> bool:
        return self.wifi_ip is not None and (time.monotonic() - self._last_wifi) < WIFI_STALE_AFTER

    @property
    def ble_available(self) -> bool:
        return self.ble_device is not None

    @property
    def is_provisioned(self) -> bool:
        """True if the fan has ever been seen on Wi-Fi (i.e. onboarded)."""
        return self._ever_wifi

    @property
    def connection(self) -> str:
        if self.prefer_ble and self.ble_available:
            return "ble"
        if self.wifi_available:
            return "wifi"
        if self.ble_available:
            return "ble"
        return "offline"

    @property
    def available(self) -> bool:
        return self.connection != "offline"

    # ---- sightings (called by the manager) ----
    def update_wifi(self, ip: str, series: str | None, state: FanState | None) -> None:
        self.wifi_ip = ip
        self._last_wifi = time.monotonic()
        self._ever_wifi = True
        if series:
            self.series = series
        if state is not None:
            self.state = state
            self._state_event.set()

    def update_ble(self, device: BLEDevice, series: str | None, rssi: int | None) -> None:
        self.ble_device = device
        self.ble_rssi = rssi
        self._last_ble = time.monotonic()
        if series:
            self.series = series

    def _apply_optimistic(self, command: dict) -> None:
        """Reflect a command in local state immediately for a snappy UI."""
        if self.state is None:
            return
        s = self.state
        for k, v in command.items():
            if hasattr(s, k):
                setattr(s, k, v)

    # ---- control with fallback ----
    async def async_send(self, command: dict, verify: bool = True) -> str:
        """Send a command, choosing transport with BLE fallback. Returns transport used."""
        order = ["ble", "wifi"] if self.prefer_ble else ["wifi", "ble"]
        last_err: Exception | None = None
        for transport in order:
            if transport == "wifi" and self.wifi_available:
                try:
                    self._state_event.clear()
                    await asyncio.get_running_loop().run_in_executor(
                        None, udp_mod.send_command, self.wifi_ip, command
                    )
                    self._apply_optimistic(command)
                    if not verify:
                        return "wifi"
                    # The fan broadcasts fresh state after accepting a command.
                    try:
                        await asyncio.wait_for(self._state_event.wait(), timeout=1.5)
                        return "wifi"
                    except asyncio.TimeoutError:
                        _LOGGER.debug("%s: Wi-Fi command unconfirmed, falling back", self.device_id)
                except OSError as err:
                    last_err = err
            elif transport == "ble" and self.ble_available:
                try:
                    async with ble_mod.BleTransport(self.ble_device) as bt:
                        await bt.send_command(command)
                        state = await bt.read_state()
                    if state is not None:
                        self.state = state
                    else:
                        self._apply_optimistic(command)
                    return "ble"
                except Exception as err:  # noqa: BLE001
                    last_err = err
                    _LOGGER.debug("%s: BLE command failed: %s", self.device_id, err)
        raise NoTransportAvailable(str(last_err) if last_err else "no transport")

    async def async_refresh(self) -> None:
        """Ask the fan for its current state (Wi-Fi read command or BLE read)."""
        if self.wifi_available and not self.prefer_ble:
            await asyncio.get_running_loop().run_in_executor(
                None, udp_mod.send_command, self.wifi_ip, READ_COMMAND
            )
        elif self.ble_available:
            try:
                async with ble_mod.BleTransport(self.ble_device) as bt:
                    state = await bt.read_state()
                if state is not None:
                    self.state = state
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("%s: BLE refresh failed: %s", self.device_id, err)
