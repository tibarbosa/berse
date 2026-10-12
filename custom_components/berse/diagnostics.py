"""Privacy-conscious diagnostic data."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return catalog and coordinator health without the selected entity ID."""
    coordinator = hass.data[DOMAIN]["coordinators"].get(entry.entry_id)
    service = hass.data[DOMAIN].get("catalog_service")
    data = coordinator.data if coordinator and coordinator.data else {}
    catalog = service.catalog if service else None
    return {
        "integration_version": VERSION,
        "config": {
            key: value
            for key, value in entry.data.items()
            if key != "energy_entity"
        },
        "options": {key: value for key, value in entry.options.items() if key != "energy_entity"},
        "catalog": {
            "source_url": catalog.source_url if catalog else None,
            "content_hash": catalog.content_hash if catalog else None,
            "parser_version": catalog.parser_version if catalog else None,
            "offer_count": len(catalog.offers) if catalog else 0,
            "diagnostics": catalog.diagnostics if catalog else {},
            "last_successful_update": service.last_successful_update if service else None,
            "last_error": service.error if service else None,
        },
        "coordinator": {
            "status": data.get("status"),
            "ranking_status": data.get("ranking_status"),
            "reference_days": data.get("reference_days"),
            "reference_kwh": data.get("reference_kwh"),
            "new_offer_count": data.get("new_offer_count"),
        },
    }
