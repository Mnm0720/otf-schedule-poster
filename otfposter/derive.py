"""Everything the poster shows that is *implied* by the day-by-day schedule.

In the original one-off build these panels were typed out by hand next to the
calendar data, so the two could -- and did -- drift. Here they are computed, so
the day list is the only thing anyone edits.
"""
from __future__ import annotations

from datetime import date

from .categories import BY_KEY, CATEGORIES, light_text
from .models import Month

# Icons (Material Symbols names) used for the Key Dates rows, per category.
KEY_DATE_ICONS = {
    "bench": ("local_cafe", "#6A1B9A"),
    "sig": ("military_tech", "#F4511E"),
    "spec": ("local_fire_department", "#E53935"),
}


def calendar_grid(m: Month) -> list[list[int | None]]:
    """The month laid out Sunday-first, padded with None."""
    cells: list[int | None] = [None] * m.weekday_of(1)
    cells += list(range(1, m.length + 1))
    while len(cells) % 7:
        cells.append(None)
    return [cells[i:i + 7] for i in range(0, len(cells), 7)]


def marked_dates(m: Month) -> list[dict]:
    """Benchmarks, signatures and specialties, in date order."""
    out = []
    for day in m.days:
        for e in day.entries:
            if e.cat.titled and e.category != "unknown":
                out.append({
                    "day": day.day,
                    "mmdd": m.mmdd(day.day),
                    "category": e.category,
                    "label": e.cat.label,
                    "title": e.title,
                    "text": f"{m.mmdd(day.day)} {e.label}",
                    "weekday": date(m.year, m.month, day.day).strftime("%A"),
                })
    return out


def highlights(m: Month) -> list[dict]:
    """One row per category: the colour, the label, and the dates it lands on."""
    hits: dict[str, list[str]] = {}
    titles: dict[str, list[str]] = {}
    for day in m.days:
        for e in day.entries:
            hits.setdefault(e.category, []).append(m.mmdd(day.day))
            if e.cat.titled and e.title:
                titles.setdefault(e.category, []).append(f"{m.mmdd(day.day)} {e.title}")

    rows = []
    for cat in sorted(CATEGORIES, key=lambda c: c.order):
        if cat.key == "std":
            continue  # every month is mostly Standard; listing them is noise
        dates = hits.get(cat.key, [])
        if not dates and not cat.always_list:
            continue
        if cat.titled and titles.get(cat.key):
            value = BULLET_SEP.join(titles[cat.key])
        elif dates:
            value = ", ".join(dates)
        else:
            value = "none scheduled this month"
        rows.append({
            "color": cat.color,
            "label": _plural(cat.label),
            "value": value,
            "count": len(dates),
        })
    return rows


BULLET_SEP = " · "


def _plural(label: str) -> str:
    if label in ("Run/Row", "Signature", "Specialty", "Benchmark"):
        return {"Run/Row": "Run/Rows", "Signature": "Signatures",
                "Specialty": "Specialties", "Benchmark": "Benchmarks"}[label]
    if label in ("Switch Template",):
        return "Switch Templates"
    return label


def repeat_map(m: Month) -> list[dict]:
    return [
        {"day": m.mmdd(d.day), "source": m.mmdd(d.repeat_of)}
        for d in m.days
        if d.repeat_of
    ]


def repeat_window_start(m: Month) -> int | None:
    """The first day of the month that belongs to the repeat cycle.

    Everything before this is an original by definition, so calling those days
    "not a repeat" would be noise. The boundary is the earlier of: the first
    day that repeats something, and the day after the last day anything points
    back to.
    """
    repeats = [d.day for d in m.days if d.repeat_of]
    if not repeats:
        return None
    sources = [d.repeat_of for d in m.days if d.repeat_of]
    return min(min(repeats), max(sources) + 1)


# Below this share of the repeat window actually being repeats, the month has
# no tight cycle (Oct 2025 has only 7 repeats across 20 days). Calling the rest
# "not a repeat" then labels most of the calendar and says nothing.
TIGHT_CYCLE = 0.6


def repeat_coverage(m: Month) -> float:
    """Share of the repeat window that actually repeats something."""
    start = repeat_window_start(m)
    if start is None:
        return 0.0
    window = [d for d in m.days if d.day >= start]
    if not window:
        return 0.0
    return sum(1 for d in window if d.repeat_of) / len(window)


def has_tight_cycle(m: Month) -> bool:
    return repeat_coverage(m) >= TIGHT_CYCLE


def non_repeat_days(m: Month) -> list[int]:
    """Days inside the repeat window that are *not* repeats.

    Empty when the month has no tight repeat cycle -- see TIGHT_CYCLE.
    """
    start = repeat_window_start(m)
    if start is None or not has_tight_cycle(m):
        return []
    return [d.day for d in m.days if d.day >= start and not d.repeat_of]


def key_dates(m: Month) -> list[dict]:
    """The Key Dates panel: marked workouts, then the non-repeat callout."""
    rows = []
    seen: set[int] = set()
    for md in marked_dates(m):
        if md["day"] in seen:
            continue
        seen.add(md["day"])
        icon, color = KEY_DATE_ICONS.get(md["category"], ("star", "#E8A33D"))
        d = date(m.year, m.month, md["day"])
        rows.append({
            "icon": icon,
            "color": color,
            "heading": f"{d.strftime('%B')} {md['day']} ({d.strftime('%A')})",
            "detail": md["title"] and f"{md['label']}: {md['title']}" or md["label"],
        })

    for ev in m.events:
        d = date(m.year, m.month, ev.start)
        end = date(m.year, m.month, ev.end)
        heading = (f"{d.strftime('%B')} {ev.start}" if ev.start == ev.end
                   else f"{d.strftime('%B')} {ev.start} - {end.strftime('%B')} {ev.end}")
        rows.insert(0, {
            "icon": "flag", "color": "#F4511E",
            "heading": heading,
            "detail": f"{ev.name}; month-long event" if _is_whole_month(m, ev)
                      else f"{ev.name}; event",
        })

    nrd = non_repeat_days(m)
    if nrd:
        rows.append({
            "icon": "star", "color": "#E8A33D",
            "heading": _join_days(m, nrd),
            "detail": f"The month{RSQ}s only non-repeat day"
                      + ("s" if len(nrd) > 1 else ""),
        })
    return rows


RSQ = "’"


def _is_whole_month(m: Month, ev) -> bool:
    return ev.start == 1 and ev.end == m.length


def _join_days(m: Month, days: list[int]) -> str:
    month_name = date(m.year, m.month, 1).strftime("%B")
    nums = [str(d) for d in days]
    if len(nums) == 1:
        return f"{month_name} {nums[0]}"
    return f"{month_name} " + ", ".join(nums[:-1]) + f" & {nums[-1]}"


def default_notes(m: Month) -> list[str]:
    """The checklist beside the Strength 50 / Tread 50 split."""
    notes = [
        "Tread 50 runs daily; Strength 50 follows the split at left",
        "Tread benchmarks appear in Tread 50; signatures and specialties do not",
        "Templates never repeat inside the same Monday-Sunday week",
    ]
    start = repeat_window_start(m)
    if start and has_tight_cycle(m):
        notes.append(
            f"Repeating starts after the first {start - 1} days "
            "and runs close to in order"
        )
    elif start:
        notes.append(
            f"Only {sum(1 for d in m.days if d.repeat_of)} days repeat an "
            "earlier template this month"
        )
    for md in marked_dates(m):
        if md["category"] == "bench":
            notes.append(
                f"{md['mmdd']} is a benchmark - the {md['title']}"
                if md["title"] else f"{md['mmdd']} is a benchmark day"
            )

    month_name = date(m.year, m.month, 1).strftime("%B")
    absent = [d for d in (29, 30, 31) if d > m.length]
    if absent:
        span = (_ordinal(absent[0]) if len(absent) == 1
                else f"{_ordinal(absent[0])}-{_ordinal(absent[-1])}")
        plural = "" if len(absent) == 1 else "s"
        notes.append(
            f"{month_name} has {m.length} days, so there "
            f"{'is' if len(absent) == 1 else 'are'} no {span} bonus template{plural}"
        )
    else:
        notes.append(f"{month_name} has 31 days, including the 31st bonus template")
    return notes[:6]


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def default_footnotes(m: Month) -> list[dict]:
    """Bottom-right callouts. Some are evergreen, some depend on the month."""
    out = []
    three_g = [m.mmdd(d.day) for d in m.days if d.three_g]
    if three_g:
        out.append({"icon": "groups", "lead": "3G-only templates:",
                    "text": f"{', '.join(three_g)} run 3G-style with about 14 "
                            "minutes at each station, even where 2G is listed."})
    else:
        out.append({"icon": "groups", "lead": "No 3G-only templates this month.",
                    "text": f"{date(m.year, m.month, 1).strftime('%B')} has no "
                            "3G-only templates on the calendar."})

    specialties = [d for d in m.days
                   for e in d.entries if e.category == "spec"]
    if specialties:
        days = ", ".join(sorted({m.mmdd(d.day) for d in specialties},
                                key=lambda x: int(x.split("/")[1])))
        out.append({"icon": "local_fire_department",
                    "lead": "Specialty workouts this month.",
                    "text": f"Scheduled on {days}."})

    bench_bits = []
    for key, name in (("lowbench", "Low bench"), ("incline", "Incline bench")):
        days = [m.mmdd(d.day) for d in m.days
                if any(e.category == key for e in d.entries)]
        if days:
            bench_bits.append(f"{name} {', '.join(days)}")
    if bench_bits:
        out.append({"icon": "fitness_center", "lead": "Bench days are specific this month.",
                    "text": (" " + BULLET_SEP).join(bench_bits).strip() + "."})

    out.append({"icon": "cyclone", "lead": "Tornado & 90-minute classes",
                "text": "stay studio-specific. Two Tornado templates exist each "
                        "month; coaches pick."})
    out.append({"icon": "bolt", "lead": f"Hyrox templates aren{RSQ}t date-specific.",
                "text": "Participating studios run whichever training phase "
                        "they're in."})
    return out


def cell_note(m: Month, day) -> tuple[str, bool]:
    """The small italic footnote under a calendar cell. (text, is_flagged)"""
    if day.note:
        return day.note, True
    if day.repeat_of:
        return f"Repeat of {m.mmdd(day.repeat_of)}", False
    if day.day in non_repeat_days(m):
        return "Not a repeat", True
    return "", False


def pill(entry) -> dict:
    cat = entry.cat
    return {
        "label": entry.label,
        "color": cat.color,
        "fg": "#fff" if light_text(cat.color) else "#5C6470",
    }


def build_context(m: Month) -> dict:
    """Assemble every value the Jinja template needs."""
    grid = calendar_grid(m)
    by_day = m.by_day()
    weeks = []
    for row in grid:
        cells = []
        for d in row:
            if d is None:
                cells.append(None)
                continue
            day = by_day[d]
            note, flagged = cell_note(m, day)
            cells.append({
                "day": d,
                "pills": [pill(e) for e in day.entries],
                "two": len(day.entries) > 1,
                "note": note,
                "flag": flagged,
                "weekend": m.weekday_of(d) in (0, 6),
                "three_g": day.three_g,
            })
        weeks.append(cells)

    legend = [
        {"label": c.label, "color": c.color, "blurb": c.blurb,
         "fg": "#fff" if light_text(c.color) else "#5C6470"}
        for c in sorted(CATEGORIES, key=lambda c: c.order)
        if c.key != "unknown"
    ]

    return {
        "m": m,
        "title_month": m.name,
        "subtitle": m.subtitle,
        "theme": m.theme,
        "tagline": m.tagline,
        "marked": marked_dates(m),
        "events": [{"label": e.label(m.month), "name": e.name} for e in m.events],
        "weeks": weeks,
        "strength_split": m.strength_split,
        "notes": m.notes or default_notes(m),
        "key_dates": key_dates(m),
        "highlights": highlights(m),
        "repeat_map": repeat_map(m),
        "non_repeat": [m.mmdd(d) for d in non_repeat_days(m)],
        "legend": legend,
        "footnotes": m.footnotes or default_footnotes(m),
        "source_url": m.source_url,
    }
