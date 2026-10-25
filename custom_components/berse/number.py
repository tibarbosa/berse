"""User-adjustable prices and billing-period length."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BILLING_DAYS,
    CONF_ENERGY_PRICE,
    CONF_STANDING_CHARGE,
    DOMAIN,
)
from .coordinator import OfferCoordinator
from .entity import BerseEntity, async_update_entry_data


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: OfferCoordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    async_add_entities(
        [
            PriceNumber(coordinator, entry, CONF_ENERGY_PRICE),
            PriceNumber(coordinator, entry, CONF_STANDING_CHARGE),
            BillingDaysNumber(coordinator, entry),
        ]
    )


class PriceNumber(BerseEntity, NumberEntity):
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 10
    _attr_native_step = 0.0001

    def __init__(self, coordinator: OfferCoordinator, entry: ConfigEntry, key: str) -> None:
        name_key = "energy_price" if key == CONF_ENERGY_PRICE else "standing_charge"
        super().__init__(coordinator, entry, name_key)
        self._key = key
        self._attr_translation_key = name_key
        self._attr_native_unit_of_measurement = "EUR/kWh" if key == CONF_ENERGY_PRICE else "EUR/day"
        self._attr_icon = "mdi:cash" if key == CONF_ENERGY_PRICE else "mdi:cash-clock"

    @property
    def native_value(self) -> float:
        return float(self._entry.data[self._key])

    async def async_set_native_value(self, value: float) -> None:
        updated = {**self._entry.data, self._key: value}
        await self.coordinator.entry_storage.async_record_price_change(
            updated[CONF_ENERGY_PRICE],
            updated[CONF_STANDING_CHARGE],
            dt_util.now().isoformat(),
        )
        await async_update_entry_data(
            self.hass, self._entry, self.coordinator, {self._key: value}
        )


class BillingDaysNumber(BerseEntity, NumberEntity):
    _attr_translation_key = "billing_days"
    _attr_icon = "mdi:calendar-range"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 1
    _attr_native_max_value = 366
    _attr_native_step = 1

    def __init__(self, coordinator: OfferCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "billing_days")

    @property
    def native_value(self) -> int:
        return int(self._entry.data[CONF_BILLING_DAYS])

    async def async_set_native_value(self, value: float) -> None:
        await async_update_entry_data(
            self.hass, self._entry, self.coordinator, {CONF_BILLING_DAYS: int(value)}
        )
