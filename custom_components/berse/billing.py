"""Fixed-length billing cycles based on local civil dates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, slots=True)
class BillingCycle:
    """Half-open billing interval [start, end_exclusive)."""

    start: date
    end_exclusive: date
    index: int

    @property
    def last_included_date(self) -> date:
        return self.end_exclusive - timedelta(days=1)

    @property
    def days(self) -> int:
        return (self.end_exclusive - self.start).days


def cycle_for(anchor: date, duration_days: int, target: date) -> BillingCycle | None:
    """Return the active cycle, or None when the anchor is in the future."""
    if duration_days < 1:
        raise ValueError("Billing period length must be a positive number of days")
    if target < anchor:
        return None
    index = (target - anchor).days // duration_days
    start = anchor + timedelta(days=index * duration_days)
    return BillingCycle(start, start + timedelta(days=duration_days), index)


def completed_standing_charge_days(cycle_start: date, cutoff_local_date: date) -> int:
    """Count complete local civil days accrued at local midnight."""
    return max(0, (cutoff_local_date - cycle_start).days)
