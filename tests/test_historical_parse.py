"""Real historical monthly posts exercise the source formats that changed over time."""
import json
from pathlib import Path

import pytest

from otfposter import validate
from otfposter.parse import parse
from otfposter.thread import looks_like_thread

FIXTURES = Path(__file__).resolve().parent / 'fixtures/monthly'


def source(slug):
    return json.loads((FIXTURES / f'{slug}.json').read_text(encoding='utf-8'))['text']


def days_of(month, category):
    return [day.day for day in month.days if any(entry.category == category for entry in day.entries)]


@pytest.mark.parametrize('slug', ['2020-03', '2020-10', '2021-02', '2022-05', '2023-09'])
def test_old_monthly_posts_use_thread_reader_without_prose_as_workouts(slug):
    text = source(slug)
    assert looks_like_thread(text)
    month, report = parse(text)
    assert month.slug == slug
    assert not report.unknown_templates
    assert all(not any(word in entry.title.lower() for word in ('thanks', 'moderator', 'wiki includes'))
               for day in month.days for entry in day.entries)


def test_historical_no_on_category_lists_and_days_suffix_keep_workout_dates():
    month, report = parse(source('2024-01'))
    assert days_of(month, 'runrow') == [6, 9, 17, 25]
    assert not any('Run/Rows' in warning for warning in report.warnings)
    month, report = parse(source('2026-02'))
    assert days_of(month, 'lift') == [5, 11, 15, 20, 26]
    assert not report.unknown_templates


@pytest.mark.parametrize('slug,name,start,end', [
    ('2025-05', 'All Out Mayhem', 17, 23),
    ('2025-08', 'Marathon Month', 1, 31),
    ('2025-12', 'The 12 Days of Fitness', 1, 12),
    ('2022-05', 'Mayhem', 21, 27),
])
def test_historical_event_ranges_and_untyped_known_events_survive(slug, name, start, end):
    month, _ = parse(source(slug))
    assert (name, start, end) in [(event.name, event.start, event.end) for event in month.events]


@pytest.mark.parametrize('slug,name,start,end', [
    ('2024-01', 'Transformation Challenge', 22, 31),
    ('2024-02', 'Transformation Challenge', 1, 29),
    ('2025-06', 'Push 30', 16, 30),
    ('2025-07', 'Push 30', 1, 15),
    ('2026-02', 'Transformation Challenge', 1, 28),
])
def test_cross_month_events_keep_only_the_displayed_month_with_explicit_review(slug, name, start, end):
    month, report = parse(source(slug))
    assert (name, start, end) in [(event.name, event.start, event.end) for event in month.events]
    assert any('outside' in warning.lower() and 'clipped' in warning.lower() for warning in report.warnings)


@pytest.mark.parametrize('slug,day', [('2025-01', 26), ('2025-04', 24), ('2025-05', 26), ('2025-06', 22)])
def test_nonrepeat_prose_is_retained_without_a_false_repeat_pair_warning(slug, day):
    month, report = parse(source(slug))
    assert month.by_day()[day].note == 'Not a repeat'
    assert month.by_day()[day].repeat_of is None
    assert not any('repeat pair' in warning for warning in report.warnings)


def test_december_explicit_absence_of_60_minute_repeats_and_all_3g_dates():
    month, report = parse(source('2025-12'))
    assert not any(day.repeat_of for day in month.days)
    assert [day.day for day in month.days if day.three_g] == [24, 25, 31]
    assert not any('repeat date' in warning.lower() or 'repeat template' in warning.lower()
                   for warning in report.warnings)


def test_prefix_3g_date_lists_and_format_wording():
    month, _ = parse(source('2024-09'))
    assert [day.day for day in month.days if day.three_g] == [2, 10, 19]
    month, _ = parse(source('2024-05'))
    assert month.by_day()[7].three_g


def test_old_benchmarks_are_typed_without_misreading_prose_or_uncertain_equipment():
    month, report = parse(source('2021-02'))
    assert days_of(month, 'bench') == [5, 18]
    assert month.by_day()[5].entries[0].title == '12 Minute Run for Distance'
    assert not days_of(month, 'band'), '"might" is not a confirmed equipment date'
    assert any('Minibands' in warning for warning in report.warnings)
    assert 'possible' in month.by_day()[7].note.lower()
    assert month.by_day()[24].three_g is False


def test_numeric_key_dates_and_calendar_intel_title():
    text = ('September 2025 Calendar Intel\nKey Dates for The Month\n'
            '* 9/3: 2000 Meter Row; benchmark.\n* Run/Rows 9/3, 9/7.\n')
    month, report = parse(text)
    assert month.slug == '2025-09'
    assert days_of(month, 'bench') == [3] and days_of(month, 'runrow') == [3, 7]
    assert report.clean, report.render()


def test_real_upstream_reversed_repeat_remains_an_error_and_is_never_swapped():
    month, report = parse(source('2026-05'))
    assert month.by_day()[12].repeat_of == 29
    assert month.by_day()[29].repeat_of is None
    assert any(severity == 'error' and '5/12 repeats 5/29' in message
               for severity, message in validate.check(month))
    assert not report.unknown_templates, 'An EDIT note must not become a workout category'


def test_ambiguous_old_date_list_has_one_actionable_warning_without_fake_month_16():
    _, report = parse(source('2023-09'))
    assert any('September 16/17' in warning and 'Key Date' in warning for warning in report.warnings)
    assert not any('16/17 is not a valid date' in warning for warning in report.warnings)


def test_ordinal_either_day_schedule_is_not_silently_dropped_or_guessed():
    month, report = parse(source('2020-03'))
    assert any('March 21st and/or 22nd' in warning and 'Key Date' in warning for warning in report.warnings)
    assert all(event.name != 'Dri Tri' for event in month.events)


def test_conditional_repeat_stays_a_review_note_without_becoming_a_fixed_link():
    month, report = parse(source('2023-09'))
    assert month.by_day()[23].repeat_of is None
    assert 'ONLY if necessary' in month.by_day()[23].note
    assert any('conditional' in warning.lower() and '9/23' in warning for warning in report.warnings)
