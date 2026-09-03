"""Registry of workout template categories: colours, aliases, blurbs.

Adding a new template kind means adding one entry here. Everything else --
pill colours, the highlights panel, the legend at the bottom of the poster --
is derived from this table.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    color: str
    blurb: str
    aliases: tuple[str, ...] = ()
    # Categories that carry a per-day subtitle ("Benchmark: 1000 Meter Row").
    titled: bool = False
    # Shown in the highlights panel even when the month has none of them.
    always_list: bool = False
    order: int = 100


CATEGORIES: tuple[Category, ...] = (
    Category(
        "runrow", "Run/Row", "#1565C0",
        "Treadmill running paired with rowing intervals for cardio endurance and power.",
        aliases=("run row", "run-row", "runrow", "run/row"),
        order=10,
    ),
    Category(
        "lift", "Lift More", "#F4511E",
        "Strength-forward floor blocks: heavier loads, controlled reps, progression.",
        aliases=("lift more", "liftmore", "lift"),
        order=20,
    ),
    Category(
        "elev", "Elevation Gain", "#00838F",
        "Incline-focused tread work that builds lower-body strength and burn.",
        aliases=("elevation gain", "elevation", "elev gain"),
        order=30,
    ),
    Category(
        "switch", "Switch Template", "#E53935",
        "Stations rotate more often than usual for a faster switch-style class.",
        aliases=("switch template", "switch", "switch day"),
        order=40,
    ),
    Category(
        "bosu", "BOSU", "#6A1B9A",
        "Balance trainer work for core engagement, stability, and control.",
        aliases=("bosu", "bosu ball", "bosu trainer"),
        order=50,
    ),
    Category(
        "band", "Minibands", "#558B2F",
        "Resistance-band work targeting glutes, hips, shoulders, and stabilizers.",
        aliases=("minibands", "miniband", "mini bands", "mini band", "bands"),
        order=60,
    ),
    Category(
        "lowbench", "Low Bench", "#00695C",
        "Step-ups, lower-body strength, and bench-based movements.",
        aliases=("low bench", "lowbench", "low-bench"),
        order=70,
    ),
    Category(
        "incline", "Incline Bench", "#3949AB",
        "Angled pressing and pulling for upper-body strength.",
        aliases=("incline bench", "inclinebench", "incline-bench", "incline"),
        order=80,
    ),
    Category(
        "sig", "Signature", "#E8A33D",
        "Recurring named OTF workouts with a known format and coaching focus.",
        aliases=("signature", "signature workout", "sig"),
        titled=True, always_list=True, order=90,
    ),
    Category(
        "spec", "Specialty", "#E53935",
        "Event-style templates built around a theme or a season milestone.",
        aliases=("specialty", "special", "specialty workout", "3g", "3g only"),
        titled=True, always_list=True, order=100,
    ),
    Category(
        "bench", "Benchmark", "#1A3A6B",
        "Timed or measured efforts used to track progress over time.",
        aliases=("benchmark", "benchmarks", "bench mark"),
        titled=True, always_list=True, order=110,
    ),
    Category(
        "std", "Standard", "#E4E7EB",
        "A regular daily template with no signature, benchmark, or equipment emphasis.",
        aliases=("standard", "regular", "normal", "none", "standard template"),
        order=120,
    ),
    Category(
        "unknown", "Other", "#8A919B",
        "A template this generator does not recognise yet -- add it to categories.py.",
        aliases=(),
        titled=True, order=999,
    ),
)

BY_KEY: dict[str, Category] = {c.key: c for c in CATEGORIES}

_ALIAS_INDEX: dict[str, Category] = {}
for _c in CATEGORIES:
    _ALIAS_INDEX[_c.label.lower()] = _c
    _ALIAS_INDEX[_c.key] = _c
    for _a in _c.aliases:
        _ALIAS_INDEX[_a] = _c


def _norm(text: str) -> str:
    return " ".join(text.lower().replace("_", " ").replace("-", " ").split())


def lookup(name: str) -> Category | None:
    """Resolve a free-text template name to a category, or None if unknown."""
    return _ALIAS_INDEX.get(_norm(name)) or _ALIAS_INDEX.get(_norm(name).rstrip("s"))


def light_text(color: str) -> bool:
    """True when white text on this colour is readable (used for pill contrast)."""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    # Relative luminance, sRGB-ish. 0.55 lands Standard's #E4E7EB on dark text.
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 < 0.62
