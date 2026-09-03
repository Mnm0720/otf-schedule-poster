"""The real thing: parse the actual r/orangetheory monthly threads.

The four fixtures under schedules/raw/ are genuine posts. They are the
regression suite -- if a change breaks one of these, it breaks the tool.
"""
from pathlib import Path

import pytest

from otfposter import derive, validate
from otfposter.parse import parse
from otfposter.thread import looks_like_thread

RAW = Path(__file__).resolve().parent.parent / "schedules" / "raw"
FIXTURES = ["2025-10", "2026-04", "2026-08", "2026-09"]


def load(slug):
    m, report = parse((RAW / f"{slug}.txt").read_text(encoding="utf-8"))
    return m, report


@pytest.fixture(scope="module", params=FIXTURES)
def any_month(request):
    return load(request.param)[0]


@pytest.fixture(scope="module")
def sept():
    return load("2026-09")[0]


# ------------------------------------------------------------ detection ----
def test_real_posts_are_detected_as_threads():
    for slug in FIXTURES:
        assert looks_like_thread((RAW / f"{slug}.txt").read_text(encoding="utf-8"))


def test_a_plain_day_list_is_not_mistaken_for_a_thread():
    assert not looks_like_thread("September 2026\n9/1 - Standard\n9/2 - Lift More")


# ------------------------------------------------- every fixture parses ----
def test_every_fixture_parses_cleanly():
    for slug in FIXTURES:
        m, report = load(slug)
        assert report.clean, f"{slug}: {report.render()}"
        assert m.slug == slug
        assert len(m.days) == m.length
        assert all(d.entries for d in m.days), f"{slug} has an empty day"


def test_every_fixture_validates(any_month):
    issues = validate.check(any_month)
    assert issues == [], validate.report(issues)


def test_repeat_days_carry_their_source_templates(any_month):
    """The invariant this tool leans on: 45 pairs across four real months."""
    by_day = any_month.by_day()
    for day in any_month.days:
        if not day.repeat_of:
            continue
        here = sorted(e.label for e in day.entries if not e.cat.titled)
        there = sorted(e.label for e in by_day[day.repeat_of].entries
                       if not e.cat.titled)
        assert here == there, f"{any_month.mmdd(day.day)} vs {any_month.mmdd(day.repeat_of)}"


# ------------------------------------------- September, checked in full ----
def test_september_matches_the_hand_built_poster(sept):
    """The original poster was built by hand; this must reproduce it exactly."""
    expected = {
        1: ["Standard"], 2: ["Lift More", "Elevation Gain"], 3: ["Run/Row"],
        4: ["Low Bench"], 5: ["Run/Row", "Incline Bench"], 6: ["Standard"],
        7: ["Lift More"], 8: ["Benchmark: 1000 Meter Row", "Run/Row"],
        9: ["Standard"], 10: ["Switch Template", "Lift More"], 11: ["Standard"],
        12: ["Lift More", "Elevation Gain", "Minibands"],
        13: ["Run/Row", "Low Bench"], 14: ["BOSU"], 15: ["Lift More"],
        16: ["Standard"], 17: ["Lift More", "Elevation Gain"],
        18: ["Signature: OTF Foundations", "Lift More"], 19: ["Run/Row"],
        20: ["Low Bench"], 21: ["Run/Row", "Incline Bench"], 22: ["Standard"],
        23: ["Signature: The Chipper"], 24: ["Lift More"], 25: ["Standard"],
        26: ["Switch Template", "Lift More"], 27: ["Standard"],
        28: ["Lift More", "Elevation Gain", "Minibands"],
        29: ["Run/Row", "Low Bench"], 30: ["BOSU"],
    }
    got = {d.day: [e.label for e in d.entries] for d in sept.days}
    assert got == expected


def test_september_repeat_map(sept):
    expected = {16: 1, 17: 2, 19: 3, 20: 4, 21: 5, 22: 6, 24: 7, 25: 9,
                26: 10, 27: 11, 28: 12, 29: 13, 30: 14}
    assert {d.day: d.repeat_of for d in sept.days if d.repeat_of} == expected


def test_september_theme_is_read_from_the_prose(sept):
    assert sept.theme == "Rhythm & Routine"


def test_september_non_repeats(sept):
    assert derive.non_repeat_days(sept) == [15, 18, 23]


# ------------------------------------------------ per-month specialities ----
def test_august_month_long_event():
    m, _ = load("2026-08")
    assert [(e.name, e.start, e.end) for e in m.events] == [("Marathon Month", 1, 31)]
    assert m.theme == "Balance & Stability"


def test_august_specialties_and_signatures():
    m, _ = load("2026-08")
    by_day = m.by_day()
    assert by_day[1].entries[0].label == "Specialty: Start Line"
    assert by_day[27].entries[0].label == "Specialty: PSL"
    assert by_day[31].entries[0].label == "Specialty: Finish Line"
    # a signature lands on top of that day's existing template
    assert [e.label for e in by_day[7].entries] == [
        "Signature: Catch Me If You Can", "Run/Row"]


def test_august_3g_from_prose():
    """'This is a 3G only template' inside a Key Dates bullet."""
    m, _ = load("2026-08")
    assert [d.day for d in m.days if d.three_g] == [27]


def test_october_3g_from_a_standalone_line():
    """'10/24 and 10/31 are 3G style templates ...'"""
    m, _ = load("2025-10")
    assert [d.day for d in m.days if d.three_g] == [24, 31]


def test_october_multi_day_event_and_two_benchmarks():
    m, _ = load("2025-10")
    assert [(e.name, e.start, e.end) for e in m.events] == [("Hell Week", 24, 31)]
    benches = [md["text"] for md in derive.marked_dates(m)
               if md["category"] == "bench"]
    assert benches == ["10/8 Benchmark: 1000 meter row",
                       "10/20 Benchmark: 200 meter row"]


def test_october_has_no_theme():
    """That post predates the monthly-theme convention."""
    m, _ = load("2025-10")
    assert m.theme == ""


def test_october_loose_cycle_suppresses_non_repeat_labels():
    """Only 7 of 20 window days repeat; labelling the other 13 says nothing."""
    m, _ = load("2025-10")
    assert derive.repeat_coverage(m) < derive.TIGHT_CYCLE
    assert derive.non_repeat_days(m) == []
    assert not any(derive.cell_note(m, d)[0] == "Not a repeat" for d in m.days)


def test_tight_cycle_months_do_label_non_repeats():
    for slug in ("2026-04", "2026-08", "2026-09"):
        m, _ = load(slug)
        assert derive.has_tight_cycle(m), slug
        assert derive.non_repeat_days(m), slug


def test_april_quoted_theme_and_date_range_event():
    m, _ = load("2026-04")
    assert m.theme == "Recovery & Resilience"
    assert [(e.name, e.start, e.end) for e in m.events] == [("Dri Tri", 24, 26)]


def test_parenthetical_hints_are_not_extra_templates():
    """'9/8 (benchmark)' cross-references Key Dates; it must not add a pill."""
    m, _ = load("2026-09")
    labels = [e.label for e in m.by_day()[8].entries]
    assert labels.count("Benchmark: 1000 Meter Row") == 1
    assert len(labels) == 2
