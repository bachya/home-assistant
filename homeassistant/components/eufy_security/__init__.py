"""The Eufy Security integration."""
from __future__ import annotations

import asyncio

from eufy_security_ws_python.client import WebsocketClient
from eufy_security_ws_python.errors import BaseEufySecurityServerError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import CONF_WEBSOCKET_URI, DOMAIN, LOGGER

DATA_WEBSOCKET_CLIENT = "websocket_client"

PLATFORMS = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Eufy Security from a config entry."""
    hass.data.setdefault(DOMAIN, {DATA_WEBSOCKET_CLIENT: {}})

    websocket = hass.data[DOMAIN][DATA_WEBSOCKET_CLIENT][entry.entry_id] = Websocket(
        hass, entry
    )

    hass.async_create_task(websocket.async_init())

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        websocket = hass.data[DOMAIN][DATA_WEBSOCKET_CLIENT].pop(entry.entry_id)
        await websocket.async_shutdown()

    return unload_ok


class Websocket:
    """Define a class to manage the connection to the eufy-security-ws websocket."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        session = aiohttp_client.async_get_clientsession(hass)
        self._client = WebsocketClient(entry.data[CONF_WEBSOCKET_URI], session)
        self._driver_ready = asyncio.Event()
        self._entry = entry
        self._hass = hass
        self._listen_task: asyncio.Task = None

    async def _async_client_listen(self):
        """Start listening with the client."""
        should_reload = True
        try:
            await self._client.async_listen(self._driver_ready)
        except asyncio.CancelledError:
            should_reload = False
        except BaseEufySecurityServerError as err:
            LOGGER.error("Failed to listen: %s", err)
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception: %s", err)

        if should_reload:
            LOGGER.info("Disconnected from server. Reloading integration")
            self._hass.async_create_task(
                self._hass.config_entries.async_reload(self._entry.entry_id)
            )

    async def async_init(self) -> None:
        """Initialize the websocket manager."""
        await self._client.async_connect()

        self._listen_task = asyncio.create_task(self._async_client_listen())

        try:
            await self._driver_ready.wait()
        except asyncio.CancelledError:
            LOGGER.debug("Cancelling start platforms")
            return

        LOGGER.info("Connection to Zwave JS Server initialized")

    async def async_shutdown(self) -> None:
        """Shut down the websocket manager."""
        self._listen_task.cancel()

        if self._client.connected:
            await self._client.async_disconnect()
            LOGGER.info("Disconnected from Zwave JS Server")
