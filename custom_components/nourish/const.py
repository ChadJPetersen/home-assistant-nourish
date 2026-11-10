"""Constants for the unofficial Nourish Nutrition integration."""

DOMAIN = "nourish"
SERVICE_SYNC_NOW = "sync_now"

CONF_CLIENT_ID = "client_id"
CONF_PATIENT_ID = "patient_id"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_DEVICE_TIME_ZONE = "device_time_zone"
CONF_CONNECTION_DETAILS = "connection_details"

TOKEN_URL = "https://auth.nourish.com/oauth/token"
GOALS_URL = "https://app.nourish.com/api/patients/{patient_id}/todays-goals"
