"""Select platform: the auto-off timer.

The fan's timer is not continuous — it supports Off / 1 / 2 / 3 / 6 hours. The
command value is the option's index (0-4); the state reports the actual hours
(0/1/2/3/6). Verified over UDP against a real fan: index 4 sets a 6-hour timer.
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import build_command
from .coordinator import AtombergCoordinator
from .entity import AtombergEntity, setup_atomberg_platform

# (label, timer-hours as reported in state). The command value is the index.
TIMER_OPTIONS: list[tuple[str, int]] = [
    ("Off", 0),
    ("1 hour", 1),
    ("2 hours", 2),
    ("3 hours", 3),
    ("6 hours", 6),
]
_LABELS = [label for label, _ in TIMER_OPTIONS]
_HOURS_TO_LABEL = {hours: label for label, hours in TIMER_OPTIONS}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    def build(coordinator: AtombergCoordinator, device_id: str, device) -> list:
        return (
            [AtombergTimerSelect(coordinator, device_id)] if device.model.has_timer else []
        )

    setup_atomberg_platform(hass, entry, async_add_entities, build)


class AtombergTimerSelect(AtombergEntity, SelectEntity):
    """Auto-off timer as a discrete select."""

    _attr_name = "Timer"
    _attr_translation_key = "timer"
    _attr_icon = "mdi:timer-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _LABELS

    def __init__(self, coordinator: AtombergCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._unique_id("timer")

    @property
    def current_option(self) -> str | None:
        if not self.device.state:
            return None
        # Reported hours may be a countdown value outside the set — treat as unknown.
        return _HOURS_TO_LABEL.get(self.device.state.timer_hours)

    async def async_select_option(self, option: str) -> None:
        index = _LABELS.index(option)  # command value is the option index (0-4)
        await self.device.async_send(build_command(timer=index))
        self.async_write_ha_state()
