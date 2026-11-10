import pytest

from otfposter.models import Month
from otfposter.validate import customization_errors


def test_appearance_roundtrips_and_older_months_keep_empty_overrides():
    original = Month(2026, 11)
    assert original.appearance == {}
    original.appearance = {'layout': 'reference', 'density': 'compact', 'calendar_icons': False,
                           'show_marked_dates': True, 'show_workout_guide': True}
    again = Month.from_dict(original.to_dict())
    assert again.appearance == original.appearance
    assert not customization_errors(again)
    assert Month.from_dict({'year': 2025, 'month': 1}).appearance == {}


@pytest.mark.parametrize('appearance', [None, [], {'layout':'evil'}, {'density':'tiny'},
    {'calendar_icons':'false'}, {'show_highlights':1}, {'font':'url(evil)'}, {'surprise':True}])
def test_invalid_appearance_is_rejected(appearance):
    m = Month(2026, 11)
    m.appearance = appearance
    assert any('Appearance' in message for _, message in customization_errors(m))


def test_fresh_generation_applies_only_style_settings_and_restore_keeps_them():
    import json
    import runpy
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    bridge = runpy.run_path(str(root / 'web/bridge.py'))
    source = (root / 'schedules/raw/2026-11.txt').read_text(encoding='utf-8')
    settings = {'appearance': {'layout': 'reference', 'calendar_icons': False},
                'category_styles': {'sig': {'color': '#123456'}}, 'credits': 'Saved attribution'}
    result = json.loads(bridge['generate'](source, None, '', '', json.dumps(settings)))
    m = result['schedule']
    assert m['month'] == 11 and m['appearance'] == settings['appearance']
    assert m['credits'] == 'Saved attribution'
    assert m['days'][22]['three_g']
    restored = json.loads(bridge['restore'](json.dumps(m)))['schedule']
    assert restored == m
    with pytest.raises(ValueError, match='preset'):
        bridge['generate'](source, None, '', '', json.dumps({'days': []}))


@pytest.mark.parametrize('settings', [{'note_style':{'icon':'not_cached'}},
    {'category_styles':{'bogus':{'color':'#123456'}}}])
def test_default_style_validation_errors_are_identifiable_for_safe_generation_recovery(settings):
    import json
    import runpy
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    bridge=runpy.run_path(str(root/'web/bridge.py'))
    with pytest.raises(ValueError,match='Appearance preset:'):
        bridge['generate']((root/'schedules/raw/2026-11.txt').read_text(encoding='utf-8'),None,'','',json.dumps(settings))
