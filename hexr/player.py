"""A recording played back as it will be exported: the view beside its gloves, in the shape
chosen, at the speed it happened.

Decoding and drawing happen on the player's own thread, paced to the clock; the Recordings
screen takes the newest picture when it draws. A player that falls behind skips drawing frames
rather than slowing down. Changing the shape redraws the frame shown. It plays no sound: a
recording's sound, when the headset shared it, is in the exported video. No Tk.
"""

from __future__ import annotations

import threading
import time

from . import recorder as REC
from .exporter import GloveTrack, Recording
from .viewer import Compositor

BEHIND_S = 0.25        # this late, a frame is decoded but not drawn, to catch up


class Player:
    """Plays one recording. play(), pause(), seek() and set_shape() from the UI; latest() gives
    the newest picture, or None if there is nothing new. Opens on the moment the gloves were
    busiest (or `start_at`), paused."""

    def __init__(self, rec: Recording, layout: str, fit: tuple[int, int],
                 start_at: float | None = None):
        self.rec = rec
        self.layout, self.fit = layout, fit
        self.duration = 0.0
        self.position = 0.0
        self.playing = False
        self.ended = False
        self.error = ""
        self._track = GloveTrack(REC.gloves_path(rec.path))
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._seek_to: float | None = self._track.liveliest() if start_at is None else start_at
        self._redraw = False
        self._closed = False
        self._image = None
        self._thread = threading.Thread(target=self._run, name="hexr-player", daemon=True)
        self._thread.start()

    # -- from the UI ---------------------------------------------------------------------------

    def play(self):
        if self.ended:
            self.seek(0.0)
        self.playing = True
        self._wake.set()

    def pause(self):
        self.playing = False
        self._wake.set()

    def seek(self, t: float):
        with self._lock:
            t = max(0.0, min(t, self.duration or t))
            self._seek_to = t
            self.position = t
        self._wake.set()

    def set_shape(self, layout: str, fit: tuple[int, int]):
        with self._lock:
            self.layout, self.fit = layout, fit
            self._redraw = True
        self._wake.set()

    def close(self):
        self._closed = True
        self._wake.set()

    def latest(self):
        with self._lock:
            image, self._image = self._image, None
        return image

    # -- the player's thread -------------------------------------------------------------------

    def _run(self):
        try:
            import av
            with av.open(self.rec.path) as src:
                vs = src.streams.video[0]
                self.duration = float(vs.duration * vs.time_base) if vs.duration else \
                    (src.duration or 0) / 1e6
                compositor = Compositor()
                frames = src.decode(vs)
                shown = None           # (frame, its time): the frame on screen
                anchor = None          # (clock, frame time) the playing is paced from
                while not self._closed:
                    with self._lock:
                        seek, self._seek_to = self._seek_to, None
                        redraw, self._redraw = self._redraw, False
                        layout, fit = self.layout, self.fit
                    if seek is not None:
                        frames, shown = _seek(src, vs, seek)
                        self.ended, anchor, redraw = False, None, True
                        if shown:
                            self.position = shown[1]
                    if not self.playing:
                        anchor = None
                        if redraw and shown:
                            self._draw(compositor, shown, layout, fit)
                        self._wake.wait(0.2)
                        self._wake.clear()
                        continue

                    frame = next(frames, None)
                    if frame is None:
                        self.playing, self.ended = False, True
                        self.position = self.duration
                        continue
                    t = float(frame.time or 0.0)
                    if anchor is None:
                        anchor = (time.monotonic(), t)
                    late = time.monotonic() - (anchor[0] + t - anchor[1])
                    if late < 0:
                        self._wake.wait(-late)      # a command wakes it early
                        self._wake.clear()
                    shown = (frame, t)
                    self.position = t
                    if late < BEHIND_S or redraw:
                        self._draw(compositor, shown, layout, fit)
        except Exception as e:  # noqa: BLE001
            self.error = str(e) or type(e).__name__
            self.playing = False

    def _draw(self, compositor: Compositor, shown, layout: str, fit):
        frame, t = shown
        states, badges = self._track.at(t)
        image = compositor.draw(frame, states, badges, layout, fit)
        with self._lock:
            self._image = image


def _seek(src, vs, t: float):
    """Decoding from the frame at `t`: (the frames after it, (that frame, its time))."""
    if t > 0.5:
        src.seek(int(max(0.0, t - 1.0) / vs.time_base), stream=vs, backward=True)
    else:
        src.seek(0, stream=vs, backward=True)
    frames = src.decode(vs)
    found = None
    for frame in frames:
        found = (frame, float(frame.time or 0.0))
        if found[1] >= t - 1 / 60:
            break
    return frames, found
