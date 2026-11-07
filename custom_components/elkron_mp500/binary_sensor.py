from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_NAMES,
    CONF_STRUCTURE,
    CONF_TYPES,
    DEFAULT_INPUT_TYPE,
    DOMAIN,
    ALARM_MEMORY_ENTITY_ID,
    INPUT_ALARM,
    INPUT_OPEN,
    input_entity_id,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    names = entry.options.get(CONF_NAMES, {})
    types = entry.options.get(CONF_TYPES, {})
    structure = entry.options.get(CONF_STRUCTURE) or {}
    panel_sensors = structure.get("sensors", {})
    panel_sectors = structure.get("sectors", {})
    # One sensor per byte of the panel's 0x84 reply, not a fixed list.
    count = len(coordinator.data["inputs"])
    async_add_entities(
        ElkronInputSensor(
            coordinator,
            entry,
            input_id,
            # A name typed in the options wins; otherwise the name the panel reports.
            names.get(str(input_id)) or panel_sensors.get(str(input_id), {}).get("name", ""),
            types.get(str(input_id), DEFAULT_INPUT_TYPE),
            [
                f"{sector} - {panel_sectors[str(sector)]}" if panel_sectors.get(str(sector)) else str(sector)
                for sector in panel_sensors.get(str(input_id), {}).get("sectors", [])
            ],
        )
        for input_id in range(1, count + 1)
    )
    async_add_entities([ElkronAlarmMemorySensor(coordinator, entry)])


class ElkronInputSensor(CoordinatorEntity, BinarySensorEntity):
    """One input byte of the MP500 reply: open (0x02) or closed.

    The panel does not say what is wired to each input, so the type
    (opening, door, window, motion) is an option; it sets the device class.
    """

    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        input_id: int,
        input_name: str,
        input_type: str,
        sectors: list[str] | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._input_id = input_id
        self._attr_device_class = BinarySensorDeviceClass(input_type)
        self._sectors = sectors or []
        self._attr_unique_id = f"{entry.entry_id}_input_{input_id}"
        self.entity_id = input_entity_id(input_id)  # stable id, whatever the name
        self._attr_name = (
            f"Ingresso {input_id} ({input_name})" if input_name else f"Ingresso {input_id}"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Elkron MP500",
            "manufacturer": "Elkron",
            "model": coordinator.client.model or "MP500 / IT500WEB",
        }

    @property
    def is_on(self) -> bool | None:
        states = self.coordinator.data["inputs"]
        if self._input_id > len(states):
            return None
        # Bit test: 0x06 (open and in alarm) is open too.
        return bool(states[self._input_id - 1] & INPUT_OPEN)

    @property
    def icon(self) -> str | None:
        # door, window and motion get their icon from the device class; the
        # generic "opening" type gets a door icon that follows the state.
        if self._attr_device_class == BinarySensorDeviceClass.OPENING:
            return "mdi:door-open" if self.is_on else "mdi:door-closed"
        return None

    @property
    def extra_state_attributes(self):
        states = self.coordinator.data["inputs"]
        if self._input_id > len(states):
            return {}
        value = states[self._input_id - 1]
        attrs = {"raw_state": value, "allarme": bool(value & INPUT_ALARM)}
        if self._sectors:
            attrs["settori"] = self._sectors
        return attrs


class ElkronAlarmMemorySensor(CoordinatorEntity, BinarySensorEntity):
    """On while the panel remembers an alarm raised by one or more inputs."""

    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alarm-light"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_alarm_memory"
        self.entity_id = ALARM_MEMORY_ENTITY_ID
        self._attr_name = "Memoria allarme"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Elkron MP500",
            "manufacturer": "Elkron",
            "model": coordinator.client.model or "MP500 / IT500WEB",
        }

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("alarm_memory"))

    @property
    def extra_state_attributes(self):
        return {"ingressi": self.coordinator.data.get("alarm_memory", [])}
