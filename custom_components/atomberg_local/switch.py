"""Switch platform: sleep mode, boost, and a Prefer-BLE transport toggle."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import build_command
from .coordinator import AtombergCoordinator
from .entity import AtombergEntity, setup_atomberg_platform


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    def build(coordinator: AtombergCoordinator, device_id: str, device) -> list:
        entities: list = [AtombergPreferBleSwitch(coordinator, device_id)]
        if device.model.has_sleep:
            entities.append(AtombergSleepSwitch(coordinator, device_id))
        if device.model.has_boost:
            entities.append(AtombergBoostSwitch(coordinator, device_id))
        return entities

    setup_atomberg_platform(hass, entry, async_add_entities, build)


class AtombergSleepSwitch(AtombergEntity, SwitchEntity):
    """Sleep mode (gradually steps speed down)."""

    _attr_name = "Sleep mode"
    _attr_translation_key = "sleep"
    _attr_icon = "mdi:power-sleep"

    def __init__(self, coordinator: AtombergCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._unique_id("sleep")

    @property
    def is_on(self) -> bool | None:
        return self.device.state.sleep if self.device.state else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.device.async_send(build_command(sleep=True))
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.device.async_send(build_command(sleep=False))
        self.async_write_ha_state()


class AtombergBoostSwitch(AtombergEntity, SwitchEntity):
    """Boost / turbo mode."""

    _attr_name = "Boost"
    _attr_translation_key = "boost"
    _attr_icon = "mdi:fan-plus"

    def __init__(self, coordinator: AtombergCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._unique_id("boost")

    @property
    def is_on(self) -> bool | None:
        raw = getattr(self.device.state, "boost", None) if self.device.state else None
        return bool(raw) if raw is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.device.async_send(build_command(boost=True))
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.device.async_send(build_command(boost=False))
        self.async_write_ha_state()


class AtombergPreferBleSwitch(AtombergEntity, SwitchEntity):
    """When on, control this fan over BLE only (ignores Wi-Fi)."""

    _attr_name = "Prefer Bluetooth"
    _attr_translation_key = "prefer_ble"
    _attr_icon = "mdi:bluetooth"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AtombergCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._unique_id("prefer_ble")

    @property
    def available(self) -> bool:
        # config toggle is always usable while the device exists
        return self._device_id in self.coordinator.manager.devices

    @property
    def is_on(self) -> bool:
        return self.device.prefer_ble

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.device.prefer_ble = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.device.prefer_ble = False
        self.async_write_ha_state()
