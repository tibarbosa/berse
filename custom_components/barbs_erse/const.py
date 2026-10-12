"""Constants for barbs-erse."""

from datetime import timedelta

DOMAIN = "barbs_erse"
NAME = "barbs-erse"
VERSION = "0.1.2"
MANUFACTURER = "barbs-erse"

CONF_ENERGY_ENTITY = "energy_entity"
CONF_POWER = "power_kva"
CONF_ENERGY_PRICE = "energy_price"
CONF_STANDING_CHARGE = "standing_charge"
CONF_BILLING_START = "billing_start"
CONF_BILLING_DAYS = "billing_days"
CONF_UPDATE_TIME = "update_time"
CONF_MARKET = "market"
CONF_INCLUDE_INDEXED = "include_indexed"
CONF_ALLOW_CONDITIONAL = "allow_conditional"
CONF_NOTIFY_INDEXED = "notify_indexed"
CONF_MIN_SAVING_EUR = "min_saving_eur"
CONF_MIN_SAVING_PERCENT = "min_saving_percent"
CONF_INITIAL_SUMMARY = "initial_summary"

DEFAULT_UPDATE_TIME = "03:15:00"
DEFAULT_BILLING_DAYS = 30
DEFAULT_POWER = "4.6"
UPDATE_INTERVAL = timedelta(minutes=5)
MAX_OFFERS = 10

PLATFORMS = ["sensor", "number", "select", "date", "time", "button"]

MARKET_ALL = "all"
MARKET_REGULATED = "regulated"
MARKET_FREE = "free"

EVENT_CHEAPER_OFFER = "barbs_erse_cheaper_offer"

SOURCE_SETTINGS_URL = "https://simuladorprecos.erse.pt/config/Settings.json"
SOURCE_USER_AGENT = f"barbs-erse/{VERSION} (Home Assistant custom integration)"

POWER_OPTIONS = (
    "1.15",
    "2.3",
    "3.45",
    "4.6",
    "5.75",
    "6.9",
    "10.35",
    "13.8",
    "17.25",
    "20.7",
    "27.6",
    "34.5",
    "41.4",
)
