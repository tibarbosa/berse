"""Manual offer refresh button."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OfferCoordinator
from .entity import BarbsErseEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: OfferCoordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    async_add_entities([RefreshOffersButton(coordinator, entry)])


class RefreshOffersButton(BarbsErseEntity, ButtonEntity):
    _attr_translation_key = "refresh_offers"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: OfferCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "refresh_offers")

    async def async_press(self) -> None:
        await self.coordinator.async_force_refresh()
