"""Shared catalog updates and per-installation comparison data."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .billing import completed_standing_charge_days, cycle_for
from .const import (
    CONF_ALLOW_CONDITIONAL,
    CONF_BILLING_DAYS,
    CONF_BILLING_START,
    CONF_ENERGY_ENTITY,
    CONF_ENERGY_PRICE,
    CONF_INCLUDE_INDEXED,
    CONF_MARKET,
    CONF_POWER,
    CONF_STANDING_CHARGE,
    DOMAIN,
    MARKET_ALL,
    MAX_OFFERS,
    UPDATE_INTERVAL,
)
from .consumption import EnergyWindow, async_read_energy, meter_at
from .erse_client import ErseClient, ErseClientError
from .models import Catalog, Offer
from .notifications import async_emit_savings_event
from .parser import PARSER_VERSION
from .pricing import RankedOffer, rank_offers
from .storage import CatalogStorage, EntryStorage

_LOGGER = logging.getLogger(__name__)


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


class CatalogService:
    """One locked catalog download/snapshot service shared by entries."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.storage = CatalogStorage(hass)
        self.catalog: Catalog | None = None
        self.etag: str | None = None
        self.etag_url: str | None = None
        self.last_successful_update: str | None = None
        self.new_identity_ids: set[str] = set()
        self.error: str | None = None
        self._lock = asyncio.Lock()
        self._last_attempt_monotonic: float | None = None
        self._loaded = False
        self._client = ErseClient(async_get_clientsession(hass))

    async def async_load(self) -> None:
        if self._loaded:
            return
        self.catalog = await self.storage.async_load()
        saved = self.storage.data
        self.etag = saved.get("etag")
        self.etag_url = saved.get("etag_url")
        self.last_successful_update = saved.get("last_successful_update")
        self.new_identity_ids = set(saved.get("new_identity_ids", []))
        self._loaded = True

    async def async_refresh(self, *, force: bool = False) -> bool | None:
        """Fetch and validate once; return None when a recent attempt is reused."""
        await self.async_load()
        async with self._lock:
            now = dt_util.now()
            loop = asyncio.get_running_loop()
            parser_upgrade = (
                self.catalog is not None
                and self.catalog.parser_version != PARSER_VERSION
            )
            if (
                not parser_upgrade
                and self._last_attempt_monotonic is not None
                and loop.time() - self._last_attempt_monotonic < 15
            ):
                return None
            if (
                not parser_upgrade
                and not force
                and self._last_attempt_monotonic is not None
                and loop.time() - self._last_attempt_monotonic < 3600
            ):
                return None
            if not force and not parser_upgrade and self.last_successful_update:
                try:
                    previous_success = datetime.fromisoformat(self.last_successful_update)
                    if (
                        dt_util.as_local(now) - dt_util.as_local(previous_success)
                        < timedelta(hours=20)
                    ):
                        return None
                except ValueError:
                    pass
            self._last_attempt_monotonic = loop.time()
            try:
                result = await self._client.async_fetch(
                    None if parser_upgrade else self.etag,
                    None if parser_upgrade else self.etag_url,
                )
                timestamp = dt_util.now().isoformat()
                if result.not_modified:
                    if self.catalog is None:
                        raise ErseClientError("ERSE returned not-modified without a saved catalog")
                    self.new_identity_ids = set()
                    await self.storage.async_mark_not_modified(timestamp)
                    self.last_successful_update = timestamp
                    self.error = None
                    return True
                catalog = result.catalog
                assert isinstance(catalog, Catalog)
                current_ids = sorted(offer.identity for offer in catalog.offers)
                previous_ids = list(self.storage.data.get("current_ids", []))
                had_previous = bool(self.storage.data.get("catalog"))
                new_ids = set(current_ids).difference(previous_ids) if had_previous else set()
                await self.storage.async_save_catalog(
                    catalog,
                    previous_ids=previous_ids,
                    current_ids=current_ids,
                    etag=result.etag,
                    etag_url=result.source_url,
                    last_successful_update=timestamp,
                    new_identity_ids=sorted(new_ids),
                )
                self.catalog = catalog
                self.etag = result.etag
                self.etag_url = result.source_url
                self.new_identity_ids = new_ids
                self.last_successful_update = timestamp
                self.error = None
                return True
            except (ErseClientError, OSError) as err:
                self.error = str(err)
                _LOGGER.warning(
                    "Could not refresh ERSE offers; retaining the last valid catalog: %s",
                    err,
                )
                return False


class OfferCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Compute billing, ranking and per-entry additions."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        catalog_service: CatalogService,
        entry_storage: EntryStorage,
    ) -> None:
        self.entry = entry
        self.catalog_service = catalog_service
        self.entry_storage = entry_storage
        self._force_refresh = False
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=UPDATE_INTERVAL,
        )

    async def async_force_refresh(self) -> None:
        self._force_refresh = True
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        force_refresh = self._force_refresh
        self._force_refresh = False
        await self.catalog_service.async_refresh(force=force_refresh)
        last_success = self.catalog_service.last_successful_update
        catalog_refresh_observed = bool(
            last_success
            and self.entry_storage.data.get("last_seen_catalog_success") != last_success
        )
        return await self._async_build_data(catalog_refresh_observed)

    def _current_config(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    async def _async_build_data(self, catalog_refresh_observed: bool) -> dict[str, Any]:
        config = self._current_config()
        now = dt_util.now()
        today = dt_util.as_local(now).date()
        catalog = self.catalog_service.catalog
        if catalog is None:
            return {
                "status": "unavailable",
                "summary": "No validated ERSE catalog is available.",
                "last_successful_update": self.catalog_service.last_successful_update,
                "new_offer_count": int(self.entry_storage.data.get("new_offer_count", 0)),
                "offers": [],
                "energy_used": None,
                "current_cost": None,
                "potential_savings": None,
                "reference_kwh": None,
                "reference_days": None,
                "power_kva": config[CONF_POWER],
                "last_error": self.catalog_service.error,
                "catalog_hash": None,
            }

        anchor = date.fromisoformat(str(config[CONF_BILLING_START])[:10])
        duration_days = int(config[CONF_BILLING_DAYS])
        cycle = cycle_for(anchor, duration_days, today)
        offer_list = [
            offer for offer in catalog.offers if self._offer_is_eligible(offer, config, today)
        ]
        fingerprint = self._fingerprint(config)
        prior_fingerprint = self.entry_storage.data.get("config_fingerprint")
        config_changed = prior_fingerprint != fingerprint
        initial_config = prior_fingerprint is None
        eligibility_fingerprint = self._eligibility_fingerprint(config)
        prior_eligibility_fingerprint = self.entry_storage.data.get("eligibility_fingerprint")
        eligibility_changed = prior_eligibility_fingerprint != eligibility_fingerprint
        new_count = (
            0
            if eligibility_changed
            else int(self.entry_storage.data.get("new_offer_count", 0))
        )
        ignored_new_ids = (
            set(self.catalog_service.new_identity_ids)
            if eligibility_changed
            else set(self.entry_storage.data.get("ignored_new_identity_ids", []))
        )
        if eligibility_changed:
            new_count = 0
        elif catalog_refresh_observed:
            ignored_new_ids = set()
            new_count = sum(
                offer.identity in self.catalog_service.new_identity_ids
                for offer in offer_list
                if offer.power_kva == _decimal(config[CONF_POWER])
            )
        elif self.catalog_service.new_identity_ids:
            visible_new_ids = self.catalog_service.new_identity_ids - ignored_new_ids
            new_count = sum(
                offer.identity in visible_new_ids
                for offer in offer_list
                if offer.power_kva == _decimal(config[CONF_POWER])
            )

        if cycle is None:
            result = self._empty_result(
                "billing_not_started",
                "Billing has not started.",
                config,
                new_count,
                catalog,
            )
            result["cycle_start"] = anchor.isoformat()
            result["cycle_end"] = None
            await self._persist_entry_snapshot(
                fingerprint,
                eligibility_fingerprint,
                new_count,
                config_changed,
                ignored_new_ids,
                catalog_refresh_observed,
            )
            return result

        start_local = self._local_midnight(cycle.start)
        current_window = await async_read_energy(
            self.hass, config[CONF_ENERGY_ENTITY], start_local, now
        )
        current_cost: Decimal | None = None
        cutoff_local: datetime | None = None
        current_days = 0
        current_cost_note = None
        if current_window.coverage_complete:
            cutoff_local = (
                dt_util.as_local(current_window.cutoff)
                if current_window.cutoff
                else None
            )
            if cutoff_local:
                current_days = completed_standing_charge_days(cycle.start, cutoff_local.date())
                current_cost = await self._async_current_contract_cost(
                    current_window,
                    start_local,
                    cycle.start,
                    cutoff_local,
                    current_days,
                    config,
                )
                if current_cost is None and current_window.source == "hourly_statistics":
                    current_cost_note = (
                        "Hourly statistics cannot split usage around a within-hour price change."
                    )
        else:
            current_cost_note = (
                "Complete consumption history is not available for this billing cycle."
            )

        reference_window: EnergyWindow | None = None
        reference_days = 0
        reference_label = ""
        if cycle.index > 0:
            previous_start = self._local_midnight(cycle.start - timedelta(days=duration_days))
            previous_end = start_local
            previous_window = await async_read_energy(
                self.hass, config[CONF_ENERGY_ENTITY], previous_start, previous_end
            )
            if previous_window.coverage_complete:
                reference_window = previous_window
                reference_days = duration_days
                reference_label = "Last complete period"
        if reference_window is None and current_window.coverage_complete:
            elapsed_days = max(1, (today - cycle.start).days + 1)
            reference_window = current_window
            reference_days = min(duration_days, elapsed_days)
            reference_label = "Partial period"

        if reference_window is None or reference_window.kwh <= 0 or reference_days <= 0:
            ranking_status = "insufficient_consumption"
            summary = "Not enough consumption data for a comparable ranking."
            ranked: list[RankedOffer] = []
            reference_kwh: Decimal | None = None
        else:
            ranking_status = "ready"
            summary = f"{reference_label}: {reference_window.kwh} kWh over {reference_days} days."
            reference_kwh = reference_window.kwh
            ranked = rank_offers(
                offer_list,
                kwh=reference_window.kwh,
                days=reference_days,
                current_energy_price=_decimal(config[CONF_ENERGY_PRICE]),
                current_standing_charge=_decimal(config[CONF_STANDING_CHARGE]),
                power_kva=_decimal(config[CONF_POWER]),
                include_indexed=bool(config.get(CONF_INCLUDE_INDEXED, False)),
                include_conditional=bool(config.get(CONF_ALLOW_CONDITIONAL, False)),
                market=config.get(CONF_MARKET, MARKET_ALL),
            )
            if not ranked:
                ranking_status = "no_matching_offers"
                summary = "No eligible single-rate offers match this installation."

        offer_records = [self._offer_record(item, reference_label) for item in ranked[:MAX_OFFERS]]
        potential_savings = ranked[0].savings if ranked and reference_kwh is not None else None
        stale = bool(self.catalog_service.error)
        status = "stale" if stale else ranking_status
        if stale:
            summary = f"Catalog refresh failed; showing the last successful data. {summary}"
        result = {
            "status": status,
            "ranking_status": ranking_status,
            "summary": summary,
            "offers": offer_records,
            "last_successful_update": self.catalog_service.last_successful_update,
            "new_offer_count": new_count,
            "energy_used": current_window.kwh if current_window.coverage_complete else None,
            "current_cost": current_cost,
            "current_cost_note": current_cost_note,
            "current_cost_cutoff": cutoff_local.isoformat() if cutoff_local else None,
            "consumption_source": current_window.source,
            "standing_charge_days": current_days,
            "cycle_start": cycle.start.isoformat(),
            "cycle_end": cycle.last_included_date.isoformat(),
            "cycle_end_exclusive": cycle.end_exclusive.isoformat(),
            "reference_kwh": str(reference_kwh) if reference_kwh is not None else None,
            "reference_days": reference_days or None,
            "reference_label": reference_label or None,
            "reference_consumption_source": reference_window.source if reference_window else None,
            "power_kva": str(config[CONF_POWER]),
            "catalog_hash": catalog.content_hash,
            "catalog_diagnostics": catalog.diagnostics,
            "last_error": self.catalog_service.error,
            "potential_savings": potential_savings,
            "refresh_succeeded": catalog_refresh_observed,
            "offers_excluding_vat": True,
        }
        await self._persist_entry_snapshot(
            fingerprint,
            eligibility_fingerprint,
            new_count,
            config_changed,
            ignored_new_ids,
            catalog_refresh_observed,
        )
        if (
            catalog_refresh_observed
            and not stale
            and ranking_status == "ready"
            and reference_kwh is not None
        ):
            await async_emit_savings_event(
                self.hass,
                storage=self.entry_storage,
                ranked=ranked,
                current_energy_price=_decimal(config[CONF_ENERGY_PRICE]),
                current_standing_charge=_decimal(config[CONF_STANDING_CHARGE]),
                kwh=reference_kwh,
                days=reference_days,
                options=config,
                fingerprint=fingerprint,
                allow_alerts=not config_changed or initial_config,
            )
        return result

    async def _persist_entry_snapshot(
        self,
        fingerprint: str,
        eligibility_fingerprint: str,
        new_count: int,
        config_changed: bool,
        ignored_new_ids: set[str],
        catalog_refresh_observed: bool,
    ) -> None:
        updated = dict(self.entry_storage.data)
        updated["config_fingerprint"] = fingerprint
        updated["eligibility_fingerprint"] = eligibility_fingerprint
        updated["new_offer_count"] = new_count
        updated["ignored_new_identity_ids"] = sorted(ignored_new_ids)
        if catalog_refresh_observed and self.catalog_service.last_successful_update:
            updated["last_seen_catalog_success"] = self.catalog_service.last_successful_update
        if config_changed:
            updated.pop("notification_fingerprint", None)
            updated.pop("notification_offers", None)
        await self.entry_storage.async_save(updated)

    async def _async_current_contract_cost(
        self,
        window: EnergyWindow,
        cycle_start: datetime,
        cycle_start_date: date,
        cutoff_local: datetime,
        standing_days: int,
        config: dict[str, Any],
    ) -> Decimal | None:
        """Accrue measured energy using the price effective at each interval."""
        records = list(self.entry_storage.data.get("price_history", []))
        def _effective_moment(record: dict[str, Any]) -> datetime:
            try:
                moment = datetime.fromisoformat(record["effective_at"])
            except (KeyError, TypeError, ValueError):
                moment = cycle_start
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=dt_util.UTC)
            return dt_util.as_utc(moment)

        records.sort(key=_effective_moment)
        if not records:
            records = [
                {
                    "effective_at": cycle_start.isoformat(),
                    "energy_price": str(config[CONF_ENERGY_PRICE]),
                    "standing_charge": str(config[CONF_STANDING_CHARGE]),
                }
            ]
        cycle_start_utc = dt_util.as_utc(cycle_start)
        cutoff_utc = dt_util.as_utc(cutoff_local)
        effective: list[tuple[datetime, dict[str, Any]]] = []
        for record in records:
            moment_utc = _effective_moment(record)
            if cycle_start_utc < moment_utc < cutoff_utc:
                effective.append((moment_utc, record))
        if window.source == "hourly_statistics" and any(
            not record.get("seed", False)
            and (moment.minute != 0 or moment.second != 0 or moment.microsecond != 0)
            for moment, record in effective
        ):
            # Hourly totals cannot identify which side of a within-hour price
            # change consumed the energy, so do not publish a misleading cost.
            return None
        boundaries = [cycle_start_utc, *(moment for moment, _ in effective), cutoff_utc]
        energy_cost = Decimal("0")
        for left, right in zip(boundaries, boundaries[1:], strict=False):
            left_value = meter_at(list(window.meter_samples), left)
            right_value = meter_at(list(window.meter_samples), right)
            if left_value is None or right_value is None:
                continue
            interval_kwh = max(Decimal("0"), right_value - left_value)
            active = records[0]
            for record in records:
                if _effective_moment(record) <= left:
                    active = record
            energy_cost += interval_kwh * _decimal(
                active.get("energy_price", config[CONF_ENERGY_PRICE])
            )

        standing_cost = Decimal("0")
        for day_offset in range(standing_days):
            day_start = self._local_midnight(cycle_start_date + timedelta(days=day_offset))
            day_start_utc = dt_util.as_utc(day_start)
            active = records[0]
            for record in records:
                if _effective_moment(record) <= day_start_utc:
                    active = record
            standing_cost += _decimal(active.get("standing_charge", config[CONF_STANDING_CHARGE]))
        return energy_cost + standing_cost

    def _offer_is_eligible(self, offer: Offer, config: dict[str, Any], today: date) -> bool:
        if offer.valid_from and today < offer.valid_from:
            return False
        if offer.valid_until and today > offer.valid_until:
            return False
        # Unverified consumption-limit units stay visible in details but do not
        # qualify for savings claims until the ERSE metadata contract is checked.
        if offer.eligibility.get("ConsIni_ELE") or offer.eligibility.get("ConsFim_ELE"):
            return False
        if offer.unresolved_costs or offer.mandatory_services_per_year > 0:
            return False
        if offer.indexed and not bool(config.get(CONF_INCLUDE_INDEXED, False)):
            return False
        if offer.conditional_eligibility and not bool(config.get(CONF_ALLOW_CONDITIONAL, False)):
            return False
        market = config.get(CONF_MARKET, MARKET_ALL)
        return market == MARKET_ALL or offer.market == market

    @staticmethod
    def _offer_record(item: RankedOffer, reference_label: str) -> dict[str, Any]:
        offer = item.offer
        return {
            "identity": offer.identity,
            "supplier_code": offer.supplier_code,
            "supplier_name": offer.supplier_name,
            "offer_id": offer.offer_id,
            "offer_name": offer.offer_name,
            "power_kva": str(offer.power_kva),
            "standing_charge": str(offer.standing_charge),
            "energy_price": str(offer.energy_price),
            "mandatory_services_per_year": str(offer.mandatory_services_per_year),
            "conditional_eligibility": offer.conditional_eligibility,
            "unresolved_costs": offer.unresolved_costs,
            "candidate_cost": str(item.candidate_cost),
            "current_cost": str(item.current_cost),
            "savings": str(item.savings),
            "indexed": offer.indexed,
            "market": offer.market,
            "terms_url": offer.terms_url,
            "offer_url": offer.offer_url,
            "eligibility": offer.eligibility,
            "valid_from": offer.valid_from.isoformat() if offer.valid_from else None,
            "valid_until": offer.valid_until.isoformat() if offer.valid_until else None,
            "reference_label": reference_label,
        }

    def _local_midnight(self, day: date) -> datetime:
        """Construct local civil midnight rather than adding fixed seconds."""
        zone = dt_util.get_time_zone(self.hass.config.time_zone)
        return datetime.combine(day, time.min).replace(tzinfo=zone)

    @staticmethod
    def _fingerprint(config: dict[str, Any]) -> str:
        keys = (
            CONF_ENERGY_ENTITY,
            CONF_POWER,
            CONF_BILLING_START,
            CONF_BILLING_DAYS,
            CONF_MARKET,
            CONF_INCLUDE_INDEXED,
            CONF_ALLOW_CONDITIONAL,
        )
        return "|".join(str(config.get(key, "")) for key in keys)

    @staticmethod
    def _eligibility_fingerprint(config: dict[str, Any]) -> str:
        """Track only settings that change which variants count as additions."""
        keys = (
            CONF_POWER,
            CONF_MARKET,
            CONF_INCLUDE_INDEXED,
            CONF_ALLOW_CONDITIONAL,
        )
        return "|".join(str(config.get(key, "")) for key in keys)

    def _empty_result(
        self,
        status: str,
        summary: str,
        config: dict[str, Any],
        new_count: int,
        catalog: Catalog,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "ranking_status": status,
            "summary": summary,
            "offers": [],
            "last_successful_update": self.catalog_service.last_successful_update,
            "new_offer_count": new_count,
            "energy_used": Decimal("0"),
            "current_cost": Decimal("0"),
            "potential_savings": None,
            "reference_kwh": None,
            "reference_days": None,
            "power_kva": str(config[CONF_POWER]),
            "catalog_hash": catalog.content_hash,
            "last_error": self.catalog_service.error,
        }
