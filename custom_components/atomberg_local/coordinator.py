"""Coordinator: bridges Home Assistant Bluetooth + the Wi-Fi UDP listener into
the transport-agnostic AtombergManager, and drives entity updates."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from logging import getLogger

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import AtombergManager
from .api.ble import parse_ble_name
from .api.udp import start_listener
from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, SIGNAL_NEW_DEVICE

_LOGGER = getLogger(__name__)


class AtombergCoordinator(DataUpdateCoordinator):
    """Keeps the fan registry fresh from both transports."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.entry = entry
        self.manager = AtombergManager()
        self._known: set[str] = set()
        self._udp_transport = None
        self.manager.add_update_listener(self._on_device_update)

    async def async_setup(self) -> None:
        """Start the Wi-Fi listener (BLE comes from HA's Bluetooth stack)."""
        self._udp_transport = await start_listener(self.manager.handle_wifi_update)
        _LOGGER.debug("Atomberg UDP listener started on :5625")

    async def async_shutdown(self) -> None:
        if self._udp_transport:
            self._udp_transport.close()
        await super().async_shutdown()

    @callback
    def _on_device_update(self, device) -> None:
        """A fan was seen or changed (push from UDP or BLE)."""
        if device.device_id not in self._known:
            self._known.add(device.device_id)
            async_dispatcher_send(self.hass, SIGNAL_NEW_DEVICE, device.device_id)
        self.async_update_listeners()

    def _ingest_ble(self) -> None:
        """Feed current HA-discovered BLE adverts into the manager.

        Never raises: Bluetooth may not be set up yet (or at all), and that must
        not abort setup — Wi-Fi discovery still works without it.
        """
        try:
            infos = list(bluetooth.async_discovered_service_info(self.hass, connectable=True))
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Bluetooth not ready, skipping BLE ingest: %s", err)
            return
        matched = 0
        for info in infos:
            parsed = parse_ble_name(info.name)
            if not parsed:
                continue
            device_id, series = parsed
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, info.address, connectable=True
            )
            if ble_device:
                matched += 1
                self.manager.handle_ble_advert(device_id, series, ble_device, info.rssi)
        _LOGGER.debug(
            "BLE ingest: %d Atomberg fan(s) among %d discovered device(s)", matched, len(infos)
        )

    async def _async_update_data(self) -> dict:
        # 1) refresh BLE presence from HA's central scanner (must never fail setup)
        try:
            self._ingest_ble()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("BLE ingest failed: %s", err)
        # 2) ask fans for current state (cheap Wi-Fi read; BLE read for BLE-only)
        for device in list(self.manager.devices.values()):
            try:
                await asyncio.wait_for(device.async_refresh(), timeout=8)
            except (asyncio.TimeoutError, OSError):
                pass
            except Exception:  # noqa: BLE001
                pass
        _LOGGER.debug("Coordinator refresh: %d fan(s) known", len(self.manager.devices))
        return self.manager.devices
