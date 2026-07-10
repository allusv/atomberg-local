"""Base entity: ties an HA entity to an AtombergDevice via device_id."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AtombergDevice
from .const import DOMAIN, MANUFACTURER, SIGNAL_NEW_DEVICE
from .coordinator import AtombergCoordinator


class AtombergEntity(CoordinatorEntity[AtombergCoordinator]):
    """Common base for all Atomberg entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AtombergCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            connections={(CONNECTION_NETWORK_MAC, self._formatted_mac(device_id))},
            manufacturer=MANUFACTURER,
            model=self.device.model.name,
            name=self.device.name,
        )

    @staticmethod
    def _formatted_mac(device_id: str) -> str:
        return ":".join(device_id[i:i + 2] for i in range(0, 12, 2))

    @property
    def device(self) -> AtombergDevice:
        return self.coordinator.manager.devices[self._device_id]

    @property
    def available(self) -> bool:
        return self.device.available

    def _unique_id(self, suffix: str) -> str:
        return f"{self._device_id}_{suffix}"


def setup_atomberg_platform(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    builder: Callable[[AtombergCoordinator, str, AtombergDevice], list],
) -> None:
    """Add entities for known fans and for any discovered later."""
    coordinator: AtombergCoordinator = hass.data[DOMAIN][entry.entry_id]
    added: set[str] = set()

    @callback
    def _discover(*_args) -> None:
        new_entities: list = []
        for device_id, device in list(coordinator.manager.devices.items()):
            if device_id in added:
                continue
            added.add(device_id)
            new_entities.extend(builder(coordinator, device_id, device))
        if new_entities:
            async_add_entities(new_entities)

    _discover()
    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_NEW_DEVICE, _discover))
