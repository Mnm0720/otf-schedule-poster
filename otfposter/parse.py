"""Turn a pasted monthly-template post into a :class:`Month`.

The upstream posts are hand-written prose, so this parser is deliberately
forgiving: it scans for anything that looks like "a date, then some template
names" and ignores everything else. Whatever it could not place is returned in
``ParseReport.unparsed`` so a human can eyeball it (and ``--strict`` turns that
into a build failure).

Recognised shapes::

    9/1 - Standard
    9/2 - Lift More + Elevation Gain
    09/03: Run/Row
    Sept 4 - Low Bench
    9/16 - Standard (repeat of 9/1)
    9/23 = Signature: The Chipper

or a date on its own line followed by its templates::

    Tuesday, September 1
      Standard
      Lift More
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field

from .categories import lookup
from .models import Day, Entry, Month, make_entry

MONTH_NAMES = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTH_NAMES.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
MONTH_NAMES["sept"] = 9

EN_DASH = "–"
EM_DASH = "—"
BULLET = "•"
MIDDOT = "·"
RSQUO = "’"
NBSP = " "

# Separators between the date and the templates.
_SEP = rf"[-{EN_DASH}{EM_DASH}:{BULLET}{MIDDOT}|]+|="
# Separators between templates on one line. Note the absence of "/" -- it lives
# inside "Run/Row".
_SPLIT = re.compile(
    rf"\s*(?:\+|,|&|;|{MIDDOT}|{BULLET}|\||\band\b|\bplus\b|\bw/\b)\s*", re.I
)

_DATE_NUM = re.compile(
    rf"^(?:(\d{{1,2}})[/.](\d{{1,2}})|(\d{{1,2}})\.?)"
    rf"\s*(?=$|[-{EN_DASH}{EM_DASH}:{BULLET}{MIDDOT}|=\s])"
)
_DATE_NAME = re.compile(
    r"^(?:(?:mon|tues?|wed(?:nes)?|thu(?:rs)?|fri|sat(?:ur)?|sun)\w*\s*,?\s*)?"
    r"([a-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b",
    re.I,
)
_REPEAT = re.compile(
    r"\(?\b(?:repeat(?:s|ed)?(?:\s+of)?|same\s+as|re-?run\s+of)\s*"
    r"(?:\w+\s+)?(?:(\d{1,2})[/.](\d{1,2})|(\d{1,2}))\b\)?",
    re.I,
)
_NOT_REPEAT = re.compile(r"\bnot\s+a\s+repeat\b|\bnew\s+template\b|\boriginal\b", re.I)
_TITLED = re.compile(
    r"^\s*(signature|benchmark|specialty|special|3g)\b\s*[:\-" + EN_DASH + EM_DASH + r"]?\s*(.*)$",
    re.I,
)
_NOISE = re.compile(
    r"^\s*(?:edit\b|source\b|as always\b|disclaimer\b|note:|thanks\b|enjoy\b|"
    r"https?://|u/|\*{2,}|_{2,}|#{1,6}\s)",
    re.I,
)


@dataclass
class ParseReport:
    unparsed: list[tuple[int, str]] = field(default_factory=list)
    unknown_templates: list[tuple[int, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not (self.unparsed or self.unknown_templates or self.warnings)

    def render(self) -> str:
        out = []
        for ln, text in self.unparsed:
            out.append(f"  line {ln}: could not read -- {text!r}")
        for ln, text in self.unknown_templates:
            out.append(f"  line {ln}: unknown template {text!r} (add it to categories.py)")
        out += [f"  {w}" for w in self.warnings]
        return "\n".join(out)


def _clean(line: str) -> str:
    """Strip markdown bullets, emphasis and list markers."""
    line = line.replace(RSQUO, "'").replace(NBSP, " ")
    line = re.sub(r"^\s*(?:[*\-+>]\s+|\d+\.\s+(?=[A-Za-z]))", "", line)
    line = re.sub(r"[*_`]{1,3}", "", line)
    return line.strip()


def _month_year_hint(text: str) -> tuple[int | None, int | None]:
    """Find 'September 2026' (or 'Sep 2026') anywhere in the post."""
    m = re.search(r"\b([A-Za-z]{3,9})\.?\s+(20\d{2})\b", text)
    if m and m.group(1).lower() in MONTH_NAMES:
        return MONTH_NAMES[m.group(1).lower()], int(m.group(2))
    return None, None


def _read_date(line: str, month: int | None) -> tuple[int | None, int | None, str]:
    """Return (month, day, remainder) for a line that starts with a date."""
    m = _DATE_NUM.match(line)
    if m:
        if m.group(1):
            mo, day = int(m.group(1)), int(m.group(2))
        else:
            mo, day = month, int(m.group(3))
        return mo, day, line[m.end():]
    m = _DATE_NAME.match(line)
    if m and m.group(1).lower() in MONTH_NAMES:
        return MONTH_NAMES[m.group(1).lower()], int(m.group(2)), line[m.end():]
    return None, None, line


def _strip_sep(text: str) -> str:
    return re.sub(rf"^\s*(?:{_SEP})\s*", "", text).strip()


def _read_entries(text: str, report: ParseReport, lineno: int) -> list[Entry]:
    entries: list[Entry] = []
    for chunk in _SPLIT.split(text):
        chunk = chunk.strip(" .()")
        if not chunk:
            continue
        titled = _TITLED.match(chunk)
        if titled:
            entry = make_entry(titled.group(1), titled.group(2).strip(" :-"), raw=chunk)
        else:
            entry = make_entry(chunk, raw=chunk)
        if entry.category == "unknown":
            report.unknown_templates.append((lineno, chunk))
        entries.append(entry)
    return entries


def parse(
    text: str, year: int | None = None, month: int | None = None
) -> tuple[Month, ParseReport]:
    """Parse a pasted post into a Month plus a report of anything unclear."""
    report = ParseReport()
    hint_month, hint_year = _month_year_hint(text)
    month = month or hint_month
    year = year or hint_year
    if month is None or year is None:
        raise ValueError(
            "could not tell which month this is -- pass --month YYYY-MM "
            "or include e.g. 'September 2026' in the text"
        )

    days: dict[int, Day] = {}
    current: Day | None = None
    length = calendar.monthrange(year, month)[1]

    for lineno, raw_line in enumerate(text.splitlines(), 1):
        line = _clean(raw_line)
        if not line or _NOISE.match(line):
            current = None
            continue

        mo, dnum, rest = _read_date(line, month)
        if dnum is not None and mo == month and 1 <= dnum <= length:
            rest = _strip_sep(rest)
            day = days.setdefault(dnum, Day(day=dnum))
            current = day
        elif dnum is not None and mo != month:
            # A date from a neighbouring month (e.g. a "10/1 preview" footer).
            current = None
            continue
        elif current is not None:
            day, rest = current, line
        else:
            if _looks_like_template(line):
                report.unparsed.append((lineno, line))
            continue

        rep = _REPEAT.search(rest)
        if rep:
            rmo = int(rep.group(1)) if rep.group(1) else month
            rday = int(rep.group(2)) if rep.group(2) else int(rep.group(3))
            if rmo == month and 1 <= rday <= length:
                day.repeat_of = rday
            rest = (rest[: rep.start()] + " " + rest[rep.end():]).strip(
                " .,;-" + EN_DASH + EM_DASH
            )
        elif _NOT_REPEAT.search(rest):
            day.note = "Not a repeat"
            rest = _NOT_REPEAT.sub("", rest).strip(" .,;()-" + EN_DASH + EM_DASH)

        rest = _strip_sep(rest)
        if rest:
            day.entries.extend(_read_entries(rest, report, lineno))

    if not days:
        raise ValueError("no dated lines found -- is this the right text?")

    for d in range(1, length + 1):
        day = days.setdefault(d, Day(day=d))
        if not day.entries and day.repeat_of is not None:
            # A bare "repeat of N" line: inherit that day's templates.
            src = days.get(day.repeat_of)
            if src and src.entries:
                day.entries = [Entry(e.category, e.title, e.raw) for e in src.entries]
        if not day.entries:
            report.warnings.append(f"{month}/{d} has no template listed")

    return Month(year=year, month=month, days=[days[d] for d in sorted(days)]), report


def _looks_like_template(line: str) -> bool:
    """Only complain about prose that plausibly names a workout."""
    if len(line) > 120:
        return False
    return lookup(line) is not None or bool(_TITLED.match(line))
