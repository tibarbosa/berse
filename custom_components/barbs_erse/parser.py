"""Parse the ERSE ZIP into a conservative single-rate electricity catalog."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import zipfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from importlib import resources
from typing import Any

from .models import Catalog, Offer

_LOGGER = logging.getLogger(__name__)
PARSER_VERSION = 2
MAX_ZIP_BYTES = 12 * 1024 * 1024
MAX_ENTRY_BYTES = 12 * 1024 * 1024
CONDITION_FILE = "CondComerciais.csv"
PRICE_FILE = "Precos_ELEGN.csv"


class CatalogParseError(ValueError):
    """The downloaded archive cannot be trusted as a catalog."""


def parse_decimal(value: str | None) -> Decimal | None:
    """Parse a decimal comma or dot without treating missing values as zero."""
    if value is None:
        return None
    normalized = value.strip().replace("\u00a0", "")
    if not normalized:
        return None
    normalized = normalized.replace(",", ".")
    try:
        parsed = Decimal(normalized)
        return parsed if parsed.is_finite() else None
    except InvalidOperation:
        return None


def _date(value: str | None) -> date | None:
    if not value or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def _read_csv(archive: zipfile.ZipFile, expected_name: str) -> list[dict[str, str]]:
    candidates = [
        info
        for info in archive.infolist()
        if info.file_size <= MAX_ENTRY_BYTES
        and info.filename.replace("\\", "/").rsplit("/", 1)[-1].casefold()
        == expected_name.casefold()
    ]
    if len(candidates) != 1:
        raise CatalogParseError(f"Expected exactly one {expected_name} file")
    try:
        raw = archive.read(candidates[0])
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        if not reader.fieldnames:
            raise CatalogParseError(f"{expected_name} has no header")
        return [
            {
                str(key).strip(): (value or "").strip()
                for key, value in row.items()
                if key is not None
            }
            for row in reader
        ]
    except (UnicodeDecodeError, csv.Error, zipfile.BadZipFile) as err:
        raise CatalogParseError(f"Could not read {expected_name}: {err}") from err


def _flag(value: str | None) -> bool | None:
    """Interpret only explicit scalar yes/no values, never positional strings."""
    if value is None or not value.strip():
        return None
    normalized = value.strip().casefold()
    if normalized in {"s", "sim", "y", "yes", "true", "1"}:
        return True
    if normalized in {"n", "não", "nao", "no", "false", "0"}:
        return False
    return None


def _name_map() -> dict[str, str]:
    try:
        path = resources.files(__package__).joinpath("supplier_names.json")
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _LOGGER.warning("Supplier-name mapping is unavailable; source codes will be shown")
        return {}


def parse_catalog(payload: bytes, source_url: str, fetched_at: datetime) -> Catalog:
    """Validate and normalize an ERSE ZIP; no caller state changes on failure."""
    if len(payload) > MAX_ZIP_BYTES:
        raise CatalogParseError("ERSE archive exceeds the download size limit")
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except (zipfile.BadZipFile, OSError) as err:
        raise CatalogParseError(f"ERSE response is not a valid ZIP archive: {err}") from err
    infos = archive.infolist()
    if len(infos) > 100 or sum(info.file_size for info in infos) > 24 * 1024 * 1024:
        raise CatalogParseError("ERSE archive has too many or too-large entries")
    if any(info.file_size > MAX_ENTRY_BYTES for info in infos):
        raise CatalogParseError("ERSE archive contains an entry above the size limit")
    bad_member = archive.testzip()
    if bad_member:
        raise CatalogParseError(f"ERSE archive has a corrupt entry: {bad_member}")

    conditions = _read_csv(archive, CONDITION_FILE)
    prices = _read_csv(archive, PRICE_FILE)
    if not conditions or not prices:
        raise CatalogParseError("ERSE archive contains an empty source table")

    condition_by_id: dict[tuple[str, str], dict[str, str]] = {}
    conflicting_condition_ids: set[tuple[str, str]] = set()
    diagnostics: dict[str, int] = {"conditions": len(conditions), "price_rows": len(prices)}
    for row in conditions:
        key = (row.get("COM", "").strip(), row.get("COD_Proposta", "").strip())
        if not all(key):
            diagnostics["invalid_condition_identity"] = (
                diagnostics.get("invalid_condition_identity", 0) + 1
            )
            continue
        if key in conflicting_condition_ids:
            continue
        if key in condition_by_id and condition_by_id[key] != row:
            diagnostics["conflicting_conditions"] = diagnostics.get("conflicting_conditions", 0) + 1
            condition_by_id.pop(key, None)
            conflicting_condition_ids.add(key)
            continue
        condition_by_id[key] = row

    # Group component rows before filtering so a gas row cannot hide an electric row.
    variants: dict[tuple[str, str, str, str], list[dict[str, str]]] = {}
    for row in prices:
        power = parse_decimal(row.get("Pot_Cont"))
        if power is None or power <= 0:
            diagnostics["invalid_power_rows"] = diagnostics.get("invalid_power_rows", 0) + 1
            continue
        identity = (
            row.get("COM", "").strip(),
            row.get("COD_Proposta", "").strip(),
            str(power.normalize()),
            row.get("Contagem", "").strip(),
        )
        variants.setdefault(identity, []).append(row)

    names = _name_map()
    offers: list[Offer] = []
    used_identities: set[str] = set()
    for identity, component_rows in variants.items():
        supplier_code, offer_id, power_raw, counting = identity
        if not supplier_code or not offer_id or counting != "1":
            continue
        condition = condition_by_id.get((supplier_code, offer_id))
        if condition is None:
            diagnostics["orphan_or_ambiguous_price_rows"] = (
                diagnostics.get("orphan_or_ambiguous_price_rows", 0) + 1
            )
            continue
        if condition.get("Fornecimento", "").strip().upper() != "ELE":
            continue
        # Dom is the only segment with an unambiguous residential interpretation.
        if condition.get("Segmento", "").strip().casefold() != "dom":
            continue
        if "1" not in condition.get("TipoContagem", ""):
            continue

        electric_rows = []
        for row in component_rows:
            energy = row.get("TV|TVFV|TVP", "") or row.get("TV", "")
            if row.get("TF", "").strip() and energy.strip():
                electric_rows.append((row.get("TF", ""), energy))
        if not electric_rows:
            continue
        distinct = set(electric_rows)
        if len(distinct) != 1:
            diagnostics["conflicting_electric_variants"] = (
                diagnostics.get("conflicting_electric_variants", 0) + 1
            )
            continue

        power = parse_decimal(power_raw)
        standing = parse_decimal(electric_rows[0][0])
        energy_price = parse_decimal(electric_rows[0][1])
        if (
            power is None
            or standing is None
            or energy_price is None
            or power <= 0
            or standing < 0
            or energy_price < 0
        ):
            diagnostics["missing_or_invalid_prices"] = (
                diagnostics.get("missing_or_invalid_prices", 0) + 1
            )
            continue
        valid_from = _date(condition.get("Data ini"))
        valid_until = _date(condition.get("Data fim"))
        if valid_from is None or valid_until is None:
            diagnostics["missing_validity"] = diagnostics.get("missing_validity", 0) + 1
            continue

        service_cost_value = parse_decimal(condition.get("CustoServicos_s/IVA (€/ano)"))
        service_cost = service_cost_value if service_cost_value is not None else Decimal("0")
        indexed_flag = _flag(condition.get("FiltroPrecosIndex_ELE"))
        indexed = indexed_flag if indexed_flag is not None else bool(
            condition.get("FiltroPrecosIndex_ELE", "").strip()
        )
        # The ERSE table has no general market field. The source documentation
        # identifies TUR as the regulated reference; other source codes remain free market.
        market = "regulated" if supplier_code.upper() == "TUR" else "free"
        eligibility = {
            key: value
            for key in (
                "TipoContagem",
                "ConsIni_ELE",
                "ConsFim_ELE",
                "FiltroContratacao",
                "Filtrofaturacao",
                "FiltroPagamento",
                "FiltroAtendimento",
                "FiltroFidelização",
                "FiltroRenovavel_ELE",
                "FiltroRestrições",
                "FiltroServicosAdic",
                "FiltroTarifaSocial",
                "FiltroReembolsos",
                "FiltroNovosClientes",
                "TxTOferta",
                "TxTERSE",
                "TxTContratação",
                "TxTFatura",
                "TxTPagamento",
                "TxTFidelização",
                "TxTRestricoesAdic",
                "Detalhe restrições",
                "TxTServicoAdic",
            )
            if (value := condition.get(key, "").strip())
        }
        service_flag_value = condition.get("FiltroServicosAdic", "").strip()
        service_flag = _flag(service_flag_value)
        conditional_eligibility = bool(service_flag_value) and service_flag is not False
        normalized_identity = (supplier_code, offer_id, str(power.normalize()), "1")
        identity_key = ":".join(normalized_identity)
        if identity_key in used_identities:
            diagnostics["duplicate_normalized_variants"] = (
                diagnostics.get("duplicate_normalized_variants", 0) + 1
            )
            continue
        used_identities.add(identity_key)
        offers.append(
            Offer(
                supplier_code=supplier_code,
                offer_id=offer_id,
                supplier_name=names.get(supplier_code, supplier_code),
                offer_name=condition.get("NomeProposta", "").strip() or offer_id,
                power_kva=power,
                standing_charge=standing,
                energy_price=energy_price,
                valid_from=valid_from,
                valid_until=valid_until,
                indexed=indexed,
                market=market,
                terms_url=condition.get("LinkFichaPadrao", "").strip() or None,
                offer_url=condition.get("LinkOfertaCom", "").strip() or None,
                eligibility=eligibility,
                mandatory_services_per_year=service_cost,
                conditional_eligibility=conditional_eligibility,
                # ERSE leaves the annual cost blank when the explicit service
                # filter is "N". That means there is no additional service
                # cost, not an unknown amount. A blank cost with "S" or an
                # unrecognized flag remains unresolved and is excluded.
                unresolved_costs=service_cost_value is None and service_flag is not False,
                source_identity=normalized_identity,
            )
        )
    if not offers:
        raise CatalogParseError("No unambiguous single-rate domestic electricity offers were found")
    diagnostics["normalized_offers"] = len(offers)
    return Catalog(
        offers=offers,
        source_url=source_url,
        fetched_at=fetched_at.isoformat(),
        content_hash=hashlib.sha256(payload).hexdigest(),
        parser_version=PARSER_VERSION,
        diagnostics=diagnostics,
    )
