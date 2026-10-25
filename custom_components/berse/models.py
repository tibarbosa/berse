"""Data models for the normalized ERSE catalog."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


def decimal_value(value: Any) -> Decimal:
    """Read a JSON decimal without introducing binary float noise."""
    return Decimal(str(value))


@dataclass(frozen=True, slots=True)
class Offer:
    """One eligible single-rate electricity price variant."""

    supplier_code: str
    offer_id: str
    supplier_name: str
    offer_name: str
    power_kva: Decimal
    standing_charge: Decimal
    energy_price: Decimal
    valid_from: date | None
    valid_until: date | None
    indexed: bool
    market: str
    terms_url: str | None
    offer_url: str | None
    eligibility: dict[str, str] = field(default_factory=dict)
    mandatory_services_per_year: Decimal = Decimal("0")
    conditional_eligibility: bool = False
    unresolved_costs: bool = False
    source_identity: tuple[str, str, str, str] = ("", "", "", "1")

    commercial_details: dict[str, str] = field(default_factory=dict)
    general_conditions_url: str | None = None
    supplier_logo_url: str | None = None

    @property
    def identity(self) -> str:
        """Stable, display-name-independent identity."""
        return ":".join(self.source_identity)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for Home Assistant storage and entity attributes."""
        data = asdict(self)
        for field_name in (
            "power_kva",
            "standing_charge",
            "energy_price",
            "mandatory_services_per_year",
        ):
            data[field_name] = str(data[field_name])
        for field_name in ("valid_from", "valid_until"):
            data[field_name] = data[field_name].isoformat() if data[field_name] else None
        data["source_identity"] = list(self.source_identity)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Offer:
        """Restore an offer from storage."""
        payload = dict(data)
        for field_name in (
            "power_kva",
            "standing_charge",
            "energy_price",
            "mandatory_services_per_year",
        ):
            payload[field_name] = decimal_value(payload[field_name])
        for field_name in ("valid_from", "valid_until"):
            if payload.get(field_name):
                payload[field_name] = date.fromisoformat(payload[field_name])
        payload["source_identity"] = tuple(payload.get("source_identity", ()))
        return cls(**payload)


@dataclass(slots=True)
class Catalog:
    """Validated source snapshot."""

    offers: list[Offer]
    source_url: str
    fetched_at: str
    content_hash: str
    parser_version: int = 1
    diagnostics: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "offers": [offer.to_dict() for offer in self.offers],
            "source_url": self.source_url,
            "fetched_at": self.fetched_at,
            "content_hash": self.content_hash,
            "parser_version": self.parser_version,
            "diagnostics": self.diagnostics,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Catalog:
        return cls(
            offers=[Offer.from_dict(item) for item in data.get("offers", [])],
            source_url=data["source_url"],
            fetched_at=data["fetched_at"],
            content_hash=data["content_hash"],
            parser_version=data.get("parser_version", 1),
            diagnostics=dict(data.get("diagnostics", {})),
        )
