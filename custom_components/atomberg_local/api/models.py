"""Best-effort Atomberg fan model recognition + capability profiles.

Locally a fan announces only a *series* code (e.g. ``S2``, ``I2``) in its BLE
advertised name (``atomberg_S2_<id>_3``) and in field 7 of its state string. A
series maps to a product family rather than a single SKU, so the friendly name
is a best guess.

The capability flags, however, decide which Home Assistant entities we expose,
so they are kept accurate. Which series have a dimmable underlight and which
have colour modes is cross-checked against Atomberg's own cloud integration
(github.com/dasshubham762/atomberg-integration), extended across each product
family. Getting these right matters: advertising a control the fan doesn't have
just gives the user a slider that does nothing.

Contributions welcome: refine a mapping for your model and open a PR.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelProfile:
    """What a fan series is called and what it can do."""

    name: str
    family: str
    # capability flags -> drive entity creation
    has_light: bool = True          # LED underlight (at least on/off)
    has_brightness: bool = False    # dimmable underlight
    has_color: bool = False         # warm/cool/daylight modes
    has_sleep: bool = True
    has_timer: bool = True
    has_boost: bool = False
    max_speed: int = 6


# series code -> (friendly name, product family). Best-effort names.
_NAMES: dict[str, tuple[str, str]] = {
    "R1": ("Renesa", "Renesa"),
    "R2": ("Renesa+", "Renesa"),
    "R3": ("Renesa Smart+", "Renesa"),
    "S1": ("Studio+", "Studio"),
    "S2": ("Renesa Elite", "Renesa"),
    "I1": ("Aris", "Aris"),
    "I2": ("Aris Starlight", "Aris"),
    "I3": ("Aris Star", "Aris"),
    "I4": ("Aris", "Aris"),
    "I5": ("Aris Contours", "Aris"),
    "M1": ("Efficio", "Efficio"),
    "M2": ("Efficio+", "Efficio"),
    "K1": ("Gorilla", "Gorilla"),
}

# Dimmable white underlight. Validated for I1/I5/M1/S1/S2 by the cloud
# integration; extended across the decorative Aris (I*) family.
_BRIGHTNESS: set[str] = {"I1", "I2", "I3", "I4", "I5", "M1", "S1", "S2"}
# Warm/cool/daylight colour modes: the decorative Aris (I*) underlight family.
_COLOR: set[str] = {"I1", "I2", "I3", "I4", "I5"}
# Series whose fans have no LED at all (control power/speed/sleep/timer only).
_NO_LIGHT: set[str] = {"K1"}  # Gorilla

# First-letter -> family, for unknown exact codes within a known family.
_FAMILY_PREFIX = {
    "R": "Renesa",
    "S": "Studio",
    "I": "Aris",
    "M": "Efficio",
    "K": "Gorilla",
}


def profile_for_series(series: str | None) -> ModelProfile:
    """Return a capability profile for a series code, with sensible fallbacks."""
    if not series:
        return ModelProfile("Atomberg Fan", "Atomberg")
    s = series.strip().upper()
    known = s in _NAMES
    if known:
        name, family = _NAMES[s]
    else:
        family = _FAMILY_PREFIX.get(s[:1], "Atomberg")
        name = (
            f"Atomberg {family} ({s})" if family != "Atomberg" else f"Atomberg Fan ({s})"
        )
    # Unknown codes inherit capabilities from their family (Aris = lit + colour).
    is_aris = s[:1] == "I"
    return ModelProfile(
        name=name,
        family=family,
        has_light=s not in _NO_LIGHT,
        has_brightness=(s in _BRIGHTNESS) or (not known and is_aris),
        has_color=(s in _COLOR) or (not known and is_aris),
    )
