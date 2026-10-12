"""Persistent, grouped savings-event generation."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_INITIAL_SUMMARY,
    CONF_MIN_SAVING_EUR,
    CONF_MIN_SAVING_PERCENT,
    CONF_NOTIFY_INDEXED,
    DOMAIN,
    EVENT_CHEAPER_OFFER,
)
from .pricing import RankedOffer, base_cost
from .storage import EntryStorage


def _decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def _saving_percent(saving: Decimal, current_cost: Decimal) -> Decimal:
    """Return a percent value without dividing by a zero-cost reference."""
    return saving / current_cost * Decimal("100") if current_cost > 0 else Decimal("0")


def _meets_thresholds(
    saving: Decimal,
    current_cost: Decimal,
    minimum_eur: Decimal,
    minimum_percent: Decimal,
) -> bool:
    """Apply both configured minimums when both are nonzero."""
    return not (
        (minimum_eur > 0 and saving < minimum_eur)
        or (minimum_percent > 0 and _saving_percent(saving, current_cost) < minimum_percent)
    )


async def async_emit_savings_event(
    hass: HomeAssistant,
    *,
    storage: EntryStorage,
    ranked: list[RankedOffer],
    current_energy_price: Decimal,
    current_standing_charge: Decimal,
    kwh: Decimal,
    days: int,
    options: dict[str, Any],
    fingerprint: str,
    allow_alerts: bool,
) -> None:
    """Compare all eligible offers to the prior successful snapshot."""
    saved = storage.data
    old_fingerprint = saved.get("notification_fingerprint")
    previous = saved.get("notification_offers")
    first_snapshot = previous is None or old_fingerprint != fingerprint
    current_cost = base_cost(kwh, days, current_energy_price, current_standing_charge)
    snapshot = {
        item.offer.identity: {
            "energy_price": str(item.offer.energy_price),
            "standing_charge": str(item.offer.standing_charge),
            "cost": str(item.candidate_cost),
            "current_energy_price": str(current_energy_price),
            "current_standing_charge": str(current_standing_charge),
        }
        for item in ranked
    }
    candidates: list[dict[str, Any]] = []
    initial = bool(options.get(CONF_INITIAL_SUMMARY, False))
    minimum_eur = _decimal(options.get(CONF_MIN_SAVING_EUR, 0))
    minimum_percent = _decimal(options.get(CONF_MIN_SAVING_PERCENT, 0))

    if allow_alerts and not first_snapshot:
        for item in ranked:
            if item.offer.indexed and not options.get(CONF_NOTIFY_INDEXED, False):
                continue
            if item.savings <= 0:
                continue
            prior = previous.get(item.offer.identity) if isinstance(previous, dict) else None
            if prior is None:
                improved = True
            else:
                prior_offer_cost = base_cost(
                    kwh,
                    days,
                    _decimal(prior.get("energy_price")),
                    _decimal(prior.get("standing_charge")),
                )
                prior_current_cost = base_cost(
                    kwh,
                    days,
                    _decimal(prior.get("current_energy_price"), str(current_energy_price)),
                    _decimal(prior.get("current_standing_charge"), str(current_standing_charge)),
                )
                was_saving = prior_current_cost - prior_offer_cost > 0
                improved = prior_offer_cost > item.candidate_cost or not was_saving
            if not improved:
                continue
            saving_pct = _saving_percent(item.savings, current_cost)
            if not _meets_thresholds(
                item.savings, current_cost, minimum_eur, minimum_percent
            ):
                continue
            candidates.append(
                {
                    "identity": item.offer.identity,
                    "supplier_code": item.offer.supplier_code,
                    "supplier_name": item.offer.supplier_name,
                    "offer_id": item.offer.offer_id,
                    "offer_name": item.offer.offer_name,
                    "power_kva": str(item.offer.power_kva),
                    "energy_price_eur_per_kwh_ex_vat": str(item.offer.energy_price),
                    "standing_charge_eur_per_day_ex_vat": str(item.offer.standing_charge),
                    "candidate_base_cost_eur_ex_vat": str(item.candidate_cost),
                    "current_base_cost_eur_ex_vat": str(current_cost),
                    "saving_eur_ex_vat": str(item.savings),
                    "saving_percent": str(saving_pct),
                    "indexed_estimate": item.offer.indexed,
                    "terms_url": item.offer.terms_url,
                }
            )
    elif allow_alerts and first_snapshot and initial:
        candidates = [
            {
                "identity": item.offer.identity,
                "supplier_code": item.offer.supplier_code,
                "supplier_name": item.offer.supplier_name,
                "offer_id": item.offer.offer_id,
                "offer_name": item.offer.offer_name,
                "power_kva": str(item.offer.power_kva),
                "energy_price_eur_per_kwh_ex_vat": str(item.offer.energy_price),
                "standing_charge_eur_per_day_ex_vat": str(item.offer.standing_charge),
                "candidate_base_cost_eur_ex_vat": str(item.candidate_cost),
                "current_base_cost_eur_ex_vat": str(current_cost),
                "saving_eur_ex_vat": str(item.savings),
                "saving_percent": str(_saving_percent(item.savings, current_cost)),
                "indexed_estimate": item.offer.indexed,
                "terms_url": item.offer.terms_url,
            }
            for item in ranked
            if item.savings > 0
            and (not item.offer.indexed or options.get(CONF_NOTIFY_INDEXED, False))
            and _meets_thresholds(
                item.savings, current_cost, minimum_eur, minimum_percent
            )
        ]

    # Persist before firing so a restart cannot replay an already emitted event.
    new_saved = dict(saved)
    new_saved["notification_fingerprint"] = fingerprint
    new_saved["notification_offers"] = snapshot
    await storage.async_save(new_saved)
    if candidates:
        hass.bus.async_fire(
            EVENT_CHEAPER_OFFER,
            {
                "integration": DOMAIN,
                "config_entry_id": storage.entry_id,
                "reference_kwh": str(kwh),
                "reference_days": days,
                "price_basis": "excluding VAT",
                "candidates": candidates,
            },
        )
