"""What a headset's gloves are doing to the wearer's hands, moment by moment, for the overlay.

Two sources, the better one used when the headset has it:

- Exact: a headset with HexR 0.10.2 or later sends a "haptics" line for every command, stamped
  on the clock its video frames are stamped with, so each touch lands on the frame showing it.
- Measured: every headset's status carries each glove's measured pressure five times a second.
  Enough to show a press and a hold; too slow to show a vibration or a tap.

Levels are worked out from the history for whatever moment is asked about, never stepped along
frame by frame, so the live view and a recording drawn later from the same moment agree.

Nothing here touches Tk or images; hexr/overlay.py draws what this says.
"""

from __future__ import annotations

import math
import threading
from collections import deque
from dataclasses import dataclass, field

HANDS = ("left", "right")
FINGERS = 6

ATTACK_S = 0.09      # how fast an actuator is drawn filling: the website's glove uses the same
RELEASE_S = 0.25     # and emptying
TAP_S = 0.12         # how long a tap (on and off within one headset frame) is shown
PRESS_S = 0.3        # how long "PRESS." stays lit before "HOLD."
RELEASE_WORD_S = 0.7 # and "RELEASE." after a release
KEEP_S = 60.0        # history kept

# The view reaches the screen after the status saying what the glove did at the same moment:
# about this much later, after encoding, the network and decoding.
VIDEO_LAG_S = 0.15

# A frame whose presentation time is this close to the headset's clock is on that clock.
SAME_CLOCK_S = 5.0

# Measured pressure, in kPa above ambient, drawn as fully on. Commands drive 15-50 kPa.
FULL_KPA = 45.0
QUIET_KPA = 2.0


@dataclass
class Segment:
    t0: float                  # seconds on the headset's clock
    t1: float | None           # None while still on
    mode: str                  # pressure | vibration | pulse
    intensity: float           # 0.1-1
    hz: float = 0.0


@dataclass
class HandState:
    """One glove at one moment, ready to draw."""
    levels: list[float] = field(default_factory=lambda: [0.0] * FINGERS)   # 0-1
    vibrating: list[float] = field(default_factory=lambda: [0.0] * FINGERS)  # Hz while vibrating
    since: list[float] = field(default_factory=lambda: [0.0] * FINGERS)    # s since it started
    words: int = 0             # caption set: 0 press/hold/release, 1 pulse/buzz/click
    word: int = -1             # which word of it is lit, -1 none
    hz: float = 0.0            # the current vibration's frequency, for the caption


def segment_level(s: Segment, t: float) -> float:
    """How full one actuator is drawn at `t`: fills while on, empties after, as air does."""
    if t < s.t0:
        return 0.0
    end = t if s.t1 is None else s.t1
    filled = 1 - math.exp(-max(0.0, min(t, end) - s.t0) / ATTACK_S)
    level = filled if t <= end else filled * math.exp(-(t - end) / RELEASE_S)
    level *= s.intensity
    if s.mode != "pressure" and t <= end:
        if s.hz <= 5:
            # Slow enough to see each pulse on a 30 fps video.
            phase = ((t - s.t0) * s.hz) % 1
            level *= 0.2 + 0.8 * (0.5 + 0.5 * math.tanh(5 * math.cos(2 * math.pi * phase)))
        else:
            # Faster than video can show: a steady glow with a shimmer; the rings say "vibrating".
            level *= 0.86 + 0.14 * math.sin((t - s.t0) * 2 * math.pi * 7)
    return level if level > 0.003 else 0.0


class HapticsTimeline:
    """One headset's haptics history. Fed from the control link's thread, read from the
    decode and recording threads."""

    def __init__(self):
        self._lock = threading.Lock()
        self._segments: dict[tuple[str, int], list[Segment]] = {
            (h, f): [] for h in HANDS for f in range(FINGERS)}
        self._pressure: dict[str, deque] = {h: deque(maxlen=600) for h in HANDS}
        self._offsets: deque = deque(maxlen=40)   # headset clock - our clock, seconds
        self.exact = False      # the headset sends haptics lines
        self._used: set[str] = set()

    # -- feeding ------------------------------------------------------------------------------

    def on_status(self, status, arrived: float):
        """A status: the clocks' offset, and the measured pressure for the fallback."""
        with self._lock:
            if status.haptics:
                self.exact = True
            if status.clock_us:
                self._offsets.append(status.clock_us / 1e6 - arrived)
            for hand in HANDS:
                g = status.gloves.get(hand)
                kpa = list(g.pressure_kpa[:FINGERS]) if g and g.connected and \
                    len(g.pressure_kpa) >= FINGERS else [0.0] * FINGERS
                self._pressure[hand].append((arrived, kpa))
                if max(kpa) > QUIET_KPA * 3:
                    self._used.add(hand)

    def on_haptics(self, update):
        """A haptics line from the headset."""
        t = update.t_us / 1e6
        with self._lock:
            self.exact = True
            for c in update.channels:
                segs = self._segments[(update.hand, c.finger)]
                if segs and segs[-1].t1 is None:
                    segs[-1].t1 = max(segs[-1].t0, t)
                if c.mode != "off":
                    segs.append(Segment(t, t + TAP_S if c.tap else None, c.mode,
                                        max(0.1, c.intensity), c.hz))
                    self._used.add(update.hand)
                while segs and segs[0].t1 is not None and segs[0].t1 < t - KEEP_S:
                    segs.pop(0)

    def reset_clock(self):
        """Forget the clock's offset: the headset may have restarted, and its clock with it."""
        with self._lock:
            self._offsets.clear()

    # -- reading ------------------------------------------------------------------------------

    def hands_used(self) -> list[str]:
        with self._lock:
            return [h for h in HANDS if h in self._used]

    def offset(self) -> float | None:
        """Headset clock minus ours. The largest sample is the one that waited least on the way."""
        with self._lock:
            return max(self._offsets) if self._offsets else None

    def frame_time(self, pts_us: int, arrived: float) -> float:
        """When a frame was made, on the headset's clock: its presentation time, if that is on the
        headset's clock as it should be, or else when it arrived, less the video's usual lag."""
        pts = pts_us / 1e6
        off = self.offset()
        if off is None or abs(pts - (arrived + off)) < SAME_CLOCK_S:
            return pts
        return arrived + off - VIDEO_LAG_S

    def state(self, hand: str, pts_us: int, arrived: float) -> HandState:
        """The glove as the frame with this presentation time, which arrived then, shows it."""
        if self.exact:
            return self._exact(hand, self.frame_time(pts_us, arrived))
        return self._measured(hand, arrived - VIDEO_LAG_S)

    def segments_between(self, t0: float, t1: float) -> list[tuple[str, int, Segment]]:
        """Every command that overlaps [t0, t1] on the headset's clock, for a recording's log."""
        out = []
        with self._lock:
            for (hand, finger), segs in self._segments.items():
                for s in segs:
                    end = t1 if s.t1 is None else s.t1
                    if s.t0 <= t1 and end >= t0:
                        out.append((hand, finger, Segment(s.t0, s.t1, s.mode, s.intensity, s.hz)))
        return sorted(out, key=lambda x: x[2].t0)

    def _exact(self, hand: str, t: float) -> HandState:
        st = HandState()
        active = fading = None
        with self._lock:
            for f in range(FINGERS):
                for s in reversed(self._segments[(hand, f)]):
                    end = s.t1
                    if end is not None and end < t - RELEASE_S * 8:
                        break
                    level = segment_level(s, t)
                    if level > st.levels[f]:
                        st.levels[f] = level
                        on = s.mode != "pressure" and t >= s.t0 and (end is None or t <= end)
                        st.vibrating[f] = s.hz if on else 0.0
                        st.since[f] = t - s.t0
                    if s.t0 <= t and (end is None or t <= end):
                        if active is None or s.t0 > active.t0:
                            active = s
                    elif end is not None and 0 <= t - end < RELEASE_WORD_S:
                        if fading is None or end > fading.t1:
                            fading = s
        cur = active or fading
        if cur is not None:
            if cur.mode == "pressure":
                st.words = 0
                st.word = 2 if cur is not active else 0 if t - cur.t0 < PRESS_S else 1
            else:
                st.words = 1
                short = cur.t1 is not None and cur.t1 - cur.t0 < 0.2
                st.word = 2 if short else 0 if cur.hz <= 3 else 1
                st.hz = cur.hz
        return st

    def _measured(self, hand: str, t: float) -> HandState:
        st = HandState()
        with self._lock:
            samples = list(self._pressure[hand])
        if not samples:
            return st
        now = _pressure_at(samples, t)
        before = _pressure_at(samples, t - 0.25)
        st.levels = [_level(k) for k in now]
        total, was = sum(st.levels), sum(_level(k) for k in before)
        if total > 0.15 or was > 0.15:
            st.words = 0
            st.word = 0 if total > was + 0.15 else 2 if total < was - 0.15 else 1 if total > 0.15 else 2
        return st


def _level(kpa: float) -> float:
    return 0.0 if kpa < QUIET_KPA else min(1.0, kpa / FULL_KPA)


def _pressure_at(samples: list, t: float) -> list[float]:
    """The measured pressure at `t`, between the two readings around it."""
    if t <= samples[0][0]:
        return samples[0][1]
    for (ta, a), (tb, b) in zip(samples, samples[1:]):
        if ta <= t <= tb:
            k = (t - ta) / (tb - ta) if tb > ta else 1.0
            return [x + (y - x) * k for x, y in zip(a, b)]
    return samples[-1][1]
