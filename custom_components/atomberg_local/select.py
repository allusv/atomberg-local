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

# (option key, timer-hours as reported in state). The command value sent to the
# fan is the option's index in this list (0-4). Option keys are machine values;
# their display text comes from strings.json/translations so the entity (name
# and the five option labels) is translatable, per HA's SelectEntity convention.
TIMER_OPTIONS: list[tuple[str, int]] = [
    ("off", 0),
    ("1h", 1),
    ("2h", 2),
    ("3h", 3),
    ("6h", 6),
]
_KEYS = [key for key, _ in TIMER_OPTIONS]
_HOURS_TO_KEY = {hours: key for key, hours in TIMER_OPTIONS}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    def build(coordinator: AtombergCoordinator, device_id: str, device) -> list:
        return (
            [AtombergTimerSelect(coordinator, device_id)] if device.model.has_timer else []
        )

    setup_atomberg_platform(hass, entry, async_add_entities, build)


class AtombergTimerSelect(AtombergEntity, SelectEntity):
    """Auto-off timer as a discrete select.

    No `_attr_name` here: leaving it unset lets Home Assistant derive both the
    entity name and the five option labels from `_attr_translation_key` via
    strings.json/translations (entity.select.timer.name / .state.*).
    """

    _attr_translation_key = "timer"
    _attr_icon = "mdi:timer-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _KEYS

    def __init__(self, coordinator: AtombergCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._unique_id("timer")

    @property
    def current_option(self) -> str | None:
        if not self.device.state:
            return None
        # Reported hours may be a countdown value outside the set — treat as unknown.
        return _HOURS_TO_KEY.get(self.device.state.timer_hours)

    async def async_select_option(self, option: str) -> None:
        index = _KEYS.index(option)  # command value is the option index (0-4)
        await self.device.async_send(build_command(timer=index))
        self.async_write_ha_state()
