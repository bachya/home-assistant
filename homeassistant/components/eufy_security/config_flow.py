"""Config flow for Eufy Security integration."""
from __future__ import annotations

from typing import Any

from eufy_security_ws_python.errors import BaseEufySecurityServerError
from eufy_security_ws_python.version import async_get_server_version
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


class CannotConnect(HomeAssistantError):
    """Indicate connection error."""


class InvalidInput(HomeAssistantError):
    """Error to indicate input data is invalid."""

    def __init__(self, error: str) -> None:
        """Initialize error."""
        super().__init__()
        self.error = error


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    if not data[CONF_WEBSOCKET_URI].startswith(("ws://", "wss://")):
        raise InvalidInput("invalid_ws_url")

    session = aiohttp_client.async_get_clientsession(hass)

    try:
        await async_get_server_version(data[CONF_WEBSOCKET_URI], session)
    except BaseEufySecurityServerError as err:
        raise InvalidInput("cannot_connect") from err
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
        except InvalidInput as err:
            errors[CONF_WEBSOCKET_URI] = err.error
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
