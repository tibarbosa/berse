"""Manual consumption and five-offer comparisons without Recorder history."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_pricing import offer

from custom_components.berse.config_flow import _consumption_errors
from custom_components.berse.coordinator import OfferCoordinator
from custom_components.berse.models import Catalog


@pytest.mark.parametrize("amount", [0, -1, "nan", "inf", None, "bad", 1000001])
def test_reject_invalid_manual_amount(amount):
    assert _consumption_errors(None, {"consumption_mode": "manual", "manual_kwh": amount})


@pytest.mark.parametrize("amount", [0.01, 100, 500, 1000000])
def test_manual_mode_needs_no_sensor(amount):
    assert not _consumption_errors(None, {"consumption_mode": "manual", "manual_kwh": amount})


def test_sensor_mode_still_requires_valid_sensor():
    assert _consumption_errors(None, {"consumption_mode": "sensor", "manual_kwh": 100}) == {
        "energy_entity": "invalid_energy_sensor"
    }


@pytest.mark.parametrize("kwh", [100, 500])
@pytest.mark.parametrize("current_price", ["0.01", "0.4"])
def test_manual_ranking_has_five_offers_without_recorded_consumption(
    monkeypatch, kwh, current_price
):
    import custom_components.berse.coordinator as module

    monkeypatch.setattr(module.dt_util, "now", lambda: datetime(2026, 10, 12, 12, tzinfo=UTC))
    read_energy = AsyncMock(side_effect=AssertionError("Manual mode must not read Recorder"))
    monkeypatch.setattr(module, "async_read_energy", read_energy)
    coordinator = object.__new__(OfferCoordinator)
    coordinator.hass = SimpleNamespace(config=SimpleNamespace(time_zone="Europe/Lisbon"))
    coordinator.entry = SimpleNamespace(
        data={
            "consumption_mode": "manual",
            "manual_kwh": kwh,
            "billing_start": "2026-11-01",
            "billing_days": 30,
            "power_kva": "4.6",
            "energy_price": current_price,
            "standing_charge": "0.3",
        },
        options={},
    )
    coordinator.catalog_service = SimpleNamespace(
        catalog=Catalog(
            offers=[offer(str(i), "0.2", str(Decimal("0.1") + Decimal(i) / 100)) for i in range(8)],
            source_url="https://example.com",
            fetched_at="2026-10-12",
            content_hash="test",
        ),
        last_successful_update="2026-10-12T12:00:00+00:00",
        new_identity_ids=set(),
        error=None,
    )
    coordinator.entry_storage = SimpleNamespace(data={}, async_save=AsyncMock())
    data = asyncio.run(coordinator._async_build_data(False))
    assert data["ranking_status"] == "ready"
    assert len(data["offers"]) == 5
    assert data["reference_kwh"] == str(kwh)
    assert data["reference_days"] == 30
    assert data["reference_consumption_source"] == "manual"
    assert data["energy_used"] is None
    assert data["current_cost"] is None
    assert f"{kwh:.2f} kWh" in data["summary"]
    assert Decimal(data["offers"][0]["candidate_cost"]) == Decimal(kwh) * Decimal("0.1") + 6
    costs = [Decimal(row["candidate_cost"]) for row in data["offers"]]
    assert costs == sorted(costs)
    assert (Decimal(data["offers"][0]["savings"]) > 0) == (current_price == "0.4")
    read_energy.assert_not_awaited()
