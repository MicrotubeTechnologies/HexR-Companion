"""The glove over a headset's view: microtube.tech/hexr's six touch points, lit as the glove fires.

Pressure glows and holds, a vibration sends rings out from the touch point, and a caption reads
PRESS. HOLD. RELEASE. or PULSE. BUZZ. CLICK., as on the website and in HexR Overlay Studio.

It draws onto a PIL image in place, at whatever size that image is: the screen and a recording
each draw their own, so both are sharp. Everything scales with the glove's height. What never
changes from frame to frame (the panel, the glove, its shadow) is drawn once and kept, and the
small round shapes are drawn three times over and scaled down so their edges are smooth.

Like the website, its words are English: they are part of the picture, not the app's text.
A GloveOverlay is not shared between threads; the screen and a recording each have their own.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import theme as T
from .haptics import HandState

ORANGE = (242, 102, 26)
WHITE = (255, 255, 255)

# Touch points on the glove art, a right hand with its palm towards the viewer, as fractions of
# the picture (the same points as the website); the left hand is drawn mirrored.
# (x, y, its label goes to the left)
DOTS = ((.87, .3233, False), (.50, .0758, False), (.457, .4749, True), (.423, .5951, True),
        (.337, .6895, True), (.59, .7081, False))
NAMES = ("THUMB", "INDEX", "MIDDLE", "RING", "PINKY", "PALM")
WORDS = (("PRESS.", "HOLD.", "RELEASE."), ("PULSE.", "BUZZ.", "CLICK."))
GLOVE_ASPECT = 520 / 885
SS = 3                       # supersampling for round shapes


@dataclass
class OverlayLook:
    corner: str = "br"       # tl | tr | bl | br
    size: float = 0.32       # the glove's height, as a share of the picture's
    labels: str = "active"   # active | always | off
    caption: bool = True
    backdrop: bool = True
    title: bool = True       # "LEFT HAND" / "RIGHT HAND" above the glove
    margin: float = .46      # room beside the glove for finger tags, as a share of its width


def panel_size(gh: int, look: OverlayLook) -> tuple[int, int]:
    """One hand's panel, in pixels, for a glove `gh` pixels tall."""
    gw = gh * GLOVE_ASPECT
    cap = gh * (.24 if look.caption else .06)
    return int(gw + gw * look.margin * 2), int(gh * .12 + gh + cap)


def touch_points(hand: str, gh: int, look: OverlayLook) -> list[tuple[float, float]]:
    """Where the six touch points sit in one hand's panel: the drawing and a click both use it."""
    gw = gh * GLOVE_ASPECT
    gx, gy = gw * look.margin, gh * .1
    return [(gx + (1 - dx if hand == "left" else dx) * gw, gy + dy * gh) for dx, dy, _ in DOTS]


def nearest_point(points: list[tuple[float, float]], x: float, y: float,
                  radius: float) -> int | None:
    """The touch point nearest (x, y), if one is within `radius`."""
    best, best_d = None, radius * radius
    for i, (px, py) in enumerate(points):
        d = (px - x) ** 2 + (py - y) ** 2
        if d <= best_d:
            best, best_d = i, d
    return best


def _asset(name: str) -> str:
    return T.resource_path("assets", "overlay", name)


class GloveOverlay:
    def __init__(self):
        self._art: Image.Image | None = None
        self._fonts: dict = {}
        self._cache: dict = {}

    # -- public ---------------------------------------------------------------------------

    def draw(self, img: Image.Image, hands: list[str], states: dict[str, HandState],
             look: OverlayLook):
        """Draws the glove for each of `hands` ("left", "right") onto `img`, in its corner."""
        if not hands:
            return
        gh = max(60, int(round(look.size * img.height)))
        pw, ph = panel_size(gh, look)
        gap = int(gh * .08)
        margin = int(min(img.width, img.height) * .03)
        total = pw * len(hands) + gap * (len(hands) - 1)
        x = margin if look.corner[1] == "l" else img.width - margin - total
        y = margin if look.corner[0] == "t" else img.height - margin - ph
        for i, hand in enumerate(hands):
            panel = self.panel(hand, gh, look, states.get(hand) or HandState())
            img.paste(panel.convert("RGB"), (x + i * (pw + gap), y), panel)

    # -- one hand -------------------------------------------------------------------------

    def panel(self, hand: str, gh: int, look: OverlayLook, st: HandState) -> Image.Image:
        """One hand's glove as an RGBA image `panel_size(gh, look)` big, lit as `st` says."""
        panel = self._static(hand, gh, look).copy()
        gy = gh * .1
        top = Image.new("RGBA", panel.size, WHITE + (0,))
        tags = []
        for ch, (cx, cy) in enumerate(touch_points(hand, gh, look)):
            left = DOTS[ch][2] != (hand == "left")
            rgb = tuple(st.tints[ch]) if st.tints and st.tints[ch] else ORANGE
            level = st.levels[ch]
            _put(panel, self._glow(gh, level, rgb), cx, cy)
            if st.vibrating[ch] > 0:
                rate = min(st.vibrating[ch], 2.5)
                for k in range(2):
                    phase = (st.since[ch] * rate + k / 2) % 1
                    _put(top, self._ring(gh, gh * .03 * (1 + 2.4 * phase), (1 - phase) * .9), cx, cy)
            _put(top, self._core(gh, .35 + .65 * level, rgb), cx, cy)
            show = (.55 + .45 * min(1, level * 2) if look.labels == "always" else
                    min(1.0, max(0.0, (level - .08) * 4)) if look.labels == "active" else 0)
            if show > 0:
                tags.append((cx, cy, NAMES[ch], left, show, level > .15))
        for cx, cy, name, left, show, hot in tags:
            tag = self._tag(gh, name, hot, show)
            off = gh * .045
            tx = cx - off - tag.width / 2 if left else cx + off + tag.width / 2
            _put(top, tag, tx, cy - tag.height * .3)
        if look.caption:
            cap = self._caption(gh, panel.width, st)
            _put(top, cap, panel.width / 2, gy + gh + gh * .02 + cap.height / 2)
        panel.alpha_composite(top)
        return panel

    def _static(self, hand: str, gh: int, look: OverlayLook) -> Image.Image:
        key = ("static", hand, gh, look.caption, look.backdrop, look.title, look.margin)
        if key in self._cache:
            return self._cache[key]
        w, h = panel_size(gh, look)
        big = Image.new("RGBA", (w * SS, h * SS), (8, 9, 12, 0))
        d = ImageDraw.Draw(big)
        if look.backdrop:
            d.rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), radius=int(gh * .07 * SS),
                                fill=(8, 9, 12, 148), outline=(255, 255, 255, 22),
                                width=max(SS, int(gh * .003 * SS)))
        if look.title:
            d.text((gh * .06 * SS, gh * .065 * SS), "LEFT HAND" if hand == "left" else "RIGHT HAND",
                   font=self._font("Inter-Bold.ttf", gh * .036 * SS), fill=(150, 151, 154, 255),
                   anchor="lm")
        panel = big.resize((w, h), Image.LANCZOS)

        gw = int(round(gh * GLOVE_ASPECT))
        art = self._glove_art().resize((gw, gh), Image.LANCZOS)
        if hand == "left":
            art = art.transpose(Image.FLIP_LEFT_RIGHT)
        gx, gy = int(gw * look.margin), int(gh * .1)
        shadow = Image.new("RGBA", art.size, (0, 0, 0, 0))
        shadow.putalpha(art.getchannel("A").point(lambda a: int(a * .55)))
        pad = int(gh * .08)
        shadow = _padded(shadow, pad).filter(ImageFilter.GaussianBlur(gh * .03))
        _paste_at(panel, shadow, gx - pad, gy - pad + int(gh * .025))
        _paste_at(panel, art, gx, gy)
        self._cache[key] = panel
        return panel

    # -- pieces, kept by size ---------------------------------------------------------------

    def _glove_art(self) -> Image.Image:
        if self._art is None:
            self._art = Image.open(_asset("glove.webp")).convert("RGBA")
        return self._art

    def _font(self, name: str, size: float) -> ImageFont.FreeTypeFont:
        key = (name, int(round(size)))
        if key not in self._fonts:
            try:
                self._fonts[key] = ImageFont.truetype(_asset(name), max(6, key[1]))
            except OSError:
                self._fonts[key] = ImageFont.load_default(max(6, key[1]))
        return self._fonts[key]

    def clear(self):
        """Forget every piece kept: for a view whose size keeps changing."""
        self._cache.clear()

    def _glow(self, gh: int, level: float, rgb=ORANGE) -> Image.Image:
        step = round(level * 32)
        key = ("glow", gh, step, rgb)
        if key not in self._cache:
            lv = step / 32
            r = gh * .085 * (.55 + .9 * lv)
            peak = (.15 + .85 * lv) * 255
            size = int(math.ceil(r)) * 2 + 4
            alpha = Image.new("L", (size, size), 0)
            d = ImageDraw.Draw(alpha)
            c = size / 2
            for i in range(int(math.ceil(r)), 0, -1):
                d.ellipse((c - i, c - i, c + i, c + i), fill=int(peak * (1 - i / r)) if i < r else 0)
            sprite = Image.new("RGBA", (size, size), tuple(rgb) + (0,))
            sprite.putalpha(alpha.filter(ImageFilter.GaussianBlur(1)))
            self._cache[key] = sprite
        return self._cache[key]

    def _core(self, gh: int, alpha: float, rgb=ORANGE) -> Image.Image:
        step = round(alpha * 16)
        key = ("core", gh, step, rgb)
        if key not in self._cache:
            a = step / 16
            r, ring = gh * .016, gh * .008
            outer = r + gh * .004 + ring / 2
            size = int(math.ceil(outer * 2)) + 4

            def paint(d, s):
                c = size * s / 2
                d.ellipse((c - outer * s, c - outer * s, c + outer * s, c + outer * s),
                          fill=tuple(rgb) + (int(230 * a),))
                d.ellipse((c - r * s, c - r * s, c + r * s, c + r * s), fill=WHITE + (int(255 * a),))
            self._cache[key] = _supersampled((size, size), paint, rgb)
        return self._cache[key]

    def _ring(self, gh: int, radius: float, alpha: float) -> Image.Image:
        rq, aq = round(radius * 2) / 2, round(alpha * 12)
        key = ("ring", gh, rq, aq)
        if key not in self._cache:
            width = max(1.0, gh * .007)
            size = int(math.ceil((rq + width) * 2)) + 4

            def paint(d, s):
                c = size * s / 2
                d.ellipse((c - rq * s, c - rq * s, c + rq * s, c + rq * s),
                          outline=ORANGE + (int(255 * aq / 12),), width=max(1, int(width * s)))
            self._cache[key] = _supersampled((size, size), paint, ORANGE)
        return self._cache[key]

    def _tag(self, gh: int, name: str, hot: bool, alpha: float) -> Image.Image:
        aq = round(alpha * 8)
        key = ("tag", gh, name, hot, aq)
        if key not in self._cache:
            fs = max(9.0, gh * .04)
            font = self._font("Inter-Bold.ttf", fs * SS)
            tw = font.getlength(name) / SS
            ph, bh = fs * .55, fs * 1.7
            w, h = int(math.ceil(tw + ph * 2)), int(math.ceil(bh))
            fill = (ORANGE if hot else (8, 9, 12)) + (int((235 if hot else 190) * aq / 8),)

            def paint(d, s):
                d.rounded_rectangle((0, 0, w * s - 1, h * s - 1), radius=h * s / 2, fill=fill)
                d.text((w * s / 2, h * s / 2), name, font=font, fill=WHITE + (int(255 * aq / 8),),
                       anchor="mm")
            self._cache[key] = _supersampled((w, h), paint, fill[:3])
        return self._cache[key]

    def _caption(self, gh: int, width: int, st: HandState) -> Image.Image:
        hz = round(st.hz, 1) if st.words == 1 and st.word >= 0 else 0
        key = ("caption", gh, width, st.words, st.word, hz)
        if key not in self._cache:
            words = WORDS[st.words]
            fs = gh * .085
            font = self._font("Archivo-Black.ttf", fs)
            space = fs * .3
            total = sum(font.getlength(w) for w in words) + space * 2
            if total > width - gh * .12:
                fs *= (width - gh * .12) / total
                font = self._font("Archivo-Black.ttf", fs)
                space = fs * .3
                total = sum(font.getlength(w) for w in words) + space * 2
            h = int(gh * .22)
            img = Image.new("RGBA", (width, h), WHITE + (0,))
            d = ImageDraw.Draw(img)
            x = (width - total) / 2
            base = gh * .19
            for i, w in enumerate(words):
                lit = i == st.word
                d.text((x, base), w, font=font, anchor="ls",
                       fill=ORANGE + (255,) if lit else (255, 255, 255, 60))
                x += font.getlength(w) + space
            if hz:
                sub = f"{hz:g} Hz"
                small = self._font("Inter-SemiBold.ttf", gh * .045)
                d.text((width / 2, gh * .075), sub, font=small, anchor="ms", fill=(235, 235, 237, 255))
            self._cache[key] = img
        return self._cache[key]


# -- helpers ------------------------------------------------------------------------------------

def _supersampled(size: tuple[int, int], paint, rgb) -> Image.Image:
    """Draws at SS times the size and scales down: smooth edges from a drawing API without them.
    The see-through background carries the shape's own colour so the edges do not darken."""
    big = Image.new("RGBA", (size[0] * SS, size[1] * SS), tuple(rgb) + (0,))
    paint(ImageDraw.Draw(big), SS)
    return big.resize(size, Image.LANCZOS)


def _padded(img: Image.Image, pad: int) -> Image.Image:
    out = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    out.paste(img, (pad, pad))
    return out


def _paste_at(base: Image.Image, sprite: Image.Image, x: int, y: int):
    """alpha_composite at a top-left corner, clipped to `base`."""
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(base.width, x + sprite.width), min(base.height, y + sprite.height)
    if x1 <= x0 or y1 <= y0:
        return
    base.alpha_composite(sprite.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


def _put(base: Image.Image, sprite: Image.Image, cx: float, cy: float):
    """alpha_composite a sprite centred on (cx, cy), clipped to `base`."""
    _paste_at(base, sprite, int(round(cx - sprite.width / 2)), int(round(cy - sprite.height / 2)))
