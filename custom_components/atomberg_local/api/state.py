"""Decode fan state and build commands.

State arrives as a comma-separated ``state_string`` whose first field is a
bitfield holding the live state; the same JSON commands drive the fan over
either transport.
"""

from __future__ import annotations

from dataclasses import dataclass

from .const import (
    ATTR_BRIGHTNESS,
    ATTR_LED,
    ATTR_LIGHT_MODE,
    ATTR_POWER,
    ATTR_SLEEP,
    ATTR_SPEED,
    ATTR_TIMER,
    LIGHT_MODE_COOL,
    LIGHT_MODE_DAYLIGHT,
    LIGHT_MODE_WARM,
    MAX_SPEED,
    MAX_TIMER_INDEX,
    MIN_SPEED,
)


@dataclass
class FanState:
    """Decoded fan state."""

    power: bool
    speed: int
    led: bool
    sleep: bool
    brightness: int
    timer_hours: int
    light_mode: str
    series: str | None = None
    raw: int = 0

    def as_dict(self) -> dict:
        return {
            ATTR_POWER: self.power,
            ATTR_SPEED: self.speed,
            ATTR_LED: self.led,
            ATTR_SLEEP: self.sleep,
            ATTR_BRIGHTNESS: self.brightness,
            "timer_hours": self.timer_hours,
            ATTR_LIGHT_MODE: self.light_mode,
        }


def decode_state(state_string: str) -> FanState | None:
    """Decode a fan ``state_string``. Returns None for non-state replies
    (e.g. the fan's ``"No command detected in the message"`` error)."""
    parts = state_string.split(",")
    field0 = parts[0].strip()
    if not field0.lstrip("-").isdigit():
        return None
    v = int(field0)
    cool = bool(v & 0x08)
    warm = bool(v & 0x8000)
    light_mode = (
        LIGHT_MODE_DAYLIGHT if cool and warm
        else LIGHT_MODE_COOL if cool
        else LIGHT_MODE_WARM
    )
    series = parts[7].strip() if len(parts) > 7 else None
    return FanState(
        power=bool(v & 0x10),
        speed=v & 0x07,
        led=bool(v & 0x20),
        sleep=bool(v & 0x80),
        brightness=(v & 0x7F00) >> 8,
        timer_hours=(v & 0x0F0000) >> 16,
        light_mode=light_mode,
        series=series,
        raw=v,
    )


def build_command(**kwargs) -> dict:
    """Validate and build a command dict from keyword args.

    Accepts: power(bool), speed(1-6), sleep(bool), led(bool),
    brightness(int), timer(0-4), boost(bool), light_mode(cool/warm/daylight).
    """
    cmd: dict = {}
    for key, val in kwargs.items():
        if val is None:
            continue
        if key == ATTR_SPEED:
            val = int(val)
            if not MIN_SPEED <= val <= MAX_SPEED:
                raise ValueError(f"speed must be {MIN_SPEED}-{MAX_SPEED}")
        elif key == ATTR_TIMER:
            val = int(val)
            if not 0 <= val <= MAX_TIMER_INDEX:
                raise ValueError(f"timer index must be 0-{MAX_TIMER_INDEX}")
        elif key in (ATTR_POWER, ATTR_SLEEP, ATTR_LED, "boost"):
            val = bool(val)
        elif key == ATTR_LIGHT_MODE:
            if val not in (LIGHT_MODE_COOL, LIGHT_MODE_WARM, LIGHT_MODE_DAYLIGHT):
                raise ValueError("light_mode must be cool/warm/daylight")
        cmd[key] = val
    return cmd
