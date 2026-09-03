import json
import runpy
from pathlib import Path

import pytest

from otfposter.categories import BY_KEY
from otfposter.derive import build_context, key_dates
from otfposter.models import Month
from otfposter.parse import parse
from otfposter.render import render_html
from otfposter import validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def month():
    return parse((ROOT / 'schedules/raw/2026-09.txt').read_text(encoding='utf-8'))[0]


def test_legend_defaults_to_used_types_and_can_override_without_removing_workouts(month):
    used = {e.cat.label for d in month.days for e in d.entries}
    assert {row['label'] for row in build_context(month)['legend']} == used
    month.category_styles = {'runrow': {'visible': False}, 'spec': {'visible': True}}
    context = build_context(month)
    assert 'Run/Row' not in {r['label'] for r in context['legend']}
    assert 'Specialty' in {r['label'] for r in context['legend']}
    assert any(r['label'] == 'Run/Rows' for r in context['highlights'])
    assert month.days[2].entries[0].category == 'runrow'


def test_type_color_propagates_without_mutating_registry_or_other_months(month):
    original = BY_KEY['bench'].color
    month.category_styles = {'bench': {'color': '#00FF00'}}
    context = build_context(month)
    assert any(p['color'] == '#00FF00' and p['fg'] == '#000000'
               for week in context['weeks'] for cell in week if cell for p in cell['pills'])
    assert next(r for r in context['highlights'] if r['label'] == 'Benchmarks')['color'] == '#00FF00'
    assert next(r for r in context['legend'] if r['label'] == 'Benchmark')['color'] == '#00FF00'
    assert next(r for r in context['key_dates'] if '1000 Meter Row' in r['detail'])['color'] == '#00FF00'
    assert BY_KEY['bench'].color == original
    fresh = Month.load(ROOT / 'schedules/2026-09.json')
    assert '#00FF00' not in render_html(fresh, allow_fetch=False)


def test_custom_key_dates_link_multiple_dates_and_preserve_automatic_rows(month):
    original = key_dates(month)
    month.key_dates = [{'days': [3, 7, 9], 'detail': 'Studio challenge', 'icon': 'flag', 'color': '#123456'}]
    rows = key_dates(month)
    custom = next(r for r in rows if r['detail'] == 'Studio challenge')
    assert custom['heading'] == 'September 3, 7 & 9'
    assert len(rows) == len(original) + 1
    html = render_html(month, allow_fetch=False)
    assert 'Studio challenge' in html and 'color:#123456' in html


def test_key_date_style_override_keeps_workout_text_linked_and_can_hide(month):
    row = next(r for r in key_dates(month) if '1000 Meter Row' in r['detail'])
    month.key_date_overrides = {row['id']: {'icon':'bolt', 'color':'#345678'}}
    entry = next(e for e in month.days[7].entries if e.category == 'bench')
    entry.title = 'Renamed row'
    updated = next(r for r in key_dates(month) if r['id'] == row['id'])
    assert updated['detail'] == 'Benchmark: Renamed row'
    assert (updated['icon'], updated['color']) == ('bolt', '#345678')
    month.key_date_overrides[row['id']]['hidden'] = True
    assert row['id'] not in {r['id'] for r in key_dates(month)}


def test_multiple_named_workouts_on_one_day_each_get_a_linked_key_date(month):
    from otfposter.models import Entry
    month.days[7].entries.append(Entry('sig', 'Second workout'))
    rows = [r for r in key_dates(month) if r['days'] == [8]]
    assert len(rows) == 2
    assert len({r['id'] for r in rows}) == 2


def test_automatic_monthly_notes_keep_dynamic_text_when_styled(month):
    month.footnote_styles = {'three_g': {'icon':'star', 'color':'#654321'}}
    month.note_style = {'icon':'bolt', 'color':'#123456'}
    month.days[2].three_g = True
    context = build_context(month)
    footnote = context['footnotes'][0]
    assert '9/3' in footnote['text']
    assert (footnote['icon'], footnote['color']) == ('star', '#654321')
    html = render_html(month, allow_fetch=False)
    assert 'color:#654321' in html and 'color:#123456' in html


def test_all_types_can_be_hidden_and_settings_roundtrip(month):
    month.category_styles = {key: {'visible':False} for key in BY_KEY}
    month.key_dates = [{'days':[2], 'detail':'Extra', 'icon':'flag', 'color':'#123456'}]
    month.note_style = {'icon':'groups', 'color':'#456789'}
    again = Month.from_dict(month.to_dict())
    assert again.to_dict() == month.to_dict()
    assert build_context(again)['legend'] == []
    assert 'Extra' in render_html(again, allow_fetch=False)


@pytest.mark.parametrize('visible_count', [0, 1, 4, 7, 11, 13])
def test_legend_has_no_empty_layout_columns_when_types_are_toggled(month, visible_count):
    month.category_styles = {key: {'visible': index < visible_count}
                             for index, key in enumerate(BY_KEY)}
    html = render_html(month, allow_fetch=False)
    columns = html.count('<div class="bcol">')
    assert f'grid-template-columns:repeat({columns},1fr)' in html


@pytest.mark.parametrize('field,value', [
    ('category_styles', {'runrow': {'color':'red;display:none'}}),
    ('category_styles', {'typo': {'color':'#123456'}}),
    ('category_styles', {'std': {'visible':'false'}}),
    ('key_dates', [{'days':[0, 31], 'detail':'Bad', 'icon':'flag', 'color':'#123456'}]),
    ('key_dates', [{'days':[], 'detail':'Bad', 'icon':'flag', 'color':'#123456'}]),
    ('key_dates', [{'days':[1.5], 'detail':'Bad', 'icon':'flag', 'color':'#123456'}]),
    ('key_dates', [{'days':[1], 'detail':'Bad', 'icon':'../../bad', 'color':'#123456'}]),
    ('footnote_styles', {'three_g': {'color':'not a color'}}),
    ('note_style', {'icon':'not-cached'}),
])
def test_invalid_customizations_block_browser_render(month, field, value):
    data = month.to_dict(); data[field] = value
    bridge = runpy.run_path(str(ROOT / 'web/bridge.py'))
    with pytest.raises(ValueError):
        bridge['regenerate'](json.dumps(data))


def test_highlights_follow_schedule_edits_instead_of_key_date_additions(month):
    from otfposter.models import Entry
    month.days[0].entries = [Entry('bosu')]
    month.key_dates = [{'days':[4], 'detail':'BOSU reminder', 'icon':'flag', 'color':'#123456'}]
    bosu = next(r for r in build_context(month)['highlights'] if r['label'] == 'BOSU')
    assert bosu['value'] == '9/1, 9/14, 9/30'
