"""Thin browser entry points; the package owns parsing, models, and rendering."""
import json
import re

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


def _structured_validation(m, severity, message):
    issue = {'severity': severity, 'message': message, 'source': 'validation'}
    found = re.search(rf'\b{m.month}/(\d{{1,2}})\b', message)
    if found and 1 <= int(found[1]) <= m.length:
        issue.update(day=int(found[1]), control='repeat' if ' repeats ' in message else 'schedule')
    return issue


def _import_issues(report):
    issues = list(report.issues)
    for lineno, text in report.unparsed:
        issues.append({'severity': 'warning', 'source': 'import',
                       'message': f'Line {lineno}: could not read this workout line: {text}'})
    for lineno, text in report.unknown_templates:
        where = f'Line {lineno}: ' if lineno else ''
        issues.append({'severity': 'warning', 'source': 'import',
                       'message': f'{where}Unknown workout {text!r} was kept on its dates with a new color. Check the spelling.'})
    return issues


def _result(m, parse_notes="", *, edited=False, import_report=None):
    errors = validate.customization_errors(m)
    if errors:
        raise ValueError('\n'.join(message for _, message in errors))
    m.register_unknowns()
    issues = validate.check(m)
    errors = [msg for severity, msg in issues if severity == "error"]
    if edited and errors:
        raise ValueError("\n".join(errors))
    return json.dumps({
        "slug": m.slug, "html": render_html(m, allow_fetch=False),
        "notes": "\n".join(n for n in [parse_notes, validate.report(issues)] if n.strip()),
        "parseNotes": parse_notes, "errors": errors, "days": len(m.days),
        "issues": ((_import_issues(import_report) if import_report else [])
                   + [_structured_validation(m, severity, message) for severity, message in issues]),
        "importSummary": ({"recognizedDays": import_report.recognized_days,
                           "inferredDays": import_report.inferred_days} if import_report else None),
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


def generate(text, month=None, theme="", tagline="", appearance_preset_json=""):
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
    if appearance_preset_json:
        try:
            settings = json.loads(appearance_preset_json)
            allowed = {'appearance', 'category_styles', 'note_style', 'footnote_styles', 'credits'}
            if not isinstance(settings, dict) or set(settings) - allowed:
                raise ValueError('unsupported schedule fields')
            style = Month(m.year, m.month)
            for key, value in settings.items():
                if key == 'category_styles' and (not isinstance(value, dict)
                        or any(name.startswith('custom_') for name in value)):
                    raise ValueError('use built-in workout types')
                setattr(style, key, value)
            errors = validate.customization_errors(style)
            if errors:
                raise ValueError('; '.join(message for _, message in errors))
        except (ValueError, TypeError, AttributeError) as error:
            raise ValueError('Appearance preset: ' + str(error)) from None
        for key in settings:
            setattr(m, key, getattr(style, key))
    return _result(m, report.render() if not report.clean else "", import_report=report)


def regenerate(schedule_json):
    return _result(Month.from_dict(json.loads(schedule_json)), edited=True)


def restore(schedule_json):
    """Reopen a saved preview, retaining correctable schedule validation errors."""
    return _result(Month.from_dict(json.loads(schedule_json)))


def export_schedule(schedule_json, kind):
    from otfposter.exports import calendar_file, compact_html
    m = Month.from_dict(json.loads(schedule_json))
    _result(m, edited=True)
    if kind == 'ics':
        return json.dumps({'text': calendar_file(m)})
    return json.dumps(compact_html(m, kind))
