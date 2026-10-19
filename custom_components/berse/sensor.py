"""Sensors for energy, cost, offer ranking and update status."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OfferCoordinator
from .entity import BerseEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: OfferCoordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    async_add_entities(
        [
            EnergyUsedSensor(coordinator, entry),
            CurrentCostSensor(coordinator, entry),
            BestOffersSensor(coordinator, entry),
            PotentialSavingsSensor(coordinator, entry),
            LastUpdateSensor(coordinator, entry),
            NewOffersSensor(coordinator, entry),
        ]
    )


class EnergyUsedSensor(BerseEntity, SensorEntity):
    _attr_translation_key = "energy_used"
    _attr_icon = "mdi:lightning-bolt"
    _attr_native_unit_of_measurement = "kWh"
    _attr_device_class = SensorDeviceClass.ENERGY

    def __init__(self, coordinator: OfferCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "energy_used")

    @property
    def native_value(self):
        return self.coordinator.data.get("energy_used")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "cycle_start": self.coordinator.data.get("cycle_start"),
            "cycle_end": self.coordinator.data.get("cycle_end"),
            "current_cost_cutoff": self.coordinator.data.get("current_cost_cutoff"),
            "consumption_source": self.coordinator.data.get("consumption_source"),
        }


class CurrentCostSensor(BerseEntity, SensorEntity):
    _attr_translation_key = "current_cost"
    _attr_icon = "mdi:cash"
    _attr_native_unit_of_measurement = "EUR"
    _attr_device_class = SensorDeviceClass.MONETARY

    def __init__(self, coordinator: OfferCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "current_cost")

    @property
    def native_value(self):
        return self.coordinator.data.get("current_cost")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "data_cutoff": self.coordinator.data.get("current_cost_cutoff"),
            "standing_charge_days": self.coordinator.data.get("standing_charge_days"),
            "cost_note": self.coordinator.data.get("current_cost_note"),
            "cost_price_mode": self.coordinator.data.get("current_cost_price_mode"),
            "consumption_source": self.coordinator.data.get("consumption_source"),
            "price_basis": "excluding VAT",
        }


class BestOffersSensor(BerseEntity, SensorEntity):
    _attr_translation_key = "best_offers"
    _attr_icon = "mdi:format-list-numbered"

    def __init__(self, coordinator: OfferCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "best_offers")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("offers", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        entity_registry = er.async_get(self.hass)
        refresh_entity = entity_registry.async_get_entity_id(
            "button", DOMAIN, f"{self._entry.entry_id}_refresh_offers"
        )
        data = self.coordinator.data
        return {
            "offers": data.get("offers", []),
            "last_successful_update": data.get("last_successful_update"),
            "new_offer_count": data.get("new_offer_count", 0),
            "reference_kwh": data.get("reference_kwh"),
            "reference_days": data.get("reference_days"),
            "reference_label": data.get("reference_label"),
            "reference_consumption_source": data.get("reference_consumption_source"),
            "power_kva": data.get("power_kva"),
            "status": data.get("status"),
            "ranking_status": data.get("ranking_status", data.get("status")),
            "summary": data.get("summary"),
            "last_error": data.get("last_error"),
            "catalog_hash": data.get("catalog_hash"),
            "offers_excluding_vat": data.get("offers_excluding_vat", True),
            "refresh_entity": refresh_entity,
        }


class PotentialSavingsSensor(BerseEntity, SensorEntity):
    _attr_translation_key = "potential_savings"
    _attr_icon = "mdi:piggy-bank-outline"
    _attr_native_unit_of_measurement = "EUR"
    _attr_device_class = SensorDeviceClass.MONETARY

    def __init__(self, coordinator: OfferCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "potential_savings")

    @property
    def native_value(self):
        return self.coordinator.data.get("potential_savings")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "reference_kwh": self.coordinator.data.get("reference_kwh"),
            "reference_days": self.coordinator.data.get("reference_days"),
            "price_basis": "excluding VAT",
        }


class LastUpdateSensor(BerseEntity, SensorEntity):
    _attr_translation_key = "last_update"
    _attr_icon = "mdi:clock-check-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: OfferCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "last_update")

    @property
    def native_value(self):
        value = self.coordinator.data.get("last_successful_update")
        if not value:
            return None
        from datetime import datetime

        return datetime.fromisoformat(value)


class NewOffersSensor(BerseEntity, SensorEntity):
    _attr_translation_key = "new_offers"
    _attr_icon = "mdi:new-box"

    def __init__(self, coordinator: OfferCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "new_offers")

    @property
    def native_value(self) -> int:
        return self.coordinator.data.get("new_offer_count", 0)
