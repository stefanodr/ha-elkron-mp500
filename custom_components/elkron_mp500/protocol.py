from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time

import aiohttp

_LOGGER = logging.getLogger(__name__)

# Factory defaults of the plant code ("codice impianto", 8 digits) and of the
# technical code ("codice tecnico"). Both are asked in the configuration, so
# other installations can use their own. The HTTP bootstrap (clogin) enables the
# TCP service; the TCP startup commands receive one-byte acknowledgements.
DEFAULT_PLANT_ID = "55555555"
DEFAULT_TECH_CODE = "000000"
CMD_MODE_2 = {"cmd": 2}
CMD_MODE_3 = {"cmd": 3}

# The IT500WEB is a small embedded server: it was seen to stop answering the
# /user/*.cgi pages (404) after many logins and to need a power cycle. After a
# failed bootstrap the integration therefore waits, with a growing delay, before
# trying again instead of repeating the login on every poll.
BACKOFF_FIRST = 60.0
BACKOFF_MAX = 900.0

CMD_START = bytes.fromhex("81 55 55 00 00 00 00 60 fe f6 03")


def _checksum(body: bytes) -> int:
    """16-bit two's complement of the byte sum (frame bytes after 0x81)."""
    return (-sum(body)) & 0xFFFF


def build_session_frame(plant_id: str) -> bytes:
    """0x49 session frame. The plant code travels as 4 BCD bytes (8 digits).

    With the factory plant code 55555555 this is exactly the frame captured
    from Hi-Connect. For other plant codes the bytes follow the same layout,
    but that has not been verified on a real panel.
    """
    body = bytes.fromhex("55 55 00 00 07 00 49") + bytes.fromhex(plant_id) + bytes(3)
    return b"\x81" + body + _checksum(body).to_bytes(2, "big") + b"\x03"


def valid_plant_id(value: str) -> bool:
    return bool(re.fullmatch(r"\d{8}", value or ""))


def valid_tech_code(value: str) -> bool:
    return bool(re.fullmatch(r"\d{4,8}", value or ""))


CMD_SESSION = build_session_frame(DEFAULT_PLANT_ID)
CMD_KEEPALIVE = bytes.fromhex("81 55 55 00 00 00 00 65 fe f1 03")

# State/command frames from the Hi-Connect capture (traffico_hi_connect.pcapng).
CMD_INPUTS = bytes.fromhex("81 55 55 00 00 00 00 84 fe d2 03")
CMD_GLOBAL_STATE = bytes.fromhex("81 55 55 00 00 00 00 80 fe d6 03")
# Arm/disarm: TCP command 0x11, answered by an event record (command 0x12).
# 16 bytes each.
# The payload 81 ff 00 xx 00 looks like a sector mask, but that is unverified.
CMD_ARM = bytes.fromhex("81 55 55 00 00 04 00 11 81 ff 00 ff 00 fc d3 03")
CMD_DISARM = bytes.fromhex("81 55 55 00 00 04 00 11 81 ff 00 00 00 fd d2 03")
RESP_EVENT = 0x12

# Global state payload (command 0x80): ff 00 = armed, 00 00 = disarmed.
STATE_ARMED = b"\xff\x00"
STATE_DISARMED = b"\x00\x00"


class ElkronProtocolError(Exception):
    """Raised when the IT500WEB protocol returns an unexpected frame."""


class ElkronBusyError(ElkronProtocolError):
    """The web server answered 503: someone else is using it. Retry later."""


class ElkronRejectedError(ElkronProtocolError):
    """The web server answered but refused the command (result != ACK)."""


class ElkronAuthError(ElkronProtocolError):
    """A login was refused (web user/password, or plant code/technical code)."""


_SENSOR_PREFIX = re.compile(r"^\s*Ingresso\s+\d+\s*-\s*", re.IGNORECASE)
_SECTOR_PREFIX = re.compile(r"^\s*Settore\s+\d+\s*-\s*", re.IGNORECASE)


async def fetch_structure(host: str, user: str, password: str, timeout: float = 8.0) -> dict:
    """Read input and sector names from the web API with one short login.

    Sequence seen in the browser capture: GET /sys/info.cgi (cookie), POST
    /user/login.cgi, GET /spweco/plantstructure.cgi, POST /user/logout.cgi.
    The 6-digit user code is not needed for this. The session lasts well
    under a second, so apps and Hi-Connect are not kept out.
    """
    base = f"http://{host}"
    jar = aiohttp.CookieJar(unsafe=True)
    client_timeout = aiohttp.ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(
        timeout=client_timeout,
        cookie_jar=jar,
        headers={"User-Agent": "Home Assistant Elkron MP500"},
    ) as http:

        async def call(method: str, path: str, payload: dict | None = None) -> dict:
            kwargs: dict = {}
            if payload is not None:
                kwargs = {
                    "data": json.dumps(payload, separators=(",", ":")),
                    "headers": {"Content-Type": "application/json; charset=utf-8"},
                }
            async with http.request(method, base + path, **kwargs) as response:
                status = response.status
                body = await response.text()
            if status == 503:
                raise ElkronBusyError(f"Web server occupato ({path})")
            if status != 200:
                raise ElkronProtocolError(f"HTTP {path}: stato {status}")
            try:
                result = json.loads(body)
            except (TypeError, json.JSONDecodeError) as err:
                raise ElkronProtocolError(f"Risposta non JSON da {path}") from err
            if result.get("result") != "ACK":
                if path == "/user/login.cgi":
                    raise ElkronAuthError("Utente o password del Web Server rifiutati")
                raise ElkronProtocolError(f"Comando rifiutato da {path}")
            return result

        await call("GET", "/sys/info.cgi")
        # The panel's web page sends md5(md5(password)) as 32 lowercase hex;
        # clear text is refused (checked against a browser capture).
        pwd_hash = hashlib.md5(
            hashlib.md5(password.encode("utf-8")).hexdigest().encode("ascii")
        ).hexdigest()
        await call("POST", "/user/login.cgi", {"user": user, "pwd": pwd_hash})
        try:
            result = await call("GET", "/spweco/plantstructure.cgi")
        finally:
            try:
                await call("POST", "/user/logout.cgi", {})
            except Exception as err:  # noqa: BLE001 - logout is best effort
                _LOGGER.debug("Logout web IT500WEB non riuscito: %r", err)

    data = result.get("data") or {}
    sensors = {
        str(item["NID"]): {
            "name": _SENSOR_PREFIX.sub("", item.get("NAME", "")).strip(),
            "sectors": [int(s) for s in item.get("PID", [])],
        }
        for item in data.get("cfgsensor", [])
    }
    sectors = {
        str(item["NID"]): _SECTOR_PREFIX.sub("", item.get("NAME", "")).strip()
        for item in data.get("cfgzone", [])
    }
    if not sensors:
        raise ElkronProtocolError("Struttura impianto vuota")
    return {"sensors": sensors, "sectors": sectors}


class ElkronTcpClient:
    """IT500WEB session: captured HTTP bootstrap followed by persistent TCP."""

    def __init__(
        self,
        host: str,
        port: int,
        timeout: float = 8.0,
        plant_id: str = DEFAULT_PLANT_ID,
        tech_code: str = DEFAULT_TECH_CODE,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._login = {"plantid": plant_id, "code": tech_code}
        self._session_frame = build_session_frame(plant_id)
        self.model: str | None = None  # "cmodel" from /sys/info.cgi, e.g. "ELKRON - MP500/8"
        self._http: aiohttp.ClientSession | None = None
        self._refresh_task: asyncio.Task | None = None
        self._bootstrap_lock = asyncio.Lock()
        self._op_lock = asyncio.Lock()  # one poll or command at a time
        self._tcp_lock = asyncio.Lock()
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._keepalive_task: asyncio.Task | None = None
        self._started = False
        self.bootstraps = 0  # HTTP+TCP sessions opened since start (diagnostic)
        self._failures = 0  # consecutive failed bootstraps
        self._retry_at = 0.0  # time.monotonic() before which no new login is tried

    @property
    def _base_url(self) -> str:
        return f"http://{self.host}"

    async def _http_request(self, path: str, payload: dict | None = None) -> dict:
        assert self._http is not None
        url = self._base_url + path
        async with asyncio.timeout(self.timeout):
            if payload is None:
                async with self._http.get(url) as response:
                    body = await response.text()
            else:
                async with self._http.post(
                    url,
                    data=("" if not payload else json.dumps(payload, separators=(",", ":"))),
                    headers={"Content-Type": "application/json; charset=utf-8"},
                ) as response:
                    body = await response.text()
        if response.status == 503:
            raise ElkronBusyError(f"Web server occupato ({path})")
        if response.status != 200:
            raise ElkronProtocolError(f"HTTP {path}: stato {response.status}")
        try:
            result = json.loads(body)
        except (TypeError, json.JSONDecodeError) as err:
            raise ElkronProtocolError(f"Risposta HTTP non JSON da {path}") from err
        if result.get("result") != "ACK":
            raise ElkronRejectedError(
                f"Comando HTTP rifiutato da {path} (risposta: {body[:200]})"
            )
        return result

    async def _ensure_http_session(self) -> None:
        if self._http is not None and not self._http.closed:
            return
        async with self._bootstrap_lock:
            if self._http is not None and not self._http.closed:
                return
            wait = self._retry_at - time.monotonic()
            if wait > 0:
                raise ElkronBusyError(
                    f"Nuovo accesso alla centrale rimandato di {int(wait) + 1} s "
                    "dopo un errore (per non sovraccaricare il modulo)"
                )
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._http = aiohttp.ClientSession(
                timeout=timeout,
                cookie_jar=aiohttp.CookieJar(unsafe=True),
                headers={"User-Agent": "Home Assistant Elkron MP500"},
            )
            try:
                # This sequence is directly visible in the Hi-Connect capture: the TCP
                # listener is opened only after CLOGIN and the two mode calls.
                info = await self._http_request("/sys/info.cgi")
                self.model = (info.get("data") or {}).get("cmodel") or self.model
                try:
                    login = await self._http_request("/user/clogin.cgi", self._login)
                except ElkronRejectedError as err:
                    raise ElkronAuthError(
                        "Accesso locale rifiutato dalla centrale: codici errati oppure un altro "
                        f"accesso (pagina web, app o Hi-Connect) è aperto in questo momento ({err})"
                    ) from err
                if login.get("data", {}).get("authlevel", 0) <= 0:
                    raise ElkronAuthError(f"Accesso locale senza permessi (risposta: {login.get('data')})")
                await self._http_request("/sys/mode.cgi", CMD_MODE_2)
                await self._http_request("/sys/info.cgi")
                await self._http_request("/sys/mode.cgi", CMD_MODE_3)
                await self._http_request("/sys/info.cgi")
            except Exception as err:
                await self._http.close()
                self._http = None
                self._failures += 1
                delay = min(BACKOFF_FIRST * 2 ** (self._failures - 1), BACKOFF_MAX)
                self._retry_at = time.monotonic() + delay
                _LOGGER.warning(
                    "Accesso a IT500WEB non riuscito (%s); nuovo tentativo tra %d s",
                    err,
                    delay,
                )
                raise
            self._failures = 0
            self._retry_at = 0.0
            self.bootstraps += 1
            _LOGGER.info("Sessione IT500WEB aperta (n. %s)", self.bootstraps)
            self._refresh_task = asyncio.create_task(self._refresh_http_session())

    async def _stop_http_refresh(self) -> None:
        task, self._refresh_task = self._refresh_task, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _release_http_session(self, reset_mode: bool = False) -> None:
        """Log out. With reset_mode, first leave the TCP service mode like Hi-Connect."""
        await self._stop_http_refresh()
        if self._http is not None and not self._http.closed:
            if reset_mode:
                try:
                    await self._http_request("/sys/mode.cgi", CMD_MODE_2)
                    await self._http_request("/sys/info.cgi")
                except Exception as err:  # noqa: BLE001 - best effort
                    _LOGGER.debug("Ritorno a modalità normale IT500WEB: %s", err)
            try:
                await self._http_request("/user/logout.cgi", {})
            except Exception as err:
                _LOGGER.warning("Logout HTTP IT500WEB non riuscito: %r", err)
            finally:
                await self._http.close()
        self._http = None

    async def _refresh_http_session(self) -> None:
        """Keep the captured Hi-Connect HTTP session alive during TCP use."""
        try:
            while self._http is not None and not self._http.closed:
                await asyncio.sleep(10)
                await self._http_request("/user/refresh.cgi")
        except asyncio.CancelledError:
            raise
        except Exception as err:
            # The login expired or was taken over (only one web login at a time):
            # forget it so the next TCP (re)connection logs in again.
            _LOGGER.warning("Sessione web IT500WEB persa (%s); sarà riaperta alla prossima connessione", err)
            http, self._http = self._http, None
            self._refresh_task = None
            if http is not None and not http.closed:
                await http.close()

    async def _read_byte(self, reader: asyncio.StreamReader, timeout: float | None = None) -> int:
        data = await asyncio.wait_for(reader.readexactly(1), timeout or self.timeout)
        return data[0]

    async def _read_response(
        self,
        reader: asyncio.StreamReader,
        allow_single_16: bool = False,
        first_timeout: float | None = None,
    ) -> bytes:
        first = await self._read_byte(reader, first_timeout)
        if first in (0x06,):
            return bytes((first,))
        if first != 0x16:
            raise ElkronProtocolError(f"Inizio risposta IT500WEB inatteso: 0x{first:02X}")

        # Hi-Connect's keepalive response is a lone 0x16. A data response is
        # 0x16 0x81 ...; read its fixed header before trusting the length byte.
        while True:
            try:
                second = await asyncio.wait_for(
                    reader.readexactly(1), min(0.25, self.timeout)
                )
            except asyncio.TimeoutError:
                if allow_single_16:
                    return bytes((first,))
                raise
            if second[0] == 0x16:
                # The previous 0x16 was a lone filler and this one may start the
                # real frame (they can arrive ~0.2 s apart after a command).
                continue
            break
        if second[0] != 0x81:
            raise ElkronProtocolError(
                f"Header risposta IT500WEB inatteso dopo 0x16: 0x{second[0]:02X}"
            )
        header = bytes((first,)) + second + await asyncio.wait_for(
            reader.readexactly(7), self.timeout
        )
        payload_length = header[6]
        if payload_length > 240:
            raise ElkronProtocolError(f"Lunghezza risposta IT500WEB non valida: {payload_length}")
        trailer = await asyncio.wait_for(
            reader.readexactly(payload_length + 3), self.timeout
        )
        frame = header + trailer
        if frame[-1] != 0x03:
            raise ElkronProtocolError(
                f"Terminatore risposta IT500WEB non valido: 0x{frame[-1]:02X}"
            )
        return frame

    async def _exchange(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        command: bytes,
        expected_command: int | None,
        *,
        allow_ack_only: bool = False,
        first_timeout: float | None = None,
        tolerate_silence: bool = False,
    ) -> bytes:
        """Send a frame and read its reply.

        With ``tolerate_silence`` a missing reply (nothing within ``first_timeout``)
        returns b"" instead of raising: used for the arm/disarm event, which the
        panel does not always send.
        """
        writer.write(command)
        await writer.drain()
        # Waiting for a data reply: a lone 0x16 (keepalive-style filler) may come
        # first. After the arm/disarm command the panel sends 0x16 about 0.3 s
        # later and the 0x12 event about 0.5 s later (Hi-Connect capture), so a
        # lone 0x16 must not end the wait.
        wait_for_data = expected_command is not None and not allow_ack_only
        try:
            while True:
                response = await self._read_response(
                    reader,
                    allow_single_16=allow_ack_only or wait_for_data,
                    first_timeout=first_timeout,
                )
                if wait_for_data:
                    if response == b"\x16":
                        continue
                    if (
                        len(response) > 8
                        and response[8] == RESP_EVENT
                        and expected_command != RESP_EVENT
                    ):
                        # A late arm/disarm event record: not the reply we wait for.
                        _LOGGER.debug("Evento 0x12 in ritardo ignorato")
                        continue
                break
        except TimeoutError:
            if tolerate_silence:
                return b""
            raise
        except ElkronProtocolError as err:
            raise ElkronProtocolError(
                f"Errore in risposta al frame {command.hex(' ')}: {err}"
            ) from err
        if response == b"\x06" or (allow_ack_only and response == b"\x16"):
            return response
        if len(response) < 12 or response[0] != 0x16:
            raise ElkronProtocolError("Risposta dati IT500WEB incompleta")
        if expected_command is not None and response[8] != expected_command:
            raise ElkronProtocolError(
                f"Risposta inattesa al comando 0x{expected_command:02X}: comando 0x{response[8]:02X}"
            )
        return response

    async def _ensure_tcp(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        if self._reader is not None and self._writer is not None and not self._writer.is_closing():
            return self._reader, self._writer
        await self._ensure_http_session()
        async with self._tcp_lock:
            if self._reader is not None and self._writer is not None and not self._writer.is_closing():
                return self._reader, self._writer
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), self.timeout
            )
            try:
                await self._exchange(self._reader, self._writer, CMD_START, None)
                await self._exchange(self._reader, self._writer, self._session_frame, None)
                # The capture shows Hi-Connect sends its first keepalive after
                # the startup ACKs and before the first state request.
                await asyncio.sleep(0.2)
                await self._exchange(
                    self._reader,
                    self._writer,
                    CMD_KEEPALIVE,
                    None,
                    allow_ack_only=True,
                )
                await asyncio.sleep(0.15)
            except Exception:
                await self._close_tcp()
                await self._release_http_session()
                raise
            self._started = True
            return self._reader, self._writer

    async def _close_tcp(self) -> None:
        task, self._keepalive_task = getattr(self, "_keepalive_task", None), None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        writer, self._writer = self._writer, None
        self._reader = None
        self._started = False
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _end_session(self) -> None:
        """Close TCP and leave the web session like Hi-Connect, freeing the panel."""
        await self._close_tcp()
        await self._release_http_session(reset_mode=True)

    async def read_state(self) -> dict:
        """One complete session per reading (login, TCP read, exit).

        The panel accepts a single web login at a time and drops the TCP service
        about a minute after the login is released, so keeping a connection open
        does not work. Each reading opens a session and closes it, which leaves
        the web page, the app and Hi-Connect free between two readings.
        """
        async with self._op_lock:
            try:
                return await self._read_state_locked()
            finally:
                await self._end_session()

    async def _read_global_state(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> bytes:
        frame = await self._exchange(reader, writer, CMD_GLOBAL_STATE, 0x80)
        if frame[0] != 0x16 or frame[6] != 2 or len(frame) != 14:
            raise ElkronProtocolError("Risposta stato generale non valida")
        return bytes(frame[9:11])

    async def _read_state_locked(self) -> dict:
        reader, writer = await self._ensure_tcp()
        try:
            async with self._tcp_lock:
                input_frame = await self._exchange(
                    writer=writer,
                    reader=reader,
                    command=CMD_INPUTS,
                    expected_command=0x84,
                )
                global_frame = await self._exchange(
                    writer=writer,
                    reader=reader,
                    command=CMD_GLOBAL_STATE,
                    expected_command=0x80,
                )
        except Exception as err:
            _LOGGER.warning(
                "Lettura IT500WEB non riuscita (%r); sessioni aperte finora: %s",
                err,
                self.bootstraps,
            )
            raise
        # 0x84 reply: 16 81 55 55 00 00 <n> 00 84 <n input bytes> <2 checksum> 03
        input_count = input_frame[6]
        if (
            input_frame[0] != 0x16
            or input_count < 1
            or len(input_frame) != 12 + input_count
        ):
            raise ElkronProtocolError("Risposta ingressi non valida")
        if global_frame[0] != 0x16 or global_frame[6] != 2 or len(global_frame) != 14:
            raise ElkronProtocolError("Risposta stato generale non valida")
        return {
            "inputs": list(input_frame[9 : 9 + input_count]),
            "global_state": bytes(global_frame[9:11]),
        }

    async def _set_armed(self, armed: bool) -> None:
        """Send the TCP arm/disarm command and confirm it via the global state.

        /sys/mode.cgi does NOT arm or disarm: it only switches the module's
        sysmode (1 idle, 2/3 TCP service). Arm/disarm is TCP command 0x11.
        The command is sent after a fresh Hi-Connect-style bootstrap (HTTP
        login, mode 2/3, TCP start) so the panel sees the captured sequence.
        """
        command = CMD_ARM if armed else CMD_DISARM
        expected = STATE_ARMED if armed else STATE_DISARMED
        async with self._op_lock:
            await self._close_tcp()
            await self._release_http_session()
            # A command is an explicit request: do not wait for the back-off of the
            # periodic readings, and try once more if another web login (app,
            # Hi-Connect, web page) is busy for a few seconds.
            self._retry_at = 0.0
            try:
                reader, writer = await self._ensure_tcp()
            except (ElkronAuthError, ElkronBusyError):
                await asyncio.sleep(5)
                self._retry_at = 0.0
                reader, writer = await self._ensure_tcp()
            try:
                async with self._tcp_lock:
                    # The 0x12 event record is not always sent (or arrives late):
                    # it is optional. The proof is the state read afterwards.
                    event = await self._exchange(
                        reader, writer, command, RESP_EVENT,
                        first_timeout=3.0, tolerate_silence=True,
                    )
                    if not event:
                        _LOGGER.debug("Nessun evento 0x12 dopo il comando: verifico lo stato")
                    state = b""
                    for attempt in range(20):
                        state = await self._read_global_state(reader, writer)
                        if state == expected:
                            return
                        if attempt < 19:
                            await asyncio.sleep(0.5)
                raise ElkronProtocolError(
                    f"Stato dopo il comando non confermato: {state.hex(' ')}"
                )
            finally:
                await self._end_session()

    async def arm(self) -> None:
        """Arm the system with TCP command 0x11."""
        await self._set_armed(True)

    async def disarm(self) -> None:
        """Disarm the system with TCP command 0x11."""
        await self._set_armed(False)

    async def close(self) -> None:
        await self._close_tcp()
        await self._stop_http_refresh()
        if self._http is not None and not self._http.closed:
            try:
                # Hi-Connect resets the interface mode and logs out on exit.
                await self._http_request("/sys/mode.cgi", CMD_MODE_2)
                await self._http_request("/user/logout.cgi", {})
            except Exception as err:
                _LOGGER.debug("Chiusura sessione IT500WEB: %s", err)
            await self._http.close()
        self._http = None
