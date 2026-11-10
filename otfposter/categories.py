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
        order=30,
    ),
    Category(
        "elev", "Elevation Gain", "#00838F",
        "Incline-focused tread work that builds lower-body strength and burn.",
        aliases=("elevation gain", "elevation", "elev gain"),
        order=40,
    ),
    Category(
        "switch", "Switch Template", "#E53935",
        "Stations rotate more often than usual for a faster switch-style class.",
        aliases=("switch template", "switch", "switch day"),
        order=20,
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
        order=80,
    ),
    Category(
        "lowbench", "Low Bench", "#00695C",
        "Step-ups, lower-body strength, and bench-based movements.",
        aliases=("low bench", "lowbench", "low-bench"),
        order=60,
    ),
    Category(
        "incline", "Incline Bench", "#3949AB",
        "Angled pressing and pulling for upper-body strength.",
        aliases=("incline bench", "inclinebench", "incline-bench", "incline"),
        order=70,
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
        titled=True, always_list=True, order=110,
    ),
    Category(
        "bench", "Benchmark", "#1A3A6B",
        "Timed or measured efforts used to track progress over time.",
        aliases=("benchmark", "benchmarks", "bench mark"),
        titled=True, always_list=True, order=100,
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

# Shared by full/compact calendars and the browser's category inventory. Unknown
# month-local types retain a labelled star instead of guessing their equipment.
CATEGORY_ICONS = {
    'runrow': 'rowing', 'switch': 'swap_horiz', 'lift': 'fitness_center',
    'elev': 'filter_hdr', 'bosu': 'balance', 'lowbench': 'chair_alt',
    'incline': 'airline_seat_recline_extra', 'band': 'all_inclusive',
    'sig': 'military_tech', 'bench': 'timer', 'spec': 'local_fire_department',
    'std': 'check_circle', 'unknown': 'star',
}


def category_icon(key: str) -> str:
    return CATEGORY_ICONS.get(key, 'star')

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
    return contrast_foreground(color) == '#FFFFFF'


def relative_luminance(color: str) -> float:
    """WCAG relative luminance after linearizing the sRGB channels."""
    if len(color) == 4:
        color = '#' + ''.join(char * 2 for char in color[1:])
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4
              for v in channels]
    return sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))


def contrast_ratio(first: str, second: str) -> float:
    light, dark = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (light + .05) / (dark + .05)


def contrast_foreground(background: str) -> str:
    """Choose the higher-contrast black/white foreground (always at least 4.5)."""
    return max(('#000000', '#FFFFFF'), key=lambda color: contrast_ratio(background, color))
