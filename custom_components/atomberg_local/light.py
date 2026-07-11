"""Light platform: the fan's LED underlight.

Capabilities depend on the model: a simple on/off indicator, a dimmable white
underlight, or (on decorative models) discrete warm/cool/daylight colour modes.

Wire protocol note: the fan ignores ``brightness``/``light_mode`` when they are
sent together with ``led`` in the same datagram. So a brightness/colour command
is sent *on its own* — which also turns the LED on — exactly as the fan expects.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import build_command
from .api.const import LIGHT_MODE_COOL, LIGHT_MODE_DAYLIGHT, LIGHT_MODE_WARM
from .coordinator import AtombergCoordinator
from .entity import AtombergEntity, setup_atomberg_platform

# Discrete colour modes are exposed as light "effects" (they are not a
# continuous colour temperature), matching how the fan actually behaves.
EFFECTS = {
    "Daylight": LIGHT_MODE_DAYLIGHT,
    "Cool": LIGHT_MODE_COOL,
    "Warm": LIGHT_MODE_WARM,
}
_MODE_TO_EFFECT = {v: k for k, v in EFFECTS.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    def build(coordinator: AtombergCoordinator, device_id: str, device) -> list:
        return [AtombergLight(coordinator, device_id)] if device.model.has_light else []

    setup_atomberg_platform(hass, entry, async_add_entities, build)


class AtombergLight(AtombergEntity, LightEntity):
    """The fan's LED light."""

    _attr_translation_key = "led"
    _attr_name = "LED"

    def __init__(self, coordinator: AtombergCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._unique_id("led")
        model = self.device.model
        if model.has_brightness:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        else:
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}
        if model.has_color:
            self._attr_supported_features = LightEntityFeature.EFFECT
            self._attr_effect_list = list(EFFECTS)

    @property
    def is_on(self) -> bool | None:
        return self.device.state.led if self.device.state else None

    @property
    def brightness(self) -> int | None:
        if not self.device.state or not self.device.model.has_brightness:
            return None
        # fan brightness is 0-100 -> HA 0-255
        return round(self.device.state.brightness * 255 / 100)

    @property
    def effect(self) -> str | None:
        if not self.device.state or not self.device.model.has_color:
            return None
        return _MODE_TO_EFFECT.get(self.device.state.light_mode)

    async def async_turn_on(self, **kwargs: Any) -> None:
        cmd: dict = {"led": True}
        if ATTR_BRIGHTNESS in kwargs and self.device.model.has_brightness:
            cmd["brightness"] = max(1, round(kwargs[ATTR_BRIGHTNESS] * 100 / 255))
        if ATTR_EFFECT in kwargs and self.device.model.has_color:
            cmd["light_mode"] = EFFECTS.get(kwargs[ATTR_EFFECT], LIGHT_MODE_WARM)
        # The fan ignores brightness/light_mode if 'led' is also present, so when
        # we have a specific attribute to set we drop 'led' (setting the attribute
        # turns the light on anyway).
        if len(cmd) > 1:
            cmd.pop("led", None)
        await self.device.async_send(build_command(**cmd))
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.device.async_send(build_command(led=False))
        self.async_write_ha_state()
