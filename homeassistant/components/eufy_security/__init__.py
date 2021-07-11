"""The Eufy Security integration."""
from __future__ import annotations

import asyncio

from eufy_security_ws_python.client import WebsocketClient
from eufy_security_ws_python.errors import BaseEufySecurityServerError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from .const import CONF_WEBSOCKET_URI, DOMAIN, LOGGER

DATA_LISTEN_TASK = "listen_task"
DATA_UNSUBSCRIBE_CALLBACKS = "unsubscribe_callbacks"
DATA_WEBSOCKET_CLIENT = "websocket_client"

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Eufy Security from a config entry."""
    hass.data.setdefault(
        DOMAIN,
        {
            DATA_LISTEN_TASK: {},
            DATA_UNSUBSCRIBE_CALLBACKS: {},
            DATA_WEBSOCKET_CLIENT: {},
        },
    )
    hass.data[DOMAIN][DATA_UNSUBSCRIBE_CALLBACKS][entry.entry_id] = []
    hass.data[DOMAIN][DATA_WEBSOCKET_CLIENT][entry.entry_id] = None

    session = aiohttp_client.async_get_clientsession(hass)
    hass.data[DOMAIN][DATA_WEBSOCKET_CLIENT][entry.entry_id] = WebsocketClient(
        entry.data[CONF_WEBSOCKET_URI], session
    )

    await async_websocket_init(hass, entry)

    async def handle_ha_shutdown(_: Event) -> None:
        """React when shutdown occurs."""
        await async_websocket_shutdown(hass, entry)

    hass.data[DOMAIN][DATA_UNSUBSCRIBE_CALLBACKS][entry.entry_id].append(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, handle_ha_shutdown)
    )

    # hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    unload_ok = True

    if unload_ok:
        if entry.entry_id in hass.data[DOMAIN][DATA_LISTEN_TASK]:
            await async_websocket_shutdown(hass, entry)
        for unsub in hass.data[DOMAIN][DATA_UNSUBSCRIBE_CALLBACKS].pop(entry.entry_id):
            unsub()

    return unload_ok


async def async_websocket_init(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Initialize connection to the websocket."""
    client = hass.data[DOMAIN][DATA_WEBSOCKET_CLIENT][entry.entry_id]
    driver_ready = asyncio.Event()

    try:
        await client.async_connect()
    except BaseEufySecurityServerError as err:
        raise ConfigEntryNotReady(err) from err

    hass.data[DOMAIN][DATA_LISTEN_TASK][entry.entry_id] = asyncio.create_task(
        async_websocket_listen(hass, entry, driver_ready)
    )

    try:
        await driver_ready.wait()
    except asyncio.CancelledError:
        LOGGER.debug("Cancelling start platforms")
        return

    LOGGER.info("Connection to Zwave JS Server initialized")


async def async_websocket_listen(
    hass: HomeAssistant,
    entry: ConfigEntry,
    driver_ready: asyncio.Event,
) -> None:
    """Start listening to the websocket."""
    client = hass.data[DOMAIN][DATA_WEBSOCKET_CLIENT][entry.entry_id]
    should_reload = True

    try:
        await client.async_listen(driver_ready)
    except asyncio.CancelledError:
        should_reload = False
    except BaseEufySecurityServerError as err:
        LOGGER.error("Failed to listen: %s", err)
    except Exception as err:  # pylint: disable=broad-except
        LOGGER.exception("Unexpected exception: %s", err)

    if should_reload:
        LOGGER.info("Disconnected from server. Reloading integration")
        hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))


async def async_websocket_shutdown(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Shut down connection to the websocket."""
    listen_task = hass.data[DOMAIN][DATA_LISTEN_TASK].pop(entry.entry_id)
    listen_task.cancel()

    client = hass.data[DOMAIN][DATA_WEBSOCKET_CLIENT][entry.entry_id]
    if client.connected:
        await client.async_disconnect()
        LOGGER.info("Disconnected from Zwave JS Server")
