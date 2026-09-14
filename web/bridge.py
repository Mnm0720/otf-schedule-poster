"""Thin browser entry points; the package owns parsing, models, and rendering."""
import json

from otfposter.categories import CATEGORIES
from otfposter.derive import default_notes, default_footnotes, automatic_key_dates, highlights
from otfposter.assets import ICON_NAMES, make_icon_fn
from otfposter.models import Month, DEFAULT_CREDITS
from otfposter.parse import parse
from otfposter.render import render_html
from otfposter import validate


_EMPTY_MSG = (
    "Paste the monthly thread first. Copy the whole Reddit post "
    "\u2014 title, prose, and the category lists \u2014 and try again."
)
_NO_SCHEDULE_MSG = (
    "That didn't look like a monthly Orangetheory thread. Copy the entire post (title + lists) "
    "\u2014 it's fine to include links and prose; the tool ignores the rest. "
    "You can also type the month manually (e.g. 2026-09) and try again."
)
_NO_MONTH_MSG = (
    "Couldn't read the month from that text. Paste the full post, or set the Month field "
    "(e.g. 2026-09) and retry."
)
_MONTH_ERROR_HINTS = ("could not tell which month", "could not find a line like")


def _friendly_parse_error(err):
    msg = str(err)
    friendly = _NO_MONTH_MSG if any(h in msg for h in _MONTH_ERROR_HINTS) else _NO_SCHEDULE_MSG
    return friendly + "\nTechnical detail: " + msg


def _result(m, parse_notes="", *, edited=False):
    errors = validate.customization_errors(m)
    if errors:
        raise ValueError('\n'.join(message for _, message in errors))
    m.register_unknowns()
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
                     "key_dates": automatic_key_dates(m), "credits": DEFAULT_CREDITS},
        "keyDateTypes": sorted(c.label for c in CATEGORIES if c.titled and c.key != 'unknown'),
        "highlights": highlights(m),
        "icons": [{"key": name, "label": name.replace('_', ' ').title(),
                   "svg": str(make_icon_fn(allow_fetch=False)(name))} for name in ICON_NAMES],
        "categories": [{"key": c.key, "label": c.label, "titled": c.titled, "color": c.color}
                       for c in sorted(m.categories(), key=lambda c: c.order)],
    })


def generate(text, month=None, theme="", tagline=""):
    if not text or not text.strip():
        raise ValueError(_EMPTY_MSG)
    year = mo = None
    if month:
        year, mo = (int(p) for p in month.split("-"))
    try:
        m, report = parse(text, year=year, month=mo)
    except ValueError as err:
        raise ValueError(_friendly_parse_error(err)) from None
    if not m.days:
        raise ValueError(_NO_SCHEDULE_MSG)
    if theme:
        m.theme = theme
    if tagline:
        m.tagline = tagline
    return _result(m, report.render() if not report.clean else "")


def regenerate(schedule_json):
    return _result(Month.from_dict(json.loads(schedule_json)), edited=True)


def export_schedule(schedule_json, kind):
    from otfposter.exports import calendar_file, compact_html
    m = Month.from_dict(json.loads(schedule_json))
    _result(m, edited=True)
    if kind == 'ics':
        return json.dumps({'text': calendar_file(m)})
    return json.dumps(compact_html(m, kind))
