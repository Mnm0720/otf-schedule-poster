"""Visual design behavior shared by full and compact poster outputs."""
from copy import deepcopy
from pathlib import Path
import re

import pytest

from otfposter import assets, categories, derive
from otfposter.exports import compact_html
from otfposter.models import Entry
from otfposter.parse import parse
from otfposter.render import render_html

ROOT = Path(__file__).resolve().parents[1]


def test_default_restores_the_requested_classic_poster_appearance(month):
    html = output(month, 'full')
    assert 'data-visual-style="classic"' in html
    assert 'class="corner tl"' in html and 'class="hero-icon dark"' in html
    assert "font-family:'Anton'" in html and 'font-size:72px' in html
    assert 'MARKED DATES' in html
    assert 'Template &amp; Equipment Highlights' in html
    assert 'Workout Types &amp; Monthly Notes' in html
    assert 'class="workout-icon"' not in html
    assert derive.category_foreground(month, 'lift') == '#fff'
    benchmark = next(row for row in derive.key_dates(month)
                     if row['detail'].startswith('Benchmark:'))
    assert (benchmark['icon'], benchmark['color']) == ('local_cafe', '#6A1B9A')


@pytest.fixture
def month():
    return parse((ROOT / 'schedules/raw/2026-11.txt').read_text(encoding='utf-8'))[0]


def output(month, layout):
    return (render_html(month, allow_fetch=False) if layout == 'full'
            else compact_html(month, layout)['html'])


def contrast(first, second):
    def luminance(color):
        if len(color) == 4:
            color = '#' + ''.join(char * 2 for char in color[1:])
        channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4
                  for v in channels]
        return sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))
    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + .05) / (dark + .05)


@pytest.mark.parametrize('key,foreground', [
    ('runrow', '#fff'), ('lift', '#fff'), ('elev', '#fff'), ('switch', '#fff'),
    ('bosu', '#fff'), ('band', '#fff'), ('lowbench', '#fff'), ('incline', '#fff'),
    ('sig', '#5C6470'), ('spec', '#fff'), ('bench', '#fff'),
    ('std', '#5C6470'), ('unknown', '#fff'),
])
def test_builtin_pill_foregrounds_retain_the_original_palette(month, key, foreground):
    assert derive.category_foreground(month, key) == foreground


@pytest.mark.parametrize('color', ['#000000', '#FFFFFF', '#777777', '#F4511E', '#00FF00'])
def test_explicit_custom_pill_colors_keep_the_existing_linear_contrast_rule(month, color):
    month.category_styles['lift'] = {'color': color}
    foreground = derive.category_foreground(month, 'lift')
    assert foreground in ('#000000', '#FFFFFF')
    assert contrast(color, foreground) >= 4.5


def test_classic_default_keeps_original_panels_and_all_custom_copy(month):
    month.notes = ['Custom Strength/Tread reminder']
    month.footnotes = [{'icon': 'star', 'lead': 'Custom monthly note', 'text': 'Keep this copy'}]
    month.additional_info = 'Bring water'
    before = deepcopy(month.to_dict())
    html = output(month, 'full')
    assert 'layout-reference density-comfortable' in html
    assert 'class="corner ' in html and 'class="hero-icon ' in html
    assert 'MARKED DATES' in html
    assert 'data-section="highlights"' in html
    assert 'data-section="workout-guide"' in html
    assert 'data-section="key-dates"' in html
    assert 'data-section="repeat-map"' in html
    for text in ('Custom Strength/Tread reminder', 'Custom monthly note', 'Keep this copy',
                 'Bring water', 'Upper Body', 'Strength in Numbers', 'u/MnM0720'):
        assert text in html
    assert month.to_dict() == before


def test_reference_layout_restores_panels_and_explicit_choices_take_precedence(month):
    month.appearance = {'layout': 'reference'}
    html = output(month, 'full')
    assert 'layout-reference' in html
    assert 'MARKED DATES' in html
    assert 'data-section="highlights"' in html
    assert 'data-section="workout-guide"' in html
    month.appearance.update(show_marked_dates=False, show_highlights=False,
                            show_repeat_map=False, show_workout_guide=False)
    html = output(month, 'full')
    for marker in ('MARKED DATES', 'data-section="highlights"',
                   'data-section="repeat-map"', 'data-section="workout-guide"'):
        assert marker not in html


def test_every_builtin_category_has_a_cached_semantic_icon(month):
    mapping = getattr(categories, 'CATEGORY_ICONS', {})
    assert set(categories.BY_KEY) <= set(mapping)
    assert mapping['bench'] in ('timer', 'military_tech', 'trophy')
    assert mapping['runrow'] != mapping['lift'] != mapping['switch']
    for icon in mapping.values():
        assert icon in assets.ICON_NAMES
        assert (assets.ICON_DIR / f'{icon}.svg').is_file()
    for day, category in zip(month.days, categories.CATEGORIES):
        day.entries = [Entry(category.key)]
    context = derive.build_context(month)
    for cell in (cell for week in context['weeks'] for cell in week if cell):
        assert all(pill.get('icon') in assets.ICON_NAMES for pill in cell['pills'])


@pytest.mark.parametrize('layout', ['full', 'phone', 'social'])
def test_calendar_icons_keep_text_and_can_be_turned_off(month, layout):
    # Icons remain available as an explicit choice; the requested classic
    # default has none on calendar dates.
    assert 'class="workout-icon"' not in output(month, layout)
    month.appearance = {'calendar_icons': True}
    html = output(month, layout)
    calendar = html.split('<tbody>', 1)[1].split('</tbody>', 1)[0]
    pills = re.findall(r'<div class="pill(?: two)?"[^>]*>(.*?)</div>', calendar, re.S)
    assert pills
    assert all('class="workout-icon"' in pill for pill in pills)
    assert all('aria-hidden="true"' in pill for pill in pills)
    assert all(re.sub('<[^>]+>', '', pill).strip() for pill in pills)
    assert 'Strength in Numbers' in html and '.25 Mile' in html
    assert ('class="g3"' if layout == 'full' else 'class="three-g"') in html
    month.appearance = {'calendar_icons': False}
    html = output(month, layout)
    assert 'class="workout-icon"' not in html
    assert 'Strength in Numbers' in html and '.25 Mile' in html


@pytest.mark.parametrize('layout', ['phone', 'social'])
def test_compact_retains_original_font_stack_and_optional_density(month, layout):
    month.appearance = {'density': 'compact'}
    html = output(month, layout)
    assert "font-family:'Inter',Arial,sans-serif" in html
    assert 'density-compact' in html
    assert 'data:font/woff2;base64,' in html


def test_benchmark_key_date_retains_original_artwork(month):
    rows = [row for row in derive.key_dates(month) if row['detail'].startswith('Benchmark:')]
    assert len(rows) == 3
    assert all((row['icon'], row['color']) == ('local_cafe', '#6A1B9A') for row in rows)
