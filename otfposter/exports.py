"""Portable calendar and compact image layouts for the same Month model."""
from datetime import date, datetime, timedelta, timezone
import hashlib
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup
from .assets import font_css
from .derive import build_context
from .render import safe_tagline


def _text(value):
    return str(value).replace('\\', '\\\\').replace('\r\n', '\n').replace('\r', '\n').replace('\n', r'\n').replace(';', r'\;').replace(',', r'\,')


def _fold(line):
    parts, current = [], ''
    for char in line:
        if len((current + char).encode('utf-8')) > 75:
            parts.append(current)
            current = ' '
        current += char
    return '\r\n'.join(parts + [current])


def calendar_file(m):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//OTF Schedule Poster//EN', 'CALSCALE:GREGORIAN',
             'X-WR-CALNAME:' + _text('OTF ' + m.name)]

    def event(uid, start, end, title, description):
        lines.extend(['BEGIN:VEVENT', f'UID:{uid}@otf-schedule-poster', 'DTSTAMP:' + stamp,
            'DTSTART;VALUE=DATE:' + start.strftime('%Y%m%d'), 'DTEND;VALUE=DATE:' + end.strftime('%Y%m%d'),
            'SUMMARY:' + _text(title), 'DESCRIPTION:' + _text(description), 'TRANSP:TRANSPARENT', 'END:VEVENT'])

    for day in m.days:
        start = date(m.year, m.month, day.day)
        labels = [e.title or m.category(e.category).label if e.category.startswith('custom_') else e.label for e in day.entries]
        title = 'OTF: ' + (' + '.join(labels) or 'Schedule') + (' (3G)' if day.three_g else '')
        detail = [day.note]
        if day.repeat_of:
            detail.append('Repeat of ' + m.mmdd(day.repeat_of))
        detail.extend(e.name for e in m.events if e.start <= day.day <= e.end)
        detail.append('All-day workout schedule; check your studio for class times.')
        event(f'{m.slug}-day-{day.day}', start, start + timedelta(days=1), title, '\n'.join(filter(None, detail)))
    for e in m.events:
        uid = hashlib.sha256(f'{e.name}:{e.start}:{e.end}'.encode()).hexdigest()[:16]
        event(f'{m.slug}-event-{uid}', date(m.year, m.month, e.start), date(m.year, m.month, e.end) + timedelta(days=1), e.name, 'OTF monthly event')
    lines.append('END:VCALENDAR')
    return '\r\n'.join(map(_fold, lines)) + '\r\n'


def compact_html(m, layout):
    if layout not in ('phone', 'social'):
        raise ValueError('Choose phone or social layout.')
    height = 1920 if layout == 'phone' else 1350
    env = Environment(loader=FileSystemLoader(Path(__file__).parent / 'templates'), autoescape=True,
                      undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
    context = build_context(m)
    context['tagline'] = safe_tagline(m.tagline)
    return {'html': env.get_template('compact.html.j2').render(**context,
            font_css=Markup(font_css(allow_fetch=False)), layout=layout, height=height), 'width': 1080, 'height': height}
