"""Schedule validation has the same event rules in the CLI and browser."""
from copy import deepcopy

import pytest

from otfposter.models import Day, Entry, Event, Month
from otfposter.render import render_html
from otfposter.validate import check, customization_errors, has_errors


@pytest.mark.parametrize('event', [
    Event('Challenge', 0, 31),
    Event('Challenge', 24, 32),
    Event('Challenge', 31, 24),
    Event('Challenge', 24.5, 31),
    Event('Challenge', 24, '31'),
    Event('Challenge', True, 31),
    Event('Challenge', 24, False),
    Event('', 24, 31),
    Event('   ', 24, 31),
    Event(None, 24, 31),
    Event(42, 24, 31),
])
def test_invalid_events_are_rejected_by_shared_validation_and_rendering(event):
    month = Month(year=2026, month=10, events=[event],
                  days=[Day(d, entries=[Entry('std')]) for d in range(1, 32)])
    before = deepcopy(month.to_dict())
    issues = check(month)
    assert has_errors(issues)
    assert any('Event 1:' in message for _, message in issues)
    assert customization_errors(month)
    with pytest.raises(ValueError, match='Event 1:'):
        render_html(month, allow_fetch=False)
    assert month.to_dict() == before


def test_valid_single_day_and_month_long_events_remain_unchanged():
    month = Month(year=2026, month=11,
                  events=[Event('Challenge', 1, 30), Event('Finish', 30, 30)],
                  days=[Day(d, entries=[Entry('std')]) for d in range(1, 31)])
    before = deepcopy(month.to_dict())
    assert check(month) == []
    assert 'Challenge' in render_html(month, allow_fetch=False)
    assert month.to_dict() == before
