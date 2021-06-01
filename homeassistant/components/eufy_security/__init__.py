"""The Eufy Security integration."""
from __future__ import annotations

from eufy_security_ws_python import WebsocketClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import CONF_WEBSOCKET_URI, DOMAIN

DATA_WEBSOCKET_CLIENT = "websocket_client"

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Eufy Security from a config entry."""
    hass.data.setdefault(DOMAIN, {DATA_WEBSOCKET_CLIENT: {}})

    # websocket = hass.data[DOMAIN][DATA_WEBSOCKET_CLIENT][entry.entry_id] = Websocket(
    #     hass, entry.data[CONF_WEBSOCKET_URI]
    # )

    # hass.async_create_task(websocket.async_init)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class Websocket:
    """Define a class to manage the connection to the eufy-security-ws websocket."""

    def __init__(self, hass: HomeAssistant, websocket_uri: str) -> None:
        """Initialize."""
        session = aiohttp_client.async_get_clientsession(hass)
        self._client = WebsocketClient(websocket_uri, session)

    async def async_init(self) -> None:
        """Initialize the websocket manager."""
        await self._client.async_connect()
