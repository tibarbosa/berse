"""VAT-exclusive combined-cost ranking tests."""

from datetime import date
from decimal import Decimal

from custom_components.berse.models import Offer
from custom_components.berse.pricing import base_cost, rank_offers


def offer(
    supplier: str,
    standing: str,
    energy: str,
    *,
    indexed: bool = False,
    conditional: bool = False,
    unresolved_costs: bool = False,
    service_cost: str = "0",
    power: str = "4.6",
) -> Offer:
    return Offer(
        supplier_code=supplier,
        offer_id=supplier,
        supplier_name=supplier,
        offer_name=supplier,
        power_kva=Decimal(power),
        standing_charge=Decimal(standing),
        energy_price=Decimal(energy),
        valid_from=date(2026, 1, 1),
        valid_until=date(2026, 12, 31),
        indexed=indexed,
        market="free",
        terms_url=None,
        offer_url=None,
        mandatory_services_per_year=Decimal(service_cost),
        conditional_eligibility=conditional,
        unresolved_costs=unresolved_costs,
        source_identity=(supplier, supplier, power, "1"),
    )


def test_combined_cost_ranks_tradeoff_over_energy_price() -> None:
    first = offer("A", "0.3500", "0.1600")
    second = offer("B", "0.4200", "0.1580")
    third = offer("C", "0.3000", "0.1750")

    ranked = rank_offers(
        [second, third, first],
        kwh=Decimal("300"),
        days=30,
        current_energy_price=Decimal("0.2"),
        current_standing_charge=Decimal("0.5"),
        power_kva=Decimal("4.6"),
    )

    assert [row.offer.supplier_code for row in ranked] == ["A", "B", "C"]
    assert ranked[0].candidate_cost == Decimal("58.5000")
    assert ranked[1].candidate_cost == Decimal("60.0000")
    assert ranked[2].candidate_cost == Decimal("61.5000")


def test_cost_uses_full_decimal_precision_and_daily_charge() -> None:
    assert base_cost(Decimal("300"), 30, Decimal("0.1711"), Decimal("0.2499")) == Decimal("58.8270")


def test_filters_power_indexation_and_conditional_costs() -> None:
    offers = [
        offer("A", "0.1", "0.1"),
        offer("B", "0.1", "0.1", indexed=True),
        offer("C", "0.1", "0.1", conditional=True),
        offer("D", "0.1", "0.1", power="5.75"),
    ]
    kwargs = {
        "kwh": Decimal("100"),
        "days": 30,
        "current_energy_price": Decimal("0.2"),
        "current_standing_charge": Decimal("0.3"),
        "power_kva": Decimal("4.6"),
    }

    assert [row.offer.supplier_code for row in rank_offers(offers, **kwargs)] == ["A"]
    ranked = rank_offers(
        offers, include_indexed=True, include_conditional=True, **kwargs
    )
    assert {row.offer.supplier_code for row in ranked} == {"A", "B", "C"}


def test_unresolved_or_mandatory_service_costs_never_make_savings_claims() -> None:
    offers = [
        offer("UNKNOWN", "0.1", "0.1", unresolved_costs=True),
        offer("SERVICE", "0.1", "0.1", service_cost="12"),
    ]
    ranked = rank_offers(
        offers,
        kwh=Decimal("100"),
        days=30,
        current_energy_price=Decimal("0.2"),
        current_standing_charge=Decimal("0.3"),
        power_kva=Decimal("4.6"),
        include_conditional=True,
    )
    assert ranked == []
