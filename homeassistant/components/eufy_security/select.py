"""Support for Eufy Security select entities."""
from __future__ import annotations

from eufy_security_ws_python.model.station import Station

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EufySecurity, StationEntity
from .const import DATA_CLIENT, DOMAIN, LOGGER

GUARD_STATE_AWAY = "away"
GUARD_STATE_CUSTOM1 = "custom_1"
GUARD_STATE_CUSTOM2 = "custom_2"
GUARD_STATE_CUSTOM3 = "custom_3"
GUARD_STATE_DISARMED = "disarmed"
GUARD_STATE_GEO = "geo"
GUARD_STATE_HOME = "home"
GUARD_STATE_OFF = "off"
GUARD_STATE_SCHEDULE = "schedule"

GUARD_STATE_LABEL_MAP = {
    "AWAY": GUARD_STATE_AWAY,
    "CUSTOM1": GUARD_STATE_CUSTOM1,
    "CUSTOM2": GUARD_STATE_CUSTOM2,
    "CUSTOM3": GUARD_STATE_CUSTOM3,
    "DISARMED": GUARD_STATE_DISARMED,
    "GEO": GUARD_STATE_GEO,
    "HOME": GUARD_STATE_HOME,
    "OFF": GUARD_STATE_OFF,
    "SCHEDULE": GUARD_STATE_SCHEDULE,
}

SELECT_TYPE_GUARD_MODE = "guard_mode"

STATION_SELECTS = {
    SELECT_TYPE_GUARD_MODE: (
        list(GUARD_STATE_LABEL_MAP.values()),
        "Guard Mode",
        "mdi:shield",
    )
}


@callback
def async_get_guard_mode_as_code(
    eufy_security: EufySecurity, station: Station, state: str
) -> int:
    """Convert a Guard Mode state into the equivalent Eufy Security integer value."""
    [label] = [
        eufy_label
        for eufy_label, ha_state in GUARD_STATE_LABEL_MAP.items()
        if ha_state == state
    ]
    [code] = [
        code
        for code, eufy_label in eufy_security.metadata[station.serial_number][
            "guardMode"
        ]["states"].items()
        if eufy_label == label
    ]
    return int(code)


@callback
def async_get_guard_mode_as_state(
    eufy_security: EufySecurity, station: Station
) -> str | None:
    """Get the Home Assistant state representation of a station's Guard Mode."""
    try:
        return GUARD_STATE_LABEL_MAP[
            eufy_security.metadata[station.serial_number]["guardMode"]["states"][
                str(station.guard_mode)
            ]
        ]
    except KeyError:
        LOGGER.warning(
            'Unknown guard mode for station "%s": %s', station.name, station.guard_mode
        )
        return None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Eufy Security selects based on a config entry."""
    eufy_security = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    entities = []
    for serial_number, station in eufy_security.client.driver.stations.items():
        for select_type, (options, name, icon) in STATION_SELECTS.items():
            entities.append(
                StationSelect(
                    eufy_security,
                    station,
                    select_type,
                    options,
                    name,
                    icon,
                )
            )

    async_add_entities(entities)


class StationSelect(StationEntity, SelectEntity):
    """Define a base station entity."""

    def __init__(
        self,
        eufy_security: EufySecurity,
        station: Station,
        select_type: str,
        options: list[str],
        name: str,
        icon: str,
    ) -> None:
        """Initialize."""
        super().__init__(eufy_security, station)

        self._attr_icon = icon
        self._attr_name = name
        self._attr_options = options
        self._select_type = select_type

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        if self._select_type == SELECT_TYPE_GUARD_MODE:
            if state := async_get_guard_mode_as_state(
                self._eufy_security, self._station
            ):
                self._attr_current_option = state

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        code = async_get_guard_mode_as_code(self._eufy_security, self._station, option)
        await self._eufy_security.client.async_send_command(
            {
                "command": "station.set_property",
                "serialNumber": self._station.serial_number,
                "name": "guardMode",
                "value": code,
            }
        )
