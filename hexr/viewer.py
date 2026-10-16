"""What a headset's view turns into on the screen and in a recording: framed, with the glove on top.

The headset sends a square view (Quest's compositor delivers one). Landscape cuts a 16:9 band
out of it, by default a little below the middle, where hands usually are; the band can be moved
up and down. A view that is already wider than 16:9 is left as it is.

Runs on the video and recording threads; no Tk. The screen changes how it looks by handing the
compositor a new ViewLook rather than changing the one it holds, so a frame being drawn never
sees half of a change.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from PIL import Image

from .haptics import HapticsTimeline
from .overlay import GloveOverlay, OverlayLook


@dataclass(frozen=True)
class ViewLook:
    landscape: bool = True
    offset: float = 0.35          # the 16:9 band's place in the square: -1 top, 0 middle, 1 bottom
    overlay: bool = True
    hands: str = "auto"           # auto (the hands that have done something) | left | right | both
    glove: OverlayLook = field(default_factory=OverlayLook)

    def but(self, **changes) -> "ViewLook":
        return replace(self, **changes)


def crop_box(width: int, height: int, look: ViewLook) -> tuple[int, int, int, int]:
    """The part of a width x height view that is shown: all of it, or a 16:9 band."""
    if not look.landscape or width * 9 >= height * 16:
        return 0, 0, width, height
    band = int(width * 9 / 16) // 2 * 2
    top = round((height - band) / 2 * (1 + max(-1.0, min(1.0, look.offset))))
    top = min(max(0, top), height - band)
    return 0, top, width, top + band


class Compositor:
    """Frames and overlays one stream of frames. One per thread: it keeps the overlay's pieces."""

    def __init__(self, timeline: HapticsTimeline, look: ViewLook):
        self.timeline = timeline
        self.look = look
        self._overlay = GloveOverlay()

    def hands(self, look: ViewLook) -> list[str]:
        if look.hands in ("left", "right"):
            return [look.hands]
        if look.hands == "both":
            return ["left", "right"]
        return self.timeline.hands_used() or ["right"]

    def compose(self, frame, pts_us: int, arrived: float,
                fit: tuple[int, int] | None = None) -> Image.Image:
        """The frame as it is shown: framed, scaled to fit inside `fit` (or at its own size), with
        the glove drawn at that size so it stays sharp."""
        look = self.look
        x0, y0, x1, y1 = crop_box(frame.width, frame.height, look)
        cw, ch = x1 - x0, y1 - y0
        scale = min(fit[0] / cw, fit[1] / ch) if fit else 1.0
        if abs(scale - 1.0) > 1e-3:
            # FFmpeg's scaler on the whole frame, then the cut: cheaper than scaling in PIL.
            sw, sh = max(2, round(frame.width * scale)), max(2, round(frame.height * scale))
            img = frame.reformat(width=sw, height=sh, format="rgb24").to_image()
            box = (round(x0 * scale), round(y0 * scale),
                   round(x0 * scale) + max(2, round(cw * scale)),
                   round(y0 * scale) + max(2, round(ch * scale)))
            img = img.crop((box[0], box[1], min(sw, box[2]), min(sh, box[3])))
        else:
            img = frame.to_image()
            if (cw, ch) != (frame.width, frame.height):
                img = img.crop((x0, y0, x1, y1))
        if look.overlay:
            hands = self.hands(look)
            states = {h: self.timeline.state(h, pts_us, arrived) for h in hands}
            self._overlay.draw(img, hands, states, look.glove)
        return img
