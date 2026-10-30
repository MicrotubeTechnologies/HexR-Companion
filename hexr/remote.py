"""HexR Remote: find the HEXR headsets on this network, control them, watch them.

The other end is the HexR Remote component in the com.microtube.hexr Unity package, and its
contract is that package's Documentation~/RemoteProtocol.md. The phone app speaks the same thing
(android/app/src/main/java/com/microtube/hexr/remote/ on the android branch); the reference
lines in tests/test_remote.py are the ones its tests and the package's use, so a change to the
protocol is a change in all three.

Four ports, all on the local network and nothing else:
- 47800 UDP: every headset broadcasts an announcement every two seconds.
- 47801 TCP: control, one JSON object per line each way.
- 47802 TCP: the headset's view as H.264, while the wearer is sharing it.
- 47803 TCP: the app's sound as AAC beside the view, from HexR 0.10.5 on, when the app shares it.

Nothing here touches Tk. Each connection runs on its own daemon thread and reports through
callbacks, which run on that thread; the caller hops to Tk itself.
"""

from __future__ import annotations

import json
import socket
import struct
import threading
import time
from dataclasses import dataclass, field

from .i18n import tr

DISCOVERY_PORT = 47800
CONTROL_PORT = 47801
VIDEO_PORT = 47802
AUDIO_PORT = 47803
PROTOCOL = 1
CLIENT = "HexR Companion"

# A headset sends its status five times a second, and once a second even while asleep, so this
# much silence means it has gone. It drops a client it has not heard from in 15 s; the ping
# keeps it from doing that.
SILENT_AFTER_S = 4.0
PING_EVERY_S = 5.0
MAX_LINE = 16 * 1024

HANDS = ("left", "right")


# ---------------------------------------------------------------------------
# Requests, client to headset
# ---------------------------------------------------------------------------

def _line(obj: dict) -> str:
    # Compact and in insertion order: the reference lines are byte-for-byte.
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def hello(client: str = CLIENT) -> str:
    return _line({"type": "hello", "protocol": PROTOCOL, "client": client})


def ping() -> str:
    return _line({"type": "ping"})


def glove(action: str, hand: str | None = None, address: str | None = None) -> str:
    """connect / disconnect / forget a hand's glove; connect with an address for that exact
    glove (HexR 0.10.6 and later). "search", with no hand, lists every glove in range."""
    obj = {"type": "glove", "action": action}
    if hand is not None:
        obj["hand"] = hand
    if address:
        obj["address"] = address
    return _line(obj)


def trigger(hand: str | None = None) -> str:
    """Every channel of the connected gloves pressed for a second (HexR 0.10.6 and later)."""
    return _line({"type": "trigger"} if hand is None else {"type": "trigger", "hand": hand})


def release(hand: str | None = None) -> str:
    return _line({"type": "release"} if hand is None else {"type": "release", "hand": hand})


def scene(index: int) -> str:
    return _line({"type": "scene", "index": index})


def command(command_id: str) -> str:
    return _line({"type": "command", "id": command_id})


def stream(action: str) -> str:
    return _line({"type": "stream", "action": action})


def recenter() -> str:
    return _line({"type": "recenter"})


# ---------------------------------------------------------------------------
# What headsets send
# ---------------------------------------------------------------------------

@dataclass
class Announce:
    id: str
    name: str
    model: str
    platform: str
    app: str
    app_id: str
    hexr_version: str
    control: int
    video: int
    started_at: int


@dataclass
class GloveState:
    hand: str
    state: str                     # connected | connecting | disconnected | missing
    message: str = ""
    battery_pct: int = -1          # -1 until the glove has reported it
    pressure_kpa: list[float] = field(default_factory=list)  # six channels, then the source
    # The glove this hand is saved to and connects to only (HexR 0.10.6 and later); empty when
    # it takes the first glove of its hand it finds.
    saved_address: str = ""

    @property
    def connected(self) -> bool:
        return self.state == "connected"


@dataclass
class NearbyGlove:
    address: str
    name: str                      # what it advertises, e.g. "HaptGloveAR Left"
    hand: str = ""                 # left | right from that name, or "" when it does not say
    rssi: int = 0                  # dBm, nearer 0 is closer; 0 when unknown


@dataclass
class GloveSearch:
    """The headset's last search for every glove in range."""
    state: str = "idle"            # idle | searching | done | failed
    message: str = ""
    found: list[NearbyGlove] = field(default_factory=list)   # nearest first


@dataclass
class AudioState:
    """The app's sound beside its view. A headset before HexR 0.10.5 sends none: "off"."""
    state: str = "off"             # off | live | denied | unsupported | error
    port: int = 0
    sample_rate: int = 0
    channels: int = 0
    message: str = ""


@dataclass
class StreamState:
    state: str = "off"             # off | requesting | live | denied | unsupported | error
    port: int = 0
    width: int = 0
    height: int = 0
    viewers: int = 0
    message: str = ""
    audio: AudioState = field(default_factory=AudioState)


@dataclass
class Status:
    id: str
    name: str
    model: str
    platform: str
    app: str
    app_version: str
    hexr_version: str
    paused: bool
    headset_battery_pct: int
    scene_index: int
    scene_name: str
    scenes: list[tuple[int, str]]
    gloves: dict[str, GloveState]
    stream: StreamState
    commands: list[tuple[str, str]]
    allow_glove_control: bool
    allow_video: bool
    expose_scenes: bool
    allow_recenter: bool
    controllers: int
    haptics: bool = False          # the headset sends "haptics" lines (HexR 0.10.2 and later)
    clock_us: int = 0              # its clock when it sent this: the one haptics and video use
    # None from a headset before HexR 0.10.6, which cannot search for gloves.
    glove_search: GloveSearch | None = None


@dataclass
class HapticChannel:
    finger: int                    # 0 thumb … 4 pinky, 5 palm
    mode: str                      # off | pressure | vibration | pulse
    intensity: float = 0.0         # 0.1–1 while on
    hz: float = 0.0                # vibration and pulse frequency
    tap: bool = False              # on and off again within one headset frame


@dataclass
class HapticsUpdate:
    """What one glove's haptic channels started doing at `t_us`, on the headset's clock."""
    hand: str
    t_us: int
    channels: list[HapticChannel]


def parse_json(text: str) -> dict | None:
    """One JSON object, or None for anything else: a client never trusts the network."""
    try:
        obj = json.loads(text)
    except (ValueError, UnicodeDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def parse_announce(data: bytes) -> Announce | None:
    obj = parse_json(data.decode("utf-8", "replace"))
    if not obj or obj.get("hexr") != PROTOCOL or obj.get("type") != "announce" or not obj.get("id"):
        return None
    return Announce(
        id=str(obj["id"]),
        name=str(obj.get("name", "")),
        model=str(obj.get("model", "")),
        platform=str(obj.get("platform", "")),
        app=str(obj.get("app", "")),
        app_id=str(obj.get("appId", "")),
        hexr_version=str(obj.get("hexrVersion", "")),
        control=_int(obj.get("control"), CONTROL_PORT),
        video=_int(obj.get("video"), VIDEO_PORT),
        started_at=_int(obj.get("startedAt"), 0),
    )


def parse_status(obj: dict) -> Status:
    scene_obj = obj.get("scene") or {}
    gloves = {}
    for g in obj.get("gloves") or []:
        if not isinstance(g, dict) or g.get("hand") not in HANDS:
            continue
        gloves[g["hand"]] = GloveState(
            hand=g["hand"],
            state=str(g.get("state", "disconnected")),
            message=str(g.get("message", "")),
            battery_pct=_int(g.get("batteryPct"), -1),
            pressure_kpa=[_int(p, 0) / 10 for p in g.get("pressureDeciKPa") or []],
            saved_address=str(g.get("savedAddress", "")),
        )
    s = obj.get("stream") or {}
    a = s.get("audio") if isinstance(s.get("audio"), dict) else {}
    return Status(
        id=str(obj.get("id", "")),
        name=str(obj.get("name", "")),
        model=str(obj.get("model", "")),
        platform=str(obj.get("platform", "")),
        app=str(obj.get("app", "")),
        app_version=str(obj.get("appVersion", "")),
        hexr_version=str(obj.get("hexrVersion", "")),
        paused=bool(obj.get("paused", False)),
        headset_battery_pct=_int(obj.get("headsetBatteryPct"), -1),
        scene_index=_int(scene_obj.get("index"), -1),
        scene_name=str(scene_obj.get("name", "")),
        scenes=[(_int(x.get("index"), -1), str(x.get("name", "")))
                for x in obj.get("scenes") or [] if isinstance(x, dict)],
        gloves=gloves,
        stream=StreamState(
            state=str(s.get("state", "off")),
            port=_int(s.get("port"), 0),
            width=_int(s.get("width"), 0),
            height=_int(s.get("height"), 0),
            viewers=_int(s.get("viewers"), 0),
            message=str(s.get("message", "")),
            audio=AudioState(
                state=str(a.get("state", "off")),
                port=_int(a.get("port"), 0),
                sample_rate=_int(a.get("sampleRate"), 0),
                channels=_int(a.get("channels"), 0),
                message=str(a.get("message", "")),
            ),
        ),
        commands=[(str(c.get("id", "")), str(c.get("label", "")))
                  for c in obj.get("commands") or [] if isinstance(c, dict)],
        allow_glove_control=bool(obj.get("allowGloveControl", True)),
        allow_video=bool(obj.get("allowVideo", True)),
        expose_scenes=bool(obj.get("exposeScenes", True)),
        # Missing before HexR 0.10.6, which does not know the request either.
        allow_recenter=bool(obj.get("allowRecenter", False)),
        controllers=_int(obj.get("controllers"), 0),
        haptics=bool(obj.get("haptics", False)),
        clock_us=_int(obj.get("clockUs"), 0),
        glove_search=_glove_search(obj.get("gloveSearch")),
    )


def _glove_search(obj) -> GloveSearch | None:
    if not isinstance(obj, dict):
        return None
    found = []
    for g in obj.get("found") or []:
        if not isinstance(g, dict) or not g.get("address"):
            continue
        found.append(NearbyGlove(
            address=str(g["address"]),
            name=str(g.get("name", "")),
            hand=g.get("hand") if g.get("hand") in HANDS else "",
            rssi=_int(g.get("rssi"), 0),
        ))
    return GloveSearch(state=str(obj.get("state", "idle")), message=str(obj.get("message", "")),
                       found=found)


HAPTIC_MODES = ("off", "pressure", "vibration", "pulse")


def parse_haptics(obj: dict) -> HapticsUpdate | None:
    """A "haptics" line, or None if it is not a usable one."""
    if obj.get("hand") not in HANDS:
        return None
    channels = []
    for c in obj.get("channels") or []:
        if not isinstance(c, dict):
            continue
        finger = _int(c.get("finger"), -1)
        mode = c.get("mode")
        if not 0 <= finger <= 5 or mode not in HAPTIC_MODES:
            continue
        channels.append(HapticChannel(
            finger=finger,
            mode=mode,
            intensity=max(0, min(100, _int(c.get("intensityPct"), 0))) / 100,
            hz=max(0, _int(c.get("frequencyDeciHz"), 0)) / 10,
            tap=c.get("tap") is True,
        ))
    return HapticsUpdate(hand=obj["hand"], t_us=_int(obj.get("t"), 0), channels=channels)


def _int(value, default: int) -> int:
    # bool is an int to Python, and never a valid number here.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return int(value)


# -- video framing -----------------------------------------------------------

VIDEO_MAGIC = b"HXV1"
CODEC_H264 = 1
FLAG_CONFIG = 1
FLAG_KEYFRAME = 2


def parse_video_header(header: bytes) -> tuple[int, int, int]:
    """The 9 bytes a video connection starts with: (width, height, codec)."""
    if len(header) != 9 or header[:4] != VIDEO_MAGIC:
        raise ValueError("not a HexR video stream")
    width, height, codec = struct.unpack(">HHB", header[4:])
    return width, height, codec


AUDIO_MAGIC = b"HXA1"
CODEC_AAC = 1


def parse_audio_header(header: bytes) -> tuple[int, int, int]:
    """The 10 bytes a sound connection starts with: (sample rate, channels, codec)."""
    if len(header) != 10 or header[:4] != AUDIO_MAGIC:
        raise ValueError("not a HexR sound stream")
    rate, channels, codec = struct.unpack(">IBB", header[4:])
    return rate, channels, codec


def parse_packet_header(header: bytes) -> tuple[int, int, int]:
    """One packet's 13-byte header: (payload length, flags, presentation time in µs)."""
    if len(header) != 13:
        raise ValueError("short packet header")
    return struct.unpack(">IBQ", header)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

class Discovery:
    """Listens for headsets announcing themselves.

    `on_announce(announce, host)` runs for every announcement, about every two seconds per
    headset. `on_error(message)` runs if the port cannot be opened at all: most often another
    copy of this app, or the probe, already listening on it.

    Windows Firewall decides whether anything arrives. The first time this listens Windows asks
    whether to allow the app on private networks; if that was refused, or the Wi-Fi is set to a
    public network, nothing arrives and no error says why. Adding a headset by its address still
    works then, because that is a connection out rather than in.
    """

    def __init__(self, on_announce, on_error=None, port: int = DISCOVERY_PORT):
        self._on_announce = on_announce
        self._on_error = on_error
        self._port = port
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="hexr-discovery", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", self._port))
            sock.settimeout(1.0)
        except OSError as e:
            if self._on_error:
                self._on_error(tr("Cannot listen for headsets on UDP {port}: {error}",
                                  port=self._port, error=e))
            return
        with sock:
            while not self._stop.is_set():
                try:
                    data, (host, _port) = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                except OSError:
                    if self._stop.wait(1.0):
                        break
                    continue
                announce = parse_announce(data)
                if announce:
                    self._on_announce(announce, host)


# ---------------------------------------------------------------------------
# Control
# ---------------------------------------------------------------------------

class HeadsetLink:
    """One headset's control connection: requests out, status and errors in.

    It keeps itself connected: a link that goes quiet for SILENT_AFTER_S is dropped and
    reopened, with a growing pause, until stop(). The listener gets
    `on_link(key, state)` with "connecting", "connected" or "lost",
    `on_status(key, status)`, `on_error(key, request, message)`, and, if it has one,
    `on_haptics(key, update)` for each haptics line.
    """

    def __init__(self, key: str, host: str, port: int, listener):
        self.key = key
        self.host = host
        self.port = port
        self._listener = listener
        self._lock = threading.Lock()
        self._sock: socket.socket | None = None
        self._generation = 0
        self._running = False

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._generation += 1
            gen = self._generation
        threading.Thread(target=self._run, args=(gen,), name=f"hexr-link-{self.host}",
                         daemon=True).start()

    def stop(self):
        with self._lock:
            self._running = False
            self._generation += 1
            sock, self._sock = self._sock, None
        _close(sock)

    def retarget(self, host: str, port: int):
        """The same headset at a new address or port (its app restarted): reconnect there."""
        if (host, port) == (self.host, self.port):
            return
        self.host, self.port = host, port
        with self._lock:
            sock, self._sock = self._sock, None
        _close(sock)  # the loop notices and reconnects to the new address

    def send(self, line: str) -> bool:
        with self._lock:
            sock = self._sock
        if sock is None:
            return False
        try:
            sock.sendall((line + "\n").encode("utf-8"))
            return True
        except OSError:
            return False

    def _alive(self, gen: int) -> bool:
        with self._lock:
            return self._running and gen == self._generation

    def _run(self, gen: int):
        backoff = 0.5
        while self._alive(gen):
            self._listener.on_link(self.key, "connecting")
            try:
                sock = socket.create_connection((self.host, self.port), timeout=3.0)
            except OSError:
                self._listener.on_link(self.key, "lost")
                if self._wait(gen, backoff):
                    return
                backoff = min(backoff * 2, 8.0)
                continue

            sock.settimeout(0.5)
            with self._lock:
                if not (self._running and gen == self._generation):
                    _close(sock)
                    return
                self._sock = sock
            self.send(hello())
            self._listener.on_link(self.key, "connected")
            backoff = 0.5
            self._read(sock, gen)
            with self._lock:
                if self._sock is sock:
                    self._sock = None
            _close(sock)
            if self._alive(gen):
                self._listener.on_link(self.key, "lost")
                if self._wait(gen, backoff):
                    return

    def _read(self, sock: socket.socket, gen: int):
        buf = b""
        last_heard = last_ping = time.monotonic()
        while self._alive(gen):
            now = time.monotonic()
            if now - last_ping >= PING_EVERY_S:
                self.send(ping())
                last_ping = now
            if now - last_heard > SILENT_AFTER_S:
                return
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                return
            if not chunk:
                return
            last_heard = time.monotonic()
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                self._handle(raw.rstrip(b"\r"))
            if len(buf) > MAX_LINE:
                return

    def _handle(self, raw: bytes):
        obj = parse_json(raw.decode("utf-8", "replace"))
        if not obj:
            return
        kind = obj.get("type")
        if kind == "status":
            self._listener.on_status(self.key, parse_status(obj))
        elif kind == "error":
            self._listener.on_error(self.key, str(obj.get("request", "")),
                                    str(obj.get("message", "")))
        elif kind == "haptics" and hasattr(self._listener, "on_haptics"):
            update = parse_haptics(obj)
            if update:
                self._listener.on_haptics(self.key, update)

    def _wait(self, gen: int, seconds: float) -> bool:
        """Sleep, but wake early if stopped. True if this loop should end."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if not self._alive(gen):
                return True
            time.sleep(0.1)
        return not self._alive(gen)


def _close(sock):
    if sock is None:
        return
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Video
# ---------------------------------------------------------------------------

def video_available() -> str | None:
    """None if this build can show a headset's view, otherwise why it cannot.

    The view is H.264, decoded with PyAV, which brings its own FFmpeg. Both the Windows and
    the macOS build ship it; only a run from source without it installed lacks it.
    """
    try:
        import av  # noqa: F401
    except ImportError:
        return tr("This build cannot show a headset's view: it was made without PyAV.")
    return None


class VideoReceiver:
    """Reads one headset's view, decoding on this thread, and hands each frame on.

    `render(frame, pts_us, arrived)` runs here for every decoded frame, with its presentation
    time on the headset's clock and the time.monotonic() it arrived, and returns whatever the UI
    draws. `latest()` hands the UI the newest result, or None if there is nothing new since the
    last call; frames the UI was too slow for are simply skipped. Each callable in `taps` (a
    recorder) gets every frame too. `state` and `message` say what it is doing, for the screen.
    """

    def __init__(self, host: str, port: int, render):
        self.host = host
        self.port = port
        self._render = render
        self._lock = threading.Lock()
        self._frame = None
        self._stop = threading.Event()
        self._sock: socket.socket | None = None
        self.taps: list = []
        self.state = "connecting"      # connecting | playing | ended | failed
        self.message = ""
        self.render_error = ""
        self.frames = 0
        self.bad_packets = 0
        threading.Thread(target=self._run, name=f"hexr-video-{host}", daemon=True).start()

    def latest(self):
        with self._lock:
            frame, self._frame = self._frame, None
        return frame

    def stop(self):
        self._stop.set()
        _close(self._sock)

    def _run(self):
        try:
            import av
        except ImportError:
            self.state, self.message = "failed", video_available() or ""
            return
        try:
            sock = socket.create_connection((self.host, self.port), timeout=5.0)
        except OSError as e:
            self.state, self.message = "failed", tr("Could not reach the view: {error}",
                                                    error=e)
            return
        self._sock = sock
        try:
            sock.settimeout(10.0)
            width, height, codec = parse_video_header(_read_exact(sock, 9))
            if codec != CODEC_H264:
                raise ValueError(f"unknown video codec {codec}")
            decoder = av.CodecContext.create("h264", "r")
            config = b""
            while not self._stop.is_set():
                length, flags, pts = parse_packet_header(_read_exact(sock, 13))
                payload = _read_exact(sock, length)
                # A new viewer is sent the encoder's SPS/PPS on their own first. FFmpeg refuses a
                # packet with no picture in it, so they go in front of the next one instead.
                if flags & FLAG_CONFIG:
                    config = payload
                    continue
                if config:
                    payload, config = config + payload, b""
                # One packet is one encoder output, so it goes to the decoder whole, carrying its
                # presentation time: that is what puts each haptic touch on the right frame.
                packet = av.Packet(payload)
                packet.pts = pts
                try:
                    frames = decoder.decode(packet)
                except av.error.InvalidDataError:
                    # One packet the decoder cannot read costs that frame, not the view: it
                    # picks up again at the next keyframe, at most a second away.
                    self.bad_packets += 1
                    continue
                for frame in frames:
                    self._keep(frame, pts if frame.pts is None else frame.pts, time.monotonic())
            self.state = "ended"
        except (OSError, ValueError, EOFError) as e:
            if self._stop.is_set() or isinstance(e, EOFError):
                self.state, self.message = "ended", ""
            else:
                self.state, self.message = "failed", tr("The view stopped: {error}",
                                                        error=e)
        except av.error.FFmpegError as e:
            self.state, self.message = "failed", tr("The view could not be decoded: {error}",
                                                    error=e)
        finally:
            _close(sock)

    def _keep(self, frame, pts_us: int, arrived: float):
        # A fault in drawing or recording one frame must not end the view: it is reported once
        # (render_error, for the screen) and the next frame tries again.
        for tap in list(self.taps):
            try:
                tap(frame, pts_us, arrived)
            except Exception as e:  # noqa: BLE001
                self.render_error = str(e) or type(e).__name__
        try:
            drawn = self._render(frame, pts_us, arrived)
        except Exception as e:  # noqa: BLE001
            self.render_error = str(e) or type(e).__name__
            return
        with self._lock:
            self._frame = drawn
        self.frames += 1
        self.state = "playing"


# ---------------------------------------------------------------------------
# Sound
# ---------------------------------------------------------------------------

class AudioReceiver:
    """Reads one headset's sound, decoding on this thread, and hands each piece on.

    Each callable in `taps` (a recorder) gets `(frame, pts_us)` for every decoded av.AudioFrame:
    1024 samples, with when they played on the headset's clock, the clock the video frames carry.
    `sample_rate` and `channels` are what the headset said it sends. `state` and `message` say what
    it is doing, as a VideoReceiver's do.
    """

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._stop = threading.Event()
        self._sock: socket.socket | None = None
        self.taps: list = []
        self.state = "connecting"      # connecting | playing | ended | failed
        self.message = ""
        self.sample_rate = 0
        self.channels = 0
        self.frames = 0
        self.bad_packets = 0
        self.tap_error = ""
        threading.Thread(target=self._run, name=f"hexr-sound-{host}", daemon=True).start()

    def stop(self):
        self._stop.set()
        _close(self._sock)

    def _run(self):
        try:
            import av
        except ImportError:
            self.state, self.message = "failed", video_available() or ""
            return
        try:
            sock = socket.create_connection((self.host, self.port), timeout=5.0)
        except OSError as e:
            self.state, self.message = "failed", tr("Could not reach the sound: {error}",
                                                    error=e)
            return
        self._sock = sock
        try:
            sock.settimeout(10.0)
            rate, channels, codec = parse_audio_header(_read_exact(sock, 10))
            if codec != CODEC_AAC:
                raise ValueError(f"unknown sound codec {codec}")
            self.sample_rate, self.channels = rate, channels
            decoder = None
            while not self._stop.is_set():
                length, flags, pts = parse_packet_header(_read_exact(sock, 13))
                payload = _read_exact(sock, length)
                # The AudioSpecificConfig comes first, and the decoder is made from it.
                if flags & FLAG_CONFIG:
                    decoder = av.CodecContext.create("aac", "r")
                    decoder.extradata = payload
                    continue
                if decoder is None:
                    continue
                packet = av.Packet(payload)
                packet.pts = pts
                try:
                    frames = decoder.decode(packet)
                except av.error.InvalidDataError:
                    self.bad_packets += 1
                    continue
                for frame in frames:
                    self._keep(frame, pts if frame.pts is None else frame.pts)
            self.state = "ended"
        except (OSError, ValueError, EOFError) as e:
            if self._stop.is_set() or isinstance(e, EOFError):
                self.state, self.message = "ended", ""
            else:
                self.state, self.message = "failed", tr("The sound stopped: {error}", error=e)
        except av.error.FFmpegError as e:
            self.state, self.message = "failed", tr("The sound could not be decoded: {error}",
                                                    error=e)
        finally:
            _close(sock)

    def _keep(self, frame, pts_us: int):
        for tap in list(self.taps):
            try:
                tap(frame, pts_us)
            except Exception as e:  # noqa: BLE001
                self.tap_error = str(e) or type(e).__name__
        self.frames += 1
        self.state = "playing"


def _read_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise EOFError("the headset closed the view")
        buf += chunk
    return bytes(buf)
