"""Persistent catalog and per-entry notification state."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .models import Catalog

STORAGE_VERSION = 1


class CatalogStorage:
    """Persist the active catalog and successful identity snapshots atomically."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.catalog")
        self.data: dict[str, Any] = {}

    async def async_load(self) -> Catalog | None:
        raw = await self._store.async_load()
        self.data = raw or {}
        payload = self.data.get("catalog")
        return Catalog.from_dict(payload) if payload else None

    async def async_save_catalog(
        self,
        catalog: Catalog,
        *,
        previous_ids: list[str],
        current_ids: list[str],
        etag: str | None,
        etag_url: str,
        last_successful_update: str,
        new_identity_ids: list[str],
    ) -> None:
        updated = {
            "catalog": catalog.to_dict(),
            "previous_ids": previous_ids,
            "current_ids": current_ids,
            "etag": etag,
            "etag_url": etag_url,
            "last_successful_update": last_successful_update,
            "new_identity_ids": new_identity_ids,
        }
        await self._store.async_save(updated)
        self.data = updated

    async def async_mark_not_modified(self, last_successful_update: str) -> None:
        updated = dict(self.data)
        updated["new_identity_ids"] = []
        updated["last_successful_update"] = last_successful_update
        await self._store.async_save(updated)
        self.data = updated


class EntryStorage:
    """Persist config fingerprint, successful offer prices and alert identities."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.entry_id = entry_id
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}")
        self.data: dict[str, Any] = {}

    async def async_load(self) -> dict[str, Any]:
        self.data = await self._store.async_load() or {}
        return self.data

    async def async_save(self, data: dict[str, Any]) -> None:
        await self._store.async_save(data)
        self.data = data

    async def async_seed_price_history(
        self, energy_price: Any, standing_charge: Any, effective_at: str
    ) -> None:
        """Record the first known contract prices without prompting for a name."""
        if self.data.get("price_history"):
            return
        updated = dict(self.data)
        updated["price_history"] = [
            {
                "effective_at": effective_at,
                "energy_price": str(energy_price),
                "standing_charge": str(standing_charge),
                "seed": True,
            }
        ]
        await self.async_save(updated)

    async def async_record_price_change(
        self, energy_price: Any, standing_charge: Any, effective_at: str
    ) -> None:
        """Append a contract-price change effective from this local instant."""
        updated = dict(self.data)
        history = list(updated.get("price_history", []))
        snapshot = {
            "effective_at": effective_at,
            "energy_price": str(energy_price),
            "standing_charge": str(standing_charge),
            "seed": False,
        }
        if history and all(
            str(history[-1].get(key)) == str(snapshot[key])
            for key in ("energy_price", "standing_charge")
        ):
            return
        history.append(snapshot)
        updated["price_history"] = history
        await self.async_save(updated)
