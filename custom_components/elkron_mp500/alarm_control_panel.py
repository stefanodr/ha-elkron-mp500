from __future__ import annotations

import logging
import time

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    CodeFormat,
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ALARM_ENTITY_ID, CONF_DISARM_HASH, CONF_DISARM_SALT, DOMAIN
from .disarm_code import AttemptLimiter, verify_code
from .protocol import STATE_ARMED, STATE_DISARMED

_LOGGER = logging.getLogger(__name__)

KEYPAD_KEYS = "0123456789C"
KEYPAD_TIMEOUT = 30  # seconds of inactivity before the typed digits are dropped


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ElkronAlarmPanel(data["coordinator"], data["client"], entry)])
    # On-screen keypad used by the dashboard card: the digits live only in
    # memory (never in the state machine or the recorder).
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "keypad_press", {vol.Required("key"): vol.In(list(KEYPAD_KEYS))}, "async_keypad_press"
    )
    platform.async_register_entity_service("keypad_submit", {}, "async_keypad_submit")


class ElkronAlarmPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Overall MP500 alarm state and arm/disarm controls."""

    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY
    _attr_should_poll = False
    _attr_code_arm_required = False

    def __init__(self, coordinator, client, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._client = client
        self._entry = entry
        self._limiter = AttemptLimiter()
        self._digits = ""
        self._digits_at = 0.0
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
            "cifre_digitate": len(self._digits),
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

    async def _async_command(self, action: str, command) -> None:
        """Run arm/disarm; show the real cause in the UI instead of "unknown error"."""
        try:
            await command()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Comando %s non riuscito (%s): %s", action, type(err).__name__, err, exc_info=True
            )
            raise HomeAssistantError(f"{action} non riuscito: {err}") from err
        finally:
            # The panel may have changed state even if the reply was unexpected.
            await self.coordinator.async_request_refresh()

    async def async_alarm_arm_away(self, code=None) -> None:
        await self._async_command("Inserimento", self._client.arm)

    @property
    def code_format(self) -> CodeFormat | None:
        # A numeric keypad is shown (and a code expected) only to disarm, and only
        # when a code was set in the options. Arming never asks for it.
        return CodeFormat.NUMBER if self._code_configured else None

    @property
    def _code_configured(self) -> bool:
        options = getattr(self._entry, "options", {}) or {}
        return bool(options.get(CONF_DISARM_HASH) and options.get(CONF_DISARM_SALT))

    def _check_disarm_code(self, code) -> None:
        """Raise ServiceValidationError unless the disarm code is right (if one is set)."""
        if not self._code_configured:
            return
        locked = self._limiter.seconds_locked()
        if locked:
            raise ServiceValidationError(
                f"Troppi codici errati: disinserimento bloccato per altri {locked} secondi."
            )
        options = self._entry.options
        if not verify_code(code, options[CONF_DISARM_SALT], options[CONF_DISARM_HASH]):
            self._limiter.failed()
            _LOGGER.warning("Disinserimento rifiutato: codice mancante o errato")
            raise ServiceValidationError("Codice non valido: disinserimento non eseguito.")
        self._limiter.succeeded()

    async def async_alarm_disarm(self, code=None) -> None:
        self._check_disarm_code(code)
        await self._async_command("Disinserimento", self._client.disarm)

    # ---- on-screen keypad -------------------------------------------------
    def _fresh_digits(self) -> str:
        if self._digits and time.monotonic() - self._digits_at > KEYPAD_TIMEOUT:
            self._digits = ""
        return self._digits

    async def async_keypad_press(self, key: str) -> None:
        digits = self._fresh_digits()
        self._digits = "" if key == "C" else (digits + key)[:6]
        self._digits_at = time.monotonic()
        self.async_write_ha_state()

    async def async_keypad_submit(self) -> None:
        """Check the code now, then send the command in the background.

        The panel needs several seconds to execute the command; the dashboard
        keypad should not stay open for that long. A wrong code is still
        reported at once; a later failure of the command is shown as a
        persistent notification.
        """
        code = self._fresh_digits()
        self._digits = ""
        self.async_write_ha_state()
        self._check_disarm_code(code)
        self.hass.async_create_task(self._async_background_disarm())

    async def _async_background_disarm(self) -> None:
        try:
            await self._async_command("Disinserimento", self._client.disarm)
        except HomeAssistantError as err:
            from homeassistant.components import persistent_notification

            persistent_notification.async_create(
                self.hass,
                str(err),
                title="Elkron MP500",
                notification_id=f"{DOMAIN}_disarm_failed",
            )
