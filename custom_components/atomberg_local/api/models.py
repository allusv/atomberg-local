"""Best-effort Atomberg fan model recognition from the series code.

The fan announces only a *series* code (e.g. ``S2``, ``R2``) locally - both in
its BLE advertised name (``atomberg_S2_<id>_3``) and in field 7 of the state
string. A series maps to a product family rather than a single SKU, so this is
a friendly, easily-extended best guess plus a capability profile that drives
which Home Assistant entities we expose.

Contributions welcome: refine a mapping and open a PR.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelProfile:
    """What a fan series is called and what it can do."""

    name: str
    family: str
    # capability flags -> drive entity creation
    has_light: bool = True          # LED on/off
    has_brightness: bool = False    # dimmable underlight
    has_color: bool = False         # cool/warm/daylight
    has_sleep: bool = True
    has_boost: bool = False
    has_timer: bool = True
    max_speed: int = 6
    aliases: tuple[str, ...] = field(default_factory=tuple)


# Series prefix / exact code -> profile. Exact code wins over prefix.
_SERIES: dict[str, ModelProfile] = {
    # Renesa family (R*, S*) - smart BLDC ceiling fans with LED indicator.
    "R1": ModelProfile("Renesa", "Renesa"),
    "R2": ModelProfile("Renesa+", "Renesa", has_brightness=True, has_color=True),
    "R3": ModelProfile("Renesa Elite", "Renesa", has_brightness=True, has_color=True),
    "S1": ModelProfile("Studio+", "Studio"),
    "S2": ModelProfile("Renesa Elite", "Renesa", has_brightness=True, has_color=True),
    # Aris family (I*) - decorative with underlight.
    "I1": ModelProfile("Aris", "Aris", has_brightness=True, has_color=True),
    "I2": ModelProfile("Aris Starlight", "Aris", has_brightness=True, has_color=True),
    "I3": ModelProfile("Aris", "Aris", has_brightness=True, has_color=True),
    "I4": ModelProfile("Aris", "Aris", has_brightness=True, has_color=True),
    "I5": ModelProfile("Aris", "Aris", has_brightness=True, has_color=True),
    # Efficio / Gorilla (M*, K*) - value BLDC, usually no light.
    "M1": ModelProfile("Efficio", "Efficio", has_light=False),
    "M2": ModelProfile("Efficio+", "Efficio", has_light=False),
    "K1": ModelProfile("Gorilla", "Gorilla", has_light=False),
}

_PREFIX = {
    "R": ModelProfile("Renesa", "Renesa"),
    "S": ModelProfile("Renesa", "Renesa"),
    "I": ModelProfile("Aris", "Aris", has_brightness=True, has_color=True),
    "M": ModelProfile("Efficio", "Efficio", has_light=False),
    "K": ModelProfile("Gorilla", "Gorilla", has_light=False),
}


def profile_for_series(series: str | None) -> ModelProfile:
    """Return a capability profile for a series code, with sensible fallbacks."""
    if not series:
        return ModelProfile("Atomberg Fan", "Atomberg")
    series = series.strip().upper()
    if series in _SERIES:
        return _SERIES[series]
    prof = _PREFIX.get(series[:1])
    if prof:
        # Unknown exact code within a known family: keep the family, label with series.
        return ModelProfile(f"Atomberg {prof.family} ({series})", prof.family,
                            has_light=prof.has_light, has_brightness=prof.has_brightness,
                            has_color=prof.has_color, has_boost=prof.has_boost,
                            max_speed=prof.max_speed)
    return ModelProfile(f"Atomberg Fan ({series})", "Atomberg")
