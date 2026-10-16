"""The HEXR glove in the app's own screens: tap its fingertips, watch them light up.

The same glove the headset overlay and the website draw (hexr/overlay.py), so the
app tells one visual story everywhere: an orange glow where the glove presses, green
for good, amber for poor, red for failed, dimmed for a glove that is not there.

Each hand is one image, drawn again only when what it shows has changed; the
selection rings and the hover label are Tk items on top, so picking a finger costs
nothing. The glove grows and shrinks with the room it is given.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Sequence

from PIL import Image, ImageTk

from . import protocol as P
from . import theme as T
from .haptics import FINGERS, PRESS_S, RELEASE_WORD_S, HandState, level_from_kpa
from .i18n import tr
from .overlay import GloveOverlay, OverlayLook, nearest_point, panel_size, touch_points

STEP = 20            # the glove's height snaps to multiples of this, so resizing reuses work
HIT = 0.09           # how near a click must be to a touch point, as a share of the glove
GAP = 0.18           # between two gloves, as a share of the glove's height
NAME_H = 26          # room under each glove for its hand's name


def _rgb(colour: str) -> tuple[int, int, int]:
    colour = colour.lstrip("#")
    return tuple(int(colour[i:i + 2], 16) for i in (0, 2, 4))


class GloveView(tk.Canvas):
    def __init__(self, parent, *, bg=None, min_gh=160, max_gh=360, caption=False,
                 names=False, on_toggle: Callable[[str, int], None] | None = None):
        bg = bg or parent.cget("bg")
        # Asks for room for its smallest glove, so a page with more on it scrolls rather
        # than squeezing the glove to a thumbnail; it grows into whatever room there is.
        want = int(min_gh * 1.2) + (NAME_H if names else 0)
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0, width=1, height=want)
        self._bg = _rgb(bg)
        self.min_gh, self.max_gh = min_gh, max_gh
        self.names = names
        self.on_toggle = on_toggle
        self._overlay = GloveOverlay()
        self._look = OverlayLook(labels="off", backdrop=False, title=False, margin=.12,
                                 caption=caption)
        self._hands: list[str] = ["right"]
        self._states: dict[str, HandState] = {}
        self._selected: set[int] | None = None
        self._dim: dict[str, float] = {}
        self._values: dict[str, list[str]] | None = None
        self._gh = 0
        self._origin: dict[str, tuple[int, int]] = {}
        self._photo: dict[str, ImageTk.PhotoImage] = {}
        self._item: dict[str, int] = {}
        self._drawn: dict[str, tuple] = {}
        self._hover: tuple[str, int] | None = None
        self._resize_after = None
        self.bind("<Configure>", self._on_configure)
        self.bind("<Button-1>", self._click)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))

    # -- what it shows ------------------------------------------------------------------------

    def set_hands(self, hands: Sequence[str]):
        """Which gloves to draw, "left" and/or "right"; the left one goes on the left."""
        hands = [h for h in ("left", "right") if h in hands] or ["right"]
        if hands != self._hands:
            self._hands = hands
            self._layout()

    def set_states(self, states: dict[str, HandState]):
        self._states = dict(states)
        self._paint()

    def set_selected(self, channels: set[int] | None):
        """The touch points picked (rings), or None when nothing can be picked."""
        channels = None if channels is None else set(channels)
        if channels != self._selected:
            self._selected = channels
            self._overlay_items()

    def set_dim(self, dim: dict[str, float]):
        """How faint each hand is drawn, 0-1 (1 is not dimmed): a glove not connected."""
        if dim != self._dim:
            self._dim = dict(dim)
            self._paint()

    def set_values(self, values: dict[str, list[str]] | None):
        """Numbers beside each touch point (Details), or None for none."""
        if values != self._values:
            self._values = values
            self._overlay_items()

    def hit_test(self, x: float, y: float) -> tuple[str, int] | None:
        """The hand and touch point at (x, y) on the canvas, if any."""
        if not self._gh:
            return None
        for hand in self._hands:
            ox, oy = self._origin.get(hand, (0, 0))
            pts = touch_points(hand, self._gh, self._look)
            i = nearest_point(pts, x - ox, y - oy, HIT * self._gh)
            if i is not None:
                return hand, i
        return None

    # -- layout -------------------------------------------------------------------------------

    def _on_configure(self, _e):
        if self._resize_after:
            self.after_cancel(self._resize_after)
        self._resize_after = self.after(80, self._layout)

    def _fit_gh(self, w: int, h: int) -> int:
        """The tallest glove that fits: panels side by side, names under them."""
        n = len(self._hands)
        pw, ph = panel_size(1000, self._look)
        per_w = pw / 1000 * n + GAP * (n - 1)
        per_h = ph / 1000
        name_h = NAME_H if self.names else 0
        gh = min(self.max_gh, (w - 8) / per_w, (h - name_h - 4) / per_h)
        return max(self.min_gh, int(gh) // STEP * STEP)

    def _layout(self):
        self._resize_after = None
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1:
            return
        gh = self._fit_gh(w, h)
        if gh != self._gh:
            self._gh = gh
            self._overlay.clear()
            for item in self._item.values():
                self.delete(item)
            self._item.clear()
            self._photo.clear()
            self._drawn.clear()
        pw, ph = panel_size(gh, self._look)
        gap = int(gh * GAP)
        total = pw * len(self._hands) + gap * (len(self._hands) - 1)
        x0 = (w - total) // 2
        y0 = max(0, (h - ph - (NAME_H if self.names else 0)) // 2)
        self._origin = {hand: (x0 + i * (pw + gap), y0) for i, hand in enumerate(self._hands)}
        for hand in list(self._item):
            if hand not in self._hands:
                self.delete(self._item.pop(hand))
                self._photo.pop(hand, None)
                self._drawn.pop(hand, None)
        for hand, item in self._item.items():
            self.coords(item, *self._origin[hand])
        self._paint()

    # -- drawing ------------------------------------------------------------------------------

    def _signature(self, hand: str, st: HandState) -> tuple:
        rings = tuple(int(st.since[i] * min(st.vibrating[i], 2.5) * 8) if st.vibrating[i] else -1
                      for i in range(FINGERS))
        return (self._gh, tuple(round(v * 32) for v in st.levels), rings, st.words, st.word,
                round(st.hz, 1), tuple(tuple(t) if t else None for t in st.tints) if st.tints else None,
                round(self._dim.get(hand, 1.0), 2))

    def _paint(self):
        if not self._gh:
            return
        for hand in self._hands:
            st = self._states.get(hand) or HandState()
            sig = self._signature(hand, st)
            if self._drawn.get(hand) == sig:
                continue
            self._drawn[hand] = sig
            panel = self._overlay.panel(hand, self._gh, self._look, st)
            dim = self._dim.get(hand, 1.0)
            if dim < 0.999:
                panel.putalpha(panel.getchannel("A").point(lambda a, k=dim: int(a * k)))
            flat = Image.new("RGB", panel.size, self._bg)
            flat.paste(panel, (0, 0), panel)
            photo = self._photo.get(hand)
            if photo is not None and (photo.width(), photo.height()) == flat.size:
                photo.paste(flat)
            else:
                photo = ImageTk.PhotoImage(flat, master=self)
                self._photo[hand] = photo
                if hand in self._item:
                    self.itemconfigure(self._item[hand], image=photo)
            if hand not in self._item:
                self._item[hand] = self.create_image(*self._origin[hand], image=photo,
                                                     anchor="nw", tags="glove")
                self.tag_lower("glove")
        self._overlay_items()

    def _overlay_items(self):
        """Rings, numbers, names and the hover label: Tk items over the glove images."""
        self.delete("over")
        if not self._gh:
            return
        r = self._gh * .05
        _pw, ph = panel_size(self._gh, self._look)
        for hand in self._hands:
            ox, oy = self._origin[hand]
            pts = touch_points(hand, self._gh, self._look)
            for ch, (px, py) in enumerate(pts):
                x, y = ox + px, oy + py
                if self._selected is not None:
                    on = ch in self._selected
                    hot = self._hover == (hand, ch)
                    if on or hot:
                        # White and dark: the glove is orange, so the accent would vanish.
                        self.create_oval(x - r, y - r, x + r, y + r,
                                         outline=T.TEXT if on else T.CANVAS,
                                         width=2.5 if on else 1.5, tags="over")
                if self._values and hand in self._values:
                    left = (ch in (2, 3, 4)) != (hand == "left")
                    self.create_text(x - r - 4 if left else x + r + 4, y,
                                     text=self._values[hand][ch], anchor="e" if left else "w",
                                     fill=T.TEXT_2, font=T.mono(10.5), tags="over")
            if self.names:
                self.create_text(ox + panel_size(self._gh, self._look)[0] / 2,
                                 oy + ph + NAME_H / 2, text=tr(hand.capitalize()),
                                 fill=T.TEXT_2, font=T.font(13, 600), tags="over")
        if self._hover:
            hand, ch = self._hover
            ox, oy = self._origin[hand]
            px, py = touch_points(hand, self._gh, self._look)[ch]
            text = tr(P.FINGER_LABELS[P.Finger(ch)])
            tx, ty = ox + px, oy + py - r - 14
            pad_w = T.font(12, 600).measure(text) / 2 + 9
            self.create_rectangle(tx - pad_w, ty - 11, tx + pad_w, ty + 11, fill=T.INSET,
                                  outline=T.BORDER, tags="over")
            self.create_text(tx, ty, text=text, fill=T.TEXT, font=T.font(12, 600), tags="over")

    # -- input --------------------------------------------------------------------------------

    def _click(self, e):
        if self._selected is None or not self.on_toggle:
            return
        hit = self.hit_test(e.x, e.y)
        if hit:
            self.on_toggle(*hit)

    def _motion(self, e):
        hit = self.hit_test(e.x, e.y) if self._selected is not None else None
        self._set_hover(hit)

    def _set_hover(self, hit):
        if hit != self._hover:
            self._hover = hit
            self.configure(cursor="hand2" if hit else "")
            self._overlay_items()


def pad_state(kpa: list[float] | None, held: bool, since_press: float,
                    since_release: float | None, mode: str, intensity: float, hz: float,
                    channels: set[int]) -> HandState:
    """The Test screen's glove at one moment: what it measures, if it streams; otherwise
    what it was told to do while the pad is held. The caption follows the pad."""
    st = HandState()
    if kpa is not None:
        st.levels = [level_from_kpa(k) for k in kpa[:FINGERS]]
    elif held:
        st.levels = [intensity if ch in channels else 0.0 for ch in range(FINGERS)]
    vibrating = mode == "vibration"
    if held and vibrating:
        st.vibrating = [hz if ch in channels else 0.0 for ch in range(FINGERS)]
        st.since = [since_press] * FINGERS
        st.words, st.word, st.hz = 1, (0 if hz <= 3 else 1), hz
    elif held:
        st.word = 0 if since_press < PRESS_S else 1
    elif not vibrating and since_release is not None and since_release < RELEASE_WORD_S:
        st.word = 2
    return st
