"""Read cumulative energy history and handle counter resets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from homeassistant.components.recorder import history, statistics
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util


@dataclass(frozen=True, slots=True)
class EnergyWindow:
    """Measured energy over a half-open time window."""

    kwh: Decimal
    start_reading: Decimal | None
    end_reading: Decimal | None
    cutoff: datetime | None
    coverage_complete: bool
    meter_samples: tuple[tuple[datetime, Decimal], ...] = ()
    source: str = "state_history"


def _state_value(state: State) -> Decimal | None:
    try:
        value = Decimal(state.state)
    except (InvalidOperation, TypeError, ValueError):
        return None
    return value if value.is_finite() and value >= 0 else None


def _cumulative_samples(
    samples: list[tuple[datetime, Decimal]],
) -> list[tuple[datetime, Decimal]]:
    """Turn a resettable cumulative counter into a monotonic energy series."""
    adjusted: list[tuple[datetime, Decimal]] = []
    previous_raw: Decimal | None = None
    cumulative: Decimal | None = None
    for timestamp, raw_value in samples:
        if previous_raw is None or cumulative is None:
            cumulative = raw_value
        else:
            delta = raw_value - previous_raw
            cumulative += delta if delta >= 0 else raw_value
        adjusted.append((timestamp, cumulative))
        previous_raw = raw_value
    return adjusted


def _last_complete_hour(end: datetime) -> datetime:
    """Return the UTC boundary at the end of the last complete hour."""
    timestamp = int(end.timestamp() // 3600) * 3600
    return dt_util.utc_from_timestamp(timestamp)


async def async_read_energy(
    hass: HomeAssistant,
    entity_id: str,
    start: datetime,
    end: datetime,
    *,
    max_boundary_gap: timedelta = timedelta(hours=3),
) -> EnergyWindow:
    """Integrate a cumulative kWh sensor over retained Recorder history.

    The Recorder query includes the state immediately before ``start``. A drop
    in a total-increasing counter is treated as a meter reset; the post-reset
    reading is counted from zero.
    """
    start_utc = dt_util.as_utc(start)
    end_utc = dt_util.as_utc(end)
    if end_utc <= start_utc:
        return EnergyWindow(Decimal("0"), None, None, None, False)
    instance = get_instance(hass)
    rows = await instance.async_add_executor_job(
        history.get_significant_states,
        hass,
        start_utc,
        end_utc,
        [entity_id],
        None,
        True,
        False,
        False,
        False,
        False,
    )
    states = rows.get(entity_id, [])
    parsed: list[tuple[datetime, Decimal]] = []
    for state in states:
        if not isinstance(state, State):
            continue
        reading = _state_value(state)
        if reading is None:
            continue
        timestamp = state.last_updated
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=dt_util.UTC)
        if timestamp <= end_utc:
            parsed.append((dt_util.as_utc(timestamp), reading))

    current_state = hass.states.get(entity_id)
    if current_state is not None:
        reading = _state_value(current_state)
        if reading is not None and current_state.last_updated <= end_utc:
            parsed.append((dt_util.as_utc(current_state.last_updated), reading))
    parsed.sort(key=lambda item: item[0])
    # Recorder can return an identical current state; collapse same-time repeats.
    deduped: list[tuple[datetime, Decimal]] = []
    for timestamp, reading in parsed:
        if deduped and timestamp == deduped[-1][0]:
            deduped[-1] = (timestamp, reading)
        else:
            deduped.append((timestamp, reading))

    before_or_at_start = [(stamp, value) for stamp, value in deduped if stamp <= start_utc]
    end_candidates = [(stamp, value) for stamp, value in deduped if stamp <= end_utc]
    if not before_or_at_start or not end_candidates:
        return await _async_read_hourly_statistics(hass, entity_id, start_utc, end_utc)

    start_stamp, _ = before_or_at_start[-1]
    end_stamp, _ = end_candidates[-1]
    first_index = deduped.index((start_stamp, before_or_at_start[-1][1]))
    raw_samples = [
        (stamp, value)
        for stamp, value in deduped[first_index:]
        if stamp <= end_utc
    ]
    samples = _cumulative_samples(raw_samples)
    start_reading = _interpolated_meter(samples, start_utc)
    end_reading = _interpolated_meter(samples, end_stamp)
    total = (
        max(Decimal("0"), end_reading - start_reading)
        if start_reading is not None and end_reading is not None
        else Decimal("0")
    )
    start_gap = start_utc - start_stamp
    end_gap = end_utc - end_stamp
    sample_gaps = [
        right[0] - left[0]
        for left, right in zip(samples, samples[1:], strict=False)
    ]
    coverage = (
        start_gap <= max_boundary_gap
        and end_gap <= max_boundary_gap
        and all(gap <= max_boundary_gap for gap in sample_gaps)
    )
    state_window = EnergyWindow(
        total,
        start_reading,
        end_reading,
        end_stamp,
        coverage,
        tuple(samples),
    )
    if coverage:
        return state_window
    return await _async_read_hourly_statistics(hass, entity_id, start_utc, end_utc)


async def _async_read_hourly_statistics(
    hass: HomeAssistant,
    entity_id: str,
    start: datetime,
    end: datetime,
) -> EnergyWindow:
    """Fall back to complete hourly cumulative statistics, never a partial hour."""
    cutoff = _last_complete_hour(end)
    if cutoff <= start:
        return EnergyWindow(
            Decimal("0"), None, None, None, False, source="hourly_statistics"
        )

    # Include the bucket ending at start so it can provide the cumulative
    # baseline for the first complete hour in the requested window.
    query_start = start - timedelta(hours=2)
    instance = get_instance(hass)
    try:
        result = await instance.async_add_executor_job(
            statistics.statistics_during_period,
            hass,
            query_start,
            end,
            {entity_id},
            "hour",
            None,
            {"sum"},
        )
    except Exception:  # Recorder state history can exist without long-term statistics.
        return EnergyWindow(
            Decimal("0"), None, None, None, False, source="hourly_statistics"
        )

    return _build_hourly_statistics_window(result.get(entity_id, []), start, cutoff)


def _build_hourly_statistics_window(
    rows: list[dict[str, Any]], start: datetime, cutoff: datetime
) -> EnergyWindow:
    """Build a fully covered energy window from cumulative hourly statistics."""
    raw_samples: list[tuple[datetime, Decimal]] = []
    for row in rows:
        try:
            sample_time = dt_util.utc_from_timestamp(float(row["end"]))
            reading = Decimal(str(row["sum"]))
        except (KeyError, TypeError, ValueError, InvalidOperation):
            continue
        if reading.is_finite() and sample_time <= cutoff:
            raw_samples.append((sample_time, reading))
    raw_samples.sort(key=lambda item: item[0])

    baselines = [item for item in raw_samples if item[0] <= start]
    if not baselines:
        return EnergyWindow(
            Decimal("0"), None, None, None, False, source="hourly_statistics"
        )
    selected = [baselines[-1], *(item for item in raw_samples if start < item[0] <= cutoff)]
    if selected[0][0] != start or selected[-1][0] != cutoff:
        return EnergyWindow(
            Decimal("0"), None, None, cutoff, False, source="hourly_statistics"
        )
    if any(
        (right[0] - left[0]) != timedelta(hours=1)
        for left, right in zip(selected, selected[1:], strict=False)
    ):
        return EnergyWindow(
            Decimal("0"), None, None, cutoff, False, source="hourly_statistics"
        )
    adjusted = _cumulative_samples(selected)

    first_reading = adjusted[0][1]
    last_reading = adjusted[-1][1]
    return EnergyWindow(
        max(Decimal("0"), last_reading - first_reading),
        first_reading,
        last_reading,
        cutoff,
        True,
        tuple(adjusted),
        "hourly_statistics",
    )


def _interpolated_meter(
    samples: list[tuple[datetime, Decimal]], moment: datetime
) -> Decimal | None:
    """Interpolate a cumulative meter at a price-effective instant."""
    if not samples:
        return None
    if moment <= samples[0][0]:
        return samples[0][1]
    if moment >= samples[-1][0]:
        return samples[-1][1]
    for (left_time, left_value), (right_time, right_value) in zip(
        samples, samples[1:], strict=False
    ):
        if left_time <= moment <= right_time:
            span = Decimal(str((right_time - left_time).total_seconds()))
            if span <= 0:
                return right_value
            fraction = Decimal(str((moment - left_time).total_seconds())) / span
            return left_value + (right_value - left_value) * fraction
    return None


meter_at = _interpolated_meter
