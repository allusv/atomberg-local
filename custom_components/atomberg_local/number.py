"""Number platform: the off-timer (0-4 hours)."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import build_command
from .api.const import MAX_TIMER_HOURS
from .coordinator import AtombergCoordinator
from .entity import AtombergEntity, setup_atomberg_platform


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    def build(coordinator: AtombergCoordinator, device_id: str, device) -> list:
        return [AtombergTimer(coordinator, device_id)] if device.model.has_timer else []

    setup_atomberg_platform(hass, entry, async_add_entities, build)


class AtombergTimer(AtombergEntity, NumberEntity):
    """Auto-off timer in hours."""

    _attr_name = "Timer"
    _attr_translation_key = "timer"
    _attr_icon = "mdi:timer-outline"
    _attr_native_min_value = 0
    _attr_native_max_value = MAX_TIMER_HOURS
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: AtombergCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._unique_id("timer")

    @property
    def native_value(self) -> float | None:
        return self.device.state.timer_hours if self.device.state else None

    async def async_set_native_value(self, value: float) -> None:
        await self.device.async_send(build_command(timer=int(value)))
        self.async_write_ha_state()
