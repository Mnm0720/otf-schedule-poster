"""Events stay visible on their dates across poster layouts and regeneration."""
import json
import re
import runpy
from html.parser import HTMLParser
from pathlib import Path

import pytest

from otfposter.derive import default_footnotes, default_notes
from otfposter.exports import compact_html
from otfposter.models import Entry, Event, Month
from otfposter.parse import parse
from otfposter.render import render_html

ROOT = Path(__file__).resolve().parents[1]


class CalendarText(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.cells = {}
        self.parts = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'td':
            self.parts = []

    def handle_data(self, data):
        if self.parts is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'td' and self.parts is not None:
            text = ' '.join(self.parts)
            day = re.match(r'\s*(\d+)\b', text)
            if day:
                self.cells[int(day[1])] = text
            self.parts = None


@pytest.fixture
def october():
    return parse((ROOT / 'schedules/raw/2026-10.txt').read_text(encoding='utf-8'))[0]


def poster(m, layout):
    return render_html(m, allow_fetch=False) if layout == 'full' else compact_html(m, layout)['html']


@pytest.mark.parametrize('layout', ['full', 'phone', 'social'])
def test_hell_week_is_visible_on_all_eight_dates_without_inferred_standard(october, layout):
    before = october.to_dict()
    cells = CalendarText(poster(october, layout)).cells
    assert set(cells) == set(range(1, 32))
    for day in range(1, 32):
        assert ('Hell Week' in cells[day]) == (24 <= day <= 31)
    assert all('Standard' not in cells[day] for day in range(24, 32))
    assert 'Standard' in cells[2]
    assert '12 Minute Tread for Distance' in cells[15]
    assert 'Repeat of 10/1' in cells[17]
    assert october.to_dict() == before


@pytest.mark.parametrize('layout', ['full', 'phone', 'social'])
def test_overlapping_events_keep_explicit_workouts_notes_repeats_and_3g(october, layout):
    october.events.append(Event('Studio challenge', 25, 25))
    day = october.by_day()[25]
    day.entries = [Entry('std'), Entry('bosu')]
    day.note = 'Bring water'
    day.repeat_of = 2
    day.three_g = True
    cells = CalendarText(poster(october, layout)).cells
    assert all(text in cells[25] for text in ('Hell Week', 'Studio challenge', 'Standard', 'BOSU', 'Bring water', '3G'))
    assert 'Studio challenge' not in cells[24]
    day.note = ''
    assert 'Repeat of 10/2' in CalendarText(poster(october, layout)).cells[25]


@pytest.mark.parametrize('layout', ['full', 'phone', 'social'])
def test_event_names_are_plain_text_in_day_cells(october, layout):
    october.events[0].name = '<img src=x onerror=alert(1)> & Friends'
    html = poster(october, layout)
    assert '<img src=x' not in html
    assert '&lt;img src=x onerror=alert(1)&gt; &amp; Friends' in html
    assert '<img src=x onerror=alert(1)> & Friends' in CalendarText(html).cells[24]


def test_browser_event_edits_and_removal_refresh_day_labels_without_reparsing(october):
    bridge = runpy.run_path(str(ROOT / 'web/bridge.py'))
    bridge['regenerate'].__globals__['parse'] = lambda *a, **k: pytest.fail('reparsed')
    data = Month.from_dict(october.to_dict()).to_dict()
    data['events'][0].update(name='Renamed event', start=25, end=27)
    result = json.loads(bridge['regenerate'](json.dumps(data)))
    cells = CalendarText(result['html']).cells
    assert 'Hell Week' not in result['html']
    assert [d for d, text in cells.items() if 'Renamed event' in text] == [25, 26, 27]
    assert 'Standard' in cells[24]
    data['events'] = []
    result = json.loads(bridge['regenerate'](json.dumps(data)))
    cells = CalendarText(result['html']).cells
    assert all('Standard' in cells[d] for d in range(24, 32))
    assert result['schedule']['days'] == data['days']


def test_strength_tread_guidance_is_independent_of_60_minute_repeat_links(october):
    original = default_notes(october)
    for day in october.days:
        day.repeat_of = None
    assert default_notes(october) == original
    assert any('first 14 days' in note and 'two weeks' in note for note in original)
    assert not any('Only 6 days' in note for note in original)


def test_multiple_benchmarks_never_hide_strength_tread_bonus_guidance(october):
    for day in (5, 6, 7, 8, 9):
        october.by_day()[day].entries.append(Entry('bench', f'Extra benchmark {day}'))
    notes = default_notes(october)
    assert any('29th-31st' in note and 'bonus' in note for note in notes)
    assert all(any(f'Extra benchmark {day}' in note for note in notes) for day in (5, 6, 7, 8, 9))
    assert any('12 Minute Tread for Distance' in note for note in notes)
    assert any('500 Meter Row' in note for note in notes)


def test_3g_footnote_does_not_assume_station_duration(october):
    for day in (26, 31):
        october.by_day()[day].three_g = True
    note = next(note for note in default_footnotes(october) if note['id'] == 'three_g')
    assert all(text in note['text'] for text in ('10/26', '10/31', '3G-style', '2G'))
    assert '14' not in note['text']
    assert 'minutes' not in note['text']


@pytest.mark.parametrize('raw,title', [('', ''), ('Standard', ''), ('(not listed)', 'Studio workout')])
def test_event_keeps_a_sole_explicit_or_titled_standard_entry(october, raw, title):
    october.by_day()[24].entries = [Entry('std', title=title, raw=raw)]
    for layout in ('full', 'phone', 'social'):
        cell = CalendarText(poster(october, layout)).cells[24]
        assert 'Hell Week' in cell
        assert (title or 'Standard') in cell


@pytest.mark.parametrize('year,month,length,span', [
    (2027, 2, 28, 'no 29th-31st bonus templates'),
    (2028, 2, 29, '29th is a bonus template'),
    (2026, 9, 30, '29th-30th are bonus templates'),
    (2026, 10, 31, '29th-31st are bonus templates'),
])
def test_strength_tread_bonus_guidance_matches_month_length(year, month, length, span):
    notes = default_notes(Month(year=year, month=month))
    assert any(f'has {length} days' in note and span in note for note in notes)
