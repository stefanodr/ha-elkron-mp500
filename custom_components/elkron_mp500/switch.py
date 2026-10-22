from __future__ import annotations

import time

import voluptuous as vol
from datetime import datetime, timedelta, timezone

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .protocol import DEFAULT_PAUSE_MINUTES

SWITCH_ENTITY_ID = "switch.elkron_mp500_connessione"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ElkronConnectionSwitch(data["coordinator"], data["client"], data["logins"], entry)])
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service("reset_login_counter", {}, "async_reset_login_counter")
    platform.async_register_entity_service(
        "pause", {vol.Optional("minutes", default=DEFAULT_PAUSE_MINUTES): vol.All(vol.Coerce(float), vol.Range(min=1, max=120))},
        "async_pause",
    )


class ElkronConnectionSwitch(CoordinatorEntity, SwitchEntity):
    """On: the integration holds the panel's single web login.
    Off: paused, so the web page or the Android app can log in; resumes by itself."""

    _attr_should_poll = False
    _attr_icon = "mdi:lan-connect"

    def __init__(self, coordinator, client, logins, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._client = client
        self._logins = logins
        self._attr_unique_id = f"{entry.entry_id}_connection"
        self.entity_id = SWITCH_ENTITY_ID
        self._attr_name = "Connessione centrale"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}

    @property
    def available(self) -> bool:
        # Always available: it is the way out of a pause.
        return True

    @property
    def is_on(self) -> bool:
        return not self._client.paused

    @property
    def extra_state_attributes(self):
        attrs = {"login_totali": self._logins.count, "contatore_dal": self._logins.since}
        if self._client.paused:
            left = max(0.0, self._client.resume_at - time.monotonic())
            attrs["riprende_alle"] = (datetime.now(timezone.utc) + timedelta(seconds=left)).isoformat(
                timespec="seconds"
            )
        return attrs

    async def async_turn_off(self, **kwargs) -> None:
        await self._client.pause(DEFAULT_PAUSE_MINUTES)
        self.async_write_ha_state()
        self.coordinator.async_update_listeners()

    async def async_turn_on(self, **kwargs) -> None:
        self._client.resume()
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_reset_login_counter(self) -> None:
        """Call after restarting the panel: counts logins from zero again."""
        self._logins.reset()
        self.async_write_ha_state()

    async def async_pause(self, minutes: float = DEFAULT_PAUSE_MINUTES) -> None:
        await self._client.pause(minutes)
        self.async_write_ha_state()
        self.coordinator.async_update_listeners()
