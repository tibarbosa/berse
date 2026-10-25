"""Discover supplier names and cache ERSE logos without sharing user consumption."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlsplit

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SOURCE_USER_AGENT
from .models import Catalog

_LOGGER = logging.getLogger(__name__)
SIMULATOR_URL = "https://simuladorprecos.erse.pt/connectors/simular_eletricidade/"
MAX_METADATA_BYTES = 4 * 1024 * 1024
MAX_LOGO_BYTES = 512 * 1024


class SupplierMetadata:
    """Keep optional display metadata independent of price availability."""

    def __init__(self, hass: HomeAssistant, session: aiohttp.ClientSession) -> None:
        self.hass = hass
        self.session = session
        self.directory = Path(hass.config.path(".storage", "berse_supplier_logos"))
        self.store = Store(hass, 1, f"{DOMAIN}.suppliers")
        self.records: dict[str, dict[str, str]] = {}
        self._last_attempt: datetime | None = None
        self._downloads = asyncio.Semaphore(4)

    async def async_load(self) -> None:
        await self.hass.async_add_executor_job(
            lambda: self.directory.mkdir(parents=True, exist_ok=True)
        )
        saved = await self.store.async_load() or {}
        try:
            self._last_attempt = datetime.fromisoformat(saved["last_attempt"])
        except (KeyError, TypeError, ValueError):
            self._last_attempt = None
        records = saved.get("records", {})
        if isinstance(records, dict):
            self.records = {
                code: record
                for code, record in records.items()
                if isinstance(code, str)
                and isinstance(record, dict)
                and isinstance(record.get("name"), str)
            }

    def apply(self, catalog: Catalog | None) -> None:
        """Enrich display fields while leaving price and identity fields untouched."""
        if catalog is None:
            return
        catalog.offers = [
            replace(
                offer,
                supplier_name=self.records.get(offer.supplier_code, {}).get(
                    "name", offer.supplier_name
                ),
                supplier_logo_url=self.records.get(offer.supplier_code, {}).get(
                    "local_url", offer.supplier_logo_url
                ),
            )
            for offer in catalog.offers
        ]

    async def _payload(self, power_index: int | None = None) -> dict:
        # This is a fixed fictional profile. No integration options, household
        # consumption, current contract rates or account details are submitted.
        data = {
            "idioma": "EN",
            "caseType": "0",
            "socialOffer": "1",
            "filtro_IndexacaoSpot": "1",
            "filtro_ServicosAdicionais": "0",
            "filtro_SemRestricoesAdicionais": "0",
            "filtro_SemPrecosIndexados": "0",
            "filtro_SemReembolsos": "0",
            "filtro_energia100Renovavel": "0",
            "filtro_Fidelizacao": "0",
            "filtro_FamiliasNumerosas": "0",
            "filtro_NovosClientes": "1",
            "pageStartIndex": "0",
            "pageStep": "1000",
            "filtro_comercializadores": "",
            "filtro_contratacao": "1",
            "filtro_faturacao": "1",
            "filtro_pagamento": "1",
            "filtro_TipoOfertaELE": "1",
            "filtro_TipoOfertaGas": "1",
            "filtro_gas100Renovavel": "0",
        }
        if power_index is not None:
            data.update(
                {
                    "caseType": "3",
                    "electSupply": str(power_index),
                    "cycle": "1",
                    "electCalendar": "2",
                    "electPonta": "3000",
                    "showElectPrice": "false",
                }
            )
        async with self.session.post(
            SIMULATOR_URL,
            data=data,
            headers={"User-Agent": SOURCE_USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=20),
            allow_redirects=False,
        ) as response:
            if response.status != 200:
                raise ValueError(f"Supplier metadata HTTP status {response.status}")
            chunks = []
            size = 0
            async for chunk in response.content.iter_chunked(64 * 1024):
                size += len(chunk)
                if size > MAX_METADATA_BYTES:
                    raise ValueError("Supplier metadata exceeds the size limit")
                chunks.append(chunk)
        payload = json.loads(b"".join(chunks))
        if not isinstance(payload, dict) or payload.get("status") != "OK":
            raise ValueError("Invalid supplier metadata response")
        return payload

    async def _logo(self, code: str, name: str, source: str, now: datetime) -> None:
        previous = self.records.get(code, {})
        record = {**previous, "name": name}
        self.records[code] = record
        try:
            parts = urlsplit(source)
            if (
                parts.scheme != "https"
                or parts.hostname != "simuladorprecos.erse.pt"
                or not parts.path.startswith("/content/logos/")
                or parts.username
                or parts.password
                or parts.port not in (None, 443)
            ):
                return
            checked = datetime.fromisoformat(
                previous.get("checked_at", "2000-01-01T00:00:00+00:00")
            )
            if previous.get("source_url") == source and now - checked < timedelta(days=7):
                local = previous.get("local_url", "").rsplit("/", 1)[-1]
                if local and await self.hass.async_add_executor_job(
                    (self.directory / local).is_file
                ):
                    return
            async with (
                self._downloads,
                self.session.get(
                    quote(source, safe=":/%"),
                    timeout=aiohttp.ClientTimeout(total=10),
                    allow_redirects=False,
                ) as response,
            ):
                if response.status != 200:
                    raise ValueError(f"Logo HTTP status {response.status}")
                chunks = []
                size = 0
                async for chunk in response.content.iter_chunked(16 * 1024):
                    size += len(chunk)
                    if size > MAX_LOGO_BYTES:
                        raise ValueError("Supplier logo exceeds the size limit")
                    chunks.append(chunk)
            image = b"".join(chunks)
            extension = (
                "png"
                if image.startswith(b"\x89PNG\r\n\x1a\n")
                else ("jpg" if image.startswith(b"\xff\xd8\xff") else None)
            )
            if extension is None:
                raise ValueError("Unsupported supplier logo format")
            filename = f"{hashlib.sha256(image).hexdigest()}.{extension}"
            await self.hass.async_add_executor_job((self.directory / filename).write_bytes, image)
            record.update(
                {
                    "source_url": source,
                    "local_url": f"/berse/supplier-cache/{filename}",
                    "checked_at": now.isoformat(),
                }
            )
        except (aiohttp.ClientError, TimeoutError, ValueError, OSError) as err:
            _LOGGER.debug("Keeping previous logo for supplier %s: %s", code, err)

    async def async_refresh(self, catalog: Catalog) -> None:
        """Discover daily, retain saved values on failure, and refresh images weekly."""
        now = dt_util.utcnow()
        if self._last_attempt and now - self._last_attempt < timedelta(hours=20):
            self.apply(catalog)
            return
        self._last_attempt = now
        by_offer: dict[str, set[str]] = {}
        supplier_codes = {offer.supplier_code for offer in catalog.offers}
        for offer in catalog.offers:
            by_offer.setdefault(offer.offer_id, set()).add(offer.supplier_code)
        discovered: dict[str, tuple[str, str]] = {}

        def collect(payload: dict) -> None:
            names = {
                item["code"]: item["name"]
                for item in payload.get("Comercializadores", [])
                if isinstance(item, dict)
                and isinstance(item.get("code"), str)
                and isinstance(item.get("name"), str)
            }
            for code, name in names.items():
                if code in supplier_codes and name.strip():
                    self.records[code] = {**self.records.get(code, {}), "name": name.strip()}
            for result in payload.get("Resultados", []):
                for offer in result.get("Oferta", []):
                    candidates = by_offer.get(offer.get("CodOferta"), set())
                    code = next(
                        (
                            item
                            for item in candidates
                            if names.get(item) == offer.get("Comercializador")
                        ),
                        next(iter(candidates)) if len(candidates) == 1 else None,
                    )
                    name = names.get(code) or offer.get("Comercializador")
                    logo = offer.get("Logotipo")
                    if code and isinstance(name, str) and name.strip() and isinstance(logo, str):
                        discovered[code] = (name.strip(), logo)

        try:
            collect(await self._payload())
            # For suppliers absent from the default profile, try the catalog's
            # published powers, with the same fictional 3000 kWh annual usage.
            powers = [
                "1.15",
                "2.3",
                "3.45",
                "4.6",
                "5.75",
                "6.9",
                "10.35",
                "13.8",
                "17.25",
                "20.7",
                "27.6",
                "34.5",
                "41.4",
            ]
            missing = {offer.supplier_code for offer in catalog.offers} - discovered.keys()
            profiles = []
            for code in sorted(missing):
                power = next(
                    str(offer.power_kva.normalize())
                    for offer in catalog.offers
                    if offer.supplier_code == code
                )
                if power in powers and powers.index(power) not in profiles:
                    profiles.append(powers.index(power))
            for power_index in profiles[:3]:
                try:
                    collect(await self._payload(power_index))
                except (
                    aiohttp.ClientError,
                    TimeoutError,
                    ValueError,
                    TypeError,
                    KeyError,
                    AttributeError,
                ):
                    _LOGGER.debug("Additional supplier profile is unavailable")
            await asyncio.gather(
                *[
                    self._logo(code, name, source, now)
                    for code, (name, source) in list(discovered.items())[:64]
                ]
            )
            await self.store.async_save({"records": self.records, "last_attempt": now.isoformat()})
        except (
            aiohttp.ClientError,
            TimeoutError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
        ) as err:
            _LOGGER.debug("Keeping cached supplier metadata: %s", err)
        self.apply(catalog)
