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

    # -- a repeat day must carry its source day's templates ---------------
    # Checked against Apr 2026, Aug 2026, Sep 2026 and Oct 2025: 45 repeat
    # pairs, zero mismatches. So a mismatch means the paste lost a category
    # line or a repeat pair, which is exactly the typo worth catching.
    for day in m.days:
        src = by_day.get(day.repeat_of) if day.repeat_of else None
        if src is None:
            continue
        here, there = _template_set(day), _template_set(src)
        if here != there:
            issues.append((WARN, f"{m.mmdd(day.day)} repeats {m.mmdd(src.day)} but "
                                 f"lists {_fmt_set(here)} vs {_fmt_set(there)}"))

    return issues


def _template_set(day) -> tuple:
    """The equipment/format templates on a day.

    Named workouts are excluded: a signature lands on top of whatever template
    the day was already running, so 8/7 (Catch Me If You Can + Run/Row) still
    counts as a Run/Row day for repeat purposes.
    """
    return tuple(sorted(e.label for e in day.entries if not e.cat.titled))


def _fmt_set(s: tuple) -> str:
    return " + ".join(s) if s else "nothing"


def _fmt(m: Month, days) -> str:
    return ", ".join(m.mmdd(d) for d in sorted(days))


def report(issues: list[tuple[str, str]]) -> str:
    return "\n".join(f"  [{sev}] {msg}" for sev, msg in issues)


def has_errors(issues) -> bool:
    return any(sev == ERROR for sev, _ in issues)
