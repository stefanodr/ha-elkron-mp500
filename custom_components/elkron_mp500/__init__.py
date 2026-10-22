from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_PLANT_ID,
    CONF_TECH_CODE,
    CONF_WEB_PASSWORD,
    CONF_WEB_USER,
    DEFAULT_PLANT_ID,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TECH_CODE,
    MIN_SCAN_INTERVAL,
    ALARM_ENTITY_ID,
    DOMAIN,
    input_entity_id,
)
from .protocol import ElkronBackoffError, ElkronBusyError, ElkronPausedError, ElkronTcpClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "alarm_control_panel", "switch"]

# How long the last valid state is shown after a failed reading before the
# entities become unavailable (a stale door state must not look current).
STALE_GRACE = 90


class LoginCounter:
    """Logins made on the panel since the user last said it was restarted.

    The panel was seen to stop answering after many logins; this number tells how
    many it can take. It survives Home Assistant restarts.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store(hass, 1, f"{DOMAIN}_logins_{entry_id}")
        self.count = 0
        self.since = datetime.now(timezone.utc).isoformat(timespec="seconds")

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.count = int(data.get("count", 0))
        self.since = data.get("since", self.since)

    def _data(self) -> dict:
        return {"count": self.count, "since": self.since}

    def increment(self) -> None:
        self.count += 1
        self._store.async_delay_save(self._data, 30)

    def reset(self) -> None:
        self.count = 0
        self.since = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._store.async_delay_save(self._data, 1)


class ElkronCoordinator(DataUpdateCoordinator[dict]):
    """Coordinate the single TCP poll used by all Elkron entities."""

    def __init__(self, hass: HomeAssistant, client: ElkronTcpClient, interval: int) -> None:
        self.client = client
        self._last_valid_data: dict | None = None
        self._last_ok = 0.0
        super().__init__(
            hass,
            _LOGGER,
            name="Elkron MP500",
            update_interval=timedelta(seconds=interval),
        )

    async def _async_update_data(self) -> dict:
        try:
            data = await self.client.read_state()
            self._last_valid_data = data
            self._last_ok = time.monotonic()
            return data
        except ElkronPausedError as err:
            # On purpose: show the entities as unavailable, not as stale.
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            quiet = isinstance(err, (ElkronBackoffError, ElkronBusyError))
            fresh = time.monotonic() - self._last_ok < STALE_GRACE
            if self._last_valid_data is not None and fresh:
                # Short interruption: keep the last state for a while.
                if quiet:
                    _LOGGER.debug("Lettura rimandata: %s", err)
                else:
                    _LOGGER.warning(
                        "Lettura IT500WEB non riuscita; mantengo per poco l'ultimo stato valido. "
                        "Errore: %s",
                        err,
                    )
                return self._last_valid_data
            if quiet:
                _LOGGER.debug("Lettura non possibile: %s", err)
            raise UpdateFailed(f"Comunicazione IT500WEB: {err}") from err


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate entries from earlier versions of the integration.

    Version 5: the web user and password are no longer stored (they are only
    needed once, to read the names), and the plant/technical codes are saved.
    """
    if entry.version < 5:
        data = {k: v for k, v in entry.data.items() if k not in (CONF_WEB_USER, CONF_WEB_PASSWORD)}
        data.setdefault(CONF_PORT, DEFAULT_PORT)
        data.setdefault(CONF_PLANT_ID, DEFAULT_PLANT_ID)
        data.setdefault(CONF_TECH_CODE, DEFAULT_TECH_CODE)
        hass.config_entries.async_update_entry(entry, data=data, version=5)
    return True


def _desired_entity_id(unique_id: str, entry_id: str) -> str | None:
    if unique_id == f"{entry_id}_alarm":
        return ALARM_ENTITY_ID
    prefix = f"{entry_id}_input_"
    if unique_id.startswith(prefix) and unique_id[len(prefix):].isdigit():
        return input_entity_id(int(unique_id[len(prefix):]))
    return None


@callback
def async_fix_entity_ids(registry: er.EntityRegistry, entry: ConfigEntry) -> None:
    """One-time move of entities created by earlier versions to the stable ids.

    Earlier versions derived the id from the name ("binary_sensor.ingresso_1_...").
    An id that is already taken is left alone.
    """
    for item in er.async_entries_for_config_entry(registry, entry.entry_id):
        wanted = _desired_entity_id(item.unique_id, entry.entry_id)
        if wanted and item.entity_id != wanted and registry.async_get(wanted) is None:
            _LOGGER.info("Entità %s rinominata in %s", item.entity_id, wanted)
            registry.async_update_entity(item.entity_id, new_entity_id=wanted)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = ElkronTcpClient(
        entry.data[CONF_HOST],
        int(entry.data.get(CONF_PORT, DEFAULT_PORT)),
        plant_id=entry.data.get(CONF_PLANT_ID, DEFAULT_PLANT_ID),
        tech_code=entry.data.get(CONF_TECH_CODE, DEFAULT_TECH_CODE),
    )
    # Each reading is a complete session on the panel: never poll faster than
    # the minimum, whatever an older configuration says.
    interval = max(
        MIN_SCAN_INTERVAL,
        int(
            entry.options.get(
                CONF_SCAN_INTERVAL,
                entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            )
        ),
    )
    coordinator = ElkronCoordinator(hass, client, interval)
    counter = LoginCounter(hass, entry.entry_id)
    await counter.async_load()
    client.on_login = counter.increment

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await client.close()
        raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "logins": counter,
    }
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    async_fix_entity_ids(er.async_get(hass), entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if data is not None:
            await data["client"].close()
    return unload_ok
