"""Offline test: a fake IT500WEB (HTTP :80 + TCP :5555) replaying the Hi-Connect capture.

Run:  python3 -I tests/test_fake_panel.py   (needs aiohttp; binds ports 80 and 5555)
"""
import asyncio
import hashlib

DBL = hashlib.md5(hashlib.md5(b"p").hexdigest().encode()).hexdigest()
import importlib.util
import pathlib

from aiohttp import web

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "protocol", ROOT / "custom_components/elkron_mp500/protocol.py"
)
proto = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proto)



def inputs_frame(values, declared=None):
    """0x84 reply: 16 81 55 55 00 00 <n> 00 84 <n bytes> <checksum> 03 (checksum not checked by the client)."""
    n = len(values) if declared is None else declared
    return bytes([0x16, 0x81, 0x55, 0x55, 0, 0, n, 0, 0x84, *values, 0xFE, 0xC9, 0x03])


DISARMED = bytes.fromhex("16 81 55 55 00 00 02 00 80 00 00 fe d4 03")
ARMED = bytes.fromhex("16 81 55 55 00 00 02 00 80 ff 00 fd d5 03")
EVENT = bytes.fromhex(
    "16 81 55 55 00 00 10 00 12 38 15 10 0a 1a 3d 43 00 00 00 06 00 ff 00 04 01 fd 29 03"
)


STRUCT = {
    "cfgarea": [{"NAME": "", "NID": 0, "PID": []}],
    "cfgoutput": [],
    "cfgsensor": [
        {"NAME": "Ingresso 1 - PORTA INGRESSO", "NID": 1, "PID": [1]},
        {"NAME": "Ingresso 7 - PORTA SECONDARIA", "NID": 7, "PID": [7]},
        {"NAME": "Ingresso 8 - FINESTRA SALOTTO", "NID": 8, "PID": [8]},
        {"NAME": "Ingresso 9 - SENSORE VERANDA", "NID": 9, "PID": [7]},
    ],
    "cfgzone": [
        {"NAME": "Settore 1 - SETTORE INGRESSO", "NID": 1, "PID": [0]},
        {"NAME": "Settore 7 - SETTORE SECONDARIO", "NID": 7, "PID": [0]},
    ],
}


class FakePanel:
    def __init__(self, obey=True):
        self.armed = False
        self.obey = obey
        self.inputs = [0] * 9
        self.declared = None
        self.busy = False
        self.logins = []
        self.mode_calls = []
        self.http_paths = []
        self.event_mode = "normal"
        self.clogins = []
        self.plant_id = "55555555"
        self.tech_code = "000000"
        self.tcp_frames = []

    async def http(self, request):
        path = request.path
        self.http_paths.append(path)
        body = {"result": "ACK", "title": path}
        if self.busy and path == "/sys/info.cgi":
            return web.Response(status=503, text="503 - Service Not Available")
        if path == "/user/login.cgi":
            creds = await request.json()
            self.logins.append(creds.get("pwd"))
            if (creds.get("user"), creds.get("pwd")) != ("u", DBL):  # panel expects the MD5 hex, not clear text
                return web.json_response({"result": "NAK", "title": path})
            body["data"] = {"authlevel": 1, "userid": -1, "username": "..."}
        if path == "/spweco/plantstructure.cgi":
            body["data"] = STRUCT
        if path == "/sys/info.cgi":
            body["data"] = {"cmodel": "ELKRON - MP500/8", "sysmode": 1}
        if path == "/user/clogin.cgi":
            creds = await request.json()
            self.clogins.append(creds)
            if creds != {"plantid": self.plant_id, "code": self.tech_code}:
                return web.json_response({"result": "NAK", "title": path})
            body["data"] = {"authlevel": 5, "userid": 1, "username": "TECNICO"}
        if path == "/sys/mode.cgi":
            self.mode_calls.append((await request.json())["cmd"])
        return web.json_response(body)

    async def tcp(self, reader, writer):
        try:
            while True:
                frame = await reader.readuntil(b"\x03")
                self.tcp_frames.append(frame)
                if frame == proto.CMD_START or frame[7:8] == b"\x49":
                    writer.write(b"\x06")
                elif frame == proto.CMD_KEEPALIVE:
                    writer.write(b"\x16")
                elif frame == proto.CMD_INPUTS:
                    writer.write(inputs_frame(self.inputs, self.declared))
                elif frame == proto.CMD_GLOBAL_STATE:
                    writer.write(ARMED if self.armed else DISARMED)
                elif frame in (proto.CMD_ARM, proto.CMD_DISARM):
                    if self.obey:
                        self.armed = frame == proto.CMD_ARM
                    # Like the real panel: a lone 0x16 ~0.3 s after the command,
                    # then the 0x12 event ~0.2 s later.
                    await asyncio.sleep(0.3)
                    writer.write(b"\x16")
                    await writer.drain()
                    if self.event_mode == "normal":
                        await asyncio.sleep(0.2)
                        writer.write(EVENT)
                    elif self.event_mode == "late":
                        # Arrives after the client stopped waiting for it.
                        asyncio.get_running_loop().call_later(3.6, writer.write, EVENT)
                    # "none": the panel never sends the 0x12 event
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass


async def main():
    panel = FakePanel()
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", panel.http)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 80).start()
    tcp = await asyncio.start_server(panel.tcp, "127.0.0.1", 5555)

    # Frame sanity: 16 bytes, 1.0.0 had 15.
    assert len(proto.CMD_ARM) == len(proto.CMD_DISARM) == 16
    # The session frame built from the factory plant code is the captured one.
    assert proto.CMD_SESSION == bytes.fromhex("81 55 55 00 00 07 00 49 55 55 55 55 00 00 00 fd b2 03")
    other = proto.build_session_frame("12345678")
    assert other[:8] == proto.CMD_SESSION[:8] and other[8:12] == bytes.fromhex("12345678") and len(other) == 18
    assert (-sum(other[1:-3])) & 0xFFFF == int.from_bytes(other[-3:-1], "big")
    assert proto.valid_plant_id("55555555") and not proto.valid_plant_id("5555")
    assert proto.valid_tech_code("000000") and not proto.valid_tech_code("12a")

    client = proto.ElkronTcpClient("127.0.0.1", 5555, timeout=4)
    try:
        s = await client.read_state()
        assert s["global_state"] == proto.STATE_DISARMED and s["inputs"] == [0] * 9, s
        assert panel.mode_calls == [2, 3, 2], panel.mode_calls  # login (2,3) + exit (2)
        assert client._http is None and client._writer is None  # nothing left open between readings
        assert client.model == "ELKRON - MP500/8" and panel.clogins == [{"plantid": "55555555", "code": "000000"}]
        print("read disarmed (model read from info.cgi): OK")

        await client.arm()
        assert panel.armed and proto.CMD_ARM in panel.tcp_frames
        assert panel.mode_calls == [2, 3, 2, 2, 3, 2], panel.mode_calls  # read, then arm session
        assert (await client.read_state())["global_state"] == proto.STATE_ARMED
        print("arm over TCP + state confirmed: OK")

        await client.disarm()
        assert not panel.armed and proto.CMD_DISARM in panel.tcp_frames
        assert (await client.read_state())["global_state"] == proto.STATE_DISARMED
        print("disarm over TCP + state confirmed: OK")

        # The 0x12 event is optional: no event at all, or one that arrives late.
        for mode in ("none", "late"):
            panel.event_mode = mode
            await client.arm()
            assert panel.armed and (await client.read_state())["global_state"] == proto.STATE_ARMED
            await client.disarm()
            assert not panel.armed and (await client.read_state())["global_state"] == proto.STATE_DISARMED
            print(f"arm/disarm with event mode '{mode}': OK")
        panel.event_mode = "normal"

        panel.obey = False
        try:
            await client.arm()
        except proto.ElkronProtocolError as err:
            print("unconfirmed command raises:", err)
        else:
            raise AssertionError("arm() must fail when the state does not change")
        assert not panel.armed

        # Inputs are taken from the reply, not from a fixed list.
        panel.obey = True
        panel.inputs = [0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 2]  # 12 bytes, 7 and 12 open
        s = await client.read_state()
        assert len(s["inputs"]) == 12 and s["inputs"][6] == 2 and s["inputs"][11] == 2, s
        print("12-byte inputs reply read as 12 inputs: OK")
        panel.inputs = [0, 0, 0, 0]
        s = await client.read_state()
        assert s["inputs"] == [0, 0, 0, 0], s
        print("4-byte inputs reply read as 4 inputs: OK")

        # A reply whose declared length does not match is rejected.
        panel.inputs = [0] * 9
        panel.declared = 7
        try:
            await client.read_state()
        except proto.ElkronProtocolError as err:
            print("inconsistent inputs frame raises:", err)
        else:
            raise AssertionError("inconsistent 0x84 frame must be rejected")

        # Web API: names and sectors with one short login.
        panel.http_paths.clear()
        st = await proto.fetch_structure("127.0.0.1", "u", "p")
        assert st["sensors"]["9"] == {"name": "SENSORE VERANDA", "sectors": [7]}, st
        assert st["sensors"]["7"]["name"] == "PORTA SECONDARIA"
        assert st["sectors"] == {"1": "SETTORE INGRESSO", "7": "SETTORE SECONDARIO"}, st
        assert panel.http_paths[-1] == "/user/logout.cgi", panel.http_paths
        assert panel.http_paths.count("/user/login.cgi") == 1
        print("fetch_structure (names, sectors, logout): OK")
        assert panel.logins[-1] == DBL  # never sent in clear
        try:
            await proto.fetch_structure("127.0.0.1", "u", "wrong")
        except proto.ElkronAuthError:
            print("wrong web password -> ElkronAuthError: OK")
        else:
            raise AssertionError("wrong password must raise ElkronAuthError")
        panel.busy = True
        try:
            await proto.fetch_structure("127.0.0.1", "u", "p")
        except proto.ElkronBusyError:
            print("503 -> ElkronBusyError: OK")
        else:
            raise AssertionError("503 must raise ElkronBusyError")
        panel.busy = False

        # Other plant/technical code: the panel's codes are used, the right frame is sent.
        panel.declared = None
        panel.plant_id, panel.tech_code = "12345678", "654321"
        wrong = proto.ElkronTcpClient("127.0.0.1", 5555, timeout=4)
        try:
            await wrong.read_state()
        except proto.ElkronAuthError:
            print("wrong plant/technical code -> ElkronAuthError: OK")
        else:
            raise AssertionError("wrong codes must raise ElkronAuthError")
        finally:
            await wrong.close()
        mine = proto.ElkronTcpClient("127.0.0.1", 5555, timeout=4, plant_id="12345678", tech_code="654321")
        try:
            assert (await mine.read_state())["global_state"] == proto.STATE_DISARMED
            assert proto.build_session_frame("12345678") in panel.tcp_frames
            print("custom plant/technical code: OK")
        finally:
            await mine.close()
        print("ALL TESTS PASSED")
    finally:
        await client.close()
        tcp.close()
        await runner.cleanup()


asyncio.run(main())
