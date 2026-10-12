"""Cumulative-meter history and hourly-statistics tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.berse.consumption import (
    _build_hourly_statistics_window,
    _cumulative_samples,
    _last_complete_hour,
    meter_at,
)


def test_counter_resets_are_counted_from_zero() -> None:
    start = datetime(2026, 10, 12, tzinfo=UTC)
    adjusted = _cumulative_samples(
        [
            (start, Decimal("10")),
            (start + timedelta(hours=1), Decimal("12")),
            (start + timedelta(hours=2), Decimal("0.5")),
            (start + timedelta(hours=3), Decimal("1.5")),
        ]
    )

    assert [value for _, value in adjusted] == [
        Decimal("10"),
        Decimal("12"),
        Decimal("12.5"),
        Decimal("13.5"),
    ]


def test_hourly_statistics_use_only_complete_hourly_coverage() -> None:
    start = datetime(2026, 10, 12, tzinfo=UTC)
    cutoff = start + timedelta(hours=2)
    rows = [
        {"end": (start + timedelta(hours=offset)).timestamp(), "sum": str(total)}
        for offset, total in ((0, 100), (1, 101.5), (2, 104))
    ]

    window = _build_hourly_statistics_window(rows, start, cutoff)

    assert window.coverage_complete
    assert window.source == "hourly_statistics"
    assert window.kwh == Decimal("4")
    assert window.cutoff == cutoff

    incomplete = _build_hourly_statistics_window([rows[0], rows[2]], start, cutoff)
    assert not incomplete.coverage_complete


def test_hourly_cutoff_and_meter_interpolation() -> None:
    start = datetime(2026, 10, 12, tzinfo=UTC)
    assert _last_complete_hour(start + timedelta(hours=2, minutes=39)) == start + timedelta(hours=2)
    assert meter_at(
        [(start, Decimal("0")), (start + timedelta(hours=2), Decimal("3"))],
        start + timedelta(hours=1),
    ) == Decimal("1.5")
