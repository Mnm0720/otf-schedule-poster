import json
import runpy
from pathlib import Path

import pytest

from otfposter.models import Month
from otfposter.render import render_html

ROOT = Path(__file__).resolve().parents[1]


def old_schedule():
    data = json.loads((ROOT / 'schedules/2026-09.json').read_text(encoding='utf-8'))
    data.pop('additional_info', None)
    data.pop('credits', None)
    return data


def test_old_schedule_gets_default_credits_and_no_empty_additional_info():
    month = Month.from_dict(old_schedule())
    assert month.additional_info == ''
    assert month.credits == ('Image: u/MnM0720\nModsquad: u/lookie4dacookie, '
                             'u/jenniferlynn5454, u/pantherluna, and u/Rizzah319')
    html = render_html(month, allow_fetch=False)
    assert '<section class="poster-extra' not in html
    for user in ['MnM0720','lookie4dacookie','jenniferlynn5454','pantherluna','Rizzah319']:
        assert f'href="https://www.reddit.com/u/{user}/"' in html
        assert f'u/{user}</a>' in html


def test_footer_text_roundtrips_and_renders_after_existing_sections():
    data = old_schedule()
    data.update(additional_info='Bring water.\nDoors open at 6.', credits='Image: u/example\nOur studio team')
    month = Month.from_dict(data)
    again = Month.from_dict(month.to_dict())
    assert again.additional_info == data['additional_info']
    assert again.credits == data['credits']
    html = render_html(again, allow_fetch=False)
    assert 'Bring water.\nDoors open at 6.' in html
    assert html.index('<div class="bottom">') < html.index('<section class="poster-extra') < html.index('<footer class="poster-credits')
    assert 'Our studio team' in html


def test_explicitly_cleared_credits_and_whitespace_info_stay_hidden_after_roundtrip():
    data = old_schedule(); data.update(additional_info=' \n\t', credits='')
    month = Month.from_dict(Month.from_dict(data).to_dict())
    assert month.credits == ''
    html = render_html(month, allow_fetch=False)
    assert '<section class="poster-extra' not in html
    assert '<footer class="poster-credits' not in html


def test_footer_escapes_user_copy_and_only_builds_safe_profile_links():
    data = old_schedule()
    data.update(additional_info='<script>alert(1)</script> & welcome',
                credits='u/example <img src=x onerror=alert(1)> javascript:alert(1)')
    html = render_html(Month.from_dict(data), allow_fetch=False)
    assert '&lt;script&gt;alert(1)&lt;/script&gt; &amp; welcome' in html
    assert '&lt;img src=x onerror=alert(1)&gt;' in html
    assert '<script>' not in html and '<img src=x' not in html
    assert 'href="javascript:' not in html
    assert 'href="https://www.reddit.com/u/example/"' in html


@pytest.mark.parametrize('field', ['additional_info','credits'])
def test_invalid_footer_values_fail_with_a_clear_error(field):
    data = old_schedule(); data[field] = ['not text']
    bridge = runpy.run_path(str(ROOT / 'web/bridge.py'))
    with pytest.raises(ValueError, match='text'):
        bridge['regenerate'](json.dumps(data))


def test_bridge_owns_credit_defaults_and_automatic_key_date_categories():
    bridge = runpy.run_path(str(ROOT / 'web/bridge.py'))
    result = json.loads(bridge['regenerate'](json.dumps(old_schedule())))
    assert result['defaults']['credits'] == result['schedule']['credits']
    assert set(result['keyDateTypes']) == {'Benchmark','Signature','Specialty'}
