"""Constants for CastnCasa."""

from homeassistant.const import Platform

DOMAIN = "castncasa"
INTEGRATION_VERSION = "1.0.22"
DATA_MANAGER = "manager"
DATA_SCHEDULE = "schedule"
DATA_PRESENCE = "presence"
DATA_COORDINATOR = "coordinator"

CONF_PRESENCE_ENTITIES = "presence_entities"
CONF_HEAT_MIN_EMPTY_MINUTES = "heat_min_empty_minutes"
CONF_HEAT_REHEAT_LEAD_MINUTES = "heat_reheat_lead_minutes"
CONF_HEAT_COMFORT_BUFFER_MINUTES = "heat_comfort_buffer_minutes"
CONF_HEAT_MIN_COMFORT_MINUTES = "heat_min_comfort_minutes"
CONF_HEAT_LEARNING_ENABLED = "heat_learning_enabled"
CONF_HEAT_LEARNING_AUTO_APPLY = "heat_learning_auto_apply"
CONF_HEAT_LEARNING_ROOM_TEMP_ENTITY = "heat_learning_room_temp_entity"
CONF_HEAT_LEARNING_OUTDOOR_TEMP_ENTITY = "heat_learning_outdoor_temp_entity"
CONF_HEAT_LEARNING_BURNER_ENTITY = "heat_learning_burner_entity"
CONF_HEAT_LEARNING_TARGET_TEMP = "heat_learning_target_temp"

DEFAULT_HEAT_MIN_EMPTY_MINUTES = 120
DEFAULT_HEAT_REHEAT_LEAD_MINUTES = 60
DEFAULT_HEAT_COMFORT_BUFFER_MINUTES = 15
DEFAULT_HEAT_MIN_COMFORT_MINUTES = 120
DEFAULT_HEAT_LEARNING_ENABLED = False
DEFAULT_HEAT_LEARNING_AUTO_APPLY = True
DEFAULT_HEAT_LEARNING_TARGET_TEMP = 22.0

STORAGE_VERSION = 1
STORAGE_KEY = "castncasa.devices"

PAIRING_TTL_SECONDS = 300
PAIRING_MAX_ATTEMPTS = 5
API_CLOCK_SKEW_SECONDS = 300
API_NONCE_TTL_SECONDS = 600
APP_PRESENCE_TTL_SECONDS = 900

SERVICE_CREATE_PAIRING = "create_pairing"
SERVICE_LIST_DEVICES = "list_devices"
SERVICE_REVOKE_DEVICE = "revoke_device"
SERVICE_SET_RESIDENT_COLOR = "set_resident_color"

PAIRING_PATH = "/api/castncasa/pairing/{pairing_id}"
PAIRING_QR_PATH = "/api/castncasa/pairing/{pairing_id}/qr.svg"
PAIR_CLAIM_PATH = "/api/castncasa/v1/pair"
STATUS_PATH = "/api/castncasa/v1/status"
SCHEDULE_PATH = "/api/castncasa/v1/schedule"
PRESENCE_PATH = "/api/castncasa/v1/presence"
STATE_PATH = "/api/castncasa/v1/state"

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.CALENDAR]
