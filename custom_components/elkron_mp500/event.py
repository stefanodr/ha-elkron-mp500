from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ALARM_EVENT_ENTITY_ID,
    DOMAIN,
    EVENT_ALARM_STOPPED,
    EVENT_ALARM_TRIGGERED,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([ElkronAlarmEvent(hass.data[DOMAIN][entry.entry_id]["coordinator"], entry)])


class ElkronAlarmEvent(CoordinatorEntity, EventEntity):
    """Fires when the alarm starts and when it ends.

    Unlike the state of the alarm panel, an event is delivered once per
    occurrence, so an automation cannot miss a short alarm.
    """

    _attr_should_poll = False
    _attr_event_types = [EVENT_ALARM_TRIGGERED, EVENT_ALARM_STOPPED]
    _attr_icon = "mdi:alarm-light-outline"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._was_triggered = bool((coordinator.data or {}).get("triggered"))
        self._attr_unique_id = f"{entry.entry_id}_alarm_event"
        self.entity_id = ALARM_EVENT_ENTITY_ID
        self._attr_name = "Allarme"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Elkron MP500",
            "manufacturer": "Elkron",
            "model": coordinator.client.model or "MP500 / IT500WEB",
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        triggered = bool(data.get("triggered"))
        if triggered != self._was_triggered:
            self._was_triggered = triggered
            self._trigger_event(
                EVENT_ALARM_TRIGGERED if triggered else EVENT_ALARM_STOPPED,
                {"ingressi": data.get("alarm_inputs", [])},
            )
        super()._handle_coordinator_update()
