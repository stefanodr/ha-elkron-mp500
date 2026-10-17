from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_NAMES,
    CONF_PLANT_ID,
    CONF_PORT,
    CONF_REFRESH,
    CONF_SCAN_INTERVAL,
    CONF_STRUCTURE,
    CONF_TECH_CODE,
    CONF_TYPES,
    CONF_WEB_PASSWORD,
    CONF_WEB_USER,
    DEFAULT_HOST,
    DEFAULT_INPUT_TYPE,
    DEFAULT_PLANT_ID,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TECH_CODE,
    DOMAIN,
    INPUT_TYPES,
    MAX_NAMED_INPUTS,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .protocol import (
    ElkronAuthError,
    ElkronBusyError,
    ElkronTcpClient,
    fetch_structure,
    valid_plant_id,
    valid_tech_code,
)

_LOGGER = logging.getLogger(__name__)

_INTERVAL = vol.All(
    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
)
_PASSWORD = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)


async def _web_structure(host: str, user: str, password: str) -> tuple[dict | None, str | None]:
    """Fetch names/sectors; return (structure, error_key)."""
    if not user or not password:
        return None, "web_credentials_missing"
    try:
        return await fetch_structure(host, user, password), None
    except ElkronBusyError:
        return None, "web_busy"
    except ElkronAuthError:
        return None, "web_login_failed"
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Lettura nomi dal Web Server IT500WEB fallita su %s: %r", host, err)
        return None, "web_failed"


class ElkronConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle configuration of the local Elkron MP500 TCP connection."""

    VERSION = 5

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return ElkronOptionsFlow()

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            plant_id = (user_input.get(CONF_PLANT_ID) or DEFAULT_PLANT_ID).strip()
            tech_code = (user_input.get(CONF_TECH_CODE) or DEFAULT_TECH_CODE).strip()
            if not valid_plant_id(plant_id):
                errors[CONF_PLANT_ID] = "invalid_plant_id"
            if not valid_tech_code(tech_code):
                errors[CONF_TECH_CODE] = "invalid_tech_code"
            client = ElkronTcpClient(
                host,
                int(user_input[CONF_PORT]),
                timeout=5,
                plant_id=plant_id if not errors else DEFAULT_PLANT_ID,
                tech_code=tech_code if not errors else DEFAULT_TECH_CODE,
            )
            try:
                if not errors:
                    await client.read_state()
            except ElkronBusyError:
                errors["base"] = "web_busy"
            except ElkronAuthError:
                errors["base"] = "local_auth_failed"
            except ConnectionRefusedError as err:
                _LOGGER.warning(
                    "IT500WEB rifiuta la connessione TCP su %s:%s: %s",
                    host,
                    user_input[CONF_PORT],
                    err,
                )
                errors["base"] = "connection_refused"
            except TimeoutError as err:
                _LOGGER.warning(
                    "Timeout collegando IT500WEB su %s:%s: %s",
                    host,
                    user_input[CONF_PORT],
                    err,
                )
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.warning(
                    "Connessione IT500WEB fallita su %s:%s (%s): %r",
                    host,
                    user_input[CONF_PORT],
                    type(err).__name__,
                    err,
                )
                errors["base"] = "cannot_connect"
            finally:
                await client.close()

            structure = None
            web_user = (user_input.get(CONF_WEB_USER) or "").strip()
            if not errors and web_user:
                structure, error = await _web_structure(
                    host, web_user, user_input.get(CONF_WEB_PASSWORD) or ""
                )
                if error:
                    errors["base"] = error

            if not errors:
                await self.async_set_unique_id(f"{host}:{user_input[CONF_PORT]}")
                self._abort_if_unique_id_configured()
                # The web user and password are used once, to read the names,
                # and are NOT stored.
                data = {
                    CONF_HOST: host,
                    CONF_PORT: int(user_input[CONF_PORT]),
                    CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    CONF_PLANT_ID: plant_id,
                    CONF_TECH_CODE: tech_code,
                }
                return self.async_create_entry(
                    title=f"Elkron MP500 ({host})",
                    data=data,
                    options={CONF_STRUCTURE: structure} if structure else {},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): _INTERVAL,
                vol.Optional(CONF_WEB_USER): str,
                vol.Optional(CONF_WEB_PASSWORD): _PASSWORD,
                vol.Optional(CONF_PLANT_ID, default=DEFAULT_PLANT_ID): str,
                vol.Optional(CONF_TECH_CODE, default=DEFAULT_TECH_CODE): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class ElkronOptionsFlow(config_entries.OptionsFlow):
    """Polling interval, web login for names, and name/type of each input."""

    def _count(self) -> int:
        runtime = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        data = runtime["coordinator"].data if runtime else None
        return min(len(data["inputs"]) if data else 8, MAX_NAMED_INPUTS)

    def _form(self, defaults: dict, errors: dict | None = None) -> FlowResult:
        entry = self.config_entry
        count = self._count()
        names = defaults.get(CONF_NAMES, entry.options.get(CONF_NAMES, {}))
        types = defaults.get(CONF_TYPES, entry.options.get(CONF_TYPES, {}))
        type_selector = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(INPUT_TYPES),
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="input_type",
            )
        )
        schema: dict = {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=defaults.get(
                    CONF_SCAN_INTERVAL,
                    entry.options.get(
                        CONF_SCAN_INTERVAL,
                        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ),
                ),
            ): _INTERVAL,
            vol.Optional(
                CONF_WEB_USER,
                description={"suggested_value": defaults.get(CONF_WEB_USER, "")},
            ): str,
            vol.Optional(CONF_WEB_PASSWORD): _PASSWORD,
            vol.Optional(CONF_REFRESH, default=False): bool,
        }
        for i in range(1, count + 1):
            schema[
                vol.Optional(
                    f"name_{i}", description={"suggested_value": names.get(str(i), "")}
                )
            ] = str
            schema[
                vol.Optional(f"type_{i}", default=types.get(str(i), DEFAULT_INPUT_TYPE))
            ] = type_selector
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema), errors=errors or {}
        )

    async def async_step_init(self, user_input=None) -> FlowResult:
        entry = self.config_entry
        if user_input is None:
            return self._form({})

        count = self._count()
        names = {
            str(i): user_input[f"name_{i}"].strip()
            for i in range(1, count + 1)
            if user_input.get(f"name_{i}", "").strip()
        }
        types = {
            str(i): user_input[f"type_{i}"]
            for i in range(1, count + 1)
            if user_input.get(f"type_{i}", DEFAULT_INPUT_TYPE) != DEFAULT_INPUT_TYPE
        }
        # User and password are only used when "Rileggi i nomi" is ticked, and
        # are never stored.
        web_user = (user_input.get(CONF_WEB_USER) or "").strip()
        web_password = user_input.get(CONF_WEB_PASSWORD) or ""
        structure = entry.options.get(CONF_STRUCTURE)

        if user_input.get(CONF_REFRESH):
            new_structure, error = await _web_structure(
                entry.data[CONF_HOST], web_user, web_password
            )
            if error:
                return self._form(
                    {
                        CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                        CONF_WEB_USER: web_user,
                        CONF_NAMES: names,
                        CONF_TYPES: types,
                    },
                    {"base": error},
                )
            structure = new_structure
            # Names typed by hand are replaced by the panel's names.
            names = {}

        options = {
            CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
            CONF_NAMES: names,
            CONF_TYPES: types,
        }
        if structure:
            options[CONF_STRUCTURE] = structure
        return self.async_create_entry(title="", data=options)
