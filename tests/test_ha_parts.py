"""Smoke test of the Home Assistant side (needs the `homeassistant` package; no running HA).

Run:  python3 - < tests/test_ha_parts.py   (from the repo root, so custom_components is importable)
Checks: imports against the installed HA, migrations keep names/types, dynamic binary sensors
(names and sectors from the panel), options flow (including the web refresh and its errors).
"""
import asyncio
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")
import homeassistant.const as hc
from homeassistant.components.binary_sensor import BinarySensorDeviceClass as DC
from custom_components.elkron_mp500 import (  # noqa: E402
    alarm_control_panel,
    async_migrate_entry,
    binary_sensor,
    config_flow,
    const,
)
from custom_components.elkron_mp500.protocol import ElkronBusyError

print("HA", hc.__version__)

STRUCTURE = {
    "sensors": {
        "1": {"name": "PORTA INGRESSO", "sectors": [1]},
        "7": {"name": "PORTA SECONDARIA", "sectors": [7]},
        "9": {"name": "SENSORE VERANDA", "sectors": [7]},
    },
    "sectors": {"1": "SETTORE INGRESSO", "7": "SETTORE SECONDARIO"},
}


class _Hass(SimpleNamespace):
    """Just enough of hass: the slow hash runs through async_add_executor_job."""

    calls = 0

    async def async_add_executor_job(self, func, *args):
        type(self).calls += 1
        return func(*args)

    def async_create_task(self, coro):
        import asyncio as _asyncio
        return _asyncio.ensure_future(coro)


class FakeEntries:
    def async_update_entry(self, entry, *, data=None, options=None, version=None):
        if data is not None:
            entry.data = data
        if options is not None:
            entry.options = options
        if version is not None:
            entry.version = version
        return True


async def main():
    # 1) migration: old entries get the codes, and the stored web login is dropped
    import inspect
    import custom_components.elkron_mp500 as integration

    moved = []
    fake_items = [SimpleNamespace(entity_id="binary_sensor.ingresso_1_x", unique_id="e1_input_1")]
    fake_registry = SimpleNamespace(
        entities=SimpleNamespace(get_entries_for_config_entry_id=lambda _id: fake_items),
        async_get=lambda eid: None,
        async_update_entity=lambda eid, new_entity_id: moved.append((eid, new_entity_id)),
    )
    integration.er.async_get = lambda _hass: fake_registry
    hass = SimpleNamespace(config_entries=FakeEntries())
    entry = SimpleNamespace(
        version=4,
        data={"host": "x", "port": 5555, "web_user": "u", "web_password": "p"},
        options={const.CONF_NAMES: {"7": "Portone"}},
        entry_id="e1",
    )
    assert await async_migrate_entry(hass, entry) and entry.version == 6
    assert moved == [("binary_sensor.ingresso_1_x", "binary_sensor.elkron_mp500_ingresso_1")], moved  # once, at migration
    assert entry.data == {"host": "x", "port": 5555, "plant_id": "55555555", "tech_code": "000000"}, entry.data
    assert entry.options == {const.CONF_NAMES: {"7": "Portone"}}  # user names untouched
    e1 = SimpleNamespace(version=1, data={"host": "x"}, options={}, entry_id="e0")
    await async_migrate_entry(hass, e1)
    assert e1.version == 6 and e1.data["port"] == 5555
    # Already at the current version: nothing is moved again, and setup never renames.
    moved.clear()
    entry_now = SimpleNamespace(version=6, data={"host": "x"}, options={}, entry_id="e1")
    await async_migrate_entry(hass, entry_now)
    assert moved == [] and entry_now.version == 6
    assert "async_fix_entity_ids" not in inspect.getsource(integration.async_setup_entry)
    print("migration (entity ids moved once, user renames kept): OK")

    # 2) sensors: count from the reply, names/sectors from the panel, manual name wins
    coordinator = SimpleNamespace(
        data={"inputs": [0, 0, 0, 0, 0, 0, 2, 0, 0]},
        last_update_success=True,
        client=SimpleNamespace(model="ELKRON - MP500/8"),
    )
    created = []
    entry = SimpleNamespace(
        entry_id="e1",
        options={
            const.CONF_NAMES: {"1": "Ingresso principale"},
            const.CONF_TYPES: {"7": "door", "9": "motion"},
            const.CONF_STRUCTURE: STRUCTURE,
        },
        data={},
    )
    hass = SimpleNamespace(data={const.DOMAIN: {"e1": {"coordinator": coordinator, "client": None}}})
    await binary_sensor.async_setup_entry(hass, entry, lambda ents: created.extend(ents))
    assert len(created) == 10 and type(created[9]).__name__ == "ElkronAlarmMemorySensor"
    created = created[:9]
    s1, s2, s7, s9 = created[0], created[1], created[6], created[8]
    assert s1.name == "Ingresso 1 (Ingresso principale)", s1.name  # manual name wins
    assert s2.name == "Ingresso 2" and s2.extra_state_attributes == {"raw_state": 0, "allarme": False}  # not in the panel data
    assert s7.name == "Ingresso 7 (PORTA SECONDARIA)" and s7.is_on is True and s7.device_class == DC.DOOR
    assert s9.name == "Ingresso 9 (SENSORE VERANDA)" and s9.device_class == DC.MOTION
    assert s9.extra_state_attributes == {"raw_state": 0, "allarme": False, "settori": ["7 - SETTORE SECONDARIO"]}, s9.extra_state_attributes
    assert s7.icon is None and s2.icon == "mdi:door-closed"  # opening type: door icon follows state
    coordinator.data = {"inputs": [0, 0]}
    assert s7.is_on is None and s7.extra_state_attributes == {}
    print("binary sensors (names, sectors, types): OK")

    # 2b) stable entity ids, whatever the names
    assert s1.entity_id == "binary_sensor.elkron_mp500_ingresso_1" and s9.entity_id == "binary_sensor.elkron_mp500_ingresso_9"
    from custom_components.elkron_mp500 import async_fix_entity_ids

    class Item(SimpleNamespace):
        pass

    items = [
        Item(entity_id="alarm_control_panel.sistema", unique_id="e1_alarm"),
        Item(entity_id="binary_sensor.ingresso_1_ingressi_princ_pt_e_1p", unique_id="e1_input_1"),
        Item(entity_id="binary_sensor.elkron_mp500_ingresso_2", unique_id="e1_input_2"),  # already right
        Item(entity_id="binary_sensor.ingresso_3_x", unique_id="e1_input_3"),
        Item(entity_id="binary_sensor.altro", unique_id="e1_input_x"),  # unknown: untouched
    ]
    taken = {"binary_sensor.elkron_mp500_ingresso_3"}  # an id that is already in use: leave alone
    renamed = {}
    registry = SimpleNamespace(
        entities=SimpleNamespace(get_entries_for_config_entry_id=lambda _id: items),
        async_get=lambda eid: object() if eid in taken else None,
        async_update_entity=lambda eid, new_entity_id: renamed.__setitem__(eid, new_entity_id),
    )
    async_fix_entity_ids(registry, SimpleNamespace(entry_id="e1"))
    assert renamed == {
        "alarm_control_panel.sistema": "alarm_control_panel.elkron_mp500_sistema",
        "binary_sensor.ingresso_1_ingressi_princ_pt_e_1p": "binary_sensor.elkron_mp500_ingresso_1",
    }, renamed
    print("stable entity ids + one-time rename: OK")

    # 3) alarm panel exposes the session counter
    client = SimpleNamespace(bootstraps=3, model=None, paused=False)
    coordinator.data = {"inputs": [0] * 9, "global_state": b"\x00\x00"}
    panel = alarm_control_panel.ElkronAlarmPanel(coordinator, client, SimpleNamespace(entry_id="e1"))
    assert panel.entity_id == "alarm_control_panel.elkron_mp500_sistema"
    assert panel.extra_state_attributes == {"sessioni_aperte": 3, "connessione_in_pausa": False, "stato_grezzo": "00 00", "cifre_digitate": 0, "ingressi_in_allarme": []}
    A = alarm_control_panel.AlarmControlPanelState
    assert panel.state == A.DISARMED
    coordinator.data["global_state"] = b"\xff\x00"
    assert panel.state == A.ARMED_AWAY
    coordinator.data["global_state"] = b"\x0f\x00"  # some sectors only: never reported as disarmed
    assert panel.state == A.ARMED_CUSTOM_BYPASS
    print("alarm states + session counter attribute: OK")

    # 3b) alarm detection from bit 0x04 of the input bytes
    from custom_components.elkron_mp500.alarm import AlarmTracker
    from custom_components.elkron_mp500 import event as event_platform

    ARMED, OFF = b"\xff\x00", b"\x00\x00"
    t = AlarmTracker()
    r = t.update([0] * 9, OFF)
    assert r == {"alarm_inputs": [], "triggered": False, "alarm_memory": []}
    assert t.update([0] * 9, ARMED)["triggered"] is False
    assert t.update([2, 0, 0, 0, 0, 0, 0, 0, 0], ARMED)["triggered"] is False  # open while armed: not an alarm yet
    r = t.update([6, 0, 0, 0, 0, 0, 0, 0, 0], ARMED)  # 0x06: open and in alarm
    assert r["triggered"] and r["alarm_inputs"] == [1] and r["alarm_memory"] == [1], r
    r = t.update([4, 0, 0, 0, 0, 0, 0, 0, 0], ARMED)  # closed again, memory stays: still the same alarm
    assert r["triggered"] and r["alarm_inputs"] == [1]
    r = t.update([4, 0, 0, 0, 0, 0, 0, 0, 0], OFF)  # disarmed: alarm over, memory still shown
    assert not r["triggered"] and r["alarm_memory"] == [1]
    r = t.update([4, 0, 0, 0, 0, 0, 0, 0, 0], ARMED)  # re-armed with old memory: NOT a new alarm
    assert not r["triggered"] and r["alarm_memory"] == [1], r
    r = t.update([6, 0, 0, 0, 0, 0, 0, 0, 0], ARMED)  # same input alarming again while memory is stale: still ignored...
    assert not r["triggered"]
    r = t.update([0, 0, 0, 0, 0, 0, 4, 0, 0], ARMED)  # memory cleared, another input alarms
    assert r["triggered"] and r["alarm_inputs"] == [7], r
    # first reading already armed and in alarm (e.g. Home Assistant restarted): treated as an alarm
    assert AlarmTracker().update([4] + [0] * 8, ARMED)["triggered"]

    coordinator.data = {"inputs": [6] + [0] * 8, "global_state": ARMED, "triggered": True, "alarm_inputs": [1], "alarm_memory": [1]}
    assert panel.state == A.TRIGGERED and panel.extra_state_attributes["ingressi_in_allarme"] == [1]
    coordinator.data["triggered"] = False
    assert panel.state == A.ARMED_AWAY
    sensors = []
    coordinator.data = {"inputs": [6] + [0] * 8, "alarm_memory": [1]}
    await binary_sensor.async_setup_entry(hass, entry, lambda ents: sensors.extend(ents))
    assert sensors[0].is_on is True and sensors[0].extra_state_attributes["allarme"] is True  # 0x06 is open
    assert sensors[-1].is_on is True and sensors[-1].extra_state_attributes == {"ingressi": [1]}
    coordinator.data = {"inputs": [4] + [0] * 8, "alarm_memory": [1]}
    assert sensors[0].is_on is False  # 0x04: closed, only remembered
    print("alarm detection (bit 0x04, stale memory, restart): OK")

    # 3c) event entity: one event per start and per end
    fired = []
    coordinator.data = {"triggered": False}
    ev = event_platform.ElkronAlarmEvent(coordinator, SimpleNamespace(entry_id="e1"))
    ev._trigger_event = lambda kind, attrs=None: fired.append((kind, attrs))
    ev.async_write_ha_state = lambda: None
    for flag, ins in ((False, []), (True, [1]), (True, [1]), (False, [])):
        coordinator.data = {"triggered": flag, "alarm_inputs": ins}
        event_platform.CoordinatorEntity._handle_coordinator_update = lambda self: None
        ev._handle_coordinator_update()
    assert fired == [("alarm_triggered", {"ingressi": [1]}), ("alarm_stopped", {"ingressi": []})], fired
    assert ev.entity_id == "event.elkron_mp500_allarme"
    print("alarm event entity: OK")

    # 3d) Repairs issue: raised only after 5 minutes of failures, never during a pause
    import time as _time
    from custom_components.elkron_mp500 import ElkronCoordinator, ir

    calls = []
    ir.async_create_issue = lambda *a, **k: calls.append(("create", a[2]))
    ir.async_delete_issue = lambda *a, **k: calls.append(("delete", a[2]))
    c = ElkronCoordinator.__new__(ElkronCoordinator)
    c.hass, c._first_failure = object(), None
    real = _time.monotonic
    now = [1000.0]
    integration.time.monotonic = lambda: now[0]
    c._update_connection_issue(False)
    now[0] += 299
    c._update_connection_issue(False)
    assert [x for x in calls if x[0] == "create"] == []
    now[0] += 2
    c._update_connection_issue(False)
    assert ("create", "connection_lost") in calls
    calls.clear()
    c._update_connection_issue(False, paused=True)  # paused on purpose: issue cleared
    assert calls == [("delete", "connection_lost")] and c._first_failure is None
    integration.time.monotonic = real
    print("Repairs issue after 5 minutes: OK")

    # 4) options flow
    coordinator.data = {"inputs": [0] * 9}
    entry = SimpleNamespace(
        entry_id="e1",
        data={"host": "192.168.1.50"},
        options={const.CONF_NAMES: {"1": "Ingresso principale"}},
    )
    fake_hass = _Hass(
        data={const.DOMAIN: {"e1": {"coordinator": coordinator}}},
        config_entries=SimpleNamespace(
            async_get_known_entry=lambda _id: entry, async_update_entry=FakeEntries().async_update_entry
        ),
    )

    def new_flow():
        flow = config_flow.ElkronConfigFlow.async_get_options_flow(entry)
        flow.hass, flow.handler = fake_hass, "e1"
        return flow

    flow = new_flow()
    form = await flow.async_step_init()
    keys = [str(k) for k in form["data_schema"].schema]
    expected = ["scan_interval", "web_user", "web_password", "refresh_structure", "disarm_code", "clear_disarm_code"] + [
        k for i in range(1, 10) for k in (f"name_{i}", f"type_{i}")
    ]
    assert keys == expected, keys

    # plain save: no web call, names kept, structure untouched
    validated = form["data_schema"]({"scan_interval": "30", "name_7": "Porta blindata", "type_7": "door"})
    result = await flow.async_step_init(validated)
    assert result["data"] == {"scan_interval": 30, "names": {"7": "Porta blindata"}, "types": {"7": "door"}}, result

    # refresh: panel names replace the manual ones and the structure is stored
    async def ok_fetch(host, user, pwd, timeout=8.0):
        assert (host, user, pwd) == ("192.168.1.50", "u", "p")
        return STRUCTURE

    config_flow.fetch_structure = ok_fetch
    validated = form["data_schema"](
        {"scan_interval": 45, "refresh_structure": True, "name_1": "x", "web_user": "u", "web_password": "p"}
    )
    result = await new_flow().async_step_init(validated)
    assert entry.data == {"host": "192.168.1.50"}  # login is not stored
    assert result["data"][const.CONF_NAMES] == {} and result["data"][const.CONF_STRUCTURE] == STRUCTURE, result

    # refresh while the panel is busy: error shown, nothing saved
    async def busy_fetch(*a, **k):
        raise ElkronBusyError("busy")

    config_flow.fetch_structure = busy_fetch
    result = await new_flow().async_step_init(validated)
    assert result["type"].value == "form" and result["errors"] == {"base": "web_busy"}, result

    # refresh without credentials
    validated = form["data_schema"]({"scan_interval": 45, "refresh_structure": True})
    result = await new_flow().async_step_init(validated)
    assert result["errors"] == {"base": "web_credentials_missing"}, result
    print("options flow (save, refresh, busy, no credentials): OK")

    try:
        form["data_schema"]({"scan_interval": 0})
    except Exception:
        print("interval 0 rejected: OK")
    else:
        raise AssertionError("interval 0 must be rejected")
    # 5) first setup: TCP check, then names with one web login; errors map to messages
    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def read_state(self):
            return {"inputs": [0] * 9, "global_state": b"\x00\x00"}

        async def close(self):
            pass

    config_flow.ElkronTcpClient = FakeClient
    calls = []

    async def fetch(host, user, pwd, timeout=8.0):
        calls.append((host, user))
        return STRUCTURE

    config_flow.fetch_structure = fetch

    def new_setup_flow():
        flow = config_flow.ElkronConfigFlow()
        flow.hass = SimpleNamespace()

        async def set_uid(uid, **k):
            flow.uid = uid

        flow.async_set_unique_id = set_uid
        flow._abort_if_unique_id_configured = lambda **k: None
        flow.context = {}
        return flow

    base = {"host": "192.168.1.50", "port": 5555, "scan_interval": 2}
    res = await new_setup_flow().async_step_user({**base, "web_user": "u", "web_password": "p"})
    assert res["type"].value == "create_entry", res
    assert res["data"] == {
        "host": "192.168.1.50", "port": 5555, "scan_interval": 2, "plant_id": "55555555", "tech_code": "000000"
    }, res["data"]  # web login not stored
    assert res["options"] == {"structure": STRUCTURE} and calls == [("192.168.1.50", "u")]
    res = await new_setup_flow().async_step_user(base)  # no web login: names stay generic
    assert res["type"].value == "create_entry" and res["options"] == {}, res
    assert len(calls) == 1
    res = await new_setup_flow().async_step_user({**base, "web_user": "u"})  # password missing
    assert res["errors"] == {"base": "web_credentials_missing"}, res
    res = await new_setup_flow().async_step_user({**base, "plant_id": "123"})  # wrong length
    assert res["errors"] == {"plant_id": "invalid_plant_id"}, res
    res = await new_setup_flow().async_step_user({**base, "tech_code": "12ab"})
    assert res["errors"] == {"tech_code": "invalid_tech_code"}, res
    res = await new_setup_flow().async_step_user({**base, "plant_id": "12345678", "tech_code": "123456"})
    assert res["data"]["plant_id"] == "12345678" and res["data"]["tech_code"] == "123456"
    from custom_components.elkron_mp500.protocol import ElkronAuthError

    class RefusedClient(FakeClient):
        async def read_state(self):
            raise ElkronAuthError("no")

    config_flow.ElkronTcpClient = RefusedClient
    res = await new_setup_flow().async_step_user(base)
    assert res["errors"] == {"base": "local_auth_failed"}, res
    print("first setup flow (codes, with and without web login): OK")
    print("ALL HA-SIDE TESTS PASSED")


asyncio.run(main())


# ---- disarm code (1.5.0) ----
from custom_components.elkron_mp500.disarm_code import hash_code, verify_code, valid_code, AttemptLimiter
s, h = hash_code("123456")
assert verify_code("123456", s, h) and not verify_code("654321", s, h)
assert not verify_code(None, s, h) and not verify_code("12345", s, h)
assert valid_code("000000") and not valid_code("12a456") and not valid_code("1234567")
lim = AttemptLimiter(3, 60)
for _ in range(3): lim.failed()
assert lim.seconds_locked() > 0
lim.succeeded(); assert lim.seconds_locked() == 0
print("disarm code OK")

# entity-level disarm gate
from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace as _N
from homeassistant.exceptions import ServiceValidationError
from custom_components.elkron_mp500.alarm_control_panel import ElkronAlarmPanel
from custom_components.elkron_mp500.const import CONF_DISARM_SALT, CONF_DISARM_HASH


async def _gate():
    client = MagicMock(); client.model = "x"; client.disarm = AsyncMock()
    coord = MagicMock(); coord.async_request_refresh = AsyncMock(); coord.data = {}
    s, h = hash_code("123456")
    entry = _N(entry_id="e", options={CONF_DISARM_SALT: s, CONF_DISARM_HASH: h}, data={})
    ent = ElkronAlarmPanel(coord, client, entry); ent.hass = _Hass()
    assert ent.code_format is not None and ent._attr_code_arm_required is False
    for bad in (None, "", "111111"):
        try:
            await ent.async_alarm_disarm(bad); raise SystemExit("no error")
        except ServiceValidationError:
            pass
    client.disarm.assert_not_called()
    await ent.async_alarm_disarm("123456"); client.disarm.assert_awaited_once()
    # no code configured -> unchanged behaviour
    entry2 = _N(entry_id="e", options={}, data={})
    ent2 = ElkronAlarmPanel(coord, client, entry2); ent2.hass = _Hass()
    assert ent2.code_format is None
    await ent2.async_alarm_disarm(None)
    assert client.disarm.await_count == 2
    # lockout after 5 wrong
    for _ in range(5):
        try: await ent.async_alarm_disarm("000000")
        except ServiceValidationError: pass
    try:
        await ent.async_alarm_disarm("123456"); raise SystemExit("not locked")
    except ServiceValidationError as e:
        assert "bloccato" in str(e)
    assert _Hass.calls >= 5  # the PBKDF2 check always goes through the executor
    print("entity disarm gate OK")

import asyncio as _a
_a.run(_gate())


async def _keypad():
    client = MagicMock(); client.model = "x"; client.disarm = AsyncMock()
    coord = MagicMock(); coord.async_request_refresh = AsyncMock()
    coord.data = {"global_state": b"\xff\x00"}
    s, h = hash_code("123456")
    entry = _N(entry_id="e", options={CONF_DISARM_SALT: s, CONF_DISARM_HASH: h}, data={})
    ent = ElkronAlarmPanel(coord, client, entry); ent.async_write_ha_state = lambda: None; ent.hass = _Hass()
    for k in "1234567": await ent.async_keypad_press(k)
    assert ent.extra_state_attributes["cifre_digitate"] == 6   # capped at 6
    await ent.async_keypad_press("C"); assert ent.extra_state_attributes["cifre_digitate"] == 0
    for k in "123456": await ent.async_keypad_press(k)
    tasks = []
    ent.hass.async_create_task = lambda c: tasks.append(c)
    await ent.async_keypad_submit()
    for c in tasks: await c
    client.disarm.assert_awaited_once(); assert ent._digits == ""
    for k in "111111": await ent.async_keypad_press(k)
    try:
        await ent.async_keypad_submit(); raise SystemExit("accepted wrong")
    except ServiceValidationError: pass
    assert client.disarm.await_count == 1 and ent._digits == ""
    print("keypad OK")

_a.run(_keypad())


async def _backoff():
    from custom_components.elkron_mp500 import protocol as P
    c = P.ElkronTcpClient("192.168.1.50", 5555)
    calls = []

    async def boom(path, payload=None):
        calls.append(path)
        raise P.ElkronProtocolError(f"HTTP {path}: stato 404")
    c._http_request = boom
    try:
        await c._ensure_http_session(); raise SystemExit("no error")
    except P.ElkronProtocolError:
        pass
    n = len(calls)
    try:
        await c._ensure_http_session(); raise SystemExit("no backoff")
    except P.ElkronBusyError:
        pass
    assert len(calls) == n, "panel contacted during backoff"
    c._retry_at = 0  # delay expired
    try:
        await c._ensure_http_session()
    except P.ElkronProtocolError:
        pass
    assert len(calls) == 2 * n and c._failures == 2
    print("backoff OK")

_a.run(_backoff())


async def _no_leak():
    from custom_components.elkron_mp500 import protocol as P
    c = P.ElkronTcpClient("192.168.1.50", 5555)
    calls = []

    async def fake(path, payload=None):
        calls.append(path)
        if path == "/user/clogin.cgi":
            return {"result": "ACK", "data": {"authlevel": 5}}
        if path == "/sys/mode.cgi" and payload == P.CMD_MODE_3:
            raise P.ElkronRejectedError("mode NAK")
        return {"result": "ACK", "data": {}}
    c._http_request = fake
    try:
        await c._ensure_http_session(); raise SystemExit("no error")
    except P.ElkronRejectedError:
        pass
    assert calls[-1] == "/user/logout.cgi", calls  # login is not left open
    assert c._http is None
    print("no login left open after a failed bootstrap: OK")

_a.run(_no_leak())
