import json
import runpy
from pathlib import Path
from otfposter.models import Month

ROOT=Path(__file__).resolve().parents[1]

def month():
    return Month.load(ROOT/'schedules/2026-09.json')

def test_calendar_dates_escaping_unicode_folding_and_stable_ids():
    from otfposter.exports import calendar_file
    m=month();m.days[-1].entries[0].title='Row, lift; smile 🧡\\\n'+('é'*100)
    first=calendar_file(m);second=calendar_file(m)
    assert first.startswith('BEGIN:VCALENDAR\r\n') and first.endswith('END:VCALENDAR\r\n')
    assert 'DTSTART;VALUE=DATE:20260930' in first
    assert 'DTEND;VALUE=DATE:20261001' in first
    assert 'Row\\, lift\\; smile 🧡\\\\\\n' in first.replace('\r\n ','')
    assert all(len(line.encode('utf-8'))<=75 for line in first.split('\r\n'))
    assert [line for line in first.splitlines() if line.startswith('UID:')]==[line for line in second.splitlines() if line.startswith('UID:')]
    assert first.count('BEGIN:VEVENT')==len(m.days)+len(m.events)

def test_compact_export_keeps_all_dates_custom_colors_and_attribution():
    bridge=runpy.run_path(str(ROOT/'web/bridge.py'))
    m=month();m.category_styles['runrow']={'color':'#123456'}
    for layout,height in [('phone',1920),('social',1350)]:
        result=json.loads(bridge['export_schedule'](json.dumps(m.to_dict()),layout))
        assert result['width']==1080 and result['height']==height
        assert result['html'].count('class="compact-day"')==30
        assert '#123456' in result['html'] and 'u/MnM0720' in result['html']
        assert '1000 Meter Row' in result['html']
        assert '&lt;b&gt;' not in result['html'] and '&amp;mdash;' not in result['html']

def test_shared_tagline_keeps_simple_emphasis_but_cannot_execute_html():
    from otfposter.render import render_html
    m=month();m.tagline='<b>Strong</b><img src=x onerror=alert(1)><script>alert(1)</script>'
    html=render_html(m,allow_fetch=False)
    assert '<b>Strong</b>' in html
    assert '<script>' not in html and '<img src=x' not in html
