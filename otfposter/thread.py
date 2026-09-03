"""Parse an r/orangetheory monthly thread.

These posts describe a month *by category*, not day by day::

    Key Dates for The Month
    * September 8 (Tuesday): 1000 Meter Row; benchmark. See our wiki for details.
    * September 18 (Friday): OTF Foundations; signature. ...

    Other info to know ...
    * Run/Rows on 9/3, 9/5, 9/8 (benchmark), 9/13, 9/19, 9/21, 9/29.
    * Lift More templates on 9/2, 9/7, 9/10, ...
    * Repeat templates are as follows: 9/16 = 9/1, 9/17 = 9/2, ...

So the schedule is assembled by inverting those lists: a day collects every
category that names it, and any day nobody names is a Standard template.

The parenthetical hints -- ``9/8 (benchmark)`` -- are cross-references to the
Key Dates block, not extra templates, so they are read for corroboration and
otherwise ignored.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field

from .categories import lookup
from .models import Day, Entry, Event, Month, make_entry

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
MONTHS["sept"] = 9
_MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))

DASH = r"[-–—]"

# "Welcome to the September 2026 Monthly Thread!" / "April 2026 - Monthly Post"
_TITLE = re.compile(
    rf"(?:welcome\s+to\s+the\s+)?\b({_MONTH_RE})\.?\s+(20\d{{2}})\b"
    rf"(?=[^\n]*monthly\s+(?:thread|post))",
    re.I,
)
# "For September, the theme is Rhythm & Routine." / "for April it is "Recovery...""
_THEME = re.compile(
    rf"\bfor\s+(?:{_MONTH_RE})\b[^.\n]*?\b(?:the\s+theme\s+is|it\s+is)\s+"
    rf"[\"“]?([^.\"”\n]+?)[\"”]?\s*\.",
    re.I,
)
_THEME_SHOUT = re.compile(r"\bHappy\s+([A-Z][A-Z&,'’ ]{3,40}?)\s+month!")

# A Key Dates bullet, single day or a range, e.g.
#   "August 27 (Thursday): PSL; specialty. This is a 3G only template..."
#   "August 1 (Saturday) - August 31 (Monday): Marathon Month; event. ..."
_KEY_DATE = re.compile(
    rf"^\**\s*({_MONTH_RE})\.?\s+(\d{{1,2}})\s*(?:\([^)]*\))?\s*"
    rf"(?:{DASH}\s*({_MONTH_RE})\.?\s+(\d{{1,2}})\s*(?:\([^)]*\))?\s*)?"
    rf":\s*(.+)$",
    re.I,
)
# The trailing "; kind." on a key date.
_KIND = re.compile(
    r"^(.*?)\s*;\s*(signature|benchmark|specialty|special\s+event|event)\b\s*\.?\s*(.*)$",
    re.I,
)
KIND_TO_CATEGORY = {
    "signature": "sig",
    "benchmark": "bench",
    "specialty": "spec",
}

# "* Lift More templates on 9/2, 9/7, ..." -- the label, then the dates.
_CATEGORY_LINE = re.compile(
    r"^\**\s*([A-Za-z][A-Za-z /]*?)\s+(?:templates?\s+)?(?:are\s+)?on\s+(.+)$", re.I
)
_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})\b")
_REPEAT_LINE = re.compile(r"repeat\s+templates?\s+are\s+as\s+follows\s*:?\s*(.+)", re.I)
_REPEAT_PAIR = re.compile(r"\b(\d{1,2})/(\d{1,2})\s*=\s*(\d{1,2})/(\d{1,2})\b")
_THREE_G = re.compile(r"((?:\b\d{1,2}/\d{1,2}\b[\s,and]*)+)\s*(?:are|is)\s+3G", re.I)
_THREE_G_INLINE = re.compile(r"\b3G[\s-]*only\b", re.I)

_SECTION_END = re.compile(r"^\s*(?:please\s+see\s+our\s+\[?wiki|NEW\s+for\s+20)", re.I)


@dataclass
class ThreadReport:
    unknown_labels: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not (self.unknown_labels or self.warnings)

    def render(self) -> str:
        out = [f"  unrecognised category label {l!r} (add it to categories.py)"
               for l in self.unknown_labels]
        out += [f"  {w}" for w in self.warnings]
        return "\n".join(out)


def looks_like_thread(text: str) -> bool:
    """Cheap sniff so `parse` can pick the right reader."""
    hits = sum(
        bool(p.search(text))
        for p in (
            re.compile(r"key\s+dates\s+for\s+the\s+month", re.I),
            _REPEAT_LINE,
            re.compile(r"regarding\s+strength\s+50", re.I),
            re.compile(r"^\**\s*[A-Za-z][A-Za-z /]*\s+on\s+\d{1,2}/\d{1,2}", re.I | re.M),
        )
    )
    return hits >= 2


def _clean(line: str) -> str:
    line = line.replace("’", "'").replace("\xa0", " ")
    line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)   # markdown links
    line = re.sub(r"^\s*[*\-+>]\s+", "", line)             # bullets
    line = re.sub(r"[*_`]{1,3}", "", line)                 # emphasis
    return line.strip()


def _month_year(text: str) -> tuple[int, int]:
    m = _TITLE.search(text)
    if not m:
        raise ValueError(
            "could not find a line like 'Welcome to the September 2026 Monthly "
            "Thread' -- pass --month YYYY-MM"
        )
    return int(m.group(2)), MONTHS[m.group(1).lower()]


def _theme(text: str) -> str:
    m = _THEME.search(text)
    if m:
        theme = m.group(1).strip().strip('"')
        if 2 < len(theme) < 60:
            return theme
    m = _THEME_SHOUT.search(text)
    if m:
        return m.group(1).strip().title().replace(" And ", " & ")
    return ""


def parse_thread(
    text: str, year: int | None = None, month: int | None = None
) -> tuple[Month, ThreadReport]:
    report = ThreadReport()
    if year is None or month is None:
        year, month = _month_year(text)
    length = calendar.monthrange(year, month)[1]

    days: dict[int, Day] = {d: Day(day=d) for d in range(1, length + 1)}
    events: list[Event] = []
    three_g: set[int] = set()

    lines = [_clean(l) for l in text.splitlines()]

    # ---- Key Dates: signatures, benchmarks, specialties, events ----------
    in_key_dates = False
    for line in lines:
        if re.match(r"key\s+dates\s+for\s+the\s+month", line, re.I):
            in_key_dates = True
            continue
        if in_key_dates and _SECTION_END.match(line):
            in_key_dates = False
        if not in_key_dates or not line:
            continue

        km = _KEY_DATE.match(line)
        if not km:
            continue
        start_mo = MONTHS[km.group(1).lower()]
        start_day = int(km.group(2))
        end_mo = MONTHS[km.group(3).lower()] if km.group(3) else None
        end_day = int(km.group(4)) if km.group(4) else None
        body = km.group(5)

        kind_m = _KIND.match(body)
        if not kind_m:
            continue
        name, kind, tail = kind_m.group(1).strip(), kind_m.group(2).lower(), kind_m.group(3)
        kind = re.sub(r"\s+", " ", kind)

        spans_days = end_day is not None and not (
            end_mo == start_mo and end_day == start_day
        )
        if kind in ("event", "special event") or spans_days:
            events.append(Event(
                name=name,
                kind="event",
                start=start_day if start_mo == month else 1,
                end=(end_day if end_mo == month else length) if end_day else start_day,
            ))
            continue

        if start_mo != month or not 1 <= start_day <= length:
            continue
        category = KIND_TO_CATEGORY.get(kind)
        if category is None:
            continue
        days[start_day].entries.append(Entry(category=category, title=name, raw=line))
        if _THREE_G_INLINE.search(tail):
            three_g.add(start_day)

    # ---- category lines and the repeat map -------------------------------
    for line in lines:
        if not line:
            continue

        rm = _REPEAT_LINE.search(line)
        if rm:
            for a_mo, a_d, b_mo, b_d in _REPEAT_PAIR.findall(rm.group(1)):
                if int(a_mo) == month == int(b_mo):
                    day, src = int(a_d), int(b_d)
                    if 1 <= day <= length and 1 <= src <= length:
                        days[day].repeat_of = src
            continue

        for group in _THREE_G.findall(line):
            for mo, d in _DATE.findall(group):
                if int(mo) == month and 1 <= int(d) <= length:
                    three_g.add(int(d))

        cm = _CATEGORY_LINE.match(line)
        if not cm:
            continue
        label, rest = cm.group(1).strip(), cm.group(2)
        dates = [(int(a), int(b)) for a, b in _DATE.findall(rest)]
        if not dates:
            continue
        cat = lookup(label) or lookup(label.rstrip("s"))
        if cat is None or cat.key in ("unknown", "std"):
            report.unknown_labels.append(label)
            for mo, d in dates:
                if mo == month and 1 <= d <= length:
                    if not any(e.category == 'unknown' and e.title == label for e in days[d].entries):
                        days[d].entries.append(make_entry(label))
            continue
        for mo, d in dates:
            if mo == month and 1 <= d <= length:
                if not any(e.category == cat.key for e in days[d].entries):
                    days[d].entries.append(Entry(category=cat.key, raw=label))

    # ---- days nobody named are Standard ----------------------------------
    for d, day in days.items():
        if not day.entries:
            day.entries.append(Entry(category="std", raw="(not listed)"))

    for d in sorted(three_g):
        days[d].three_g = True

    m = Month(
        year=year, month=month,
        theme=_theme(text),
        events=events,
        days=[days[d] for d in sorted(days)],
    )
    _order_entries(m)

    if not any(d.repeat_of for d in m.days):
        report.warnings.append("no 'Repeat templates are as follows' line found")
    return m, report


def _order_entries(m: Month) -> None:
    """Named workouts first, then the registry's display order."""
    for day in m.days:
        day.entries.sort(key=lambda e: (0 if e.cat.titled else 1, e.cat.order))
