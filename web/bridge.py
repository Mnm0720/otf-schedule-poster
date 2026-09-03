"""Thin browser entry points; the package owns parsing, models, and rendering."""
import json

from otfposter.categories import CATEGORIES
from otfposter.derive import default_notes, default_footnotes, automatic_key_dates, highlights
from otfposter.assets import ICON_NAMES
from otfposter.models import Month
from otfposter.parse import parse
from otfposter.render import render_html
from otfposter import validate


def _result(m, parse_notes="", *, edited=False):
    issues = validate.check(m)
    for index, event in enumerate(m.events, 1):
        if (type(event.start) is not int or type(event.end) is not int
                or not 1 <= event.start <= event.end <= m.length):
            raise ValueError(f"Event {index}: choose start/end days between 1 and {m.length}, in order.")
        if not event.name.strip():
            raise ValueError(f"Event {index}: enter a name.")
    errors = [msg for severity, msg in issues if severity == "error"]
    if edited and errors:
        raise ValueError("\n".join(errors))
    return json.dumps({
        "slug": m.slug, "html": render_html(m, allow_fetch=False),
        "notes": "\n".join(n for n in [parse_notes, validate.report(issues)] if n.strip()),
        "parseNotes": parse_notes, "errors": errors, "days": len(m.days),
        "schedule": m.to_dict(),
        "defaults": {"notes": default_notes(m), "footnotes": default_footnotes(m),
                     "key_dates": automatic_key_dates(m)},
        "highlights": highlights(m),
        "icons": [{"key": name, "label": name.replace('_', ' ').title()} for name in ICON_NAMES],
        "categories": [{"key": c.key, "label": c.label, "titled": c.titled, "color": c.color}
                       for c in sorted(CATEGORIES, key=lambda c: c.order)],
    })


def generate(text, month=None, theme="", tagline=""):
    year = mo = None
    if month:
        year, mo = (int(p) for p in month.split("-"))
    m, report = parse(text, year=year, month=mo)
    if theme:
        m.theme = theme
    if tagline:
        m.tagline = tagline
    return _result(m, report.render() if not report.clean else "")


def regenerate(schedule_json):
    return _result(Month.from_dict(json.loads(schedule_json)), edited=True)
