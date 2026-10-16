"""Canvas primitives for the HEXR Companion UI.

Tkinter has no rounded corners, no borders that aren't 3D bevels, and no
hover states, so every surface in the design is drawn by hand here. Two
strategies are used, and it matters which one you reach for:

* `Panel` — a real Frame that other widgets can be packed/gridded into. A
  Canvas sits *behind* the content and paints the rounded background. The
  content frame is inset by `pad`, so as long as `pad >= radius` it never
  covers the painted corners.
* Everything else (buttons, chips, toggles, meters) is a self-contained
  Canvas that draws its own text. These size themselves to their content.

Generalised from `RoundButton` / `_round_pts` in the previous aris_console.py.
"""

from __future__ import annotations

import sys
import tkinter as tk

from . import theme as T
from .i18n import tr


def round_pts(x1, y1, x2, y2, r):
    """Point list for a rounded rectangle (use with create_polygon smooth=True)."""
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]


def draw_round(canvas: tk.Canvas, x1, y1, x2, y2, r, fill, outline=None,
               tags=None):
    """Rounded rect with an optional 1 px border, as one or two polygons.

    Callers should inset by a whole pixel (0 .. w-1), not a half. Tk does not
    antialias, so an outline placed on the half-pixel boundary rasterises onto
    the row *past* the visible area and the bottom and right edges vanish.
    """
    items = []
    if fill:
        items.append(canvas.create_polygon(
            round_pts(x1, y1, x2, y2, r), smooth=True, splinesteps=24,
            fill=fill, outline=fill, tags=tags))
    if outline and outline != fill:
        items.append(canvas.create_polygon(
            round_pts(x1, y1, x2, y2, r), smooth=True, splinesteps=24,
            fill="", outline=outline, width=1, tags=tags))
    return items


class Panel(tk.Frame):
    """A rounded, bordered container. Pack or grid children into `.body`.

    `pad` must be >= `radius` or the square content frame will clip the
    painted corners.
    """

    def __init__(self, parent, bg=T.RAISED, border=T.BORDER_SOFT,
                 radius=T.R_PANEL, pad=16, outer_bg=None, **kw):
        outer_bg = outer_bg or parent.cget("bg")
        super().__init__(parent, bg=outer_bg, **kw)
        self._bg, self._border, self._radius = bg, border, radius
        self._canvas = tk.Canvas(self, bg=outer_bg, highlightthickness=0, bd=0)
        self._canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.body = tk.Frame(self, bg=bg)
        self.body.pack(fill="both", expand=True, padx=pad, pady=pad)
        tk.Misc.lower(self._canvas, self.body)  # Canvas.lower is tag_lower
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _e=None):
        c = self._canvas
        c.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w > 2 and h > 2:
            draw_round(c, 0, 0, w - 1, h - 1, self._radius,
                       self._bg, self._border)

    def restyle(self, bg=None, border=None):
        if bg:
            self._bg = bg
            self.body.configure(bg=bg)
        if border:
            self._border = border
        self._redraw()


class Surface(tk.Frame):
    """A rounded, bordered container whose content runs edge to edge.

    `Panel` paints its background behind an inset content frame, which means
    content can never reach the rounded corners. Tables need the opposite: rows
    that span the full width, with dividers that touch both edges.

    So this does it the other way round — a normal 1 px-bordered Frame that
    children pack into directly, with four small Canvases placed *on top* of
    the corners. Each paints the parent's background outside the corner radius
    and the panel fill inside it, which reads as a rounded corner.
    """

    def __init__(self, parent, bg=T.RAISED, border=T.BORDER_SOFT,
                 radius=T.R_PANEL, outer_bg=None, **kw):
        outer_bg = outer_bg or parent.cget("bg")
        super().__init__(parent, bg=bg, highlightthickness=1,
                         highlightbackground=border, highlightcolor=border,
                         bd=0, **kw)
        self._radius, self._fill, self._border = radius, bg, border
        self._outer = outer_bg
        self._corners = []
        size = radius + 1
        for _ in range(4):
            c = tk.Canvas(self, width=size, height=size, bg=outer_bg,
                          highlightthickness=0, bd=0)
            self._corners.append(c)
        self._paint_corners()
        self.bind("<Configure>", self._place_corners)

    def _paint_corners(self):
        r = self._radius
        size = r + 1
        # start angle of the quarter that this corner occupies
        for c, start in zip(self._corners, (90, 0, 180, 270)):
            c.delete("all")
            c.configure(bg=self._outer)
            # the disc is centred on the inner corner of this square
            cx = 1 if start in (90, 180) else size - 1 - r
            cy = 1 if start in (90, 0) else size - 1 - r
            # shift so the arc's centre lands on the panel's corner radius origin
            x0 = cx if start in (90, 180) else cx - r
            y0 = cy if start in (90, 0) else cy - r
            bbox = (x0, y0, x0 + 2 * r, y0 + 2 * r)
            c.create_arc(bbox, start=start, extent=90, style="pieslice",
                         fill=self._fill, outline=self._fill)
            c.create_arc(bbox, start=start, extent=90, style="arc",
                         outline=self._border, width=1)

    def _place_corners(self, _e=None):
        r = self._radius
        tl, tr, bl, br = self._corners
        tl.place(x=-1, y=-1)
        tr.place(relx=1.0, x=-r, y=-1)
        bl.place(x=-1, rely=1.0, y=-r)
        br.place(relx=1.0, x=-r, rely=1.0, y=-r)
        for c in self._corners:
            tk.Misc.lift(c)         # Canvas.lift is tag_raise, not the widget op

    def restyle(self, bg=None, border=None):
        if bg:
            self._fill = bg
            self.configure(bg=bg)
        if border:
            self._border = border
            self.configure(highlightbackground=border, highlightcolor=border)
        self._paint_corners()


class Divider(tk.Frame):
    """A 1 px horizontal rule."""

    def __init__(self, parent, color=T.BORDER_ROW):
        super().__init__(parent, bg=color, height=1)


class Dot(tk.Canvas):
    """A small status dot."""

    def __init__(self, parent, size=8, color=T.DOT_OFF, bg=None):
        bg = bg or parent.cget("bg")
        super().__init__(parent, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0)
        self._size = size
        self.set(color)

    def set(self, color):
        self.delete("all")
        self.create_oval(0, 0, self._size - 1, self._size - 1, fill=color,
                         width=0)


class Button(tk.Canvas):
    """A flat rounded button that sizes itself to its label.

    Supports the design's three shapes: solid (accent fill), outline (border
    only) and text-only (no fill, no border).
    """

    def __init__(self, parent, text, command=None, height=34, radius=T.R_CTRL,
                 fill=T.ACCENT, fg=T.CANVAS, border=None, hover_fill=None,
                 hover_fg=None, hover_border=None, font=None, glyph=None,
                 glyph_px=10, padx=18, gap=8, bg=None, min_width=0, icon=None):
        bg = bg or parent.cget("bg")
        self._font = font or T.font(13, 600)
        self._glyph_font = T.font(glyph_px)
        self.text, self.glyph = text, glyph
        # A drawn mark (icon_more, icon_fullscreen...) for the marks IBM Plex lacks.
        self.icon = icon
        self.fill, self.fg, self.border = fill, fg, border or fill
        self.hover_fill = hover_fill or fill
        self.hover_fg = hover_fg or fg
        self.hover_border = hover_border or (border or fill)
        self.command, self.radius, self.padx, self.gap = command, radius, padx, gap
        self.h, self.min_width, self._bg = height, min_width, bg
        self.disabled = False
        self._hovering = False
        super().__init__(parent, height=height, bg=bg, highlightthickness=0, bd=0)
        self._resize()
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        # a button packed with fill="x" is stretched past its content width;
        # without this it would keep painting itself at the narrower size and
        # leave a half-drawn border floating inside the allocated space
        self.bind("<Configure>", lambda e: self._render())

    def _content_width(self):
        if self.icon and not self.text:
            return max(self.h, self.min_width)
        w = self._font.measure(self.text) + self.padx * 2
        if self.glyph:
            w += self._glyph_font.measure(self.glyph) + self.gap
        if self.icon:
            w += 16 + self.gap
        return max(w, self.min_width)

    def _draw_width(self):
        return max(self._content_width(), self.winfo_width())

    def _resize(self):
        self.configure(width=self._content_width(), height=self.h)
        self._render()

    def _render(self):
        self.delete("all")
        w, h = self._draw_width(), self.winfo_height() or self.h
        fill = self.hover_fill if self._hovering else self.fill
        fg = self.hover_fg if self._hovering else self.fg
        edge = self.hover_border if self._hovering else self.border
        if self.disabled:
            fill, fg, edge = self.fill, T.TEXT_OFF, self.border
        draw_round(self, 0, 0, w - 1, h - 1, self.radius,
                   None if fill == "transparent" else fill,
                   None if edge == "transparent" else edge)
        if self.icon and not self.text:
            self.icon(self, w / 2, h / 2, fg)
        elif self.icon:
            tw = self._font.measure(self.text)
            x = (w - (16 + self.gap + tw)) / 2
            self.icon(self, x + 8, h / 2, fg)
            self.create_text(x + 16 + self.gap, h / 2, text=self.text, fill=fg,
                             anchor="w", font=self._font)
        elif self.glyph:
            gw = self._glyph_font.measure(self.glyph)
            tw = self._font.measure(self.text)
            x = (w - (gw + self.gap + tw)) / 2
            self.create_text(x, h / 2, text=self.glyph, fill=fg, anchor="w",
                             font=self._glyph_font)
            self.create_text(x + gw + self.gap, h / 2, text=self.text, fill=fg,
                             anchor="w", font=self._font)
        else:
            self.create_text(w / 2, h / 2, text=self.text, fill=fg,
                             font=self._font)
        self.configure(cursor="arrow" if self.disabled else "hand2")

    def _click(self, _e):
        if not self.disabled and self.command:
            self.command()

    def _enter(self, _e):
        if not self.disabled:
            self._hovering = True
            self._render()

    def _leave(self, _e):
        self._hovering = False
        self._render()

    def set(self, text=None, fill=None, fg=None, border=None, hover_fill=None,
            hover_fg=None, hover_border=None, glyph=None, disabled=None,
            command=None, icon=None):
        if icon is not None:
            self.icon = icon or None
        if text is not None:
            self.text = text
        if fill is not None:
            self.fill = fill
        if fg is not None:
            self.fg = fg
        if border is not None:
            self.border = border
        if hover_fill is not None:
            self.hover_fill = hover_fill
        if hover_fg is not None:
            self.hover_fg = hover_fg
        if hover_border is not None:
            self.hover_border = hover_border
        if glyph is not None:
            self.glyph = glyph
        if disabled is not None:
            self.disabled = disabled
        if command is not None:
            self.command = command
        self._resize()


class IconButton(tk.Canvas):
    """A fixed-size square-ish glyph button — the title bar controls.

    Either a text `glyph` or a `painter` that draws the mark directly. The
    maximise and restore marks are drawn rather than typed: the conventional
    code points for them (U+2750 and friends) are missing from IBM Plex, and a
    window control that renders as a hollow box is worse than no icon at all.
    """

    def __init__(self, parent, glyph="", command=None, width=44, height=34,
                 fg=T.TEXT_MUTED, hover_bg=T.BORDER_SOFT, hover_fg=T.TEXT,
                 bg=None, px=14, painter=None):
        bg = bg or parent.cget("bg")
        super().__init__(parent, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0)
        self.glyph, self.command = glyph, command
        self.w, self.h = width, height
        self.fg, self.hover_bg, self.hover_fg, self._bg = fg, hover_bg, hover_fg, bg
        self._font = T.font(px)
        self.painter = painter
        self._hot = False
        self._render(False)
        self.bind("<Button-1>", lambda e: self.command and self.command())
        self.bind("<Enter>", lambda e: self._render(True))
        self.bind("<Leave>", lambda e: self._render(False))
        self.configure(cursor="hand2")

    def set_painter(self, painter):
        """Swap the mark in place — maximise becoming restore, and back."""
        self.painter = painter
        self._render(self._hot)

    def _render(self, hot):
        self._hot = hot
        self.delete("all")
        bg = self.hover_bg if hot else self._bg
        fg = self.hover_fg if hot else self.fg
        self.create_rectangle(0, 0, self.w, self.h, width=0, fill=bg)
        if self.painter is not None:
            self.painter(self, fg, bg)
        else:
            self.create_text(self.w / 2, self.h / 2, text=self.glyph,
                             fill=fg, font=self._font)


class GlovesButton(tk.Canvas):
    """The header's one word on this computer's gloves: the Bluetooth rune, a dot
    per hand and the battery, "ᛒ  L ●  R ●  85%". Green is connected, orange is
    connecting or searching, grey is not there. A click goes to the gloves.

    The rune is drawn, not typed: U+16D2 is missing from IBM Plex, like the
    window marks below.
    """

    H = 34

    def __init__(self, parent, command=None, bg=None):
        bg = bg or parent.cget("bg")
        super().__init__(parent, width=120, height=self.H, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.command = command
        self._look = None
        self._hot = False
        self._font = T.font(13, 600)
        self._mono = T.mono(12, 500)
        self.set({}, None)
        self.bind("<Button-1>", lambda e: self.command and self.command())
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))

    def set(self, dots: dict, battery: str | None, low: bool = False):
        """`dots` maps "Left"/"Right" to a colour, or None for not there."""
        look = (tuple(sorted(dots.items())), battery, low)
        if look != self._look:
            self._look = look
            self._render()

    def _hover(self, hot: bool):
        self._hot = hot
        self._render()

    def _render(self):
        self.delete("all")
        dots, battery, low = self._look
        dots = dict(dots)
        letters = [(tr("L"), dots.get("Left")), (tr("R"), dots.get("Right"))]
        w = 34 + sum(self._font.measure(l) + 6 + 8 + 12 for l, _ in letters)
        if battery:
            w += self._mono.measure(battery) + 6
        w += 8
        self.configure(width=w)
        draw_round(self, 0, 0, w - 1, self.H - 1, T.R_CTRL,
                   fill=T.INSET if self._hot else T.RAISED,
                   outline=T.ACCENT if self._hot else T.BORDER)
        fg = T.ACCENT if self._hot else T.TEXT
        x, y = 13, 8
        self.create_line(x, y + 5, x + 9, y + 13, x + 4.5, y + 17, x + 4.5, y + 1,
                         x + 9, y + 5, x, y + 13, fill=fg, width=1.6,
                         capstyle="round", joinstyle="round")
        x = 34
        for letter, colour in letters:
            self.create_text(x, self.H / 2, text=letter, anchor="w", fill=fg, font=self._font)
            x += self._font.measure(letter) + 6
            c = colour or T.DOT_OFF
            self.create_oval(x, 13, x + 8, 21, fill=c, outline=c)
            x += 8 + 12
        if battery:
            self.create_text(x, self.H / 2, text=battery, anchor="w",
                             fill=T.WARN if low else T.TEXT_2, font=self._mono)


def paint_maximise(c: IconButton, fg: str, bg: str):
    """An empty square: this window is not filling the screen yet."""
    x, y, s = c.w / 2, c.h / 2, 4.5
    c.create_rectangle(x - s, y - s, x + s, y + s, outline=fg, width=1.3)


def paint_restore(c: IconButton, fg: str, bg: str):
    """Two offset squares, the Windows restore mark.

    The front square is filled with the button's own background so the two read
    as overlapping sheets rather than as a grid.
    """
    x, y, s = c.w / 2, c.h / 2, 4.0
    c.create_rectangle(x - s + 2.5, y - s - 2.5, x + s + 2.5, y + s - 2.5,
                       outline=fg, width=1.3)
    c.create_rectangle(x - s - 2.5, y - s + 2.5, x + s - 2.5, y + s + 2.5,
                       outline=fg, width=1.3, fill=bg)


class Select(tk.Canvas):
    """A themed dropdown. ttk.Combobox can't be styled to the design on
    Windows, so this is a Canvas face plus a tk.Menu popup."""

    def __init__(self, parent, values, value=None, command=None, label=None,
                 width=None, height=34, radius=T.R_CTRL, bg=None,
                 fill=T.RAISED, border=T.BORDER, px=12.5, extra_items=None):
        bg = bg or parent.cget("bg")
        super().__init__(parent, height=height, bg=bg, highlightthickness=0, bd=0)
        self.values, self.command, self.label = values, command, label
        # (label, callback, enabled_fn) rows appended under a separator —
        # where profile management lives, so it sits with the thing it manages
        self.extra_items = extra_items or []
        self.value = value or (values[0] if values else "")
        self.h, self.radius, self.fill, self.border = height, radius, fill, border
        self._font = T.font(px)
        self._label_font = T.font(10)
        self._fixed_w = width
        self._render()
        self.bind("<Button-1>", self._popup)
        self.configure(cursor="hand2")

    def _width(self):
        if self._fixed_w:
            return self._fixed_w
        w = 12 + max(self._font.measure(v) for v in self.values or [""]) + 8 + 9 + 12
        if self.label:
            w += self._label_font.measure(T.track(self.label)) + 8
        return w

    def _render(self):
        self.delete("all")
        w = self._width()
        self.configure(width=w)
        draw_round(self, 0, 0, w - 1, self.h - 1, self.radius,
                   self.fill, self.border)
        x = 12
        if self.label:
            self.create_text(x, self.h / 2, text=T.track(self.label),
                             fill=T.TEXT_FAINT, anchor="w", font=self._label_font)
            x += self._label_font.measure(T.track(self.label)) + 8
        self.create_text(x, self.h / 2, text=self.value, fill=T.TEXT,
                         anchor="w", font=self._font)
        self.create_text(w - 12, self.h / 2, text="▼", fill=T.TEXT_FAINT,
                         anchor="e", font=T.font(9))

    def _popup(self, e):
        m = tk.Menu(self, tearoff=0, bg=T.RAISED, fg=T.TEXT,
                    activebackground=T.ACCENT, activeforeground=T.CANVAS,
                    bd=0, relief="flat", font=self._font)
        for v in self.values:
            m.add_command(label=("• " if v == self.value else "    ") + v,
                          command=lambda val=v: self._choose(val))
        if self.extra_items:
            m.add_separator()
            for label, callback, enabled_fn in self.extra_items:
                state = "normal" if (enabled_fn is None or enabled_fn()) else "disabled"
                m.add_command(label=label, command=callback, state=state)
        try:
            m.tk_popup(self.winfo_rootx(), self.winfo_rooty() + self.h)
        finally:
            m.grab_release()

    def _choose(self, value):
        self.value = value
        self._render()
        if self.command:
            self.command(value)

    def set(self, value=None, values=None):
        if values is not None:
            self.values = values
        if value is not None:
            self.value = value
        self._render()


class NavRow(tk.Canvas):
    """One place in the left rail. Not numbered: the places are not steps."""

    def __init__(self, parent, label, command=None, bg=T.RAIL):
        super().__init__(parent, height=42, bg=bg, highlightthickness=0, bd=0)
        self.label, self.command, self._bg = label, command, bg
        self.active, self._hot = False, False
        self.bind("<Button-1>", lambda e: self.command and self.command())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        # redraw on layout: winfo_width() is 1 until the row is mapped, and
        # drawing at width 1 silently loses the fill and the completion tick
        self.bind("<Configure>", lambda e: self.render())
        self.configure(cursor="hand2")

    def _enter(self, _e):
        self._hot = True
        self.render()

    def _leave(self, _e):
        self._hot = False
        self.render()

    def render(self):
        self.delete("all")
        w = self.winfo_width()
        if w <= 1:                          # not laid out yet
            return
        bg = T.INSET if (self.active or self._hot) else self._bg
        draw_round(self, 0, 0, w, 42, T.R_CTRL, bg, None)
        if self.active:
            self.create_rectangle(0, 0, 2, 42, fill=T.ACCENT, width=0)
        self.create_text(16, 21, text=self.label, anchor="w",
                         fill=T.TEXT if self.active else T.TEXT_MUTED,
                         font=T.font(13.5, 600 if self.active else 500))

    def set(self, active=None):
        if active is not None and active != self.active:
            self.active = active
            self.render()


class Meter(tk.Canvas):
    """A signal bar with a threshold marker.

    Redraws by moving existing items rather than recreating them — these
    update ~20 times a second, per port, and delete/recreate churn shows up as
    flicker and wasted CPU.
    """

    def __init__(self, parent, height=16, bg=None, radius=T.R_METER):
        bg = bg or parent.cget("bg")
        # width=1: a Canvas asks for 378px by default. These stretch to their
        # cell, so the request is meaningless — but it is not harmless. Left
        # in, five of them made the sensor list demand 700px and squeeze the
        # detail panel next to it down to a column of clipped text.
        super().__init__(parent, width=1, height=height, bg=bg,
                         highlightthickness=0, bd=0)
        self.h, self.radius = height, radius
        self._v, self._thr, self._over, self._on = 0.0, 0.6, False, True
        self._items = {}
        self.bind("<Configure>", lambda e: self._build())

    def _build(self):
        self.delete("all")
        self._items.clear()
        w = self.winfo_width()
        if w <= 1:
            return
        draw_round(self, 0, 0, w - 1, self.h - 1, self.radius, T.RAIL,
                   T.BORDER_SOFT)
        self._items["fill"] = self.create_rectangle(
            1, 1, 1, self.h - 1, width=0, fill=T.METER_IDLE)
        self._items["thr"] = self.create_rectangle(
            0, 0, 0, self.h, width=0, fill=T.ACCENT)
        self._paint()

    def _paint(self):
        if not self._items:
            return
        w = self.winfo_width()
        inner = max(0, w - 2)
        fill_w = 1 + inner * max(0.0, min(1.0, self._v))
        colour = (T.BORDER if not self._on
                  else T.ACCENT if self._over else T.METER_IDLE)
        self.coords(self._items["fill"], 1, 1, fill_w, self.h - 1)
        self.itemconfigure(self._items["fill"], fill=colour)
        x = 1 + inner * max(0.0, min(1.0, self._thr))
        self.coords(self._items["thr"], x - 1, 0, x + 1, self.h)
        self.itemconfigure(self._items["thr"],
                           state="normal" if self._on else "hidden")

    def set(self, value=None, thr=None, over=None, on=None):
        if value is not None:
            self._v = value
        if thr is not None:
            self._thr = thr
        if over is not None:
            self._over = over
        if on is not None:
            self._on = on
        if not self._items:
            self._build()
        else:
            self._paint()


class Trace(tk.Canvas):
    """The calibration trace: N recent samples as bars, plus a threshold line."""

    def __init__(self, parent, samples=48, height=150, bg=None):
        bg = bg or parent.cget("bg")
        super().__init__(parent, width=1, height=height, bg=bg,
                         highlightthickness=0, bd=0)     # see Meter on width
        self.n, self.h = samples, height
        self._values = [0.0] * samples
        self._thr = 0.6
        self.bind("<Configure>", lambda e: self._paint())

    def set(self, values, thr):
        vals = list(values)[-self.n:]
        if len(vals) < self.n:
            vals = [0.0] * (self.n - len(vals)) + vals
        self._values, self._thr = vals, thr
        self._paint()

    def _paint(self):
        self.delete("all")
        w = self.winfo_width()
        if w <= 1:
            return
        draw_round(self, 0, 0, w - 1, self.h - 1, T.R_CTRL, T.RAIL,
                   T.BORDER_SOFT)
        pad = 10
        inner_w, inner_h = w - pad * 2, self.h - pad * 2
        gap = 2
        bar_w = max(1.0, (inner_w - gap * (self.n - 1)) / self.n)
        base = self.h - pad
        for i, v in enumerate(self._values):
            v = max(0.0, min(1.0, v))
            bh = max(2.0, v * inner_h)
            x = pad + i * (bar_w + gap)
            self.create_rectangle(x, base - bh, x + bar_w, base, width=0,
                                  fill=T.ACCENT if v >= self._thr else T.TRACE_IDLE)
        y = base - max(0.0, min(1.0, self._thr)) * inner_h
        self.create_line(pad, y, w - pad, y, fill=T.ACCENT, width=1)


class Slider(tk.Canvas):
    """A themed range slider. ttk.Scale can't match the design on Windows."""

    def __init__(self, parent, value=0.6, lo=0.05, hi=0.95, command=None,
                 height=14, bg=None):
        bg = bg or parent.cget("bg")
        super().__init__(parent, width=1, height=height, bg=bg,
                         highlightthickness=0, bd=0)     # see Meter on width
        self.value, self.lo, self.hi = value, lo, hi
        self.command, self.h = command, height
        self.bind("<Configure>", lambda e: self._paint())
        self.bind("<Button-1>", self._drag)
        self.bind("<B1-Motion>", self._drag)
        self.configure(cursor="hand2")

    def _frac(self):
        return (self.value - self.lo) / max(1e-9, self.hi - self.lo)

    def _paint(self):
        self.delete("all")
        w = self.winfo_width()
        if w <= 1:
            return
        cy, r = self.h / 2, 7
        self.create_rectangle(r, cy - 2, w - r, cy + 2, width=0, fill=T.BORDER)
        x = r + self._frac() * (w - 2 * r)
        self.create_oval(x - r, cy - r, x + r, cy + r, fill=T.ACCENT, width=0)

    def _drag(self, e):
        w = self.winfo_width()
        r = 7
        frac = (e.x - r) / max(1, w - 2 * r)
        self.set(self.lo + max(0.0, min(1.0, frac)) * (self.hi - self.lo))
        if self.command:
            self.command(self.value)

    def set(self, value):
        self.value = max(self.lo, min(self.hi, value))
        self._paint()


class Readout(Panel):
    """One of the calibration panel's labelled value cards."""

    def __init__(self, parent, label, value="—", accent=False):
        super().__init__(parent, bg=T.INSET,
                         border=T.ACCENT if accent else T.BORDER_SOFT,
                         radius=T.R_CTRL, pad=12)
        fg = T.ACCENT if accent else T.TEXT_FAINT
        tk.Label(self.body, text=T.track(label), bg=T.INSET, fg=fg,
                 font=T.font(10), anchor="w").pack(fill="x")
        self.value = tk.Label(self.body, text=value, bg=T.INSET,
                              fg=T.ACCENT if accent else T.TEXT,
                              font=T.mono(18), anchor="w")
        self.value.pack(fill="x", pady=(5, 0))

    def set(self, text):
        self.value.configure(text=text)


class Toggle(tk.Canvas):
    """The 30x17 enable switch."""

    def __init__(self, parent, command=None, bg=None):
        bg = bg or parent.cget("bg")
        super().__init__(parent, width=30, height=17, bg=bg,
                         highlightthickness=0, bd=0)
        self.command, self.on, self.live = command, True, True
        self.bind("<Button-1>", self._click)
        self.configure(cursor="hand2")
        self.render()

    def _click(self, _e):
        # must not bubble: clicking the switch toggles, it does not re-select
        if self.command:
            self.command()
        return "break"

    def set(self, on, live=True):
        if (on, self.live) == (self.on, live):
            return
        self.on, self.live = on, live
        self.render()

    def render(self):
        self.delete("all")
        # an enabled sensor with nothing plugged in cannot fire; showing its
        # switch at full accent would claim otherwise
        track = (T.ACCENT if self.live else T.BORDER) if self.on else T.BORDER
        draw_round(self, 0, 0, 29, 16, 8, track)
        x = 15 if self.on else 2
        self.create_oval(x, 2, x + 13, 15,
                         fill="#FFFFFF" if self.live else T.TEXT_OFF, width=0)


class Cell(tk.Canvas):
    """A selectable tile — mouse actions, presets, segmented tabs."""

    def __init__(self, parent, label, sub=None, command=None, height=56,
                 bg=None, mono_label=True):
        bg = bg or parent.cget("bg")
        super().__init__(parent, width=1, height=height, bg=bg,
                         highlightthickness=0, bd=0)
        self.label, self.sub, self.command = label, sub, command
        self.h, self.selected, self._hot = height, False, False
        self.mono_label = mono_label
        self.bind("<Button-1>", lambda e: self.command and self.command(self.label))
        self.bind("<Enter>", lambda e: self._set_hot(True))
        self.bind("<Leave>", lambda e: self._set_hot(False))
        self.bind("<Configure>", lambda e: self.render())
        self.configure(cursor="hand2")

    def _set_hot(self, hot):
        self._hot = hot
        self.render()

    def set(self, selected):
        if selected == self.selected:
            return
        self.selected = selected
        self.render()

    def render(self):
        self.delete("all")
        w = self.winfo_width()
        if w <= 1:
            return
        if self.selected:
            fill, edge, fg = T.ACCENT_FILL, T.ACCENT, T.ACCENT
        else:
            fill, edge = T.INSET, T.ACCENT if self._hot else T.BORDER
            fg = T.ACCENT if self._hot else T.TEXT_2
        draw_round(self, 0, 0, w - 1, self.h - 1, T.R_CTRL, fill, edge)
        if self.sub:
            self.create_text(w / 2, self.h / 2 - 8, text=self.label, fill=fg,
                             font=T.font(12.5))
            self.create_text(w / 2, self.h / 2 + 10, text=self.sub,
                             fill=T.TEXT_FAINT, font=T.mono(10))
        else:
            self.create_text(w / 2, self.h / 2, text=self.label, fill=fg,
                             font=T.mono(11.5) if self.mono_label else T.font(12.5))


class KeyCap(tk.Canvas):
    """One key on the QWERTY board, with an optional owner badge."""

    H = 32

    def __init__(self, parent, label, command=None, bg=None):
        # width=1: a Canvas asks for 378px by default, which would blow the row
        # far past the panel and clip every key after the first few. The real
        # width comes from the column weight.
        bg = bg or parent.cget("bg")
        super().__init__(parent, width=1, height=self.H, bg=bg,
                         highlightthickness=0, bd=0)
        self.label, self.command = label, command
        self.owner = None           # sensor number that owns this key
        self.mine = False           # owned by the currently selected sensor
        self.bind("<Button-1>", lambda e: self.command and self.command(label))
        self.bind("<Configure>", lambda e: self.render())
        self.configure(cursor="hand2")

    def set(self, owner, mine):
        if (owner, mine) == (self.owner, self.mine):
            return
        self.owner, self.mine = owner, mine
        self.render()

    def render(self):
        self.delete("all")
        w = self.winfo_width()
        if w <= 1:
            return
        if self.mine:
            fill, fg, edge = T.ACCENT, T.CANVAS, T.ACCENT
        elif self.owner is not None:
            fill, fg, edge = T.ACCENT_FILL, T.ACCENT, T.ACCENT_EDGE
        else:
            fill, fg, edge = T.INSET, T.TEXT_2, T.BORDER
        draw_round(self, 0, 4, w - 1, self.H - 1, T.R_CHIP, fill, edge)
        self.create_text(w / 2, (self.H + 4) / 2, text=self.label, fill=fg,
                         font=T.font(11))
        if self.owner is not None and not self.mine:
            bw = max(13, T.mono(9, 600).measure(str(self.owner)) + 8)
            x = w - bw - 1
            draw_round(self, x, 0, x + bw, 13, 6, T.ACCENT)
            self.create_text(x + bw / 2, 6.5, text=str(self.owner),
                             fill=T.CANVAS, font=T.mono(9, 600))


class Chip(tk.Canvas):
    """The action chip that lights up while its sensor is firing."""

    def __init__(self, parent, height=32, width=1, bg=None):
        bg = bg or parent.cget("bg")
        super().__init__(parent, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0)
        self.h, self.label, self.firing, self.on = height, "—", False, True
        self.command = None
        self.bind("<Configure>", lambda e: self.render())
        self.bind("<Button-1>", lambda e: self.command and self.command())

    def set(self, label, firing, on=True):
        if (label, firing, on) == (self.label, self.firing, self.on):
            return                          # nothing changed; skip the redraw
        self.label, self.firing, self.on = label, firing, on
        self.render()

    def render(self):
        self.delete("all")
        w = self.winfo_width()
        if w <= 1:
            return
        if self.firing:
            fill, fg, edge = T.ACCENT, T.CANVAS, T.ACCENT
        else:
            fill, edge = T.INSET, T.BORDER
            fg = T.TEXT if self.on else T.TEXT_OFF
        draw_round(self, 0, 0, w - 1, self.h - 1, T.R_CELL, fill, edge)
        self.create_text(w / 2, self.h / 2, text=self.label, fill=fg,
                         font=T.mono(12.5))


class Disclosure(tk.Frame):
    """A 'Fine-tune ▾' twisty over a body that packs and unpacks.

    Everything the wearer needs on a good day stays visible; the numbers behind
    it — raw readings, sensitivity, per-half re-capture — live in here, one
    click away, rather than being cut or being on screen all the time.
    """

    def __init__(self, parent, text, bg=None, fg=None):
        bg = bg or parent.cget("bg")
        super().__init__(parent, bg=bg)
        self._text, self._open = text, False
        self.head = tk.Label(self, text=f"{text}  ▾", bg=bg,
                             fg=fg or T.TEXT_MUTED, font=T.font(12),
                             anchor="w", cursor="hand2")
        self.head.pack(fill="x")
        self.head.bind("<Button-1>", lambda e: self.toggle())
        self.head.bind("<Enter>", lambda e: self.head.configure(fg=T.ACCENT))
        self.head.bind("<Leave>", lambda e: self.head.configure(
            fg=T.ACCENT if self._open else (fg or T.TEXT_MUTED)))
        self.body = tk.Frame(self, bg=bg)

    def toggle(self):
        self.set_open(not self._open)

    def set_open(self, on: bool):
        self._open = on
        self.head.configure(text=f"{self._text}  {'▴' if on else '▾'}",
                            fg=T.ACCENT if on else T.TEXT_MUTED)
        if on:
            self.body.pack(fill="x", pady=(12, 0))
        else:
            self.body.pack_forget()


class Section(tk.Frame):
    """One panel of an accordion: a numbered header with a live status on the
    right, over a body that packs and unpacks.

    A sensor's two questions — what range has it learned, and what does it
    press — will not both fit in the detail column at once, and neither will
    shrink to fit without losing the QWERTY board or the trace. Stacking them
    as an accordion keeps both one click away, keeps the dependency between
    them visible (there is no point assigning a key to a sensor that has not
    been taught), and lets the collapsed one still report its state in its
    header rather than going silent.
    """

    def __init__(self, parent, num, title, command=None, bg=None):
        bg = bg or parent.cget("bg")
        super().__init__(parent, bg=bg)
        self._bg, self._open, self.command = bg, False, command

        head = tk.Frame(self, bg=bg, cursor="hand2")
        head.pack(fill="x")
        self.head = head
        self.num = tk.Label(head, text=num, bg=bg, fg=T.TEXT_OFF,
                            font=T.mono(11), width=2, anchor="w")
        self.num.pack(side="left")
        self.title = tk.Label(head, text=T.track(title), bg=bg,
                              fg=T.TEXT_FAINT, font=T.font(10), anchor="w")
        self.title.pack(side="left", padx=(6, 0))
        self.chev = tk.Label(head, text="▾", bg=bg, fg=T.TEXT_FAINT,
                             font=T.font(9), anchor="e")
        self.chev.pack(side="right")
        self.status = tk.Label(head, text="", bg=bg, fg=T.TEXT_FAINT,
                               font=T.font(11.5), anchor="e")
        self.status.pack(side="right", padx=(0, 9))

        self.body = tk.Frame(self, bg=bg)

        for w in (head, self.num, self.title, self.status, self.chev):
            w.bind("<Button-1>", lambda e: self.command and self.command())
            w.bind("<Enter>", lambda e: self._hot(True))
            w.bind("<Leave>", lambda e: self._hot(False))

    def _hot(self, on):
        if not self._open:
            self.title.configure(fg=T.ACCENT if on else T.TEXT_FAINT)
            self.chev.configure(fg=T.ACCENT if on else T.TEXT_FAINT)

    def set_status(self, text, colour=T.TEXT_FAINT):
        self.status.configure(text=text, fg=colour)

    def is_open(self) -> bool:
        return self._open

    def set_open(self, on: bool):
        if on == self._open:
            return
        self._open = on
        self.num.configure(fg=T.ACCENT if on else T.TEXT_OFF)
        self.title.configure(fg=T.TEXT if on else T.TEXT_FAINT)
        self.chev.configure(text="▴" if on else "▾",
                            fg=T.TEXT_FAINT if on else T.TEXT_FAINT)
        if on:
            self.body.pack(fill="both", expand=True, pady=(12, 0))
        else:
            self.body.pack_forget()


class Scrubber(Slider):
    """Where a video is: what has played is lit, and a click or a drag moves it. `dragging`
    says the hand is on it, so the video's own progress does not fight the drag."""

    def __init__(self, parent, command=None, bg=None):
        super().__init__(parent, value=0.0, lo=0.0, hi=1.0, command=command, height=16, bg=bg)
        self.dragging = False
        self.bind("<ButtonPress-1>", lambda e: setattr(self, "dragging", True), add="+")
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "dragging", False), add="+")

    def _paint(self):
        self.delete("all")
        w = self.winfo_width()
        if w <= 1:
            return
        cy, r = self.h / 2, 6
        x = r + self._frac() * (w - 2 * r)
        self.create_rectangle(r, cy - 2, w - r, cy + 2, width=0, fill=T.BORDER)
        self.create_rectangle(r, cy - 2, x, cy + 2, width=0, fill=T.ACCENT)
        self.create_oval(x - r, cy - r, x + r, cy + r, fill=T.TEXT, width=0)


class Progress(tk.Canvas):
    """A determinate bar — the countdown and capture phases of teaching."""

    def __init__(self, parent, height=4, bg=None):
        bg = bg or parent.cget("bg")
        super().__init__(parent, width=1, height=height, bg=bg,
                         highlightthickness=0, bd=0)     # see Meter on width
        self.h, self._v, self._colour = height, 0.0, T.ACCENT
        self.bind("<Configure>", lambda e: self._paint())

    def set(self, value: float, colour: str | None = None):
        self._v = max(0.0, min(1.0, value))
        if colour:
            self._colour = colour
        self._paint()

    def _paint(self):
        self.delete("all")
        w = self.winfo_width()
        if w <= 1:
            return
        draw_round(self, 0, 0, w - 1, self.h - 1, self.h / 2, T.BORDER)
        if self._v > 0:
            draw_round(self, 0, 0, max(self.h, self._v * (w - 1)), self.h - 1,
                       self.h / 2, self._colour)


class ScrollArea(tk.Frame):
    """A vertically scrolling content region. `.body` is the scrolled frame."""

    def __init__(self, parent, bg=T.SURFACE, padx=28, pady=26, fill_height=False):
        super().__init__(parent, bg=bg)
        # fill_height: the body is at least as tall as the view, so a screen can grow a
        # picture into the room there is, and only scrolls when the window is too small.
        self._fill = fill_height
        self._fitted = None
        self.extra = None       # a widget under the filled part, that adds to its height
        self._canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self._canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self._canvas, bg=bg)
        self._win = self._canvas.create_window((padx, pady), window=self.body,
                                               anchor="nw")
        self._padx, self._pady = padx, pady
        self.body.bind("<Configure>", self._on_body)
        self._canvas.bind("<Configure>", self._on_canvas)
        self.bind_all("<MouseWheel>", self._on_wheel, add="+")

    def _on_body(self, _e):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas(self, e):
        self._canvas.itemconfigure(self._win, width=e.width - self._padx * 2)
        self.refit()

    def refit(self):
        """For a filling area: as tall as the view, or as its content if that is taller."""
        if not self._fill:
            return
        view = self._canvas.winfo_height() - self._pady * 2
        extra = self.extra
        below = extra.winfo_reqheight() if extra is not None and extra.winfo_manager() else 0
        h = max(view + below, self.body.winfo_reqheight())
        if h != self._fitted and view > 1:
            self._fitted = h
            self._canvas.itemconfigure(self._win, height=h)
            self._canvas.configure(scrollregion=(0, 0, self._canvas.winfo_width(),
                                                 h + self._pady * 2))

    def scroll_to(self, widget):
        """Bring `widget` to the top of the view."""
        self.update_idletasks()
        # The region follows the body on <Configure>, which may not have run yet: a scroll
        # into content just built would stop at the old end.
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        total = max(1, self.body.winfo_height() + self._pady * 2)
        y = widget.winfo_rooty() - self.body.winfo_rooty()
        self._canvas.yview_moveto(max(0.0, y / total))

    def reveal(self, widget):
        """Scroll just enough to show all of `widget`, or its top if it is taller than the view."""
        self.update_idletasks()
        # The region follows the body on <Configure>, which may not have run yet: a scroll
        # into content just built would stop at the old end.
        region = self._canvas.bbox("all")
        self._canvas.configure(scrollregion=region)
        # In canvas units, where the body sits at (padx, pady).
        top = widget.winfo_rooty() - self.body.winfo_rooty() + self._pady
        bottom = top + widget.winfo_height() + self._pady
        view = self._canvas.winfo_height()
        y0 = self._canvas.canvasy(0)
        if bottom > y0 + view:
            y0 = bottom - view
        y0 = min(y0, top - self._pady)
        self._canvas.yview_moveto(max(0.0, (y0 - region[1]) / max(1, region[3] - region[1])))

    def to_top(self):
        self._canvas.yview_moveto(0.0)

    def _on_wheel(self, e):
        # bind_all outlives the area: one the window rebuilt without (a
        # language change) is still called, and has nothing left to scroll
        if not self.winfo_exists():
            return
        # only scroll when the pointer is actually over this area
        x, y = self.winfo_pointerxy()
        w = self.winfo_containing(x, y)
        while w is not None:
            if w is self:
                # Windows reports multiples of 120 per notch; macOS reports
                # small signed deltas, where // 120 would floor -1 to -1 and
                # +1 to 0 and only ever scroll one way.
                step = e.delta if sys.platform == "darwin" else e.delta // 120
                self._canvas.yview_scroll(-1 * step, "units")
                return
            w = getattr(w, "master", None)


# -- drawn marks ----------------------------------------------------------------------------------
# Painters for Button(icon=...): (canvas, centre x, centre y, colour). IBM Plex has no
# glyph for these, and a box where a mark should be is worse than none.

def icon_more(c, cx, cy, fg):
    """⋯ — more things to do."""
    for dx in (-6, 0, 6):
        c.create_oval(cx + dx - 1.8, cy - 1.8, cx + dx + 1.8, cy + 1.8, fill=fg, width=0)


def icon_fullscreen(c, cx, cy, fg):
    """⛶ — four corners pulled outwards."""
    s, k = 7, 4
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = cx + sx * s, cy + sy * s
            c.create_line(x - sx * k, y, x, y, x, y - sy * k, fill=fg, width=1.6,
                          capstyle="round", joinstyle="round")


def icon_play(c, cx, cy, fg):
    """▶ — play."""
    c.create_polygon(cx - 4, cy - 6, cx - 4, cy + 6, cx + 6, cy, fill=fg, outline=fg,
                     width=1, joinstyle="round")


def icon_pause(c, cx, cy, fg):
    """❚❚ — pause."""
    for x in (cx - 4, cx + 2):
        c.create_rectangle(x, cy - 6, x + 2.6, cy + 6, fill=fg, width=0)


def icon_info(c, cx, cy, fg, r=7):
    """ⓘ — the details behind a screen."""
    c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=fg, width=1.3)
    c.create_line(cx, cy - 1, cx, cy + 3.6, fill=fg, width=1.6)
    c.create_oval(cx - 1.1, cy - 4.4, cx + 1.1, cy - 2.2, fill=fg, width=0)


class Tooltip:
    """A few words for a mark or a control, after a short hover.

    Bound with add="+", so the widget keeps its own hover look. `text` may be a
    callable, asked each time, so a tooltip can say what is true now; an empty
    answer shows nothing.
    """

    def __init__(self, widget, text, delay_ms=450):
        self.widget, self.text, self.delay = widget, text, delay_ms
        self._after = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _e=None):
        self._cancel()
        self._after = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._after:
            try:
                self.widget.after_cancel(self._after)
            except tk.TclError:
                pass
            self._after = None

    def _show(self):
        self._after = None
        text = self.text() if callable(self.text) else self.text
        if not text or not self.widget.winfo_exists():
            return
        tip = tk.Toplevel(self.widget)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tk.Label(tip, text=text, bg=T.INSET, fg=T.TEXT, font=T.font(12), padx=10, pady=5,
                 bd=0, highlightthickness=1, highlightbackground=T.BORDER,
                 justify="left", wraplength=320).pack()
        tip.update_idletasks()
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        tip.geometry(f"+{x}+{y}")
        self._tip = tip

    def _hide(self, _e=None):
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None


class TextLink(tk.Label):
    """Quiet words that do something: "All", "+ Add by address", "Show in folder"."""

    def __init__(self, parent, text, command=None, fg=None, hover=None, size=12.5, bg=None):
        bg = bg or parent.cget("bg")
        self._fg, self._hover = fg or T.TEXT_MUTED, hover or T.ACCENT
        super().__init__(parent, text=text, bg=bg, fg=self._fg, font=T.font(size, 500),
                         cursor="hand2", padx=2)
        self.command = command
        self.bind("<Button-1>", lambda e: self.command and self.command())
        self.bind("<Enter>", lambda e: self.configure(fg=self._hover))
        self.bind("<Leave>", lambda e: self.configure(fg=self._fg))


class DetailsToggle(tk.Canvas):
    """ⓘ Details: the numbers behind a screen, for whoever is debugging it.
    Off is quiet grey; on is the accent, so it is plain that more is showing."""

    H = 32

    def __init__(self, parent, on_change=None, value=False, bg=None):
        bg = bg or parent.cget("bg")
        super().__init__(parent, height=self.H, width=1, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.on_change, self.value, self._hot = on_change, value, False
        self._font = T.font(12.5, 500)
        self.bind("<Button-1>", lambda e: self.set(not self.value, notify=True))
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))
        self._render()

    def _hover(self, hot):
        self._hot = hot
        self._render()

    def set(self, value: bool, notify: bool = False):
        self.value = value
        self._render()
        if notify and self.on_change:
            self.on_change(value)

    def _render(self):
        self.delete("all")
        text = tr("Details")
        w = 12 + 16 + 7 + self._font.measure(text) + 12
        self.configure(width=w)
        on = self.value
        fg = T.ACCENT if (on or self._hot) else T.TEXT_MUTED
        draw_round(self, 0, 0, w - 1, self.H - 1, self.H / 2,
                   T.ACCENT_FILL if on else (T.INSET if self._hot else T.SURFACE),
                   T.ACCENT if on else T.BORDER)
        icon_info(self, 12 + 8, self.H / 2, fg)
        self.create_text(12 + 16 + 7, self.H / 2, text=text, anchor="w", fill=fg,
                         font=self._font)


class HoldButton(tk.Canvas):
    """The pad: press and hold to drive the glove, let go to release it, the way a
    hand meets an object. Space does the same while the screen has it.

    `latched` turns it into a switch for longer runs: a click turns it on and the
    next turns it off. `release()` lets go from outside (leaving the screen,
    Escape, the window losing focus), so nothing stays pressed by accident.
    """

    def __init__(self, parent, text, on_press, on_release, height=68, bg=None):
        bg = bg or parent.cget("bg")
        super().__init__(parent, width=1, height=height, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.text, self.on_press, self.on_release, self.h = text, on_press, on_release, height
        self.held = self.latched = self.disabled = False
        self.sub = ""
        self._hot = False
        self._key_release = None
        self.bind("<ButtonPress-1>", lambda e: self.down())
        self.bind("<ButtonRelease-1>", lambda e: self.up())
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))
        self.bind("<Configure>", lambda e: self.render())

    def _hover(self, hot):
        self._hot = hot
        self.render()

    def down(self):
        if self.disabled:
            return
        if self.latched:
            self._release() if self.held else self._press()
        elif not self.held:
            self._press()

    def up(self):
        if not self.latched and self.held:
            self._release()

    # Windows repeats a held key's press; X11 repeats press and release. Ignoring a
    # press while held, and waiting a moment before acting on a release, covers both.
    def key_down(self):
        if self._key_release:
            self.after_cancel(self._key_release)
            self._key_release = None
            return
        if not self.held or self.latched:
            self.down()

    def key_up(self):
        if self.latched:
            return
        if self._key_release:
            self.after_cancel(self._key_release)
        self._key_release = self.after(40, self._key_up_now)

    def _key_up_now(self):
        self._key_release = None
        self.up()

    def release(self, send: bool = True):
        """Let go now. `send=False` when the glove has been vented some other way."""
        if self.held:
            self.held = False
            self.render()
            if send:
                self.on_release()

    def _press(self):
        self.held = True
        self.render()
        self.on_press()

    def _release(self):
        self.held = False
        self.render()
        self.on_release()

    def set(self, text=None, sub=None, disabled=None, latched=None):
        if text is not None:
            self.text = text
        if sub is not None:
            self.sub = sub
        if disabled is not None:
            self.disabled = disabled
            self.configure(cursor="arrow" if disabled else "hand2")
            if disabled:
                self.release()
        if latched is not None and latched != self.latched:
            self.latched = latched
            if not latched:
                self.release()
        self.render()

    def render(self):
        self.delete("all")
        w = self.winfo_width()
        if w <= 1:
            return
        if self.disabled:
            fill, edge, fg = T.INSET, T.BORDER, T.TEXT_OFF
        elif self.held:
            fill, edge, fg = T.ACCENT, T.ACCENT, T.CANVAS
        else:
            fill = T.ACCENT_EDGE if self._hot else T.ACCENT_FILL
            edge, fg = T.ACCENT, T.ACCENT
        draw_round(self, 0, 0, w - 1, self.h - 1, 12, fill, edge)
        if self.sub:
            self.create_text(w / 2, self.h / 2 - 9, text=self.text, fill=fg, font=T.font(17, 600))
            self.create_text(w / 2, self.h / 2 + 13, text=self.sub, fill=fg, font=T.font(11.5))
        else:
            self.create_text(w / 2, self.h / 2, text=self.text, fill=fg, font=T.font(17, 600))


class StatusChip(tk.Canvas):
    """A dot and a word: "● Left glove", "● Live". Clickable when it has a command."""

    H = 32

    def __init__(self, parent, text="", dot=None, command=None, bg=None):
        bg = bg or parent.cget("bg")
        super().__init__(parent, width=1, height=self.H, bg=bg, highlightthickness=0, bd=0)
        self.text, self.dot, self.command, self._hot = text, dot, command, False
        self._font = T.font(12.5, 500)
        self.bind("<Button-1>", lambda e: self.command and self.command(e))
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))
        self._render()

    def _hover(self, hot):
        self._hot = hot and self.command is not None
        self._render()

    def set(self, text=None, dot=None):
        if (text, dot) == (self.text, self.dot):
            return
        if text is not None:
            self.text = text
        self.dot = dot
        self._render()

    def _render(self):
        self.delete("all")
        w = 12 + 8 + 8 + self._font.measure(self.text) + 14
        self.configure(width=w, cursor="hand2" if self.command else "arrow")
        draw_round(self, 0, 0, w - 1, self.H - 1, self.H / 2,
                   T.INSET if self._hot else T.RAISED, T.ACCENT if self._hot else T.BORDER)
        c = self.dot or T.DOT_OFF
        self.create_oval(12, self.H / 2 - 4, 20, self.H / 2 + 4, fill=c, outline=c)
        self.create_text(28, self.H / 2, text=self.text, anchor="w",
                         fill=T.TEXT if self.dot else T.TEXT_MUTED, font=self._font)


class Segmented(tk.Canvas):
    """Two or three choices side by side, one lit: Pressure | Vibration."""

    H = 36

    def __init__(self, parent, options, value=None, command=None, bg=None, min_width=0):
        bg = bg or parent.cget("bg")
        super().__init__(parent, width=1, height=self.H, bg=bg, highlightthickness=0, bd=0,
                         cursor="hand2")
        self.options, self.command = list(options), command
        self.value = value if value is not None else self.options[0][0]
        self.min_width = min_width
        self._font = T.font(13, 600)
        self._hot = None
        self.bind("<Button-1>", self._click)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda e: self._set_hot(None))
        self.bind("<Configure>", lambda e: self.render())

    def _seg_w(self):
        return max(self._font.measure(label) for _k, label in self.options) + 32

    def _index_at(self, x):
        w = self.winfo_width()
        return min(len(self.options) - 1, max(0, int(x / max(1, w / len(self.options)))))

    def _click(self, e):
        key = self.options[self._index_at(e.x)][0]
        if key != self.value:
            self.value = key
            self.render()
            if self.command:
                self.command(key)

    def _motion(self, e):
        self._set_hot(self._index_at(e.x))

    def _set_hot(self, i):
        if i != self._hot:
            self._hot = i
            self.render()

    def set(self, value):
        if value != self.value:
            self.value = value
            self.render()

    def render(self):
        self.delete("all")
        want = max(self.min_width, self._seg_w() * len(self.options))
        if int(self.cget("width")) != want:
            self.configure(width=want)
        w = max(self.winfo_width(), 2)
        if w <= 2:
            w = want
        draw_round(self, 0, 0, w - 1, self.H - 1, T.R_CTRL, T.INSET, T.BORDER)
        seg = w / len(self.options)
        for i, (key, label) in enumerate(self.options):
            on = key == self.value
            x0 = i * seg
            if on:
                draw_round(self, x0 + 3, 3, x0 + seg - 4, self.H - 4, T.R_CTRL - 1,
                           T.ACCENT_FILL, T.ACCENT)
            fg = T.ACCENT if on else (T.TEXT if self._hot == i else T.TEXT_MUTED)
            self.create_text(x0 + seg / 2, self.H / 2, text=label, fill=fg, font=self._font)


class SignalBars(tk.Canvas):
    """How strong a glove's radio is, as four bars rather than dBm."""

    def __init__(self, parent, bg=None):
        bg = bg or parent.cget("bg")
        super().__init__(parent, width=20, height=14, bg=bg, highlightthickness=0, bd=0)
        self._lit = -1
        self.set(None)

    @staticmethod
    def bars(rssi) -> int:
        if rssi is None:
            return 0
        return 4 if rssi >= -60 else 3 if rssi >= -70 else 2 if rssi >= -80 else 1

    def set(self, rssi):
        lit = self.bars(rssi)
        if lit == self._lit:
            return
        self._lit = lit
        self.delete("all")
        for i in range(4):
            h = 4 + i * 3
            x = i * 5
            c = T.SUCCESS if i < lit else T.BORDER
            self.create_rectangle(x, 14 - h, x + 3, 14, fill=c, width=0)
