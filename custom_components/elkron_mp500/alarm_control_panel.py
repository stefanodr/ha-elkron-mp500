from __future__ import annotations

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ALARM_ENTITY_ID, DOMAIN
from .protocol import STATE_ARMED, STATE_DISARMED


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ElkronAlarmPanel(data["coordinator"], data["client"], entry)])


class ElkronAlarmPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Overall MP500 alarm state and arm/disarm controls."""

    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY
    _attr_should_poll = False
    _attr_code_arm_required = False

    def __init__(self, coordinator, client, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_alarm"
        self.entity_id = ALARM_ENTITY_ID  # stable id
        self._attr_name = "Sistema"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Elkron MP500",
            "manufacturer": "Elkron",
            "model": client.model or "MP500 / IT500WEB",
        }

    @property
    def extra_state_attributes(self):
        # Diagnostic: how many HTTP+TCP sessions were opened since HA started.
        # It should stay close to 1; a number that keeps growing means the
        # connection drops and each login is written to the panel's history.
        return {
            "sessioni_aperte": self._client.bootstraps,
            "stato_grezzo": self.coordinator.data["global_state"].hex(" "),
        }

    @property
    def state(self) -> AlarmControlPanelState:
        raw = self.coordinator.data["global_state"]
        if raw[:2] == STATE_ARMED:
            return AlarmControlPanelState.ARMED_AWAY
        if raw[:2] == STATE_DISARMED:
            return AlarmControlPanelState.DISARMED
        # Any other value (for example some sectors armed from the panel or
        # the app): the integration only arms/disarms everything, so report
        # "partially armed" and expose the raw value in `stato_grezzo`.
        return AlarmControlPanelState.ARMED_CUSTOM_BYPASS

    async def async_alarm_arm_away(self, code=None) -> None:
        await self._client.arm()
        await self.coordinator.async_request_refresh()

    async def async_alarm_disarm(self, code=None) -> None:
        await self._client.disarm()
        await self.coordinator.async_request_refresh()
