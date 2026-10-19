"""Measured costs with corrected tariffs and hourly Recorder statistics."""

import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_pricing import offer

from custom_components.berse.consumption import EnergyWindow
from custom_components.berse.coordinator import OfferCoordinator
from custom_components.berse.models import Catalog

START = datetime(2026, 10, 1, tzinfo=UTC)


def price(hours, energy="0.2", standing="0.4", *, seed=False):
    return {
        "effective_at": (START + timedelta(hours=hours)).isoformat(),
        "energy_price": energy,
        "standing_charge": standing,
        "seed": seed,
    }


def coordinator(records):
    instance = object.__new__(OfferCoordinator)
    instance.hass = SimpleNamespace(config=SimpleNamespace(time_zone="UTC"))
    instance.entry_storage = SimpleNamespace(
        data={"price_history": records}, async_save=AsyncMock()
    )
    return instance


def cost(records, *, source="hourly_statistics", mode="recorded"):
    instance = coordinator(records)
    window = EnergyWindow(
        Decimal("72"),
        Decimal("0"),
        Decimal("72"),
        START + timedelta(hours=72),
        True,
        tuple((START + timedelta(hours=i), Decimal(i)) for i in range(73)),
        source,
    )
    return asyncio.run(
        instance._async_current_contract_cost(
            window,
            START,
            START.date(),
            window.cutoff,
            3,
            {"energy_price": "0.2", "standing_charge": "0.4", "cost_price_mode": mode},
        )
    )


def test_hourly_standing_charge_edit_does_not_require_energy_split():
    assert cost([price(-24, seed=True), price(36.5, standing="0.5")]) == Decimal("15.7")


def test_hourly_equivalent_prices_and_initial_seed_do_not_block_cost():
    assert cost(
        [price(12.5, seed=True), price(36.5, energy="0.200000", standing="0.4000")]
    ) == Decimal("15.6")


def test_last_simultaneous_price_snapshot_wins():
    assert cost([price(-24, seed=True), price(36.5, energy="0.3"), price(36.5)]) == Decimal("15.6")


def test_real_within_hour_energy_change_still_requires_precise_history():
    records = [price(-24, seed=True), price(36.5, energy="0.3")]
    assert cost(records) is None
    assert cost(records, source="state_history") == Decimal("19.15")


def test_hour_aligned_energy_change_uses_exact_hourly_totals():
    assert cost([price(-24, seed=True), price(36, energy="0.3")]) == Decimal("19.2")


def test_price_changes_outside_the_window_do_not_block_cost():
    assert cost(
        [
            price(-48, seed=True),
            price(-0.5, energy="0.3"),
            price(72, energy="0.4"),
            price(73.5, energy="0.5"),
        ]
    ) == Decimal("22.8")


@pytest.mark.parametrize("mode", ["recorded", "current"])
def test_screenshot_scenario_exposes_cost_and_keeps_offer_rankings(monkeypatch, mode):
    import custom_components.berse.coordinator as module

    now = START + timedelta(days=18, hours=9)
    monkeypatch.setattr(module.dt_util, "now", lambda: now)
    usage = Decimal("148.37")
    window = EnergyWindow(
        usage,
        Decimal("0"),
        usage,
        now,
        True,
        ((START, Decimal("0")), (now, usage)),
        "hourly_statistics",
    )
    monkeypatch.setattr(module, "async_read_energy", AsyncMock(return_value=window))
    records = [price(0, seed=True), price(12 * 24 + 0.5, "0.1337", "0.4172")]
    instance = coordinator(deepcopy(records))
    instance.entry = SimpleNamespace(
        data={
            "energy_entity": "sensor.imported_energy",
            "consumption_mode": "sensor",
            "billing_start": "2026-10-01",
            "billing_days": 30,
            "power_kva": "5.75",
            "energy_price": "0.1337",
            "standing_charge": "0.4172",
        },
        options={"cost_price_mode": mode},
    )
    instance.catalog_service = SimpleNamespace(
        catalog=Catalog(
            offers=[offer("A", "0.3", "0.1", power="5.75")],
            source_url="https://example.test/catalog.zip",
            fetched_at=now.isoformat(),
            content_hash="test",
        ),
        last_successful_update=now.isoformat(),
        new_identity_ids=set(),
        error=None,
    )
    data = asyncio.run(instance._async_build_data(False))

    assert data["energy_used"] == usage
    assert data["standing_charge_days"] == 18
    assert data["current_cost_price_mode"] == mode
    assert data["current_cost_cutoff"] == now.isoformat()
    assert data["consumption_source"] == "hourly_statistics"
    assert data["ranking_status"] == "ready"
    assert Decimal(data["offers"][0]["current_cost"]) == usage * Decimal("0.1337") + 19 * Decimal(
        "0.4172"
    )
    assert instance.entry_storage.data["price_history"] == records
    if mode == "current":
        assert data["current_cost"] == Decimal("27.346669")
        assert "current contract rates for the whole period" in data["current_cost_note"]
    else:
        assert data["current_cost"] is None
        assert "Current cost pricing" in data["current_cost_note"]


def test_current_prices_apply_the_selected_rates_without_erasing_history():
    records = [price(-24, seed=True), price(36.5, energy="0.3")]
    original = deepcopy(records)
    assert cost(records, mode="current") == Decimal("15.6")
    assert records == original


def test_options_preserve_recorded_default_and_save_explicit_current_mode():
    from custom_components.berse.config_flow import BerseOptionsFlow

    entry = SimpleNamespace(data={"consumption_mode": "manual", "manual_kwh": 100}, options={})

    class CostOptionsFlow(BerseOptionsFlow):
        @property
        def config_entry(self):
            return entry

    flow = CostOptionsFlow()
    flow.hass = SimpleNamespace()
    form = asyncio.run(flow.async_step_init())
    values = form["data_schema"]({"consumption_mode": "manual", "manual_kwh": 100})
    assert values["cost_price_mode"] == "recorded"

    selected = {**values, "cost_price_mode": "current"}
    result = asyncio.run(flow.async_step_init(selected))
    assert result["type"] == "create_entry"
    assert result["data"]["cost_price_mode"] == "current"


def test_cost_mode_does_not_reset_offer_or_notification_baselines():
    config = {"energy_entity": "sensor.energy", "cost_price_mode": "recorded"}
    changed = {**config, "cost_price_mode": "current"}
    assert OfferCoordinator._fingerprint(config) == OfferCoordinator._fingerprint(changed)
    assert OfferCoordinator._eligibility_fingerprint(
        config
    ) == OfferCoordinator._eligibility_fingerprint(changed)
