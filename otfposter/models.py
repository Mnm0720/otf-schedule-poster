"""The schedule data model -- the contract between the parser and the renderer.

A month is stored on disk as JSON (``schedules/YYYY-MM.json``). That file, not
the raw Reddit paste, is the source of truth for the poster: the paste is just
the fastest way to produce one.
"""
from __future__ import annotations

import calendar
import json
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path

from .categories import BY_KEY, Category, lookup

SCHEMA_VERSION = 1

# OTF's standing Strength 50 split. Overridable per month.
DEFAULT_STRENGTH_SPLIT = [
    {"days": "Mon / Thu", "focus": "Upper Body"},
    {"days": "Tue / Fri", "focus": "Lower Body"},
    {"days": "Wed / Sat / Sun", "focus": "Total Body"},
]


@dataclass
class Entry:
    """One template on one day."""
    category: str              # a key from categories.CATEGORIES
    title: str = ""            # e.g. "1000 Meter Row" for a Benchmark
    raw: str = ""              # the source text, kept for debugging

    @property
    def cat(self) -> Category:
        return BY_KEY.get(self.category, BY_KEY["unknown"])

    @property
    def label(self) -> str:
        """The text printed on the calendar pill."""
        if self.category == "unknown":
            # Show what the post actually said rather than the "Other" bucket.
            return self.title or self.raw or "Other"
        if self.title and self.cat.titled:
            return f"{self.cat.label}: {self.title}"
        return self.title or self.cat.label


@dataclass
class Day:
    day: int
    entries: list[Entry] = field(default_factory=list)
    repeat_of: int | None = None   # this day re-runs the template from day N
    note: str = ""                 # free-text override for the cell footnote

    @property
    def is_marked(self) -> bool:
        return any(e.cat.titled and e.category != "unknown" for e in self.entries)


@dataclass
class Month:
    year: int
    month: int
    theme: str = ""
    tagline: str = ""
    subtitle: str = "Monthly Schedule Poster"
    source_url: str = ""
    strength_split: list[dict] = field(default_factory=lambda: list(DEFAULT_STRENGTH_SPLIT))
    notes: list[str] = field(default_factory=list)     # checklist beside the split
    footnotes: list[dict] = field(default_factory=list)  # bottom-right callouts
    days: list[Day] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION

    # ---- derived helpers -------------------------------------------------
    @property
    def length(self) -> int:
        return calendar.monthrange(self.year, self.month)[1]

    @property
    def name(self) -> str:
        return date(self.year, self.month, 1).strftime("%B %Y").upper()

    @property
    def slug(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    def by_day(self) -> dict[int, Day]:
        return {d.day: d for d in self.days}

    def weekday_of(self, day: int) -> int:
        """0 = Sunday .. 6 = Saturday, matching the poster's column order."""
        return (date(self.year, self.month, day).weekday() + 1) % 7

    def mmdd(self, day: int) -> str:
        return f"{self.month}/{day}"

    # ---- (de)serialisation ----------------------------------------------
    def to_dict(self) -> dict:
        d = asdict(self)
        for day in d["days"]:
            for e in day["entries"]:
                e.pop("raw", None) if not e.get("raw") else None
        return d

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        return path

    @classmethod
    def from_dict(cls, data: dict) -> "Month":
        version = data.get("schema_version", SCHEMA_VERSION)
        if version > SCHEMA_VERSION:
            raise ValueError(
                f"schedule uses schema version {version}, this build understands {SCHEMA_VERSION}"
            )
        days = [
            Day(
                day=d["day"],
                entries=[Entry(**e) for e in d.get("entries", [])],
                repeat_of=d.get("repeat_of"),
                note=d.get("note", ""),
            )
            for d in data.get("days", [])
        ]
        known = {f for f in cls.__dataclass_fields__ if f != "days"}
        kwargs = {k: v for k, v in data.items() if k in known}
        return cls(days=days, **kwargs)

    @classmethod
    def load(cls, path: Path) -> "Month":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def make_entry(name: str, title: str = "", raw: str = "") -> Entry:
    """Build an Entry from a free-text template name."""
    cat = lookup(name)
    if cat is None:
        return Entry(category="unknown", title=name.strip(), raw=raw or name)
    return Entry(category=cat.key, title=title.strip(), raw=raw or name)
