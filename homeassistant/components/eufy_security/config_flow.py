"""Config flow for Eufy Security integration."""
from __future__ import annotations

from typing import Any

from eufy_security_ws_python.client import WebsocketClient
from eufy_security_ws_python.errors import BaseEufySecurityServerError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client

from .const import CONF_WEBSOCKET_URI, DOMAIN, LOGGER

DEFAULT_URL = "ws://localhost:3000"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_WEBSOCKET_URI, default=DEFAULT_URL): str}
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    session = aiohttp_client.async_get_clientsession(hass)

    try:
        async with WebsocketClient(data[CONF_WEBSOCKET_URI], session):
            pass
    except BaseEufySecurityServerError as err:
        raise CannotConnect from err

    return {"title": "Eufy Security"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eufy Security."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
