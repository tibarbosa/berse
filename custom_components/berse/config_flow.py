"""Config and options flows for berse."""

from __future__ import annotations

import math
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ALLOW_CONDITIONAL,
    CONF_BILLING_DAYS,
    CONF_BILLING_START,
    CONF_CONSUMPTION_MODE,
    CONF_COST_PRICE_MODE,
    CONF_ENERGY_ENTITY,
    CONF_ENERGY_PRICE,
    CONF_INCLUDE_INDEXED,
    CONF_INITIAL_SUMMARY,
    CONF_MANUAL_KWH,
    CONF_MARKET,
    CONF_MIN_SAVING_EUR,
    CONF_MIN_SAVING_PERCENT,
    CONF_NOTIFY_INDEXED,
    CONF_POWER,
    CONF_STANDING_CHARGE,
    CONF_UPDATE_TIME,
    CONSUMPTION_MANUAL,
    CONSUMPTION_SENSOR,
    COST_PRICES_CURRENT,
    COST_PRICES_RECORDED,
    DEFAULT_BILLING_DAYS,
    DEFAULT_POWER,
    DEFAULT_UPDATE_TIME,
    DOMAIN,
    MARKET_ALL,
    MARKET_FREE,
    MARKET_REGULATED,
    NAME,
    POWER_OPTIONS,
)


def _energy_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", device_class="energy", multiple=False)
    )


def _energy_price_selector() -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=10,
            step=0.0001,
            mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement="EUR/kWh",
        )
    )


def _standing_selector() -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=10,
            step=0.0001,
            mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement="EUR/day",
        )
    )


def _power_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[{"value": value, "label": f"{value} kVA"} for value in POWER_OPTIONS],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _consumption_fields(values: dict[str, Any]) -> dict:
    entity = vol.Optional(
        CONF_ENERGY_ENTITY, description={"suggested_value": values.get(CONF_ENERGY_ENTITY)}
    )
    return {
        vol.Required(
            CONF_CONSUMPTION_MODE,
            default=values.get(CONF_CONSUMPTION_MODE, CONSUMPTION_SENSOR),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    {"value": CONSUMPTION_SENSOR, "label": "Cumulative energy sensor"},
                    {"value": CONSUMPTION_MANUAL, "label": "Manual consumption per billing period"},
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        entity: _energy_selector(),
        vol.Required(
            CONF_MANUAL_KWH, default=values.get(CONF_MANUAL_KWH, 100)
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.01,
                max=1000000,
                step=0.01,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="kWh",
            )
        ),
    }


def _consumption_errors(hass, values: dict[str, Any]) -> dict[str, str]:
    if values.get(CONF_CONSUMPTION_MODE) == CONSUMPTION_MANUAL:
        try:
            amount = float(values[CONF_MANUAL_KWH])
            if math.isfinite(amount) and 0 < amount <= 1000000:
                return {}
        except (KeyError, TypeError, ValueError):
            pass
        return {CONF_MANUAL_KWH: "invalid_manual_consumption"}
    if values.get(CONF_CONSUMPTION_MODE) != CONSUMPTION_SENSOR:
        return {CONF_CONSUMPTION_MODE: "invalid_consumption_mode"}
    if not _validate_energy_sensor(hass, values.get(CONF_ENERGY_ENTITY)):
        return {CONF_ENERGY_ENTITY: "invalid_energy_sensor"}
    return {}


def _entry_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    values = defaults or {}

    def required(key: str, fallback: Any = None):
        default = values.get(key, fallback)
        return vol.Required(key) if default is None else vol.Required(key, default=default)

    return vol.Schema(
        {
            **_consumption_fields(values),
            required(CONF_POWER, DEFAULT_POWER): _power_selector(),
            required(CONF_ENERGY_PRICE): _energy_price_selector(),
            required(CONF_STANDING_CHARGE): _standing_selector(),
            required(CONF_BILLING_START, dt_util.now().date().isoformat()): selector.DateSelector(),
            required(CONF_BILLING_DAYS, DEFAULT_BILLING_DAYS): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=366,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            required(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME): selector.TimeSelector(),
        }
    )


def _validate_energy_sensor(hass, entity_id: str) -> bool:
    """Accept only cumulative imported-energy kWh sensors."""
    if not isinstance(entity_id, str) or not entity_id.startswith("sensor."):
        return False
    state = hass.states.get(entity_id)
    if state is None:
        return False
    attrs = state.attributes
    if attrs.get("device_class") != "energy":
        return False
    if attrs.get("state_class") not in {"total", "total_increasing"}:
        return False
    if str(attrs.get("unit_of_measurement", "")).strip().casefold() != "kwh":
        return False
    try:
        value = float(state.state)
        if not math.isfinite(value) or value < 0:
            return False
    except (TypeError, ValueError):
        return False
    return True


class BerseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up a single imported-energy installation."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _consumption_errors(self.hass, user_input)
            if not errors:
                manual = user_input[CONF_CONSUMPTION_MODE] == CONSUMPTION_MANUAL
                if manual:
                    user_input.pop(CONF_ENERGY_ENTITY, None)
                    friendly_name = "Manual consumption"
                else:
                    energy_entity = user_input[CONF_ENERGY_ENTITY]
                    await self.async_set_unique_id(energy_entity)
                    self._abort_if_unique_id_configured()
                    friendly_name = (
                        self.hass.states.get(energy_entity).attributes.get("friendly_name")
                        or energy_entity
                    )
                existing_entries = self.hass.config_entries.async_entries(DOMAIN)
                title = NAME if not existing_entries else f"{NAME} · {friendly_name}"
                user_input[CONF_POWER] = str(user_input[CONF_POWER])
                user_input[CONF_BILLING_DAYS] = int(user_input[CONF_BILLING_DAYS])
                return self.async_create_entry(title=title, data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=_entry_schema(user_input), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return BerseOptionsFlow()


class BerseOptionsFlow(config_entries.OptionsFlow):
    """Advanced market and savings-notification choices."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            errors = _consumption_errors(self.hass, user_input)
            if not errors:
                return self.async_create_entry(title="", data=user_input)
        options = {**self.config_entry.data, **self.config_entry.options, **(user_input or {})}
        schema = vol.Schema(
            {
                **_consumption_fields(options),
                vol.Required(
                    CONF_COST_PRICE_MODE,
                    default=options.get(CONF_COST_PRICE_MODE, COST_PRICES_RECORDED),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {
                                "value": COST_PRICES_RECORDED,
                                "label": "Prices recorded over time",
                            },
                            {
                                "value": COST_PRICES_CURRENT,
                                "label": "Current contract prices for the whole period",
                            },
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_MARKET, default=options.get(CONF_MARKET, MARKET_ALL)
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": MARKET_ALL, "label": "All eligible offers"},
                            {"value": MARKET_REGULATED, "label": "Regulated reference"},
                            {"value": MARKET_FREE, "label": "Free market"},
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_INCLUDE_INDEXED,
                    default=options.get(CONF_INCLUDE_INDEXED, False),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_ALLOW_CONDITIONAL,
                    default=options.get(CONF_ALLOW_CONDITIONAL, False),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_NOTIFY_INDEXED,
                    default=options.get(CONF_NOTIFY_INDEXED, False),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_MIN_SAVING_EUR, default=options.get(CONF_MIN_SAVING_EUR, 0.0)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=100000,
                        step=0.01,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="EUR",
                    )
                ),
                vol.Required(
                    CONF_MIN_SAVING_PERCENT,
                    default=options.get(CONF_MIN_SAVING_PERCENT, 0.0),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=100,
                        step=0.1,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="%",
                    )
                ),
                vol.Required(
                    CONF_INITIAL_SUMMARY,
                    default=options.get(CONF_INITIAL_SUMMARY, False),
                ): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
