"""The Eufy Security integration."""
from __future__ import annotations

import asyncio
from typing import Any, Callable

from eufy_security_ws_python.client import WebsocketClient
from eufy_security_ws_python.errors import BaseEufySecurityServerError
from eufy_security_ws_python.model.device import Device
from eufy_security_ws_python.model.station import Station

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_WEBSOCKET_URI,
    DATA_CLIENT,
    DATA_METADATA,
    DOMAIN,
    EVENT_GUARD_MODE_CHANGED,
    LOGGER,
)

ATTR_STATION_SERIAL_NUMBER = "station_serial_number"

EVENT_MAP = {"guard mode changed": EVENT_GUARD_MODE_CHANGED}

PLATFORMS = ["select"]

SIGNAL_RAW_EVENT_RECEIVED = f"{DOMAIN}_raw_event_received"


@callback
def async_get_event_from_data(data: dict[str, Any]) -> str | None:
    """Return an integration event from a raw data payload."""
    event = data["event"]
    try:
        return EVENT_MAP[event]
    except KeyError:
        LOGGER.debug("Received unknown event: %s", event)
        return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Eufy Security from a config entry."""
    hass.data.setdefault(DOMAIN, {DATA_CLIENT: {}, DATA_METADATA: {}})

    eufy_security = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id] = EufySecurity(
        hass, entry
    )
    hass.data[DOMAIN][DATA_METADATA][entry.entry_id] = {}

    await eufy_security.async_startup()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        eufy_security = hass.data[DOMAIN][DATA_CLIENT].pop(entry.entry_id)
        await eufy_security.async_shutdown()
        hass.data[DOMAIN][DATA_METADATA].pop(entry.entry_id)

    return unload_ok


class EufySecurity:
    """Define a data and event manager."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self._driver_ready = asyncio.Event()
        self._entry = entry
        self._hass = hass
        self._listen_task: asyncio.Task | None = None
        self._unsub_callbacks: list[Callable] = []

        session = aiohttp_client.async_get_clientsession(hass)
        self.client = WebsocketClient(entry.data[CONF_WEBSOCKET_URI], session)

    async def async_listen(self) -> None:
        """Start listening to the websocket."""
        should_reload = True

        try:
            await self.client.async_listen(self._driver_ready)
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

    async def async_shutdown(self) -> None:
        """Perform teardown."""
        if self._listen_task:
            self._listen_task.cancel()

        if self.client.connected:
            await self.client.async_disconnect()
            LOGGER.info("Disconnected from Zwave JS Server")

        for unsub in self._unsub_callbacks:
            unsub()

    async def async_startup(self) -> None:
        """Perform startup."""
        try:
            await self.client.async_connect()
        except BaseEufySecurityServerError as err:
            raise ConfigEntryNotReady(err) from err

        self._listen_task = asyncio.create_task(self.async_listen())

        try:
            await self._driver_ready.wait()
        except asyncio.CancelledError:
            LOGGER.debug("Cancelling start platforms")
            return

        LOGGER.info("Connection to Zwave JS Server initialized")

        async def handle_ha_shutdown(_: Event) -> None:
            """React when shutdown occurs."""
            await self.async_shutdown()

        self._unsub_callbacks.append(
            self._hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, handle_ha_shutdown)
        )

        async def async_get_properties_metadata(eufy_device: Device | Station) -> None:
            """Store station or device metadata."""
            metadata = await eufy_device.async_get_properties_metadata()
            self._hass.data[DOMAIN][DATA_METADATA][self._entry.entry_id][
                eufy_device.serial_number
            ] = metadata["properties"]

        metadata_tasks = []
        for device in self.client.driver.devices.values():
            metadata_tasks.append(async_get_properties_metadata(device))
        for station in self.client.driver.stations.values():
            metadata_tasks.append(async_get_properties_metadata(station))
        await asyncio.gather(*metadata_tasks)

        @callback
        def handle_raw_event(data: dict[str, Any]) -> None:
            """Handle a raw Eufy Security event."""
            event = async_get_event_from_data(data)
            if not event:
                return
            self._hass.bus.async_fire(event, data)
            async_dispatcher_send(self._hass, SIGNAL_RAW_EVENT_RECEIVED)

        for raw_event in EVENT_MAP:
            self._unsub_callbacks.append(
                self.client.driver.on(raw_event, handle_raw_event)
            )


class EufySecurityEntity(Entity):
    """Define a base Eufy Security entity."""

    def __init__(self, metadata: dict[str, Any]) -> None:
        """Initialize."""
        self._attr_extra_state_attributes = {
            ATTR_ATTRIBUTION: "Data provided by Eufy Security"
        }
        self._metadata = metadata

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""

        @callback
        def update() -> None:
            """Update the entity state."""
            self._async_update_from_latest_data()
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_RAW_EVENT_RECEIVED, update)
        )
        self._async_update_from_latest_data()


class StationEntity(EufySecurityEntity):
    """Define a base station entity."""

    def __init__(self, metadata: dict[str, Any], station: Station) -> None:
        """Initialize."""
        super().__init__(metadata)

        self._attr_device_info = {
            "identifiers": {(DOMAIN, station.serial_number)},
            "manufacturer": "Eufy Security",
            "model": station.model,
            "name": station.name,
            "sw_version": station.software_version,
        }
        self._attr_unique_id = station.serial_number
        self._station = station


class DeviceEntity(EufySecurityEntity):
    """Define a base station entity."""

    def __init__(self, metadata: dict[str, Any], device: Device) -> None:
        """Initialize."""
        super().__init__(metadata)

        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.serial_number)},
            "manufacturer": "Eufy Security",
            "model": device.model,
            "name": device.name,
            "sw_version": device.software_version,
            "via_device": (DOMAIN, device.station_serial_number),
        }
        self._attr_unique_id = device.serial_number
        self._device = device
