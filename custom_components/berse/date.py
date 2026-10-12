"""Editable billing anchor date."""

from datetime import date

from homeassistant.components.date import DateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_BILLING_START, DOMAIN
from .coordinator import OfferCoordinator
from .entity import BerseEntity, async_update_entry_data


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: OfferCoordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    async_add_entities([BillingStartDate(coordinator, entry)])


class BillingStartDate(BerseEntity, DateEntity):
    _attr_translation_key = "billing_start"
    _attr_icon = "mdi:calendar-start"

    def __init__(self, coordinator: OfferCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "billing_start")

    @property
    def native_value(self) -> date:
        return date.fromisoformat(str(self._entry.data[CONF_BILLING_START])[:10])

    async def async_set_value(self, value: date) -> None:
        await async_update_entry_data(
            self.hass,
            self._entry,
            self.coordinator,
            {CONF_BILLING_START: value.isoformat()},
        )
