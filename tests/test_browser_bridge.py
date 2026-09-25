"""Exercise the exact Python entry points loaded by the browser."""
import json
import runpy
from pathlib import Path

import pytest

from otfposter.models import Month
from otfposter.parse import parse
from otfposter.render import render_html

ROOT = Path(__file__).resolve().parents[1]


def test_browser_icon_catalog_contains_cached_artwork(bridge):
    from otfposter.assets import ICON_NAMES
    data = Month.load(ROOT / 'schedules/2026-09.json').to_dict()
    result = json.loads(bridge['regenerate'](json.dumps(data)))
    assert {row['key'] for row in result['icons']} == set(ICON_NAMES)
    for row in result['icons']:
        assert '<svg' in row['svg'] and '<path' in row['svg']
        assert row['label']


@pytest.fixture
def bridge():
    return runpy.run_path(str(ROOT / "web" / "bridge.py"))


@pytest.mark.parametrize("slug", ["2025-10", "2026-04", "2026-08", "2026-09"])
def test_unedited_browser_round_trip_matches_cli(bridge, slug):
    text = (ROOT / "schedules" / "raw" / f"{slug}.txt").read_text(encoding="utf-8")
    result = json.loads(bridge["generate"](text))
    month, _ = parse(text)
    assert result["schedule"] == month.to_dict()
    assert result["html"] == render_html(month, allow_fetch=False)
    rerender = json.loads(bridge["regenerate"](json.dumps(result["schedule"])))
    assert rerender["html"] == result["html"]
    assert rerender["defaults"]["notes"]
    assert rerender["categories"]


def test_edited_schedule_renders_without_reparsing_and_preserves_metadata(bridge):
    data = Month.load(ROOT / "schedules" / "2026-09.json").to_dict()
    data.update(theme="Our month", tagline="Our studio", subtitle="Studio schedule",
                notes=["Bring water"],
                footnotes=[{"icon": "groups", "lead": "Heads up", "text": "Book early"}],
                events=[{"name": "Studio week", "start": 1, "end": 7, "kind": "event"}])
    day = data["days"][0]
    day.update(entries=[{"category": "bench", "title": "Studio challenge", "raw": "original"},
                        {"category": "runrow", "title": ""}], three_g=True,
               note="Arrive early")
    # The regeneration path must not depend on the paste parser at all.
    bridge["regenerate"].__globals__["parse"] = lambda *a, **k: pytest.fail("reparsed")
    result = json.loads(bridge["regenerate"](json.dumps(data)))
    assert result["schedule"] == data
    for copy in ["OUR MONTH", "Our studio", "Studio schedule", "Bring water",
                 "Heads up", "Book early", "Studio week", "Studio challenge", "Arrive early"]:
        assert copy in result["html"]
    assert result["html"] == render_html(Month.from_dict(data), allow_fetch=False)


@pytest.mark.parametrize("start,end", [(0, 7), (1, 31), (7, 2), (1.5, 4), ("", 4)])
def test_bad_event_dates_are_rejected_before_render(bridge, start, end):
    data = Month.load(ROOT / "schedules" / "2026-09.json").to_dict()
    data["events"] = [{"name": "Bad event", "start": start, "end": end}]
    with pytest.raises(ValueError, match="Event"):
        bridge["regenerate"](json.dumps(data))


def test_bad_repeat_is_rejected_but_template_mismatch_remains_warning(bridge):
    data = Month.load(ROOT / "schedules" / "2026-09.json").to_dict()
    data["days"][0]["repeat_of"] = 2
    with pytest.raises(ValueError, match="not earlier"):
        bridge["regenerate"](json.dumps(data))
    data["days"][0]["repeat_of"] = None
    data["days"][1]["repeat_of"] = 1
    result = json.loads(bridge["regenerate"](json.dumps(data)))
    assert not result["errors"]
    assert "lists" in result["notes"]


def test_empty_text_raises_friendly_value_error(bridge):
    with pytest.raises(ValueError, match="Paste the monthly thread first"):
        bridge["generate"]("")


def test_whitespace_only_text_raises_friendly_value_error(bridge):
    with pytest.raises(ValueError) as excinfo:
        bridge["generate"]("   \n\t  ")
    msg = str(excinfo.value)
    assert "Paste the monthly thread first" in msg
    assert "Technical detail" not in msg, "no underlying exception, so no technical detail line"


def test_no_schedule_input_raises_didnt_look_like_monthly(bridge):
    # Recognizable month/year, but no dated lines at all.
    text = ("September 2026 Monthly Thread!\n\n"
            "This is just prose with no schedule data at all.\n\n"
            "https://example.com/post")
    with pytest.raises(ValueError) as excinfo:
        bridge["generate"](text)
    msg = str(excinfo.value)
    assert "didn't look like a monthly" in msg
    assert "Technical detail" in msg
    assert "no dated lines found" in msg


def test_unreadable_month_raises_friendly_message_with_technical_detail(bridge):
    # No month/year anywhere: parse() raises a month-detection error.
    text = "Just some random words, no dates, no months."
    with pytest.raises(ValueError) as excinfo:
        bridge["generate"](text)
    msg = str(excinfo.value)
    assert "Couldn't read the month" in msg
    assert "Technical detail" in msg
    assert "could not tell which month" in msg


def test_automatic_copy_tracks_edits_and_custom_copy_is_escaped(bridge):
    data = Month.load(ROOT / "schedules" / "2026-09.json").to_dict()
    data.update(notes=[], footnotes=[])
    data["days"][0]["three_g"] = True
    result = json.loads(bridge["regenerate"](json.dumps(data)))
    assert "9/1" in result["defaults"]["footnotes"][0]["text"]
    assert result["schedule"]["footnotes"] == []
    data["subtitle"] = '<script>alert("x")</script>'
    result = json.loads(bridge["regenerate"](json.dumps(data)))
    assert "<script>" not in result["html"]
    assert "&lt;script&gt;" in result["html"]


def test_import_summary_and_structured_validation_are_separate_and_current(bridge):
    text = ('Welcome to the September 2026 Monthly Thread!\nKey Dates for The Month\n'
            '* Run/Rows on 9/3-9/5, 9/31.\n'
            '* Repeat templates are as follows: 9/1 = 9/2.')
    result = json.loads(bridge['generate'](text))
    assert result['importSummary']['recognizedDays'] == [3, 4, 5]
    assert 4 not in result['importSummary']['inferredDays']
    assert result['errors']
    error = next(issue for issue in result['issues'] if issue['severity'] == 'error')
    assert error['source'] == 'validation'
    assert error['day'] == 1
    assert error['control'] == 'repeat'
    warning = next(issue for issue in result['issues'] if '9/31' in issue['message'])
    assert warning['source'] == 'import'
    assert warning['severity'] == 'warning'
    result['schedule']['days'][0]['repeat_of'] = None
    bridge['regenerate'].__globals__['parse'] = lambda *a, **k: pytest.fail('reparsed')
    corrected = json.loads(bridge['regenerate'](json.dumps(result['schedule'])))
    assert corrected['errors'] == []
    assert corrected['issues'] == []
    assert corrected['parseNotes'] == ''
    assert corrected['importSummary'] is None


def test_restore_reopens_initial_validation_errors_without_reparsing(bridge):
    initial = json.loads(bridge['generate']('September 2026\n9/1 - Standard (repeat of 9/2)\n9/2 - Standard'))
    assert initial['errors']
    bridge['restore'].__globals__['parse'] = lambda *a, **k: pytest.fail('reparsed')
    restored = json.loads(bridge['restore'](json.dumps(initial['schedule'])))
    assert restored['schedule'] == initial['schedule']
    assert restored['html'] == initial['html']
    assert restored['errors'] == initial['errors']
    assert any(issue.get('day') == 1 and issue['severity'] == 'error' for issue in restored['issues'])
    assert restored['importSummary'] is None
    with pytest.raises(ValueError, match='not earlier'):
        bridge['export_schedule'](json.dumps(restored['schedule']), 'ics')


@pytest.mark.parametrize('broken,match', [
    ({'schema_version': 999}, 'schema version'),
    ({'category_styles': {'runrow': {'color': 'red'}}}, 'six-digit'),
    ({'events': [{'name': 'Wrong date', 'start': 31, 'end': 31}]}, 'Event'),
])
def test_restore_still_rejects_unsupported_or_unsafe_render_data(bridge, broken, match):
    data = Month.load(ROOT / 'schedules/2026-09.json').to_dict()
    data.update(broken)
    with pytest.raises(ValueError, match=match):
        bridge['restore'](json.dumps(data))
