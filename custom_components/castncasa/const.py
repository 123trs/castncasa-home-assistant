"""Constants for CastnCasa."""

from homeassistant.const import Platform

DOMAIN = "castncasa"
INTEGRATION_VERSION = "1.0.1"
DATA_MANAGER = "manager"
DATA_SCHEDULE = "schedule"

CONF_HEAT_MIN_EMPTY_MINUTES = "heat_min_empty_minutes"
CONF_HEAT_REHEAT_LEAD_MINUTES = "heat_reheat_lead_minutes"
CONF_HEAT_COMFORT_BUFFER_MINUTES = "heat_comfort_buffer_minutes"

DEFAULT_HEAT_MIN_EMPTY_MINUTES = 120
DEFAULT_HEAT_REHEAT_LEAD_MINUTES = 60
DEFAULT_HEAT_COMFORT_BUFFER_MINUTES = 15

STORAGE_VERSION = 1
STORAGE_KEY = "castncasa.devices"

PAIRING_TTL_SECONDS = 300
PAIRING_MAX_ATTEMPTS = 5
API_CLOCK_SKEW_SECONDS = 300
API_NONCE_TTL_SECONDS = 600

SERVICE_CREATE_PAIRING = "create_pairing"
SERVICE_LIST_DEVICES = "list_devices"
SERVICE_REVOKE_DEVICE = "revoke_device"

PAIRING_PATH = "/api/castncasa/pairing/{pairing_id}"
PAIRING_QR_PATH = "/api/castncasa/pairing/{pairing_id}/qr.svg"
PAIR_CLAIM_PATH = "/api/castncasa/v1/pair"
STATUS_PATH = "/api/castncasa/v1/status"
SCHEDULE_PATH = "/api/castncasa/v1/schedule"
STATE_PATH = "/api/castncasa/v1/state"

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.CALENDAR]
