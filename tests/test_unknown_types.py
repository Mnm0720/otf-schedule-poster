import json
import runpy
from pathlib import Path

from otfposter.models import Month
from otfposter.derive import highlights, build_context
from otfposter.categories import BY_KEY

ROOT = Path(__file__).resolve().parents[1]
bridge = runpy.run_path(str(ROOT / 'web/bridge.py'))


def test_unknown_thread_categories_keep_dates_and_get_distinct_editable_types():
    text = (ROOT / 'schedules/raw/2026-09.txt').read_text(encoding='utf-8')
    text += '\n* Minvdaibands on 9/2, 9/5.\n* New Machine on 9/3.\n'
    result = json.loads(bridge['generate'](text))
    m = Month.from_dict(result['schedule'])
    custom = {c['label']: c for c in result['categories'] if c['key'].startswith('custom_')}
    assert set(custom) == {'Minvdaibands', 'New Machine'}
    assert len({c['color'] for c in custom.values()}) == 2
    for label, days in [('Minvdaibands', [2, 5]), ('New Machine', [3])]:
        key = custom[label]['key']
        assert [d.day for d in m.days if any(e.category == key for e in d.entries)] == days
        assert key not in BY_KEY
        m.category_styles[key] = {'color': '#123456'}
        row = next(r for r in highlights(m) if r['label'] == label)
        assert row['color'] == '#123456'
        assert label in result['html']
    assert 'developer' in result['notes']
    assert 'categories.py' not in result['notes']
    again = json.loads(bridge['regenerate'](json.dumps(m.to_dict())))
    assert again['schedule']['custom_categories'] == m.custom_categories
    assert all(c['color'] == '#123456' for c in build_context(m)['legend'] if c['label'] in custom)


def test_old_unknown_json_is_promoted_and_custom_color_survives_title_edit():
    data = json.loads((ROOT / 'schedules/2026-09.json').read_text())
    data['days'][0]['entries'] = [{'category': 'unknown', 'title': 'New class', 'raw': 'original'}]
    result = json.loads(bridge['regenerate'](json.dumps(data)))
    entry = result['schedule']['days'][0]['entries'][0]
    assert entry['category'].startswith('custom_')
    assert entry['raw'] == 'original'
    assert 'New class' in result['html']

def test_new_saved_schedules_version_the_added_workout_registry():
    data=json.loads((ROOT/'schedules/2026-09.json').read_text())
    assert data.get('schema_version',1)==1
    assert Month.from_dict(data).to_dict()['schema_version']==2
