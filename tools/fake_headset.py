"""A pretend HEXR headset on this computer, for trying the Headsets screen without a Quest.

It announces itself, takes the control connection, sends a status five times a second and, once
the app asks to watch, streams video the way HexR Remote does: H.264 at 30 fps, square, framed
in the protocol's packets with presentation times. The picture is a clip you give it, looped
and cut square, or else a moving test card. Its gloves play a twelve-second loop of touches
(a press, a grab, a palm pulse, a buzz, a tap), sent as haptics lines stamped on the video's
clock, so the glove overlay has something to show.

    python tools/fake_headset.py                       a test card, exact haptics
    python tools/fake_headset.py --video demo.mp4      your clip instead
    python tools/fake_headset.py --measured            an older headset: pressure only

Then open Headsets in the app. If it does not appear, type 127.0.0.1 as the headset's address.
Needs PyAV (pip install av), as the app's view does. Ctrl+C stops it.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import socket
import struct
import sys
import threading
import time
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hexr.remote import CONTROL_PORT, DISCOVERY_PORT, VIDEO_PORT  # noqa: E402

FPS = 30
SIZE = 1024
LOOP_S = 12.0
FINGERS = ("thumb", "index", "middle", "ring", "pinky", "palm")

# (start, end, hand, fingers, mode, intensity, hz) within each loop
SCRIPT = [
    (1.0, 2.5, "right", [1], "pressure", 0.8, 0),
    (3.0, 5.0, "right", [0, 1, 2, 3, 4, 5], "pressure", 0.9, 0),
    (6.0, 8.0, "right", [5], "vibration", 0.7, 2),
    (8.5, 10.0, "left", [2, 3], "vibration", 0.6, 12),
    (10.5, 10.5, "right", [1], "pressure", 0.6, 0),        # a tap: on and off in one frame
]


def now_us() -> int:
    return int(time.monotonic() * 1e6)


class FakeHeadset:
    def __init__(self, args):
        self.args = args
        self.id = "fake-" + socket.gethostname().lower()[:12]
        self.started_at = int(time.time() * 1000)
        self.clients: list[socket.socket] = []
        self.viewers: list[dict] = []
        self.lock = threading.Lock()
        self.stream_state = "off"
        self.gloves = {"left": "connected", "right": "connected"}
        self.channels = {(h, f): None for h in ("left", "right") for f in range(6)}
        self.loop_start = time.monotonic()
        self.control_port = _listen_port(CONTROL_PORT)
        self.video_port = _listen_port(VIDEO_PORT)

    # -- the loop of touches ----------------------------------------------------------------

    def touches_at(self, t: float) -> dict:
        """What each channel is doing at loop time t: None or (mode, intensity, hz)."""
        state = {k: None for k in self.channels}
        for start, end, hand, fingers, mode, intensity, hz in SCRIPT:
            if start <= t < max(end, start + 1e-9) and end > start:
                for f in fingers:
                    state[(hand, f)] = (mode, intensity, hz)
        return state

    def run_haptics(self):
        last_t = 0.0
        while True:
            t = (time.monotonic() - self.loop_start) % LOOP_S
            state = self.touches_at(t)
            stamp = now_us()
            changed = {"left": [], "right": []}
            for key, value in state.items():
                if value != self.channels[key]:
                    self.channels[key] = value
                    changed[key[0]].append(_channel(key[1], value, False))
            for start, end, hand, fingers, mode, intensity, hz in SCRIPT:
                # A tap is on and off within one frame, so it is sent once, as the loop passes it.
                passed = last_t <= start < t if t >= last_t else (start >= last_t or start < t)
                if end == start and passed:
                    for f in fingers:
                        changed[hand].append(_channel(f, (mode, intensity, hz), True))
            last_t = t
            if not self.args.measured:
                for hand, chans in changed.items():
                    if chans:
                        self.broadcast({"type": "haptics", "t": stamp, "hand": hand,
                                        "channels": chans})
            time.sleep(1 / 120)

    def snapshot(self) -> list[dict]:
        return [{"type": "haptics", "t": now_us(), "hand": hand,
                 "channels": [_channel(f, self.channels[(hand, f)], False) for f in range(6)]}
                for hand in ("left", "right")]

    def pressure(self, hand: str) -> list[int]:
        """Measured pressure the way a glove would report it: lagging the commands a little."""
        t = (time.monotonic() - self.loop_start - 0.08) % LOOP_S
        state = self.touches_at(t)
        out = []
        for f in range(6):
            value = state[(hand, f)]
            if value is None:
                out.append(5)
            elif value[0] == "pressure":
                out.append(int((15 + 35 * (value[1] - 0.1) / 0.9) * 10))
            else:
                on = math.sin(2 * math.pi * value[2] * t) > 0
                out.append(450 if on else 40)
        return out + [452]

    # -- control ------------------------------------------------------------------------

    def status(self) -> dict:
        with self.lock:
            viewers = len(self.viewers)
        return {
            "type": "status", "protocol": 1, "id": self.id, "name": self.args.name,
            "model": "Fake Quest", "platform": "quest", "app": "HexR Fake Headset",
            "appVersion": "1.0", "hexrVersion": "0.9.6" if self.args.measured else "0.10.2",
            "paused": False, "headsetBatteryPct": 80,
            "scene": {"index": 0, "name": "Test card"}, "scenes": [],
            "gloves": [{"hand": h, "state": self.gloves[h],
                        "message": "Connected" if self.gloves[h] == "connected" else "",
                        "batteryPct": 77 if self.gloves[h] == "connected" else -1,
                        "pressureDeciKPa": self.pressure(h) if self.gloves[h] == "connected" else []}
                       for h in ("left", "right")],
            "stream": {"state": self.stream_state, "port": self.video_port, "width": SIZE,
                       "height": SIZE, "viewers": viewers, "message": ""},
            "commands": [{"id": "restart", "label": "Restart the loop"}],
            "allowGloveControl": True, "allowVideo": True, "exposeScenes": False,
            "allowRecenter": False, "controllers": len(self.clients),
            **({} if self.args.measured else {"haptics": True, "clockUs": now_us()}),
        }

    def broadcast(self, obj: dict):
        line = (json.dumps(obj, separators=(",", ":")) + "\n").encode()
        with self.lock:
            clients = list(self.clients)
        for c in clients:
            try:
                c.sendall(line)
            except OSError:
                pass

    def run_control(self):
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("", self.control_port))
        server.listen()
        while True:
            conn, addr = server.accept()
            print(f"app connected from {addr[0]}")
            with self.lock:
                self.clients.append(conn)
            threading.Thread(target=self.serve_client, args=(conn,), daemon=True).start()

    def serve_client(self, conn: socket.socket):
        buf = b""
        try:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    self.handle(conn, json.loads(raw or b"{}"))
        except (OSError, ValueError):
            pass
        with self.lock:
            if conn in self.clients:
                self.clients.remove(conn)
        print("app disconnected")

    def handle(self, conn, req: dict):
        kind = req.get("type")
        if kind == "hello":
            lines = [{"type": "hello", "protocol": 1, "id": self.id, "control": self.control_port,
                      "video": self.video_port}]
            if not self.args.measured:
                lines += self.snapshot()
            for obj in lines:
                conn.sendall((json.dumps(obj, separators=(",", ":")) + "\n").encode())
        elif kind == "stream":
            if req.get("action") == "start" and self.stream_state != "live":
                self.stream_state = "requesting"
                threading.Timer(1.0, lambda: setattr(self, "stream_state", "live")).start()
            elif req.get("action") == "stop":
                self.stream_state = "off"
                with self.lock:
                    viewers, self.viewers = self.viewers, []
                for v in viewers:
                    _close(v["sock"])
        elif kind == "glove":
            self.gloves[req.get("hand", "left")] = \
                "connected" if req.get("action") == "connect" else "disconnected"
        elif kind == "command" and req.get("id") == "restart":
            self.loop_start = time.monotonic()
        elif kind not in ("ping", "release"):
            conn.sendall((json.dumps({"type": "error", "request": kind,
                                      "message": f"The fake headset does not do {kind}."}) + "\n").encode())

    def run_status(self):
        while True:
            self.broadcast(self.status())
            time.sleep(0.2)

    def run_announce(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while True:
            data = json.dumps({"hexr": 1, "type": "announce", "id": self.id, "name": self.args.name,
                               "model": "Fake Quest", "platform": "quest",
                               "app": "HexR Fake Headset", "appId": "com.microtube.fake",
                               "hexrVersion": "0.10.2", "control": self.control_port,
                               "video": self.video_port, "startedAt": self.started_at}).encode()
            # One announcement, as a headset sends: the app follows a headset to whichever
            # address announced it last, so two copies from two addresses would keep it moving.
            try:
                sock.sendto(data, ("255.255.255.255", DISCOVERY_PORT))
            except OSError:
                pass
            time.sleep(2)

    # -- video ----------------------------------------------------------------------------

    def run_video_server(self):
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("", self.video_port))
        server.listen()
        while True:
            conn, _ = server.accept()
            if self.stream_state != "live":
                _close(conn)
                continue
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            conn.sendall(b"HXV1" + struct.pack(">HHB", SIZE, SIZE, 1))
            with self.lock:
                self.viewers.append({"sock": conn, "keyed": False})
            print("viewer joined")

    def run_encoder(self):
        import av
        enc = av.CodecContext.create("libx264", "w")
        enc.width = enc.height = SIZE
        enc.pix_fmt = "yuv420p"
        enc.time_base = Fraction(1, 1_000_000)
        enc.framerate = Fraction(FPS, 1)
        enc.options = {"preset": "ultrafast", "tune": "zerolatency", "profile": "baseline",
                       "x264-params": f"keyint={FPS}:min-keyint={FPS}:repeat-headers=1:bframes=0"}
        source = _frames(self.args.video)
        period = 1 / FPS
        next_at = time.monotonic()
        while True:
            next_at += period
            delay = next_at - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            with self.lock:
                watching = list(self.viewers)
            img = next(source)
            if not watching:
                continue
            frame = av.VideoFrame.from_image(img).reformat(format="yuv420p")
            frame.pts = now_us()
            frame.time_base = Fraction(1, 1_000_000)
            for packet in enc.encode(frame):
                key = bool(packet.is_keyframe)
                payload = bytes(packet)
                header = struct.pack(">IBQ", len(payload), 2 if key else 0, packet.pts)
                for v in watching:
                    if not v["keyed"] and not key:
                        continue
                    v["keyed"] = True
                    try:
                        v["sock"].sendall(header + payload)
                    except OSError:
                        with self.lock:
                            if v in self.viewers:
                                self.viewers.remove(v)
                        print("viewer left")


def _channel(finger: int, value, tap: bool) -> dict:
    if value is None:
        return {"finger": finger, "mode": "off", "intensityPct": 0, "frequencyDeciHz": 0,
                "tap": False}
    mode, intensity, hz = value
    return {"finger": finger, "mode": mode, "intensityPct": int(intensity * 100),
            "frequencyDeciHz": int(hz * 10), "tap": tap}


def _frames(path: str | None):
    """Square frames forever: a looped clip, or a moving test card."""
    from PIL import Image, ImageDraw
    if path:
        import av
        while True:
            with av.open(path) as clip:
                for f in clip.decode(video=0):
                    img = f.to_image()
                    side = min(img.size)
                    left, top = (img.width - side) // 2, (img.height - side) // 2
                    yield img.crop((left, top, left + side, top + side)).resize((SIZE, SIZE))
    n = 0
    while True:
        img = Image.new("RGB", (SIZE, SIZE), (24, 26, 30))
        d = ImageDraw.Draw(img)
        for i in range(0, SIZE, 64):
            d.line((i, 0, i, SIZE), fill=(40, 43, 48))
            d.line((0, i, SIZE, i), fill=(40, 43, 48))
        x = SIZE / 2 + math.sin(n / 40) * 300
        d.ellipse((x - 60, 620, x + 60, 740), fill=(242, 102, 26))
        d.text((40, 40), f"HexR fake headset  {n / FPS:7.2f} s", fill=(230, 230, 230))
        n += 1
        yield img


def _listen_port(preferred: int) -> int:
    for port in range(preferred, preferred + 10):
        probe = socket.socket()
        try:
            probe.bind(("", port))
            return port
        except OSError:
            continue
        finally:
            probe.close()
    raise SystemExit(f"No free port near {preferred}.")


def _close(sock):
    try:
        sock.close()
    except OSError:
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--video", help="a clip to show instead of the test card")
    parser.add_argument("--measured", action="store_true",
                        help="behave like a headset before HexR 0.10.2: pressure only, no haptics")
    parser.add_argument("--name", default="Fake Quest")
    args = parser.parse_args()
    h = FakeHeadset(args)
    for target in (h.run_control, h.run_status, h.run_announce, h.run_video_server,
                   h.run_encoder, h.run_haptics):
        threading.Thread(target=target, daemon=True).start()
    print(f"Fake headset '{args.name}' on control port {h.control_port}, video {h.video_port}"
          f"{' (measured pressure only)' if args.measured else ''}. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
