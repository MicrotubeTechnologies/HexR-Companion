"""Records a headset's view to an MP4 on this computer, and what its gloves did beside it.

The view is recorded as the headset sends it, square and with nothing drawn on it. Beside it
goes a .gloves.jsonl: each glove's state for the frames where it changed (the levels, the
vibrations, the caption's word) and what the headset said of each glove (connected, battery).
The Recordings screen turns the two into a video to share, in landscape, portrait or square
(hexr/exporter.py), as often as wanted, without the moment having to happen again.

Frames come from the video thread and are encoded on this recorder's own thread, so recording
never slows the live view; if this falls behind, frames are dropped and counted rather than
piling up. Each frame keeps the headset's presentation time, so the file plays at the speed it
happened even when the stream's frame rate wanders.

When the headset sent exact haptics, a .haptics.json goes beside it too: the touches in HexR
Overlay Studio's project format.
"""

from __future__ import annotations

import datetime
import json
import os
import queue
import re
import sys
import threading
import time
from fractions import Fraction

from .haptics import FINGERS, HandState, HapticsTimeline
from .i18n import tr

TIME_BASE = Fraction(1, 90000)
FINGER_NAMES = ("thumb", "index", "middle", "ring", "pinky", "palm")
HANDS = ("left", "right")
GLOVES_SUFFIX = ".gloves.jsonl"


def videos_folder() -> str:
    """Where recordings go: the user's Videos (Movies on a Mac), in a HEXR Companion folder.
    HEXR_VIDEOS, when set, is used instead: for tests and screenshots."""
    if os.environ.get("HEXR_VIDEOS"):
        return os.environ["HEXR_VIDEOS"]
    base = None
    if sys.platform == "win32":
        try:
            import ctypes
            import uuid
            # FOLDERID_Videos: the Videos folder wherever the user has moved it.
            guid = (ctypes.c_char * 16).from_buffer_copy(
                uuid.UUID("18989B1D-99B5-455B-841C-AB7C74E4DDFC").bytes_le)
            out = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None,
                                                          ctypes.byref(out)) == 0:
                base = out.value
                ctypes.windll.ole32.CoTaskMemFree(out)
        except Exception:  # noqa: BLE001
            base = None
    if not base:
        home = os.path.expanduser("~")
        base = os.path.join(home, "Movies" if sys.platform == "darwin" else "Videos")
    return os.path.join(base, "HEXR Companion")


def recordings_folder() -> str:
    return os.path.join(videos_folder(), "Recordings")


def exports_folder() -> str:
    return os.path.join(videos_folder(), "Exports")


def safe_name(text: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', " ", text).strip()


def recording_path(title: str, folder: str | None = None) -> str:
    folder = folder or recordings_folder()
    os.makedirs(folder, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H.%M.%S")
    return os.path.join(folder, f"{safe_name(title) or 'Headset'} {stamp}.mp4")


def gloves_path(video_path: str) -> str:
    return os.path.splitext(video_path)[0] + GLOVES_SUFFIX


# -- a glove's state, as a line of the .gloves.jsonl --------------------------------------------

def state_to_json(st: HandState) -> dict:
    return {"l": [round(v, 3) for v in st.levels], "v": [round(v, 2) for v in st.vibrating],
            "s": [round(v, 3) for v in st.since], "w": st.words, "d": st.word,
            "hz": round(st.hz, 2)}


def state_from_json(d: dict) -> HandState:
    st = HandState()
    for name, attr in (("l", "levels"), ("v", "vibrating"), ("s", "since")):
        values = d.get(name)
        if isinstance(values, list) and len(values) == FINGERS:
            setattr(st, attr, [float(v) for v in values])
    st.words, st.word = int(d.get("w", 0)), int(d.get("d", -1))
    st.hz = float(d.get("hz", 0.0))
    return st


class Recorder:
    """One recording. tap() from the video thread, stop() from the UI; `on_done(recorder)` runs
    on the recorder's thread when the file is finished (or has failed: see `error`).
    `badges_source()` says what the headset says of each glove now, as the view's panels show."""

    QUEUE = 90           # three seconds at 30 fps

    def __init__(self, path: str, timeline: HapticsTimeline, badges_source=lambda: (),
                 on_done=None, title: str = ""):
        self.path = path
        self.timeline = timeline
        self.title = title
        self._badges_source = badges_source
        self._on_done = on_done
        self._queue: queue.Queue = queue.Queue(maxsize=self.QUEUE)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="hexr-recorder", daemon=True)
        self.started = time.monotonic()
        self.frames = 0
        self.dropped = 0
        self.error = ""
        self.done = False
        self.log_path = ""

    def start(self):
        self._thread.start()

    def tap(self, frame, pts_us: int, arrived: float):
        if self._stop.is_set():
            return
        try:
            # The gloves are read now, as the frame arrives: the badges are what is true now.
            self._queue.put_nowait((frame, pts_us, arrived, self._badges_source()))
        except queue.Full:
            self.dropped += 1

    def stop(self):
        self._stop.set()

    @property
    def seconds(self) -> float:
        return time.monotonic() - self.started

    # -- the recording thread -------------------------------------------------------------------

    def _run(self):
        container = stream = gloves = None
        first = last = None          # (pts_us, frame time on the headset's clock)
        last_pts = -1
        last_line = None
        size = None
        try:
            while True:
                try:
                    item = self._queue.get(timeout=0.2)
                except queue.Empty:
                    if self._stop.is_set():
                        break
                    continue
                frame, pts_us, arrived, badges = item
                if container is None:
                    size = (frame.width // 2 * 2, frame.height // 2 * 2)
                    container, stream = open_video(self.path, size)
                    first = (pts_us, self.timeline.frame_time(pts_us, arrived))
                    gloves = open(gloves_path(self.path), "w", encoding="utf-8")
                    gloves.write(json.dumps({
                        "hexr": "gloves", "version": 1, "title": self.title,
                        "started": datetime.datetime.now().isoformat(timespec="seconds"),
                        "size": list(size)}) + "\n")
                last = (pts_us, self.timeline.frame_time(pts_us, arrived))
                pts = max(last_pts + 1, round((pts_us - first[0]) / 1e6 / TIME_BASE))
                last_pts = pts

                line = {h: state_to_json(self.timeline.state(h, pts_us, arrived)) for h in HANDS}
                line["badges"] = {h: [b.state, b.battery] for h, b in badges}
                if line != last_line:
                    last_line = line
                    gloves.write(json.dumps({"t": round(float(pts * TIME_BASE), 4), **line}) + "\n")

                out = frame.reformat(width=size[0], height=size[1], format="yuv420p")
                out.pts = pts
                out.time_base = TIME_BASE
                for packet in stream.encode(out):
                    container.mux(packet)
                self.frames += 1
            if container is not None:
                for packet in stream.encode(None):
                    container.mux(packet)
                container.close()
                container = None
                if self.timeline.exact and first and last:
                    self.log_path = self._write_log(first[1], last[1])
            elif not self.error:
                self.error = tr("No frames arrived while recording.")
        except Exception as e:  # noqa: BLE001
            self.error = str(e) or type(e).__name__
            if container is not None:
                try:
                    container.close()
                except Exception:  # noqa: BLE001
                    pass
        finally:
            if gloves is not None:
                gloves.close()
            self.done = True
            if self._on_done:
                self._on_done(self)

    def _write_log(self, t0: float, t1: float) -> str:
        """The touches during the recording, in HexR Overlay Studio's project format."""
        events = []
        for hand, finger, s in self.timeline.segments_between(t0, t1):
            start = max(0.0, s.t0 - t0)
            end = min(t1, s.t1 if s.t1 is not None else t1) - t0
            if end <= start:
                continue
            event = {"hand": hand, "finger": FINGER_NAMES[finger],
                     "type": "pressure" if s.mode == "pressure" else "vibration",
                     "start": round(start, 3), "end": round(end, 3),
                     "strength": round(s.intensity, 2)}
            if s.mode != "pressure":
                event["hz"] = s.hz
            events.append(event)
        project = {"app": "hexr-overlay-studio", "version": 1,
                   "video": {"name": os.path.basename(self.path), "duration": round(t1 - t0, 3)},
                   "events": events}
        path = os.path.splitext(self.path)[0] + ".haptics.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(project, f, indent=2)
        return path


def open_video(path: str, size: tuple[int, int], rate: int = 30):
    """An MP4 to write H.264 into: (container, stream), timed in TIME_BASE."""
    import av
    container = av.open(path, "w", options={"movflags": "+faststart"})
    for name in ("libx264", "h264_mf", "mpeg4"):
        try:
            stream = container.add_stream(name, rate=rate)
            break
        except Exception:  # noqa: BLE001
            continue
    else:
        container.close()
        raise RuntimeError(tr("This build has no video encoder."))
    stream.width, stream.height = size
    stream.pix_fmt = "yuv420p"
    stream.codec_context.thread_type = "AUTO"
    stream.time_base = TIME_BASE
    stream.codec_context.time_base = TIME_BASE
    if stream.codec_context.name == "libx264":
        stream.options = {"crf": "20", "preset": "veryfast"}
    else:
        stream.bit_rate = 8_000_000
    return container, stream
