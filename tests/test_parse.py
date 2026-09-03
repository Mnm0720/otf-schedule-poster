import pytest

from otfposter.parse import parse


def days(m):
    return {d.day: d for d in m.days}


def test_basic_line_forms():
    text = """
    September 2026
    9/1 - Standard
    9/2: Lift More + Elevation Gain
    09/03 - Run/Row
    Sept 4 - Low Bench
    9/5 = Run/Row & Incline Bench
    """
    m, report = parse(text)
    assert (m.year, m.month) == (2026, 9)
    d = days(m)
    assert [e.category for e in d[1].entries] == ["std"]
    assert [e.category for e in d[2].entries] == ["lift", "elev"]
    assert [e.category for e in d[3].entries] == ["runrow"]
    assert [e.category for e in d[4].entries] == ["lowbench"]
    assert [e.category for e in d[5].entries] == ["runrow", "incline"]
    assert not report.unknown_templates


def test_run_row_slash_is_not_a_separator():
    m, _ = parse("October 2026\n10/1 - Run/Row")
    assert [e.label for e in days(m)[1].entries] == ["Run/Row"]


def test_titled_entries_keep_their_name():
    m, _ = parse("September 2026\n9/8 - Benchmark: 1000 Meter Row + Run/Row")
    entries = days(m)[8].entries
    assert entries[0].category == "bench"
    assert entries[0].title == "1000 Meter Row"
    assert entries[0].label == "Benchmark: 1000 Meter Row"


def test_repeat_and_not_a_repeat():
    text = """September 2026
    9/1 - Standard
    9/15 - Lift More (not a repeat)
    9/16 - Standard (repeat of 9/1)
    """
    m, _ = parse(text)
    d = days(m)
    assert d[16].repeat_of == 1
    assert d[15].repeat_of is None
    assert d[15].note == "Not a repeat"
    # the repeat marker must not leak into the template name
    assert [e.label for e in d[16].entries] == ["Standard"]


def test_bare_repeat_line_inherits_templates():
    m, _ = parse("September 2026\n9/2 - Lift More + BOSU\n9/17 - repeat of 9/2")
    assert [e.category for e in days(m)[17].entries] == ["lift", "bosu"]


def test_date_header_then_indented_templates():
    text = """September 2026
    Tuesday, September 1
      Standard
      Lift More
    """
    m, _ = parse(text)
    assert [e.category for e in days(m)[1].entries] == ["std", "lift"]


def test_month_must_be_determinable():
    with pytest.raises(ValueError, match="which month"):
        parse("1 - Standard")


def test_explicit_month_overrides_missing_header():
    m, _ = parse("1 - Standard\n2 - Lift More", year=2026, month=10)
    assert m.slug == "2026-10"
    assert len(m.days) == 31


def test_unknown_template_is_reported_not_dropped():
    m, report = parse("September 2026\n9/1 - Moon Bounce")
    assert report.unknown_templates
    entry = days(m)[1].entries[0]
    assert entry.category == "unknown"
    assert entry.label == "Moon Bounce"


def test_markdown_bullets_and_emphasis_are_stripped():
    m, _ = parse("September 2026\n* **9/1** - *Standard*")
    assert [e.category for e in days(m)[1].entries] == ["std"]


def test_other_months_dates_are_ignored():
    m, _ = parse("September 2026\n9/1 - Standard\n10/1 - Standard")
    assert days(m)[1].entries
    assert all(d.day <= 30 for d in m.days)


def test_missing_days_are_filled_and_warned():
    m, report = parse("September 2026\n9/1 - Standard")
    assert len(m.days) == 30
    assert any("9/2" in w for w in report.warnings)
