"""What a headset's view turns into: the view beside its gloves.

The headset sends a square view, and it is shown whole. Beside it goes a panel for each glove:
landscape (16:9) puts them to the right of the view, the left hand above the right; portrait
(9:16) puts them under it, side by side. Those are YouTube's two shapes. Square is the view
alone. Each panel lights its glove where the wearer is being touched, and says whether the
headset has that glove, and its battery. Nothing is drawn over the view itself.

The Headsets screen and full screen show landscape; an export (hexr/exporter.py) draws any of
the three from a recording. Like the glove, the panels' words are English: they are part of the
picture, not the app's text.

No Tk. A Compositor is not shared between threads: it keeps the pieces it has drawn. The screen
changes what the panels say by handing it a new `badges` tuple rather than changing the one it
holds, so a frame being drawn never sees half of a change.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from . import theme as T
from .haptics import HandState, HapticsTimeline
from .overlay import GLOVE_ASPECT, SS, GloveOverlay, OverlayLook, panel_size

LANDSCAPE, PORTRAIT, SQUARE = "landscape", "portrait", "square"
LAYOUTS = (LANDSCAPE, PORTRAIT, SQUARE)
SIZE = {LANDSCAPE: (1920, 1080), PORTRAIT: (1080, 1920), SQUARE: (1080, 1080)}
HANDS = ("left", "right")

# The glove in a panel: the panel is its backdrop and carries its name, and the caption sits
# under it. A finger firing is named beside it, while one or two are: more, and the names
# would crowd the glove, which says enough by lighting up. Room either side for the names.
GLOVE = OverlayLook(backdrop=False, title=False, labels="active", caption=True, margin=.6)
QUIET = OverlayLook(backdrop=False, title=False, labels="off", caption=True, margin=.6)
NAMED_AT_MOST = 2
NAMED_FROM_GH = 200          # and only on a glove big enough for the names to be read
GLOVE_STEP = 4               # the glove's height is kept to steps of this, so its pieces are reused
DIMMED = 0.3                 # a glove the headset does not have shows faintly


def _rgb(colour: str) -> tuple[int, int, int]:
    h = colour.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


BACKGROUND = _rgb(T.CANVAS)
SCREEN = _rgb(T.RAISED)      # the view's square, while there is no view in it
PANEL = _rgb(T.RAISED)
PANEL_EDGE = _rgb(T.BORDER_SOFT)
NAME = (150, 151, 154)

STATUS = {
    "connected": ("CONNECTED", _rgb(T.SUCCESS)),
    "connecting": ("CONNECTING", _rgb(T.ACCENT)),
    "disconnected": ("NOT CONNECTED", _rgb(T.TEXT_FAINT)),
    "missing": ("NO GLOVE", _rgb(T.TEXT_FAINT)),
}


@dataclass(frozen=True)
class GloveBadge:
    """What a panel says about its glove."""
    state: str = "disconnected"      # connected | connecting | disconnected | missing
    battery: int = -1                # percent, or -1 when the glove has not said


def badge_of(badges: tuple, hand: str) -> GloveBadge:
    """`badges` is ((hand, GloveBadge), ...): what the headset says of each glove."""
    return dict(badges).get(hand, GloveBadge())


# -- where things go ---------------------------------------------------------------------------

def frame_size(fit: tuple[int, int] | None, layout: str) -> tuple[int, int]:
    """The picture's size: the largest of its shape that fits inside `fit`, in even pixels as
    a video needs; an export's own size without one."""
    if fit is None:
        return SIZE[layout]
    w, h = float(fit[0]), float(fit[1])
    if layout == LANDSCAPE:
        w = min(w, h * 16 / 9)
        h = w * 9 / 16
    elif layout == PORTRAIT:
        h = min(h, w * 16 / 9)
        w = h * 9 / 16
    else:
        w = h = min(w, h)
    return max(2, int(w) // 2 * 2), max(2, int(h) // 2 * 2)


@dataclass(frozen=True)
class Boxes:
    view: tuple[int, int, int, int]
    left: tuple[int, int, int, int] | None
    right: tuple[int, int, int, int] | None

    def cell(self, hand: str):
        return self.left if hand == "left" else self.right


def boxes(size: tuple[int, int], layout: str) -> Boxes:
    """The view's square and each glove's panel, as (x0, y0, x1, y1), in a picture this big."""
    w, h = size
    if layout == LANDSCAPE:
        s, g = h, max(2, round(h * .014))
        half = (h - 3 * g) // 2
        return Boxes((0, 0, s, s), (s + g, g, w - g, g + half), (s + g, 2 * g + half, w - g, h - g))
    if layout == PORTRAIT:
        s, g = w, max(2, round(w * .014))
        half = (w - 3 * g) // 2
        return Boxes((0, 0, s, s), (g, s + g, g + half, h - g), (2 * g + half, s + g, w - g, h - g))
    return Boxes((0, 0, w, h), None, None)


def hit(size: tuple[int, int], layout: str, x: float, y: float) -> str | None:
    """What a point in the picture is on: "view", "left", "right", or None between them."""
    b = boxes(size, layout)
    for name, box in (("view", b.view), ("left", b.left), ("right", b.right)):
        if box and box[0] <= x < box[2] and box[1] <= y < box[3]:
            return name
    return None


def glove_height(cell: tuple[int, int, int, int]) -> int:
    """The glove's height in a panel: as big as fits under the panel's heading."""
    cw, ch = cell[2] - cell[0], cell[3] - cell[1]
    pad, _line, head, _stacked = _heading(cell)
    gh = min((ch - head - pad * 2) / (panel_size(100, GLOVE)[1] / 100),
             (cw - pad * 2) / (GLOVE_ASPECT * (1 + GLOVE.margin * 2)))
    return max(GLOVE_STEP * 4, int(gh) // GLOVE_STEP * GLOVE_STEP)


def _heading(cell) -> tuple[int, int, int, bool]:
    """A panel's padding, the height of a line of its heading, the heading's height, and
    whether the glove's state goes under its name (a tall, narrow panel) or beside it."""
    cw, ch = cell[2] - cell[0], cell[3] - cell[1]
    unit = min(cw, ch)
    pad, line = max(4, round(unit * .07)), max(10, round(unit * .1))
    stacked = cw < ch
    return pad, line, line * 2 if stacked else line, stacked


# -- drawing -----------------------------------------------------------------------------------

class Compositor:
    """Draws the picture, a frame at a time. One per thread: it keeps the pieces it draws.

    Live, `compose` and `idle` read the gloves from `timeline` and what the panels say from
    `badges`, always in landscape; an export calls `draw` with what it read from a recording."""

    def __init__(self, timeline: HapticsTimeline | None = None, badges: tuple = ()):
        self.timeline = timeline
        self.badges = badges
        self._overlay = GloveOverlay()
        self._gh = 0
        self._base: tuple | None = None          # ((size, layout), image)
        self._sprites: dict = {}
        self._fonts: dict = {}
        self._idle_key = None

    def compose(self, frame, pts_us: int, arrived: float,
                fit: tuple[int, int] | None = None) -> Image.Image:
        """A live frame as it is shown: the gloves as they were when the headset made it."""
        states = {h: self.timeline.state(h, pts_us, arrived) for h in HANDS}
        return self.draw(frame, states, self.badges, LANDSCAPE, fit)

    def idle(self, fit: tuple[int, int], now: float) -> Image.Image | None:
        """The picture with nothing in the view's square and the gloves as they are now; None
        when that is what was drawn last time, so the screen has nothing to do."""
        states = {h: self.timeline.state(h, 0, now) for h in HANDS}
        key = (frame_size(fit, LANDSCAPE), self.badges,
               tuple(_state_key(states[h]) for h in HANDS))
        if key == self._idle_key:
            return None
        self._idle_key = key
        return self.draw(None, states, self.badges, LANDSCAPE, fit)

    def draw(self, frame, states: dict[str, HandState], badges: tuple, layout: str,
             fit: tuple[int, int] | None = None) -> Image.Image:
        """The view (an av.VideoFrame, or None for an empty square) and, unless the layout is
        square, the gloves beside it: as big as fits inside `fit`, or the export's size."""
        size = frame_size(fit, layout)
        img = self._background(size, layout)
        b = boxes(size, layout)
        if frame is not None:
            self._paste_view(img, frame, b.view)
        if b.left:
            gh = glove_height(b.left)
            if gh != self._gh:
                self._gh = gh
                self._overlay.clear()          # a new size: the old one's pieces are no use now
            for hand in HANDS:
                self._panel(img, b.cell(hand), hand, states.get(hand) or HandState(),
                            badge_of(badges, hand), gh)
        return img

    # -- the parts -----------------------------------------------------------------------------

    def _background(self, size: tuple[int, int], layout: str) -> Image.Image:
        """A fresh copy of what never changes: the background, the square, the empty panels."""
        if self._base is None or self._base[0] != (size, layout):
            b = boxes(size, layout)
            big = Image.new("RGB", (size[0] * SS, size[1] * SS), BACKGROUND)
            d = ImageDraw.Draw(big)
            d.rectangle([v * SS for v in b.view], fill=SCREEN)
            for hand in HANDS if b.left else ():
                cell = b.cell(hand)
                pad, line, _head, _stacked = _heading(cell)
                unit = min(cell[2] - cell[0], cell[3] - cell[1])
                d.rounded_rectangle([v * SS for v in cell], radius=round(unit * .06 * SS),
                                    fill=PANEL, outline=PANEL_EDGE,
                                    width=max(SS, round(unit * .006 * SS)))
                d.text(((cell[0] + pad) * SS, (cell[1] + pad + line / 2) * SS),
                       "LEFT HAND" if hand == "left" else "RIGHT HAND",
                       font=self._font("Inter-Bold.ttf", unit * .055 * SS), fill=NAME,
                       anchor="lm")
            self._base = ((size, layout), big.resize(size, Image.LANCZOS))
        return self._base[1].copy()

    def _paste_view(self, img: Image.Image, frame, box):
        """The headset's view, whole, as big as fits in the square."""
        s = min(box[2] - box[0], box[3] - box[1])
        scale = min(s / frame.width, s / frame.height)
        w, h = max(2, round(frame.width * scale)), max(2, round(frame.height * scale))
        img.paste(to_image(frame, w, h),
                  (box[0] + (box[2] - box[0] - w) // 2, box[1] + (box[3] - box[1] - h) // 2))

    def _panel(self, img, cell, hand: str, st: HandState, badge: GloveBadge, gh: int):
        x0, y0, x1, y1 = cell
        pad, line, head, stacked = _heading(cell)
        status = self._status(badge, min(x1 - x0, y1 - y0))
        if stacked:             # under the name
            at = (x0 + pad, round(y0 + pad + line * 1.5 - status.height / 2))
        else:                   # at the other end of the name's line
            at = (x1 - pad - status.width, round(y0 + pad + line / 2 - status.height / 2))
        img.paste(status, at, status)

        firing = sum(1 for v in st.levels if v > .08)
        named = firing <= NAMED_AT_MOST and gh >= NAMED_FROM_GH
        glove = self._overlay.panel(hand, gh, GLOVE if named else QUIET, st)
        if badge.state != "connected":
            glove.putalpha(glove.getchannel("A").point(lambda a: int(a * DIMMED)))
        top = y0 + pad + head
        room = y1 - pad - top
        img.paste(glove.convert("RGB"), (x0 + (x1 - x0 - glove.width) // 2,
                                         top + max(0, (room - glove.height) // 2)), glove)

    def _status(self, badge: GloveBadge, unit: int) -> Image.Image:
        """A dot and a word for the glove's state, and its battery: an RGBA sprite."""
        key = (badge, unit)
        if key not in self._sprites:
            word, colour = STATUS.get(badge.state, STATUS["disconnected"])
            fs = unit * .05
            font = self._font("Inter-Bold.ttf", fs * SS)
            parts = [(word, colour)]
            if badge.battery >= 0 and badge.state == "connected":
                parts.append((f"·  {badge.battery}%", _rgb(T.WARN) if badge.battery < 20
                              else (200, 202, 206)))
            dot = gap = fs * .55
            widths = [font.getlength(t) / SS for t, _c in parts]
            w = int(dot + gap + sum(widths) + gap * (len(parts) - 1)) + 2
            h = int(fs * 1.5) + 2
            big = Image.new("RGBA", (w * SS, h * SS), colour + (0,))
            d = ImageDraw.Draw(big)
            cy = h * SS / 2
            d.ellipse((0, cy - dot * SS / 2, dot * SS, cy + dot * SS / 2), fill=colour + (255,))
            x = (dot + gap) * SS
            for (text, c), tw in zip(parts, widths):
                d.text((x, cy), text, font=font, fill=c + (255,), anchor="lm")
                x += (tw + gap) * SS
            self._sprites[key] = big.resize((w, h), Image.LANCZOS)
        return self._sprites[key]

    def _font(self, name: str, size: float) -> ImageFont.FreeTypeFont:
        key = (name, max(6, int(round(size))))
        if key not in self._fonts:
            try:
                self._fonts[key] = ImageFont.truetype(T.resource_path("assets", "overlay", name),
                                                      key[1])
            except OSError:
                self._fonts[key] = ImageFont.load_default(key[1])
        return self._fonts[key]


def to_image(frame, width: int, height: int) -> Image.Image:
    """An av.VideoFrame as a PIL image this big: FFmpeg's scaler, straight to RGB. Through numpy
    (which PyAV brings) it is three times quicker than PyAV's own to_image()."""
    try:
        import numpy  # noqa: F401
    except ImportError:
        return frame.reformat(width=width, height=height, format="rgb24").to_image()
    return Image.fromarray(frame.to_ndarray(width=width, height=height, format="rgb24"))


def to_frame(img: Image.Image):
    """A PIL image as an av.VideoFrame, to encode."""
    import av
    try:
        import numpy
    except ImportError:
        return av.VideoFrame.from_image(img)
    return av.VideoFrame.from_ndarray(numpy.asarray(img), format="rgb24")


def _state_key(st: HandState) -> tuple:
    """What, of a glove's state, changes the picture: a vibration moves all the time."""
    moving = any(v > 0 for v in st.vibrating)
    return (tuple(round(v * 32) for v in st.levels), st.words, st.word, round(st.hz, 1),
            tuple(round(s, 2) for s in st.since) if moving else None)
