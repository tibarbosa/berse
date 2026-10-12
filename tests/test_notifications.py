"""Savings-notification threshold tests."""

from decimal import Decimal

from custom_components.berse.notifications import _meets_thresholds


def test_notification_thresholds_require_both_when_configured() -> None:
    assert _meets_thresholds(
        Decimal("10"), Decimal("100"), Decimal("5"), Decimal("8")
    )
    assert not _meets_thresholds(
        Decimal("4"), Decimal("100"), Decimal("5"), Decimal("1")
    )
    assert not _meets_thresholds(
        Decimal("10"), Decimal("100"), Decimal("5"), Decimal("11")
    )


def test_zero_notification_thresholds_allow_any_positive_saving() -> None:
    assert _meets_thresholds(
        Decimal("0.0001"), Decimal("100"), Decimal("0"), Decimal("0")
    )
