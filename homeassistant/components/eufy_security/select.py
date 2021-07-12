"""Support for Eufy Security select entities."""
from typing import Any

from eufy_security_ws_python.model.station import Station

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import StationEntity
from .const import DATA_CLIENT, DATA_METADATA, DOMAIN

GUARD_STATE_AWAY = "away"
GUARD_STATE_CUSTOM1 = "custom_1"
GUARD_STATE_CUSTOM2 = "custom_2"
GUARD_STATE_CUSTOM3 = "custom_3"
GUARD_STATE_DISARMED = "disarmed"
GUARD_STATE_GEO = "geo"
GUARD_STATE_HOME = "home"
GUARD_STATE_OFF = "off"
GUARD_STATE_SCHEDULE = "schedule"

GUARD_STATE_MAP = {
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
    SELECT_TYPE_GUARD_MODE: (list(GUARD_STATE_MAP.values()), "Guard Mode", "mdi:shield")
}


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
                    hass.data[DOMAIN][DATA_METADATA][entry.entry_id][serial_number],
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
        metadata: dict[str, Any],
        station: Station,
        select_type: str,
        options: list[str],
        name: str,
        icon: str,
    ) -> None:
        """Initialize."""
        super().__init__(metadata, station)

        self._attr_icon = icon
        self._attr_name = name
        self._attr_options = options
        self._select_type = select_type

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        if self._select_type == SELECT_TYPE_GUARD_MODE:
            state_int_str = str(self._station.guard_mode)
            raw_state = self._metadata["guardMode"]["states"][state_int_str]
            self._attr_current_option = GUARD_STATE_MAP[raw_state]
