"""Sanity checks on a parsed month.

These encode the rules the poster itself asserts, so a typo in the source paste
turns into a build failure instead of a wrong poster nobody notices.
"""
from __future__ import annotations

from datetime import date, timedelta

from .models import Month

ERROR, WARN = "error", "warning"


def check(m: Month) -> list[tuple[str, str]]:
    """Return a list of (severity, message)."""
    issues: list[tuple[str, str]] = []
    by_day = m.by_day()

    # -- coverage ---------------------------------------------------------
    seen = sorted(by_day)
    missing = [d for d in range(1, m.length + 1) if d not in by_day]
    if missing:
        issues.append((ERROR, f"no entry for day(s): {_fmt(m, missing)}"))
    extra = [d for d in seen if d < 1 or d > m.length]
    if extra:
        issues.append((ERROR, f"day(s) outside {m.name}: {_fmt(m, extra)}"))
    empty = [d for d, day in by_day.items() if not day.entries]
    if empty:
        issues.append((WARN, f"no template listed for: {_fmt(m, empty)}"))

    # -- repeats ----------------------------------------------------------
    for day in m.days:
        if day.repeat_of is None:
            continue
        if day.repeat_of not in by_day:
            issues.append((ERROR, f"{m.mmdd(day.day)} repeats {m.mmdd(day.repeat_of)}, "
                                  f"which is not in this month"))
        elif day.repeat_of >= day.day:
            issues.append((ERROR, f"{m.mmdd(day.day)} repeats {m.mmdd(day.repeat_of)}, "
                                  f"which is not earlier in the month"))
        elif by_day[day.repeat_of].repeat_of is not None:
            issues.append((WARN, f"{m.mmdd(day.day)} repeats {m.mmdd(day.repeat_of)}, "
                                 f"which is itself a repeat"))

    dupes: dict[int, list[int]] = {}
    for day in m.days:
        if day.repeat_of:
            dupes.setdefault(day.repeat_of, []).append(day.day)
    for src, days in dupes.items():
        if len(days) > 1:
            issues.append((WARN, f"{m.mmdd(src)} is repeated more than once: "
                                 f"{_fmt(m, days)}"))

    # -- unknown templates ------------------------------------------------
    unknown = sorted({e.title or e.raw
                      for day in m.days for e in day.entries
                      if e.category == "unknown"})
    for name in unknown:
        issues.append((WARN, f"unrecognised template {name!r} - it will render in "
                             f"grey; add it to categories.py to give it a colour"))

    # -- "templates never repeat inside the same Mon-Sun week" -------------
    for a, b in _same_week_pairs(m):
        if _signature(by_day[a]) and _signature(by_day[a]) == _signature(by_day[b]):
            issues.append((WARN, f"{m.mmdd(a)} and {m.mmdd(b)} share a template set "
                                 f"inside the same Mon-Sun week"))

    return issues


def _signature(day) -> tuple:
    """What makes two days 'the same template'. Standard days are excluded --
    a month is mostly Standard and those genuinely do recur."""
    keys = tuple(sorted(e.label for e in day.entries))
    if not keys or keys == ("Standard",):
        return ()
    return keys


def _same_week_pairs(m: Month):
    weeks: dict[date, list[int]] = {}
    for day in m.days:
        d = date(m.year, m.month, day.day)
        monday = d - timedelta(days=d.weekday())
        weeks.setdefault(monday, []).append(day.day)
    for days in weeks.values():
        for i, a in enumerate(days):
            for b in days[i + 1:]:
                yield a, b


def _fmt(m: Month, days) -> str:
    return ", ".join(m.mmdd(d) for d in sorted(days))


def report(issues: list[tuple[str, str]]) -> str:
    return "\n".join(f"  [{sev}] {msg}" for sev, msg in issues)


def has_errors(issues) -> bool:
    return any(sev == ERROR for sev, _ in issues)
