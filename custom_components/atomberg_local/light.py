"""Light platform: the fan's LED underlight (on/off, brightness, colour temp)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import build_command
from .api.const import LIGHT_MODE_COOL, LIGHT_MODE_DAYLIGHT, LIGHT_MODE_WARM
from .coordinator import AtombergCoordinator
from .entity import AtombergEntity, setup_atomberg_platform

# Approximate mired/kelvin anchors for the three discrete modes.
WARM_K = 2700
DAYLIGHT_K = 4000
COOL_K = 6500


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
        if model.has_color:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
            self._attr_min_color_temp_kelvin = WARM_K
            self._attr_max_color_temp_kelvin = COOL_K
        elif model.has_brightness:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        else:
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}

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
    def color_temp_kelvin(self) -> int | None:
        if not self.device.state or not self.device.model.has_color:
            return None
        return {
            LIGHT_MODE_WARM: WARM_K,
            LIGHT_MODE_DAYLIGHT: DAYLIGHT_K,
            LIGHT_MODE_COOL: COOL_K,
        }.get(self.device.state.light_mode, WARM_K)

    async def async_turn_on(self, **kwargs: Any) -> None:
        cmd: dict = {"led": True}
        if ATTR_BRIGHTNESS in kwargs and self.device.model.has_brightness:
            cmd["brightness"] = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
        if ATTR_COLOR_TEMP_KELVIN in kwargs and self.device.model.has_color:
            k = kwargs[ATTR_COLOR_TEMP_KELVIN]
            mode = (
                LIGHT_MODE_WARM if k <= (WARM_K + DAYLIGHT_K) // 2
                else LIGHT_MODE_DAYLIGHT if k <= (DAYLIGHT_K + COOL_K) // 2
                else LIGHT_MODE_COOL
            )
            cmd["light_mode"] = mode
        await self.device.async_send(build_command(**cmd))
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.device.async_send(build_command(led=False))
        self.async_write_ha_state()
