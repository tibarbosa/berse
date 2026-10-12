"""ERSE ZIP parser tests with gas/electric duplicate components."""

import csv
import zipfile
from datetime import datetime, timezone
from io import BytesIO, StringIO

import pytest

from custom_components.barbs_erse.parser import CatalogParseError, parse_catalog


CONDITION_FIELDS = [
    "COM", "COD_Proposta", "NomeProposta", "Fornecimento", "Segmento", "TipoContagem",
    "Data ini", "Data fim", "FiltroPrecosIndex_ELE", "FiltroServicosAdic",
    "CustoServicos_s/IVA (€/ano)", "LinkFichaPadrao", "LinkOfertaCom",
]
PRICE_FIELDS = ["COM", "COD_Proposta", "Pot_Cont", "Contagem", "TF", "TV|TVFV|TVP", "TFGN", "TVGN"]


def csv_bytes(fields: list[str], rows: list[dict[str, str]]) -> bytes:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, delimiter=";", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def archive(
    *,
    condition_rows: list[dict[str, str]] | None = None,
    price_rows: list[dict[str, str]] | None = None,
) -> bytes:
    conditions = [
        {
            "COM": "A", "COD_Proposta": "A1", "NomeProposta": "Exact official offer",
            "Fornecimento": "ELE", "Segmento": "Dom", "TipoContagem": "1",
            "Data ini": "01/01/2026", "Data fim": "31/12/2026",
            "FiltroPrecosIndex_ELE": "N", "FiltroServicosAdic": "N",
            "CustoServicos_s/IVA (€/ano)": "0", "LinkFichaPadrao": "https://example.test/terms",
            "LinkOfertaCom": "",
        },
        {
            "COM": "GAS", "COD_Proposta": "G1", "NomeProposta": "Gas offer",
            "Fornecimento": "GN", "Segmento": "Dom", "TipoContagem": "1",
            "Data ini": "01/01/2026", "Data fim": "31/12/2026",
            "FiltroPrecosIndex_ELE": "N", "FiltroServicosAdic": "N",
            "CustoServicos_s/IVA (€/ano)": "0", "LinkFichaPadrao": "", "LinkOfertaCom": "",
        },
    ]
    prices = [
        {
            "COM": "A", "COD_Proposta": "A1", "Pot_Cont": "4,6", "Contagem": "1",
            "TF": "", "TV|TVFV|TVP": "", "TFGN": "0,5", "TVGN": "0,1",
        },
        {
            "COM": "A", "COD_Proposta": "A1", "Pot_Cont": "4,6", "Contagem": "1",
            "TF": "0,2499", "TV|TVFV|TVP": "0,1711", "TFGN": "", "TVGN": "",
        },
        {
            "COM": "GAS", "COD_Proposta": "G1", "Pot_Cont": "4,6", "Contagem": "1",
            "TF": "", "TV|TVFV|TVP": "", "TFGN": "0,3", "TVGN": "0,08",
        },
    ]
    if condition_rows is not None:
        conditions = condition_rows
    if price_rows is not None:
        prices = price_rows
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive_file:
        archive_file.writestr("csv\\CondComerciais.csv", csv_bytes(CONDITION_FIELDS, conditions))
        archive_file.writestr("csv\\Precos_ELEGN.csv", csv_bytes(PRICE_FIELDS, prices))
    return stream.getvalue()


def test_parser_keeps_electric_component_and_excludes_gas() -> None:
    catalog = parse_catalog(
        archive(),
        "https://example.test/offers.zip",
        datetime(2026, 10, 12, tzinfo=timezone.utc),
    )

    assert len(catalog.offers) == 1
    offer = catalog.offers[0]
    assert offer.offer_name == "Exact official offer"
    assert str(offer.power_kva) == "4.6"
    assert str(offer.standing_charge) == "0.2499"
    assert str(offer.energy_price) == "0.1711"
    assert offer.source_identity == ("A", "A1", "4.6", "1")


def test_parser_rejects_empty_tables_and_conflicting_electric_prices() -> None:
    fetched_at = datetime(2026, 10, 12, tzinfo=timezone.utc)
    with pytest.raises(CatalogParseError, match="empty source table"):
        parse_catalog(archive(price_rows=[]), "https://example.test/offers.zip", fetched_at)
    with pytest.raises(CatalogParseError, match="empty source table"):
        parse_catalog(archive(condition_rows=[]), "https://example.test/offers.zip", fetched_at)

    electric_row = {
        "COM": "A", "COD_Proposta": "A1", "Pot_Cont": "4,6", "Contagem": "1",
        "TF": "0,2499", "TV|TVFV|TVP": "0,1711", "TFGN": "", "TVGN": "",
    }
    conflicting_row = {**electric_row, "TV|TVFV|TVP": "0,1720"}
    with pytest.raises(CatalogParseError, match="No unambiguous"):
        parse_catalog(
            archive(price_rows=[electric_row, conflicting_row]),
            "https://example.test/offers.zip",
            fetched_at,
        )
