"""Constants for the Eufy Security integration."""
import logging

DOMAIN = "eufy_security"

LOGGER = logging.getLogger(__package__)

CONF_WEBSOCKET_URI = "websocket_uri"

DATA_CLIENT = "client"
DATA_METADATA = "metadata"

EVENT_GUARD_MODE_CHANGED = f"{DOMAIN}_guard_mode_changed"
