import json
from pathlib import Path

import pytest

from otfposter import derive, validate
from otfposter.models import Month
from otfposter.parse import parse
from otfposter.render import render_html

ROOT = Path(__file__).resolve().parent.parent
SEPT_RAW = ROOT / "schedules" / "raw" / "2026-09.txt"


@pytest.fixture(scope="module")
def sept() -> Month:
    m, _ = parse(SEPT_RAW.read_text(encoding="utf-8"))
    m.theme = "Rhythm & Routine"
    return m


# ------------------------------------------------------------ calendar ----
def test_calendar_grid_starts_on_the_right_weekday(sept):
    grid = derive.calendar_grid(sept)
    # 1 September 2026 is a Tuesday -> two blanks in the Sunday-first row
    assert grid[0][:3] == [None, None, 1]
    assert sum(1 for row in grid for c in row if c is not None) == 30


@pytest.mark.parametrize(
    "year,month,leading_blanks,length",
    [
        (2026, 9, 2, 30),    # Tue
        (2026, 10, 4, 31),   # Thu
        (2026, 11, 0, 30),   # Sun
        (2028, 2, 2, 29),    # leap year
    ],
)
def test_grid_geometry_across_months(year, month, leading_blanks, length):
    m = Month(year=year, month=month)
    grid = derive.calendar_grid(m)
    flat = [c for row in grid for c in row]
    assert flat[:leading_blanks] == [None] * leading_blanks
    assert flat[leading_blanks] == 1
    assert m.length == length
    assert len(flat) % 7 == 0


# ------------------------------------------------------------- derived ----
def test_repeat_window_matches_the_hand_built_poster(sept):
    # The original September poster called out exactly these three days.
    assert derive.non_repeat_days(sept) == [15, 18, 23]
    assert derive.repeat_window_start(sept) == 15


def test_repeat_map_is_complete(sept):
    rows = derive.repeat_map(sept)
    assert {r["day"] for r in rows} == {
        f"9/{d}" for d in (16, 17, 19, 20, 21, 22, 24, 25, 26, 27, 28, 29, 30)
    }


def test_highlights_are_derived_from_the_days(sept):
    hl = {h["label"]: h["value"] for h in derive.highlights(sept)}
    assert hl["Run/Rows"] == "9/3, 9/5, 9/8, 9/13, 9/19, 9/21, 9/29"
    assert hl["BOSU"] == "9/14, 9/30"
    assert hl["Specialties"] == "none scheduled this month"
    assert "Standard" not in hl  # deliberately omitted as noise


def test_marked_dates(sept):
    assert [md["text"] for md in derive.marked_dates(sept)] == [
        "9/8 Benchmark: 1000 Meter Row",
        "9/18 Signature: OTF Foundations",
        "9/23 Signature: The Chipper",
    ]


def test_key_dates_include_the_non_repeat_callout(sept):
    headings = [k["heading"] for k in derive.key_dates(sept)]
    assert headings[-1] == "September 15, 18 & 23"


def test_notes_mention_month_length(sept):
    notes = derive.default_notes(sept)
    assert any("30 days" in n and "31st" in n for n in notes)
    assert any("first 14 days" in n for n in notes)


def test_month_with_no_repeats_degrades_gracefully():
    m, _ = parse("October 2026\n" + "\n".join(f"10/{d} - Standard" for d in range(1, 32)))
    assert derive.repeat_map(m) == []
    assert derive.non_repeat_days(m) == []
    ctx = derive.build_context(m)
    assert ctx["repeat_map"] == []


# ----------------------------------------------------------- validation ----
def test_september_validates_clean(sept):
    assert validate.check(sept) == []


def test_forward_repeat_is_an_error():
    m, _ = parse("September 2026\n" + "\n".join(f"9/{d} - Standard" for d in range(1, 31))
                 + "\n9/2 - Standard (repeat of 9/20)")
    issues = validate.check(m)
    assert validate.has_errors(issues)
    assert any("not earlier" in msg for _, msg in issues)


def test_repeat_that_lost_its_templates_is_warned():
    """A dropped category line shows up as a repeat that no longer matches."""
    text = "September 2026\n" + "\n".join(f"9/{d} - Standard" for d in range(1, 31))
    text = text.replace("9/2 - Standard", "9/2 - BOSU")
    text = text.replace("9/17 - Standard", "9/17 - Standard (repeat of 9/2)")
    m, _ = parse(text)
    issues = validate.check(m)
    assert any("repeats 9/2 but lists Standard vs BOSU" in msg for _, msg in issues)


def test_matching_repeat_is_not_warned():
    text = "September 2026\n" + "\n".join(f"9/{d} - Standard" for d in range(1, 31))
    text = text.replace("9/2 - Standard", "9/2 - BOSU")
    text = text.replace("9/17 - Standard", "9/17 - BOSU (repeat of 9/2)")
    m, _ = parse(text)
    assert not any("repeats 9/2" in msg for _, msg in validate.check(m))


def test_a_signature_does_not_break_repeat_matching():
    """Named workouts sit on top of the day's template, so they don't count."""
    text = "September 2026\n" + "\n".join(f"9/{d} - Standard" for d in range(1, 31))
    text = text.replace("9/2 - Standard", "9/2 - BOSU")
    text = text.replace("9/17 - Standard",
                        "9/17 - Signature: Inferno + BOSU (repeat of 9/2)")
    m, _ = parse(text)
    assert not any("repeats 9/2" in msg for _, msg in validate.check(m))


# --------------------------------------------------------------- render ----
def test_render_html_is_selfcontained_and_has_the_data(sept):
    html = render_html(sept, allow_fetch=False)
    assert "@font-face" in html
    assert "data:font/woff2;base64," in html
    assert "https://fonts.googleapis.com" not in html
    assert "SEPTEMBER 2026" in html
    assert "Benchmark: 1000 Meter Row" in html
    assert "Repeat of 9/1" in html
    # every day number renders
    for d in range(1, 31):
        assert f'<div class="dnum">{d}</div>' in html


def test_font_css_survives_autoescaping(sept):
    """Regression: autoescaped CSS registers zero @font-face rules."""
    html = render_html(sept, allow_fetch=False)
    assert "&#39;" not in html.split("</style>")[0]


# ----------------------------------------------------------- roundtrip ----
def test_schedule_json_roundtrip(sept, tmp_path):
    path = tmp_path / "s.json"
    sept.save(path)
    again = Month.load(path)
    assert again.slug == sept.slug
    assert [d.repeat_of for d in again.days] == [d.repeat_of for d in sept.days]
    assert [e.label for d in again.days for e in d.entries] == \
           [e.label for d in sept.days for e in d.entries]


def test_future_schema_version_is_rejected(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"year": 2026, "month": 9, "schema_version": 99}))
    with pytest.raises(ValueError, match="schema version"):
        Month.load(path)
