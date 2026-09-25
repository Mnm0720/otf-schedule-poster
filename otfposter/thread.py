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
from datetime import date, timedelta

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
    r"^\**\s*([A-Za-z][A-Za-z /-]*?)(?:\s+(?:templates?\s+)?(?:are\s+)?on\s+|\s*:\s*)(.+)$", re.I
)
_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})\b")
_DATE_SPAN = re.compile(
    rf"\b(\d{{1,2}})/(\d{{1,2}})(?:\s*(?:{DASH}|\bto\b|\bthrough\b)\s*(?:(\d{{1,2}})/)?(\d{{1,2}}))?\b", re.I
)
_PROSE_START = re.compile(r"^(?:i|we|our|you|your|they|their|this|these|please|see|visit|there)\b", re.I)
_PROSE_VERBS = re.compile(r"\b(?:are|is|will|should|can|must|have|has|was|were)\b", re.I)
_REPEAT_LINE = re.compile(r"repeat\s+templates?\s+are\s+as\s+follows\s*:?\s*(.+)", re.I)
_REPEAT_PAIR = re.compile(r"\b(\d{1,2})/(\d{1,2})\s*=\s*(\d{1,2})/(\d{1,2})\b")
_THREE_G = re.compile(r"((?:\b\d{1,2}/\d{1,2}\b[\s,and]*)+)\s*(?:are|is)\s+3G", re.I)
_THREE_G_INLINE = re.compile(r"\b3G[\s-]*only\b", re.I)

_SECTION_END = re.compile(r"^\s*(?:please\s+see\s+our\s+\[?wiki|NEW\s+for\s+20)", re.I)


@dataclass
class ThreadReport:
    unknown_labels: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    recognized_days: list[int] = field(default_factory=list)
    inferred_days: list[int] = field(default_factory=list)

    def warn(self, message, day=None):
        self.warnings.append(message)
        issue = {'severity': 'warning', 'message': message, 'source': 'import'}
        if day is not None:
            issue.update(day=day, control='schedule')
        self.issues.append(issue)

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
    category_lines = any(_category_match(_clean(line)) and _DATE.search(line)
                         for line in text.splitlines())
    return hits >= 2 or bool(_TITLE.search(text) and category_lines)


def _category_match(line):
    if _PROSE_START.match(line):
        return None
    matched = _CATEGORY_LINE.match(line)
    if matched and _PROSE_VERBS.search(matched[1]):
        return None
    return matched


def _recognizable_category_line(line):
    """Catch likely workout lists without turning ordinary prose into warnings."""
    if _PROSE_START.match(line) or not _DATE.search(line):
        return False
    prefix = line[:_DATE.search(line).start()].strip()
    words = prefix.split()
    return any(lookup(' '.join(words[:count]).rstrip(':,;'))
               for count in range(1, min(len(words), 5) + 1))


def _checked_date(year, mo, day, report, line):
    try:
        return date(year, mo, day)
    except ValueError:
        report.warn(f'{mo}/{day} is not a valid date. Check this source line: {line}')
        return None


def _category_dates(rest, year, month, report, line):
    """Read full tokens so a range is never mistaken for its endpoints only."""
    found = []
    for match in _DATE_SPAN.finditer(rest):
        mo, day = int(match[1]), int(match[2])
        start = _checked_date(year, mo, day, report, line)
        end = (_checked_date(year, int(match[3] or mo), int(match[4]), report, line)
               if match[4] else start)
        if start is None or end is None:
            continue
        if end < start:
            report.warn(f'{match[0]} is a reversed date range. Put the earlier date first: {line}')
            continue
        if start.month != month or end.month != month:
            report.warn(f'{match[0]} includes dates outside {calendar.month_name[month]} {year}. '
                        f'Check the month or source dates: {line}')
        current = start
        while current <= end:
            if current.month == month:
                found.append(current.day)
            current += timedelta(days=1)
    leftover = re.sub(r'\([^)]*\)', '', _DATE_SPAN.sub('', rest))
    if re.search(r'\b(?:except|excluding)\b', rest, re.I):
        report.warn(f'Could not apply date exclusions in this workout line: {line}. '
                    'The listed range was kept; check those dates and remove excluded workouts in the editor.')
    if re.search(r'(?:^|[,;]\s*)\d{1,2}(?=\s*(?:[,;.]|$))', leftover):
        report.warn(f'Could not read every date in this workout line: {line}. '
                    f'Write the month for each date, for example {month}/3, {month}/4.')
    return sorted(set(found))


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
            report.warn(f'Could not read the workout kind for this Key Date: {line}. '
                        'Add a kind such as "; benchmark", "; signature", "; specialty", or "; event", '
                        'or add the workout in the editor.',
                        start_day if start_mo == month and 1 <= start_day <= length else None)
            continue
        name, kind, tail = kind_m.group(1).strip(), kind_m.group(2).lower(), kind_m.group(3)
        kind = re.sub(r"\s+", " ", kind)

        start_date = _checked_date(year, start_mo, start_day, report, line)
        end_date = (_checked_date(year, end_mo, end_day, report, line)
                    if end_day is not None else start_date)
        if start_date is None or end_date is None:
            continue
        if end_date < start_date:
            report.warn(f'Key Date range is reversed. Put the earlier date first: {line}')
            continue
        if start_mo != month or (end_mo is not None and end_mo != month):
            report.warn(f'Key Date includes dates outside {calendar.month_name[month]} {year}. '
                        f'Check the month or source dates: {line}')
        month_start, month_end = date(year, month, 1), date(year, month, length)
        if end_date < month_start or start_date > month_end:
            continue

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
            pairs = _REPEAT_PAIR.findall(rm.group(1))
            if not pairs:
                report.warn(f'Could not read the repeat dates. Use a pair such as {month}/16 = {month}/1: {line}')
            elif _DATE.search(_REPEAT_PAIR.sub('', rm.group(1))):
                report.warn(f'Could not read every repeat pair: {line}. '
                            f'Use pairs such as {month}/16 = {month}/1.')
            for a_mo, a_d, b_mo, b_d in pairs:
                first = _checked_date(year, int(a_mo), int(a_d), report, line)
                second = _checked_date(year, int(b_mo), int(b_d), report, line)
                if first is None or second is None:
                    continue
                if first.month != month or second.month != month:
                    report.warn(f'Repeat dates include dates outside {calendar.month_name[month]} {year}: {line}')
                    continue
                days[first.day].repeat_of = second.day
            continue

        for group in _THREE_G.findall(line):
            for mo, d in _DATE.findall(group):
                value = _checked_date(year, int(mo), int(d), report, line)
                if value is None:
                    continue
                if value.month != month:
                    report.warn(f'{mo}/{d} is outside {calendar.month_name[month]} {year}. '
                                f'Check the 3G date: {line}')
                    continue
                three_g.add(value.day)

        cm = _category_match(line)
        if not cm:
            if _recognizable_category_line(line):
                report.warn(f'Could not read this workout line: {line}. '
                            f'Use a category followed by "on {month}/3, {month}/4", or check those dates in the editor.')
            continue
        label, rest = cm.group(1).strip(), cm.group(2)
        dates = _category_dates(rest, year, month, report, line)
        if not dates:
            if not _DATE.search(rest) and lookup(label):
                report.warn(f'Could not read dates for {label}. Use dates such as {month}/3: {line}')
            continue
        cat = lookup(label) or lookup(label.rstrip("s"))
        if cat is None or cat.key == "unknown":
            report.unknown_labels.append(label)
            for d in dates:
                if not any(e.category == 'unknown' and e.title == label for e in days[d].entries):
                    days[d].entries.append(make_entry(label, raw=line))
            continue
        for d in dates:
            if not any(e.category == cat.key for e in days[d].entries):
                days[d].entries.append(Entry(category=cat.key, raw=label))

    # ---- days nobody named are Standard ----------------------------------
    report.recognized_days = [d for d, day in days.items() if day.entries]
    report.inferred_days = [d for d, day in days.items() if not day.entries]
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
        report.warn("no valid 'Repeat templates are as follows' dates found; check repeat links in the editor")
    return m, report


def _order_entries(m: Month) -> None:
    """Named workouts first, then the registry's display order."""
    for day in m.days:
        day.entries.sort(key=lambda e: (0 if e.cat.titled else 1, e.cat.order))
