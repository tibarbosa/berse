"""Billing cycle boundary tests."""

from datetime import date

import pytest

from custom_components.barbs_erse.billing import cycle_for


def test_cycles_are_fixed_length_across_months() -> None:
    anchor = date(2026, 10, 8)
    first = cycle_for(anchor, 30, date(2026, 10, 8))
    second = cycle_for(anchor, 30, date(2026, 11, 7))
    third = cycle_for(anchor, 30, date(2026, 12, 7))

    assert first is not None
    assert (first.start, first.last_included_date) == (date(2026, 10, 8), date(2026, 11, 6))
    assert second is not None
    assert (second.start, second.last_included_date) == (date(2026, 11, 7), date(2026, 12, 6))
    assert third is not None
    assert (third.start, third.last_included_date) == (date(2026, 12, 7), date(2027, 1, 5))


def test_cycle_handles_leap_day_and_future_anchor() -> None:
    leap = cycle_for(date(2024, 2, 20), 10, date(2024, 2, 29))
    future = cycle_for(date(2026, 11, 1), 30, date(2026, 10, 31))

    assert leap is not None
    assert leap.last_included_date == date(2024, 2, 29)
    assert future is None


def test_cycle_length_uses_local_calendar_dates_across_dst_boundary() -> None:
    cycle = cycle_for(date(2026, 3, 20), 10, date(2026, 3, 29))

    assert cycle is not None
    assert cycle.start == date(2026, 3, 20)
    assert cycle.days == 10
    assert cycle.last_included_date == date(2026, 3, 29)


def test_cycle_rejects_nonpositive_duration() -> None:
    with pytest.raises(ValueError):
        cycle_for(date(2026, 1, 1), 0, date(2026, 1, 1))
