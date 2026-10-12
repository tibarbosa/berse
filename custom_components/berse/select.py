"""Contracted-power selector."""

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_POWER, DOMAIN, POWER_OPTIONS
from .coordinator import OfferCoordinator
from .entity import BerseEntity, async_update_entry_data

POWER_LABELS = [f"{option} kVA" for option in POWER_OPTIONS]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: OfferCoordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    async_add_entities([ContractedPowerSelect(coordinator, entry)])


class ContractedPowerSelect(BerseEntity, SelectEntity):
    _attr_translation_key = "contracted_power"
    _attr_icon = "mdi:flash"
    _attr_options = POWER_LABELS

    def __init__(self, coordinator: OfferCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "contracted_power")
        self._attr_native_unit_of_measurement = "kVA"

    @property
    def current_option(self) -> str:
        return f"{self._entry.data[CONF_POWER]} kVA"

    async def async_select_option(self, option: str) -> None:
        await async_update_entry_data(
            self.hass,
            self._entry,
            self.coordinator,
            {CONF_POWER: option.removesuffix(" kVA")},
        )
