"""HexR Remote, the headset side of the Headsets screen.

The reference lines and bytes are the ones in com.microtube.hexr's Documentation~/RemoteProtocol.md,
which the package's own tests (Tests/Editor/RemoteTests.cs) and the phone's
(RemoteProtocolTest.kt) use too. A change to the protocol is a change in all three.

Run: python -m pytest tests -q      (or: python tests/test_remote.py)
"""

from __future__ import annotations

import os
import re
import socket
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hexr import headsets as H  # noqa: E402
from hexr import remote as R  # noqa: E402

REFERENCE_STATUS = (
    '{"type":"status","protocol":1,"id":"q3-1","name":"Quest 3","model":"Oculus Quest 3",'
    '"platform":"quest","app":"HexR Demo","appVersion":"1.2","hexrVersion":"0.10.0",'
    '"paused":false,"headsetBatteryPct":71,'
    '"scene":{"index":1,"name":"Hospital Tutorial"},'
    '"scenes":[{"index":0,"name":"Basic Tutorial"},{"index":1,"name":"Hospital Tutorial"}],'
    '"gloves":[{"hand":"left","state":"connected","message":"Connected","batteryPct":83,'
    '"pressureDeciKPa":[10,0,0,0,0,0,452]},'
    '{"hand":"right","state":"disconnected","message":"","batteryPct":-1,"pressureDeciKPa":[]}],'
    '"stream":{"state":"live","port":47802,"width":1024,"height":1024,"viewers":1,"message":"",'
    '"audio":{"state":"live","port":47803,"sampleRate":48000,"channels":2,"message":""}},'
    '"commands":[{"id":"reset","label":"Reset demo"}],'
    '"allowGloveControl":true,"allowVideo":true,"exposeScenes":true,"allowRecenter":true,'
    '"controllers":2}'
)

REFERENCE_ANNOUNCE = (
    b'{"hexr":1,"type":"announce","id":"27c6","name":"Quest 3","model":"Oculus Quest 3",'
    b'"platform":"quest","app":"HexR Meta Developer Tutorial",'
    b'"appId":"com.Microtube.HexRMetaDeveloperTutorial","hexrVersion":"0.10.0",'
    b'"control":47801,"video":47802,"startedAt":1791966541289}'
)


# -- requests -------------------------------------------------------------------

def test_requests_match_the_reference_lines():
    assert R.hello("HexR Tester") == '{"type":"hello","protocol":1,"client":"HexR Tester"}'
    assert R.ping() == '{"type":"ping"}'
    assert R.glove("connect", "left") == '{"type":"glove","action":"connect","hand":"left"}'
    assert R.glove("disconnect", "right") == \
        '{"type":"glove","action":"disconnect","hand":"right"}'
    assert R.release() == '{"type":"release"}'
    assert R.scene(2) == '{"type":"scene","index":2}'
    assert R.command("reset") == '{"type":"command","id":"reset"}'
    assert R.stream("start") == '{"type":"stream","action":"start"}'
    assert R.recenter() == '{"type":"recenter"}'


def test_hello_names_this_app_by_default():
    assert '"client":"HexR Companion"' in R.hello()


# -- status and announcements ----------------------------------------------------

def test_reads_the_reference_status():
    s = R.parse_status(R.parse_json(REFERENCE_STATUS))
    assert (s.id, s.name, s.app, s.app_version, s.hexr_version) == \
        ("q3-1", "Quest 3", "HexR Demo", "1.2", "0.10.0")
    assert s.paused is False and s.headset_battery_pct == 71
    assert (s.scene_index, s.scene_name) == (1, "Hospital Tutorial")
    assert s.scenes == [(0, "Basic Tutorial"), (1, "Hospital Tutorial")]
    left, right = s.gloves["left"], s.gloves["right"]
    assert left.connected and left.battery_pct == 83
    assert left.pressure_kpa == [1.0, 0, 0, 0, 0, 0, 45.2]
    assert right.state == "disconnected" and right.battery_pct == -1 and right.pressure_kpa == []
    assert (s.stream.state, s.stream.port, s.stream.width, s.stream.height, s.stream.viewers) \
        == ("live", 47802, 1024, 1024, 1)
    a = s.stream.audio
    assert (a.state, a.port, a.sample_rate, a.channels, a.message) == ("live", 47803, 48000, 2, "")
    assert s.commands == [("reset", "Reset demo")]
    assert s.allow_glove_control and s.allow_video and s.expose_scenes and s.controllers == 2
    assert s.allow_recenter


def test_reads_the_reference_announcement():
    a = R.parse_announce(REFERENCE_ANNOUNCE)
    assert (a.id, a.name, a.platform, a.app) == \
        ("27c6", "Quest 3", "quest", "HexR Meta Developer Tutorial")
    assert (a.control, a.video, a.started_at) == (47801, 47802, 1791966541289)


def test_ignores_what_is_not_a_hexr_announcement():
    assert R.parse_announce(b"not json") is None
    assert R.parse_announce(b'{"hexr":2,"type":"announce","id":"x"}') is None
    assert R.parse_announce(b'{"hexr":1,"type":"status","id":"x"}') is None
    assert R.parse_announce(b'{"hexr":1,"type":"announce"}') is None
    assert R.parse_announce(b"[1,2]") is None


def test_a_status_missing_fields_still_reads():
    s = R.parse_status({"type": "status", "gloves": [{"hand": "left", "state": "connecting"},
                                                     {"hand": "neither"}]})
    assert s.gloves["left"].state == "connecting" and "neither" not in s.gloves
    assert s.stream.state == "off" and s.scene_index == -1 and s.scenes == []
    # A headset before HexR 0.10.5 says nothing about sound, and sends none.
    assert s.stream.audio.state == "off" and s.stream.audio.port == 0
    # A headset before HexR 0.10.6 says nothing about recentering, and cannot do it.
    assert s.allow_recenter is False


def test_numbers_that_are_not_numbers_fall_back():
    s = R.parse_status({"headsetBatteryPct": True, "controllers": "two"})
    assert s.headset_battery_pct == -1 and s.controllers == 0


# -- video framing ------------------------------------------------------------------

def test_reads_the_reference_video_header():
    assert R.parse_video_header(bytes.fromhex("48 58 56 31 04 00 04 00 01")) == (1024, 1024, 1)


def test_reads_the_reference_packet_header():
    header = bytes.fromhex("00 00 00 04 02 00 00 00 00 00 00 03 e8")
    assert R.parse_packet_header(header) == (4, R.FLAG_KEYFRAME, 1000)


def test_reads_the_reference_sound_header():
    assert R.parse_audio_header(bytes.fromhex("48 58 41 31 00 00 bb 80 02 01")) == (48000, 2, 1)
    try:
        R.parse_audio_header(bytes.fromhex("48 58 56 31 04 00 04 00 01 00"))
    except ValueError:
        return
    raise AssertionError("took a video header for a sound one")


def test_rejects_a_stream_that_is_not_hexr_video():
    try:
        R.parse_video_header(b"HTTP/1.1 ")
    except ValueError:
        return
    raise AssertionError("accepted a header that is not HXV1")


# -- a link against a stand-in headset -----------------------------------------------

class _FakeHeadset:
    """A control port on localhost that answers like a headset: status lines out, and every
    line the client sends recorded."""

    def __init__(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(1)
        self.port = self.server.getsockname()[1]
        self.received: list[str] = []
        self.done = threading.Event()
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        conn, _ = self.server.accept()
        conn.settimeout(0.1)
        buf = b""
        while not self.done.is_set():
            conn.sendall((REFERENCE_STATUS + "\n").encode())
            try:
                buf += conn.recv(4096)
            except socket.timeout:
                pass
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                self.received.append(line.decode())
            time.sleep(0.05)
        conn.close()
        self.server.close()


class _Listener:
    def __init__(self):
        self.states: list[str] = []
        self.statuses: list[R.Status] = []

    def on_link(self, key, state):
        self.states.append(state)

    def on_status(self, key, status):
        self.statuses.append(status)

    def on_error(self, key, request, message):
        pass


def _wait_for(condition, seconds=3.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.02)
    return False


def test_a_link_says_hello_reads_status_and_sends_requests():
    headset = _FakeHeadset()
    listener = _Listener()
    link = R.HeadsetLink("q3-1", "127.0.0.1", headset.port, listener)
    link.start()
    try:
        assert _wait_for(lambda: listener.statuses), "no status arrived"
        assert "connected" in listener.states
        assert listener.statuses[-1].gloves["left"].connected
        assert link.send(R.glove("connect", "right"))
        assert _wait_for(lambda: len(headset.received) >= 2)
        assert headset.received[0] == R.hello()
        assert headset.received[1] == R.glove("connect", "right")
    finally:
        link.stop()
        headset.done.set()


def test_a_link_that_cannot_connect_says_so_and_keeps_trying():
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    port = closed.getsockname()[1]
    closed.close()                      # nothing listens there now
    listener = _Listener()
    link = R.HeadsetLink("gone", "127.0.0.1", port, listener)
    link.start()
    try:
        assert _wait_for(lambda: "lost" in listener.states)
        assert not link.send(R.ping())
    finally:
        link.stop()


# -- the screen's model ------------------------------------------------------------------

def test_headsets_of_one_model_are_told_apart_and_names_stick():
    with tempfile.TemporaryDirectory() as tmp:
        env = {k: os.environ.get(k) for k in ("APPDATA", "XDG_CONFIG_HOME", "HOME")}
        os.environ["APPDATA"] = os.environ["XDG_CONFIG_HOME"] = os.environ["HOME"] = tmp
        try:
            model = H.Headsets()
            # Two headsets nobody can reach: their links fail quietly in the background.
            for hid in ("aaaa1111", "bbbb2222"):
                a = R.parse_announce(REFERENCE_ANNOUNCE.replace(b'"27c6"', f'"{hid}"'.encode())
                                     .replace(b"47801", b"9"))
                model._on_announce(a, "127.0.0.1")
            titles = [r.title for r in model.rows()]
            assert titles == ["Quest 3 · 1111", "Quest 3 · 2222"], titles

            model.rename("bbbb2222", "  Station 1 ")
            assert [r.title for r in model.rows()] == ["Quest 3 · 1111", "Station 1"]
            # Saved, so the next launch keeps the name.
            assert H._load_nicknames() == {"bbbb2222": "Station 1"}
            model.stop()
        finally:
            for k, v in env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def _announce(hid: str, started_at: int, control: int) -> R.Announce:
    return R.parse_announce(
        ('{"hexr":1,"type":"announce","id":"%s","name":"Quest 3","app":"App %d",'
         '"control":%d,"video":47802,"startedAt":%d}' % (hid, started_at, control, started_at))
        .encode())


def test_two_apps_sharing_an_id_follow_the_newest_only():
    # Two HexR apps signed with the same key on one headset share an id, and both announce.
    # Following every announcement flipped the link between them, so it never stayed up.
    model = H.Headsets()
    older, newer = _announce("same", 100, 9), _announce("same", 200, 10)
    for a in (older, newer, older, older):
        model._on_announce(a, "127.0.0.1")
    entry = model._entries["same"]
    assert entry.announce.started_at == 200 and entry.link.port == 10
    model.stop()


def test_a_headset_added_by_address_has_its_own_key():
    model = H.Headsets()
    model.add_by_address(" 127.0.0.1:9 ")
    rows = model.rows()
    assert [r.key for r in rows] == ["ip:127.0.0.1"] and rows[0].manual
    model.forget("ip:127.0.0.1")
    assert model.rows() == []
    model.stop()



# -- picking one glove out of several (HexR 0.10.6) ------------------------------

def test_glove_search_requests_match_the_reference_lines():
    assert R.glove("search") == '{"type":"glove","action":"search"}'
    assert R.glove("connect", "left", "D4:3D:39:A1:B2:C3") == \
        '{"type":"glove","action":"connect","hand":"left","address":"D4:3D:39:A1:B2:C3"}'
    assert R.glove("forget", "left") == '{"type":"glove","action":"forget","hand":"left"}'
    assert R.trigger() == '{"type":"trigger"}'
    assert R.trigger("right") == '{"type":"trigger","hand":"right"}'


def test_reads_the_saved_gloves_and_the_last_search():
    line = REFERENCE_STATUS[:-1].replace(
        '"pressureDeciKPa":[10,0,0,0,0,0,452]}',
        '"pressureDeciKPa":[10,0,0,0,0,0,452],"savedAddress":"D4:3D:39:A1:B2:C3"}') + \
        ',"gloveSearch":{"state":"done","message":"","found":[{"address":"D4:3D:39:D4:E5:F6",' \
        '"name":"HaptGloveAR Right","hand":"right","rssi":-48},{"address":"","name":"x"},' \
        '{"address":"AA:BB","name":"HexR 07","hand":"up","rssi":"near"}]}}'
    s = R.parse_status(R.parse_json(line))
    assert s.gloves["left"].saved_address == "D4:3D:39:A1:B2:C3"
    assert s.gloves["right"].saved_address == ""
    assert s.glove_search.state == "done"
    # One without an address is no use; a hand or strength that is not one reads as unknown.
    assert s.glove_search.found == [
        R.NearbyGlove("D4:3D:39:D4:E5:F6", "HaptGloveAR Right", "right", -48),
        R.NearbyGlove("AA:BB", "HexR 07", "", 0),
    ]


def test_a_headset_before_0_10_6_cannot_search():
    assert R.parse_status(R.parse_json(REFERENCE_STATUS)).glove_search is None


def test_glove_names_stick_by_address_beside_the_headset_names():
    with tempfile.TemporaryDirectory() as tmp:
        env = {k: os.environ.get(k) for k in ("APPDATA", "XDG_CONFIG_HOME", "HOME")}
        os.environ["APPDATA"] = os.environ["XDG_CONFIG_HOME"] = os.environ["HOME"] = tmp
        try:
            model = H.Headsets()
            model.rename_glove("d4:3d:39:a1:b2:c3", "  Kit 3 Left ")
            model.rename("q3-1", "Station 1")
            # Either name saved keeps the other.
            again = H.Headsets()
            assert again.glove_name("D4:3D:39:A1:B2:C3") == "Kit 3 Left"
            assert H._load_nicknames() == {"q3-1": "Station 1"}
            again.rename_glove("D4:3D:39:A1:B2:C3", "")
            assert H.Headsets().glove_name("D4:3D:39:A1:B2:C3") == ""
            model.stop()
            again.stop()
        finally:
            for k, v in env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except AssertionError as e:
                failures += 1
                print(f"  FAIL  {name}: {e}")
    print(f"\n{'FAILED' if failures else 'All remote tests passed'}"
          f"{f' ({failures} failing)' if failures else ''}")
    sys.exit(1 if failures else 0)


# -- haptics (HexR 0.10.2 and later) ---------------------------------------------

# The package's RemoteTests.cs: the right index fingertip starting to press at 80%.
REFERENCE_HAPTICS = (
    '{"type":"haptics","t":1791966541289123,"hand":"right","channels":['
    '{"finger":1,"mode":"pressure","intensityPct":80,"frequencyDeciHz":0,"tap":false}]}'
)


def test_reads_the_reference_haptics_line():
    u = R.parse_haptics(R.parse_json(REFERENCE_HAPTICS))
    assert (u.hand, u.t_us) == ("right", 1791966541289123)
    assert u.channels == [R.HapticChannel(finger=1, mode="pressure", intensity=0.8, hz=0.0,
                                          tap=False)]


def test_reads_a_vibration_tap_and_skips_what_it_cannot_use():
    u = R.parse_haptics({"hand": "left", "t": 5, "channels": [
        {"finger": 5, "mode": "vibration", "intensityPct": 50, "frequencyDeciHz": 60, "tap": True},
        {"finger": 9, "mode": "pressure"}, {"finger": 2, "mode": "squeeze"}, "junk"]})
    assert u.channels == [R.HapticChannel(5, "vibration", 0.5, 6.0, True)]
    assert R.parse_haptics({"hand": "middle", "channels": []}) is None


def test_status_says_whether_the_headset_sends_haptics_and_its_clock():
    newer = R.parse_status(R.parse_json(REFERENCE_STATUS[:-1] +
                                        ',"haptics":true,"clockUs":1791966541289123}'))
    assert (newer.haptics, newer.clock_us) == (True, 1791966541289123)
    older = R.parse_status(R.parse_json(REFERENCE_STATUS))
    assert (older.haptics, older.clock_us) == (False, 0)


def test_a_link_hands_haptics_lines_to_its_listener():
    got = []

    class Listener:
        def on_haptics(self, key, update):
            got.append((key, update.hand))

    link = R.HeadsetLink("q3-1", "127.0.0.1", 1, Listener())
    link._handle(REFERENCE_HAPTICS.encode())
    assert got == [("q3-1", "right")]


# -- the view, against a stand-in headset's video port ---------------------------------------

def _h264_packets(count: int) -> list[bytes]:
    """`count` frames of H.264 as a headset sends them: Annex-B, SPS/PPS on the keyframe."""
    import av
    from fractions import Fraction
    from PIL import Image
    enc = av.CodecContext.create("libx264", "w")
    enc.width, enc.height, enc.pix_fmt = 64, 64, "yuv420p"
    enc.time_base = Fraction(1, 30)
    enc.options = {"preset": "ultrafast", "tune": "zerolatency"}
    out = []
    for i in range(count):
        frame = av.VideoFrame.from_image(Image.new("RGB", (64, 64), (i * 9 % 255, 80, 160)))
        frame.pts = i
        out += [bytes(p) for p in enc.encode(frame)]
    out += [bytes(p) for p in enc.encode(None)]
    return out


def _video_packet(payload: bytes, flags: int, pts: int) -> bytes:
    return len(payload).to_bytes(4, "big") + bytes([flags]) + pts.to_bytes(8, "big") + payload


def test_the_view_starts_after_the_config_packet_and_survives_a_bad_one():
    av = __import__("pytest").importorskip("av")
    try:
        av.codec.Codec("libx264", "w")
    except Exception:  # noqa: BLE001
        __import__("pytest").skip("no libx264 in this PyAV")
    packets = _h264_packets(12)
    key = packets[0]
    # SPS/PPS: everything before the first IDR slice (NAL type 5), whatever its start code.
    idr = next(m.start() for m in re.finditer(b"\x00\x00\x01", key) if key[m.end()] & 0x1F == 5)
    config = key[:idr - 1 if key[idr - 1:idr] == b"\x00" else idr]
    assert config
    stream = [_video_packet(config, R.FLAG_CONFIG, 0),           # what a new viewer gets first
              _video_packet(key, R.FLAG_KEYFRAME, 1000)]
    stream += [_video_packet(p, 0, 1000 + 33333 * (i + 1)) for i, p in enumerate(packets[1:6])]
    stream += [_video_packet(b"\x00\x00\x00\x01\x41" + b"\xff" * 40, 0, 300000)]   # damaged
    stream += [_video_packet(p, 0, 400000 + 33333 * i) for i, p in enumerate(packets[6:])]

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)

    def serve():
        conn, _ = server.accept()
        conn.sendall(b"HXV1" + (64).to_bytes(2, "big") * 2 + bytes([R.CODEC_H264]))
        for p in stream:
            conn.sendall(p)
        time.sleep(1.0)
        conn.close()
        server.close()
    threading.Thread(target=serve, daemon=True).start()

    view = R.VideoReceiver("127.0.0.1", server.getsockname()[1], lambda f, pts, t: f)
    try:
        assert _wait_for(lambda: view.frames >= len(packets) - 2), \
            f"{view.frames} frames, {view.state}: {view.message}"
        assert view.state == "playing"
    finally:
        view.stop()


# -- the sound, against a stand-in headset's sound port (HexR 0.10.5 and later) --------------

def _aac_packets(count: int) -> tuple[bytes, list[bytes]]:
    """A headset's sound as it sends it: the AudioSpecificConfig, then raw AAC frames."""
    import math
    from array import array
    from fractions import Fraction
    import av
    enc = av.CodecContext.create("aac", "w")
    enc.sample_rate, enc.layout, enc.format = 48000, "stereo", "fltp"
    enc.time_base = Fraction(1, 48000)
    out = []
    for i in range(count):
        frame = av.AudioFrame(format="fltp", layout="stereo", samples=1024)
        frame.sample_rate, frame.pts, frame.time_base = 48000, i * 1024, Fraction(1, 48000)
        tone = array("f", (0.3 * math.sin(2 * math.pi * 440 * (i * 1024 + n) / 48000)
                           for n in range(1024))).tobytes()
        for plane in frame.planes:
            plane.update(tone)
        out += [bytes(p) for p in enc.encode(frame)]
    out += [bytes(p) for p in enc.encode(None)]
    return bytes(enc.extradata), out


def test_the_sound_decodes_from_its_config_and_keeps_the_headsets_times():
    __import__("pytest").importorskip("av")
    config, packets = _aac_packets(20)
    assert config[:2] == bytes.fromhex("11 90")            # AAC-LC, 48 kHz, stereo
    stream = [_video_packet(config, R.FLAG_CONFIG, 0)]
    stream += [_video_packet(p, R.FLAG_KEYFRAME, 5_000_000 + round(i * 1024 * 1e6 / 48000))
               for i, p in enumerate(packets)]

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)

    def serve():
        conn, _ = server.accept()
        conn.sendall(b"HXA1" + (48000).to_bytes(4, "big") + bytes([2, R.CODEC_AAC]))
        time.sleep(0.2)                                     # the tap is in by now
        for p in stream:
            conn.sendall(p)
        time.sleep(1.0)
        conn.close()
        server.close()
    threading.Thread(target=serve, daemon=True).start()

    sound = R.AudioReceiver("127.0.0.1", server.getsockname()[1])
    got = []
    sound.taps.append(lambda frame, pts: got.append((frame.samples, frame.sample_rate, pts)))
    try:
        assert _wait_for(lambda: len(got) >= len(packets) - 2), \
            f"{len(got)} pieces, {sound.state}: {sound.message}"
        assert sound.state == "playing" and (sound.sample_rate, sound.channels) == (48000, 2)
        assert all(n == 1024 and rate == 48000 for n, rate, _pts in got)
        times = [pts for _n, _rate, pts in got]
        assert times[0] >= 5_000_000 and times == sorted(times)
    finally:
        sound.stop()
