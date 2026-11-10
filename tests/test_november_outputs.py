"""The verified November source survives every delivered layout and editor update."""
import json
import re
import runpy
from html.parser import HTMLParser
from pathlib import Path

import pytest

from otfposter.exports import calendar_file, compact_html
from otfposter.models import Month
from otfposter.parse import parse
from otfposter.render import render_html

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://www.reddit.com/r/orangetheory/comments/1xqghtv/november_2026_monthly_post/"
KEY_DATES = {1: "Member Choice", 5: ".25 Mile", 13: "1 Mile",
             17: "200 Meter row", 23: "Strength in Numbers"}


class CalendarText(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.cells = {}
        self.parts = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            self.parts = []

    def handle_data(self, data):
        if self.parts is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.parts is not None:
            text = " ".join(self.parts)
            day = re.match(r"\s*(\d+)\b", text)
            if day:
                self.cells[int(day[1])] = text
            self.parts = None


@pytest.fixture
def november():
    source = (ROOT / "schedules/raw/2026-11.txt").read_text(encoding="utf-8")
    month, _ = parse(source)
    month.source_url = SOURCE_URL
    return month


def assert_calendar(html):
    cells = CalendarText(html).cells
    assert set(cells) == set(range(1, 31))
    for day, title in KEY_DATES.items():
        assert title in cells[day]
    assert "3G" in cells[23]
    assert "Repeat of 11/14" in cells[29]
    for day in (27, 30):
        assert "not a repeat" in cells[day].lower()
        assert "Repeat of" not in cells[day]


@pytest.mark.parametrize("layout", ["full", "phone", "social"])
def test_november_source_details_are_visible_in_every_poster(november, layout):
    before = november.to_dict()
    html = (render_html(november, allow_fetch=False) if layout == "full"
            else compact_html(november, layout)["html"])
    assert_calendar(html)
    assert november.to_dict() == before


def assert_ics(text):
    unfolded = text.replace("\r\n ", "")
    events = {}
    for event in unfolded.split("BEGIN:VEVENT\r\n")[1:]:
        day = re.search(r"DTSTART;VALUE=DATE:202611(\d{2})", event)
        if day:
            events[int(day[1])] = event
    assert set(events) == set(range(1, 31))
    for day, title in KEY_DATES.items():
        assert title in events[day]
    assert "Strength in Numbers (3G)" in events[23]
    assert "Repeat of 11/14" in events[29]
    for day in (27, 30):
        assert "not a repeat" in events[day].lower()
        assert "Repeat of" not in events[day]


def test_november_calendar_export_preserves_decimal_3g_and_explicit_nonrepeats(november):
    assert_ics(calendar_file(november))


def test_browser_update_and_exports_keep_november_details_and_source_url(november):
    bridge = runpy.run_path(str(ROOT / "web/bridge.py"))
    data = november.to_dict()
    data["subtitle"] = "November source regression"
    bridge["regenerate"].__globals__["parse"] = lambda *a, **k: pytest.fail("reparsed")
    result = json.loads(bridge["regenerate"](json.dumps(data)))
    assert result["schedule"] == data
    assert result["schedule"]["source_url"] == SOURCE_URL
    assert not result["errors"]
    assert_calendar(result["html"])
    restored = Month.from_dict(result["schedule"])
    assert restored.by_day()[5].entries[0].title == ".25 Mile"
    assert restored.by_day()[23].three_g
    for day in (27, 30):
        assert restored.by_day()[day].repeat_of is None
        assert "not a repeat" in restored.by_day()[day].note.lower()
    for layout in ("phone", "social"):
        exported = json.loads(bridge["export_schedule"](json.dumps(result["schedule"]), layout))
        assert_calendar(exported["html"])
    assert_ics(json.loads(bridge["export_schedule"](json.dumps(result["schedule"]), "ics"))["text"])
