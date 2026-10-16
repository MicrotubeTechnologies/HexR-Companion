"""Records a headset's view, as it is shown with the glove on top, to an MP4 on this computer.

Frames come from the video thread and are drawn and encoded on this recorder's own thread, so
recording never slows the live view; if this falls behind, frames are dropped and counted rather
than piling up. Each frame keeps the headset's presentation time, so the file plays at the speed
it happened even when the stream's frame rate wanders.

Beside the video goes a .haptics.json, when the headset sent exact haptics: the touches in
HexR Overlay Studio's project format, so the overlay can be restyled there afterwards.
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

from .haptics import HapticsTimeline
from .i18n import tr
from .viewer import Compositor

TIME_BASE = Fraction(1, 90000)
FINGER_NAMES = ("thumb", "index", "middle", "ring", "pinky", "palm")


def videos_folder() -> str:
    """Where recordings go: the user's Videos (Movies on a Mac), in a HEXR Companion folder."""
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


def recording_path(title: str, folder: str | None = None) -> str:
    folder = folder or videos_folder()
    os.makedirs(folder, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|]+', " ", title).strip() or "Headset"
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H.%M.%S")
    return os.path.join(folder, f"{safe} {stamp}.mp4")


class Recorder:
    """One recording. tap() from the video thread, stop() from the UI; `on_done(recorder)` runs
    on the recorder's thread when the file is finished (or has failed: see `error`)."""

    QUEUE = 90           # three seconds at 30 fps

    def __init__(self, path: str, timeline: HapticsTimeline, look_source, on_done=None):
        self.path = path
        self.timeline = timeline
        self._look_source = look_source        # () -> the ViewLook to draw with now
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
        self._landscape = look_source().landscape   # fixed for the file: its size cannot change

    def start(self):
        self._thread.start()

    def tap(self, frame, pts_us: int, arrived: float):
        if self._stop.is_set():
            return
        try:
            self._queue.put_nowait((frame, pts_us, arrived))
        except queue.Full:
            self.dropped += 1

    def stop(self):
        self._stop.set()

    @property
    def seconds(self) -> float:
        return time.monotonic() - self.started

    # -- the recording thread -------------------------------------------------------------------

    def _run(self):
        container = stream = None
        first = last = None          # (pts_us, frame time on the headset's clock)
        last_pts = -1
        size = None
        try:
            import av
            compositor = Compositor(self.timeline, self._look_source())
            while True:
                try:
                    item = self._queue.get(timeout=0.2)
                except queue.Empty:
                    if self._stop.is_set():
                        break
                    continue
                frame, pts_us, arrived = item
                compositor.look = self._look_source().but(landscape=self._landscape)
                img = compositor.compose(frame, pts_us, arrived)
                if container is None:
                    size = (img.width // 2 * 2, img.height // 2 * 2)
                    container, stream = _open(self.path, size)
                    first = (pts_us, self.timeline.frame_time(pts_us, arrived))
                if img.size != size:
                    img = img.resize(size)
                last = (pts_us, self.timeline.frame_time(pts_us, arrived))
                pts = max(last_pts + 1, round((pts_us - first[0]) / 1e6 / TIME_BASE))
                last_pts = pts
                out = av.VideoFrame.from_image(img).reformat(format="yuv420p")
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


def _open(path: str, size: tuple[int, int]):
    import av
    container = av.open(path, "w", options={"movflags": "+faststart"})
    for name in ("libx264", "h264_mf", "mpeg4"):
        try:
            stream = container.add_stream(name, rate=30)
            break
        except Exception:  # noqa: BLE001
            continue
    else:
        container.close()
        raise RuntimeError(tr("This build has no video encoder."))
    stream.width, stream.height = size
    stream.pix_fmt = "yuv420p"
    stream.time_base = TIME_BASE
    stream.codec_context.time_base = TIME_BASE
    if stream.codec_context.name == "libx264":
        stream.options = {"crf": "20", "preset": "veryfast"}
    else:
        stream.bit_rate = 8_000_000
    return container, stream
