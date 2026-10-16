"""A recording, made into a video to share: the view beside its gloves, in landscape (16:9) or
portrait (9:16), YouTube's two shapes, or the view alone, square.

A recording is the headset's view as it came and a .gloves.jsonl of what the gloves did
(hexr/recorder.py). An export draws the two together a frame at a time (hexr/viewer.py), on a
thread of its own, and can be stopped. The same recording can be exported in every shape, as
often as wanted. No Tk.
"""

from __future__ import annotations

import bisect
import json
import os
import threading
from dataclasses import dataclass

from . import recorder as REC
from .haptics import HandState
from .viewer import LANDSCAPE, PORTRAIT, SIZE, SQUARE, Compositor, GloveBadge, to_frame

# In the exported file's name, so the shapes of one recording sit side by side in the folder.
FILE_LABEL = {LANDSCAPE: "Landscape", PORTRAIT: "Portrait", SQUARE: "Square"}
HANDS = ("left", "right")


@dataclass
class Recording:
    path: str
    title: str          # the headset's name when it was recorded
    started: str        # ISO, to the second
    modified: float

    @property
    def stem(self) -> str:
        return os.path.splitext(os.path.basename(self.path))[0]


def find_recordings(folder: str | None = None) -> list[Recording]:
    """Every recording that can be exported (a video with its gloves beside it), newest first."""
    folder = folder or REC.recordings_folder()
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    found = []
    for name in names:
        if not name.lower().endswith(".mp4"):
            continue
        path = os.path.join(folder, name)
        head = _header(REC.gloves_path(path))
        if head is None:
            continue
        try:
            modified = os.path.getmtime(path)
        except OSError:
            continue
        found.append(Recording(path, str(head.get("title") or ""), str(head.get("started") or ""),
                               modified))
    return sorted(found, key=lambda r: r.modified, reverse=True)


def export_path(rec: Recording, layout: str) -> str:
    return os.path.join(REC.exports_folder(), f"{rec.stem} ({FILE_LABEL[layout]}).mp4")


def _header(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            head = json.loads(f.readline())
    except (OSError, ValueError):
        return None
    return head if isinstance(head, dict) and head.get("hexr") == "gloves" else None


class GloveTrack:
    """What the gloves did through a recording: their state at any moment of it."""

    def __init__(self, path: str):
        self.times: list[float] = []
        self._lines: list[tuple[dict, tuple]] = []
        try:
            with open(path, encoding="utf-8") as f:
                f.readline()
                for raw in f:
                    try:
                        line = json.loads(raw)
                        t = float(line["t"])
                    except (ValueError, KeyError, TypeError):
                        continue      # a recording cut off mid-line still exports
                    states = {h: REC.state_from_json(line[h]) for h in HANDS
                              if isinstance(line.get(h), dict)}
                    badges = tuple((h, GloveBadge(str(b[0]), int(b[1])))
                                   for h, b in (line.get("badges") or {}).items()
                                   if isinstance(b, list) and len(b) == 2)
                    self.times.append(t)
                    self._lines.append((states, badges))
        except OSError:
            pass

    def at(self, t: float) -> tuple[dict[str, HandState], tuple]:
        i = bisect.bisect_right(self.times, t + 1e-6) - 1
        return self._lines[i] if i >= 0 else ({}, ())

    def liveliest(self) -> float:
        """A moment worth showing in a preview: when the gloves were busiest, else the start."""
        best, when = 0.0, 0.0
        for t, (states, _b) in zip(self.times, self._lines):
            total = sum(sum(st.levels) for st in states.values())
            if total > best + 1e-6:
                best, when = total, t
        return when


def probe(rec: Recording, thumb: int = 64):
    """(seconds long, a square thumbnail of its first frame), or (0, None) if it cannot be read."""
    try:
        import av
        with av.open(rec.path) as src:
            vs = src.streams.video[0]
            seconds = float(vs.duration * vs.time_base) if vs.duration else \
                (src.duration or 0) / 1e6
            for frame in src.decode(vs):
                img = frame.to_image()
                img.thumbnail((thumb, thumb))
                return seconds, img
    except Exception:  # noqa: BLE001
        pass
    return 0.0, None


def still(rec: Recording, layout: str, fit: tuple[int, int], at: float | None = None):
    """One frame of the export, to preview it: at `at` seconds, or where the gloves are busiest."""
    import av
    track = GloveTrack(REC.gloves_path(rec.path))
    t = track.liveliest() if at is None else at
    with av.open(rec.path) as src:
        vs = src.streams.video[0]
        if t > 0.5:
            src.seek(int(max(0.0, t - 1.0) / vs.time_base), stream=vs, backward=True)
        shown = None
        for frame in src.decode(vs):
            shown = frame
            if frame.time is None or frame.time >= t:
                break
        if shown is None:
            return None
        states, badges = track.at(float(shown.time or 0.0))
        return Compositor().draw(shown, states, badges, layout, fit)


class Export:
    """One export, on its own thread. `progress` runs 0 to 1; `done`, then `error` or `path`."""

    def __init__(self, rec: Recording, layout: str, on_done=None):
        self.rec = rec
        self.layout = layout
        self.path = export_path(rec, layout)
        self.progress = 0.0
        self.done = False
        self.error = ""
        self.stopped = False
        self._on_done = on_done
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="hexr-export", daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        container = None
        try:
            import av
            track = GloveTrack(REC.gloves_path(self.rec.path))
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            compositor = Compositor()
            with av.open(self.rec.path) as src:
                vs = src.streams.video[0]
                total = float(vs.duration * vs.time_base) if vs.duration else \
                    (src.duration or 0) / 1e6
                container, stream = REC.open_video(self.path, SIZE[self.layout])
                last_pts = -1
                for frame in src.decode(vs):
                    if self._stop.is_set():
                        break
                    t = float(frame.time or 0.0)
                    states, badges = track.at(t)
                    img = compositor.draw(frame, states, badges, self.layout)
                    out = to_frame(img).reformat(format="yuv420p")
                    pts = max(last_pts + 1, round(t / REC.TIME_BASE))
                    last_pts = pts
                    out.pts = pts
                    out.time_base = REC.TIME_BASE
                    for packet in stream.encode(out):
                        container.mux(packet)
                    if total > 0:
                        self.progress = min(1.0, t / total)
                if not self._stop.is_set():
                    for packet in stream.encode(None):
                        container.mux(packet)
                container.close()
                container = None
            if self._stop.is_set():
                self.stopped = True
                _remove(self.path)
            else:
                self.progress = 1.0
        except Exception as e:  # noqa: BLE001
            self.error = str(e) or type(e).__name__
            if container is not None:
                try:
                    container.close()
                except Exception:  # noqa: BLE001
                    pass
            _remove(self.path)
        finally:
            self.done = True
            if self._on_done:
                self._on_done(self)


def _remove(path: str):
    try:
        os.remove(path)
    except OSError:
        pass
