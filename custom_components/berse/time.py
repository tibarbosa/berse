"""Editable daily refresh time."""

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME, DOMAIN
from .coordinator import OfferCoordinator
from .entity import BerseEntity, async_update_entry_data


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: OfferCoordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    async_add_entities([UpdateTime(coordinator, entry)])


class UpdateTime(BerseEntity, TimeEntity):
    _attr_translation_key = "update_time"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: OfferCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "update_time")

    @property
    def native_value(self) -> time:
        return time.fromisoformat(self._entry.data.get(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME))

    async def async_set_value(self, value: time) -> None:
        update_time = value.isoformat(timespec="seconds")
        await async_update_entry_data(
            self.hass,
            self._entry,
            self.coordinator,
            {CONF_UPDATE_TIME: update_time},
            reload_entry=True,
        )
