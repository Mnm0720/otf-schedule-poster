"""Exercise the exact Python entry points loaded by the browser."""
import json
import runpy
from pathlib import Path

import pytest

from otfposter.models import Month
from otfposter.parse import parse
from otfposter.render import render_html

ROOT = Path(__file__).resolve().parents[1]


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
