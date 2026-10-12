"""VAT-exclusive cost calculations and offer ranking."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .models import Offer


@dataclass(frozen=True, slots=True)
class RankedOffer:
    offer: Offer
    candidate_cost: Decimal
    current_cost: Decimal
    savings: Decimal


def base_cost(kwh: Decimal, days: int, energy_price: Decimal, standing_charge: Decimal) -> Decimal:
    """Calculate energy plus daily standing charge, excluding VAT."""
    return kwh * energy_price + Decimal(days) * standing_charge


def rank_offers(
    offers: list[Offer],
    *,
    kwh: Decimal,
    days: int,
    current_energy_price: Decimal,
    current_standing_charge: Decimal,
    power_kva: Decimal,
    include_indexed: bool = False,
    include_conditional: bool = False,
    market: str = "all",
) -> list[RankedOffer]:
    """Rank candidates by total comparable base cost, not kWh price."""
    current_cost = base_cost(kwh, days, current_energy_price, current_standing_charge)
    ranked: list[RankedOffer] = []
    for offer in offers:
        if offer.power_kva != power_kva:
            continue
        if offer.indexed and not include_indexed:
            continue
        # These charges are outside the current-contract inputs, so allowing
        # them into a savings comparison would overstate the candidate cost or
        # omit an unknown cost entirely.
        if offer.unresolved_costs or offer.mandatory_services_per_year > 0:
            continue
        if offer.conditional_eligibility and not include_conditional:
            continue
        if market != "all" and offer.market != market:
            continue
        candidate_cost = base_cost(kwh, days, offer.energy_price, offer.standing_charge)
        ranked.append(
            RankedOffer(offer, candidate_cost, current_cost, current_cost - candidate_cost)
        )
    return sorted(
        ranked,
        key=lambda item: (
            item.candidate_cost,
            item.offer.supplier_code,
            item.offer.offer_id,
        ),
    )
