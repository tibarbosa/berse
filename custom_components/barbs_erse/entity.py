"""Shared entity metadata for barbs-erse."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import OfferCoordinator


class BarbsErseEntity(CoordinatorEntity[OfferCoordinator]):
    """Base class for device-bound entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OfferCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title or NAME,
            manufacturer=MANUFACTURER,
            model="Electricity offer comparison",
        )

    @property
    def available(self) -> bool:
        return (
            self.coordinator.data is not None
            and self.coordinator.data.get("status") != "unavailable"
        )


async def async_update_entry_data(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: OfferCoordinator,
    updates: dict,
    *,
    reload_entry: bool = False,
) -> None:
    """Persist an entity edit and recompute the installation view."""
    hass.config_entries.async_update_entry(entry, data={**entry.data, **updates})
    if reload_entry:
        await hass.config_entries.async_reload(entry.entry_id)
    else:
        await coordinator.async_request_refresh()
