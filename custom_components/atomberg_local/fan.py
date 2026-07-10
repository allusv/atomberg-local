"""Fan platform: power + speed (1-6)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from .api import build_command
from .api.const import MAX_SPEED, MIN_SPEED
from .coordinator import AtombergCoordinator
from .entity import AtombergEntity, setup_atomberg_platform


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    def build(coordinator: AtombergCoordinator, device_id: str, _device) -> list:
        return [AtombergFan(coordinator, device_id)]

    setup_atomberg_platform(hass, entry, async_add_entities, build)


class AtombergFan(AtombergEntity, FanEntity):
    """The fan itself."""

    _attr_name = None  # primary entity uses the device name
    _enable_turn_on_off_backwards_compatibility = False
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: AtombergCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = device_id
        self._speed_range = (MIN_SPEED, MAX_SPEED)

    @property
    def is_on(self) -> bool | None:
        return self.device.state.power if self.device.state else None

    @property
    def percentage(self) -> int | None:
        if not self.device.state or not self.device.state.power:
            return 0
        return ranged_value_to_percentage(self._speed_range, self.device.state.speed)

    @property
    def speed_count(self) -> int:
        return int_states_in_range(self._speed_range)

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.device.async_send(build_command(power=False))
        else:
            speed = round(percentage_to_ranged_value(self._speed_range, percentage))
            speed = max(MIN_SPEED, min(MAX_SPEED, speed))
            await self.device.async_send(build_command(power=True, speed=speed))
        self.async_write_ha_state()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        if percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            await self.device.async_send(build_command(power=True))
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.device.async_send(build_command(power=False))
        self.async_write_ha_state()
