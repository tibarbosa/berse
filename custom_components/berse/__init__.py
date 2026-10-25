"""berse Home Assistant integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENERGY_PRICE,
    CONF_STANDING_CHARGE,
    CONF_UPDATE_TIME,
    DOMAIN,
    PLATFORMS,
    VERSION,
)
from .coordinator import CatalogService, OfferCoordinator
from .storage import EntryStorage

_LOGGER = logging.getLogger(__name__)
CARD_URL = f"/berse/berse-offers.js?v={VERSION}"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the shared catalog service."""
    hass.data.setdefault(DOMAIN, {})
    service = CatalogService(hass)
    await service.async_load()
    hass.data[DOMAIN]["catalog_service"] = service
    hass.data[DOMAIN]["coordinators"] = {}
    return True


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the card and register its resource for storage dashboards."""
    domain_data = hass.data[DOMAIN]
    if not domain_data.get("frontend_registered"):
        js_path = Path(__file__).parent / "frontend" / "berse-offers.js"
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig("/berse/berse-offers.js", str(js_path), False),
                StaticPathConfig("/berse/suppliers", str(js_path.parent / "suppliers"), True),
                StaticPathConfig(
                    "/berse/supplier-cache",
                    str(domain_data["catalog_service"].suppliers.directory),
                    True,
                ),
            ]
        )
        domain_data["frontend_registered"] = True

    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        _LOGGER.warning(
            "Lovelace is unavailable; add %s as a dashboard module resource manually",
            CARD_URL,
        )
        return
    resources = lovelace.resources
    if lovelace.resource_mode == "yaml":
        _LOGGER.info("Lovelace resources use YAML mode; add %s under lovelace resources", CARD_URL)
        return
    try:
        await resources.async_get_info()
        items = resources.async_items()
        existing = next(
            (
                item
                for item in items
                if item.get("url", "").split("?", 1)[0] == "/berse/berse-offers.js"
            ),
            None,
        )
        if existing:
            if existing.get("url") != CARD_URL:
                await resources.async_update_item(
                    existing["id"], {"url": CARD_URL, "res_type": "module"}
                )
        else:
            await resources.async_create_item({"url": CARD_URL, "res_type": "module"})
    except Exception:  # Lovelace resource storage differs on older supported versions.
        _LOGGER.exception("Could not register the berse dashboard card resource")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one installation and its entities."""
    await _async_register_frontend(hass)
    service: CatalogService = hass.data[DOMAIN]["catalog_service"]
    entry_storage = EntryStorage(hass, entry.entry_id)
    await entry_storage.async_load()
    await entry_storage.async_seed_price_history(
        entry.data[CONF_ENERGY_PRICE],
        entry.data[CONF_STANDING_CHARGE],
        dt_util.now().isoformat(),
    )
    coordinator = OfferCoordinator(hass, entry, service, entry_storage)
    hass.data[DOMAIN]["coordinators"][entry.entry_id] = coordinator
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    update_time = str(entry.data.get(CONF_UPDATE_TIME, "03:15:00"))
    hour, minute, second = (int(value) for value in update_time.split(":"))

    async def _scheduled_refresh(_now) -> None:
        await coordinator.async_force_refresh()

    entry.async_on_unload(
        async_track_time_change(hass, _scheduled_refresh, hour=hour, minute=minute, second=second)
    )
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entities after the user changes options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload one installation's entity platforms."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    hass.data[DOMAIN]["coordinators"].pop(entry.entry_id, None)
    return True
