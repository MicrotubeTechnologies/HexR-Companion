"""The Headsets screen: the HEXR headsets on this network.

At an event a facilitator would otherwise have to take a headset off someone to connect
their gloves, and could not see what they were seeing. This lists every headset running
a HEXR app with HexR Remote; opening one puts what the wearer sees first, with its two
gloves beside it, lit as they fire (click one to connect or disconnect it), then one row to
watch, record and go full screen. A recording is exported, in the shape wanted, from the
Recordings screen. The numbers behind it (versions, addresses, pressures) are under Details.

The same thing as the phone's Headsets tab, over the same protocol (see hexr/remote.py).
"""

from __future__ import annotations

import os
import time
import tkinter as tk

from .. import recorder as REC
from .. import glovenames
from .. import remote as R
from .. import settings
from .. import speaker as SPK
from .. import theme as T
from ..haptics import HapticsTimeline
from ..headsets import Headsets, HeadsetRow
from ..i18n import N_, language, tr
from ..viewer import LANDSCAPE, Compositor, GloveBadge, boxes, frame_size, hit
from ..widgets import (Button, Divider, Dot, SignalBars, StatusChip, Surface, TextLink, Tooltip,
                       icon_fullscreen, icon_more)
from .base import Screen, section_label
from .fullview import PUMP_MS, FullView

# headset | app | state | action
COLS = (None, 220, 120, 100)

VIEW_MIN, VIEW_MAX = 480, 1280   # the picture's width: grows with the window
LIST_EVERY = 4            # ticks between list refreshes: 20 Hz / 4 = 5 Hz, what a headset sends
DOTS_EVERY = 8            # ticks per step of the searching dots: 20 Hz / 8 = 0.4 s
SAVED_SHOWN_S = 15.0      # how long "Open in Recordings" stays after a recording is saved
VIDEO_RETRY_S = 3.0       # a view that dropped while the headset still shares it: join again


def _menu(parent) -> tk.Menu:
    return tk.Menu(parent, tearoff=0, bg=T.RAISED, fg=T.TEXT, activebackground=T.ACCENT,
                   activeforeground=T.CANVAS, selectcolor=T.ACCENT, bd=0, relief="flat",
                   font=T.font(12.5))


def _popup(menu: tk.Menu, widget):
    _popup_at(menu, widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())


def _popup_at(menu: tk.Menu, x: int, y: int):
    try:
        menu.tk_popup(x, y)
    finally:
        menu.grab_release()


class HeadsetsScreen(Screen):
    title_text = N_("Headsets")
    key = "headsets"
    has_details = True

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.model: Headsets = app.headsets
        self._rows: dict[str, tk.Frame] = {}
        self._selected: str | None = None
        self._detail: _Detail | None = None
        self._ticks = 0
        self._dots = 0

        self.results = Surface(self.body)
        self.results.pack(fill="x")
        self._build_header()
        self.empty = tk.Frame(self.results, bg=T.RAISED)
        self.searching = tk.Label(self.empty, text=tr("Searching for headsets") + " " * 3,
                                  bg=T.RAISED, fg=T.TEXT, font=T.font(14, 500), anchor="w")
        self.searching.pack(fill="x")
        self.searching_sub = tk.Label(self.empty, text=tr("Same Wi-Fi as this computer."),
                                      bg=T.RAISED, fg=T.TEXT_FAINT, font=T.font(12.5), anchor="w")
        self.searching_sub.pack(fill="x", pady=(4, 0))
        self.empty.pack(fill="x", padx=18, pady=18)

        add = tk.Frame(self.body, bg=T.SURFACE)
        add.pack(fill="x", pady=(8, 0))
        self.add_link = TextLink(add, "+ " + tr("Add by address"), command=self._open_add,
                                 fg=T.TEXT_FAINT, size=12)
        self.add_link.pack(side="right")
        self.add_box = tk.Frame(add, bg=T.SURFACE)
        self.address = _entry(self.add_box, width=18)
        self.address.pack(side="left", ipady=4)
        self.address.bind("<Return>", lambda e: self._add())
        self.address.bind("<Escape>", lambda e: self._close_add())
        Button(self.add_box, tr("Add"), command=self._add, height=30, fill=T.INSET, fg=T.TEXT,
               border=T.BORDER, hover_fill=T.ACCENT, hover_fg=T.CANVAS, hover_border=T.ACCENT,
               min_width=70).pack(side="left", padx=(8, 0))

        self.detail_host = tk.Frame(self.body, bg=T.SURFACE)
        self.detail_host.pack(fill="x", pady=(18, 0))
        # A headset just opened grows for a moment (its picture is fitted once it is shown):
        # the view follows it to the top until then.
        self._follow_until = 0.0
        self.detail_host.bind("<Configure>", self._detail_resized, add="+")

    # -- list --------------------------------------------------------------------------------

    def _build_header(self):
        head = tk.Frame(self.results, bg=T.RAISED)
        head.pack(fill="x", padx=18, pady=(14, 0))
        for i, (label, width) in enumerate(
                zip((tr("Headset"), tr("App"), tr("State"), ""), COLS)):
            section_label(head, label, bg=T.RAISED).grid(row=0, column=i, sticky="w",
                                                         padx=(0, 10))
            if width:
                head.grid_columnconfigure(i, minsize=width)
            else:
                head.grid_columnconfigure(i, weight=1)
        Divider(self.results).pack(fill="x", pady=(10, 0))

    def _sync_list(self, rows: list[HeadsetRow]):
        keys = [r.key for r in rows]
        if keys != list(self._rows):
            for row in self._rows.values():
                row.destroy()
            self._rows.clear()
            for r in rows:
                self._rows[r.key] = self._build_row(r)
        if rows:
            self.empty.pack_forget()
        elif not self.empty.winfo_manager():
            self.empty.pack(fill="x", padx=18, pady=18)
        for r in rows:
            self._update_row(self._rows[r.key], r)

    def _build_row(self, r: HeadsetRow) -> tk.Frame:
        row = tk.Frame(self.results, bg=T.RAISED, cursor="hand2")
        row.pack(fill="x", padx=18, pady=(0, 2))
        name = tk.Frame(row, bg=T.RAISED)
        name.grid(row=0, column=0, sticky="w", pady=10)
        row.dot = Dot(name, color=T.DOT_OFF, bg=T.RAISED)
        row.dot.pack(side="left", pady=(4, 0))
        row.title = tk.Label(name, text="", bg=T.RAISED, fg=T.TEXT, font=T.font(13.5, 500))
        row.title.pack(side="left", padx=(8, 0))
        row.app = tk.Label(row, text="", bg=T.RAISED, fg=T.TEXT_2, font=T.font(12.5), anchor="w")
        row.app.grid(row=0, column=1, sticky="w", padx=(0, 10))
        row.state = tk.Label(row, text="", bg=T.RAISED, fg=T.TEXT_MUTED, font=T.font(12.5),
                             anchor="w")
        row.state.grid(row=0, column=2, sticky="w", padx=(0, 10))
        row.open = Button(row, tr("Open"), command=lambda k=r.key: self._select(k), height=30,
                          fill=T.INSET, fg=T.TEXT, border=T.BORDER, hover_fill=T.ACCENT,
                          hover_fg=T.CANVAS, hover_border=T.ACCENT, min_width=90)
        row.open.grid(row=0, column=3, sticky="e")
        row.grid_columnconfigure(0, weight=1)
        for i, width in enumerate(COLS):
            if width:
                row.grid_columnconfigure(i, minsize=width)
        # The whole row opens it, not only the button.
        for w in (row, name, row.dot, row.title, row.app, row.state):
            w.bind("<Button-1>", lambda e, k=r.key: self._select(k))
        return row

    def _update_row(self, row: tk.Frame, r: HeadsetRow):
        colour, word = _link_look(r)
        selected = r.key == self._selected
        row.dot.set(colour)
        row.title.configure(text=r.title, fg=T.ACCENT if selected else T.TEXT)
        row.app.configure(text=r.status.app if r.status else (r.announce.app if r.announce else ""))
        row.state.configure(text=word, fg=colour if colour != T.DOT_OFF else T.TEXT_MUTED)
        if selected and row.open.winfo_manager():
            row.open.grid_remove()
        elif not selected and not row.open.winfo_manager():
            row.open.grid()

    def _select(self, key: str):
        if key == self._selected:
            if self._detail:
                self.scroll_to(self.detail_host)
            return
        self._selected = key
        if self._detail:
            self._detail.destroy()
        self._detail = None
        self._refresh()
        self._follow_until = time.monotonic() + 1.0
        self.after(60, lambda: self.winfo_exists() and self.scroll_to(self.detail_host))

    def _detail_resized(self, _e):
        if time.monotonic() < self._follow_until:
            self.after_idle(lambda: self.winfo_exists() and self.scroll_to(self.detail_host))

    def _open_add(self):
        self.add_link.pack_forget()
        self.add_box.pack(side="right")
        self.address.focus_set()

    def _close_add(self):
        self.add_box.pack_forget()
        self.add_link.pack(side="right")

    def _add(self):
        text = self.address.get().strip()
        if text:
            self.model.add_by_address(text)
            self.address.delete(0, "end")
            self._close_add()

    # -- ticking -----------------------------------------------------------------------------

    def on_show(self):
        # Listening starts here, not at launch: Windows asks about the firewall the first time,
        # and the question makes sense to someone who has just opened Headsets.
        self.model.start()
        self._refresh()

    def on_tick(self):
        self._ticks += 1
        if self._ticks % LIST_EVERY == 0:
            self._refresh()
        if self._ticks % DOTS_EVERY == 0 and self.empty.winfo_manager():
            self._dots = (self._dots + 1) % 4
            # The dots keep a fixed width, so the words do not shuffle as they count up.
            self.searching.configure(text=tr("Searching for headsets") +
                                     "." * self._dots + " " * (3 - self._dots))
        if self._detail:
            self._detail.pump_video()

    def show_details(self, on: bool):
        if self._detail:
            self._detail.show_details(on)

    def _refresh(self):
        rows = self.model.rows()
        if self.model.discovery_error:
            self.searching.configure(text=self.model.discovery_error, fg=T.DANGER)
            self.searching_sub.pack_forget()
        self._sync_list(rows)

        row = next((r for r in rows if r.key == self._selected), None)
        if row is None:
            if self._detail:
                self._detail.destroy()
                self._detail = None
            self._selected = None
            return
        if self._detail is None:
            self._detail = _Detail(self.detail_host, self, row.key)
            self._detail.pack(fill="x")
        self._detail.update(row)


class _Detail(tk.Frame):
    """The opened headset: its view with its gloves beside it, then watch / record / full
    screen, then release and recenter. The numbers are under Details."""

    def __init__(self, parent, screen: HeadsetsScreen, key: str):
        super().__init__(parent, bg=T.SURFACE)
        self.screen_ = screen
        self.model = screen.model
        self.app = screen.app
        self.key = key
        self.video: R.VideoReceiver | None = None
        self.sound: R.AudioReceiver | None = None
        self._photo = None
        self._title = ""
        self._nickname = ""
        self._manual = False
        self._last_row: HeadsetRow | None = None

        # -- heading: its name, and ⋯ for renaming or forgetting it
        head = tk.Frame(self, bg=T.SURFACE)
        head.pack(fill="x")
        self.title = tk.Label(head, text="", bg=T.SURFACE, fg=T.TEXT, font=T.font(18, 600),
                              anchor="w")
        self.title.pack(side="left")
        self.rename_box = _entry(head, width=20)
        self.rename_box.bind("<Return>", lambda e: self._rename_done(True))
        self.rename_box.bind("<Escape>", lambda e: self._rename_done(False))
        self.more_btn = Button(head, "", icon=icon_more, command=self._more, height=30,
                               fill=T.SURFACE, fg=T.TEXT_MUTED, border=T.SURFACE,
                               hover_fill=T.INSET, hover_fg=T.TEXT, hover_border=T.BORDER)
        self.more_btn.pack(side="left", padx=(8, 0))

        # -- the picture, always there: what the wearer sees, or what is happening instead,
        # with the two gloves beside it. The video thread draws it while there is a view; the
        # screen's tick draws it, gloves only, while there is not: two compositors, one each.
        self.timeline = self.model.haptics(key) or HapticsTimeline()
        self.compositor = Compositor(self.timeline)
        self._idle = Compositor(self.timeline)
        self.screen = tk.Label(self, bg=T.SURFACE, bd=0, cursor="hand2")
        self.screen.pack(anchor="w", pady=(12, 0))
        self.screen.bind("<ButtonPress-1>", self._picture_press)
        self.screen.bind("<Double-Button-1>", self._picture_double)
        Tooltip(self.screen, self._picture_hint)
        # What is happening instead of the view, in the middle of its square. A sibling placed
        # over the picture, not a child of it: the picture repaints over its own children.
        self.say = tk.Label(self, text="", bg=T.RAISED, fg=T.TEXT_2, font=T.font(13.5),
                            justify="center")
        self.say.bind("<ButtonPress-1>", self._picture_press)

        # -- watch, record, full screen, view options, and a word for the state
        bar = tk.Frame(self, bg=T.SURFACE)
        bar.pack(fill="x", pady=(12, 0))
        self.view_btn = Button(bar, tr("Watch"), command=self._toggle_view, glyph="▶",
                               min_width=140)
        self.view_btn.pack(side="left")
        self.rec_btn = Button(bar, tr("Record"), command=self._toggle_record, glyph="●",
                              fill=T.INSET, fg=T.TEXT, border=T.BORDER, hover_fill=T.INSET,
                              hover_fg=T.DANGER, hover_border=T.DANGER, min_width=120)
        self.rec_btn.pack(side="left", padx=(10, 0))
        self.full_btn = Button(bar, "", icon=icon_fullscreen, command=self._open_full,
                               fill=T.INSET, fg=T.TEXT, border=T.BORDER, hover_fill=T.INSET,
                               hover_fg=T.ACCENT, hover_border=T.ACCENT)
        self.full_btn.pack(side="left", padx=(10, 0))
        Tooltip(self.full_btn, tr("Full screen"))
        # The headset's sound, played on this computer while its view is watched.
        self._sound_on = bool(settings.load("settings.json").get("headsetSound", True))
        self.speaker: SPK.Speaker | None = None
        self.sound_btn = Button(bar, "", command=self._toggle_sound, fill=T.INSET, fg=T.TEXT,
                                border=T.BORDER, hover_fill=T.INSET, hover_fg=T.ACCENT,
                                hover_border=T.ACCENT, min_width=120)
        self.sound_btn.pack(side="left", padx=(10, 0))
        Tooltip(self.sound_btn, self._sound_hint)
        self._show_sound_btn()
        self.state_chip = StatusChip(bar, "")
        self.state_chip.pack(side="left", padx=(14, 0))
        self.saved_link = TextLink(bar, "✓ " + tr("Open in Recordings"),
                                   command=self._open_recording, fg=T.SUCCESS, hover=T.TEXT)
        self.notice = tk.Label(self, text="", bg=T.SURFACE, fg=T.DANGER, font=T.font(12.5),
                               anchor="w", justify="left", wraplength=720)

        # -- vent both gloves, and put the wearer back on the scene's starting spot
        actions = tk.Frame(self, bg=T.SURFACE)
        actions.pack(fill="x", pady=(14, 0))
        Button(actions, tr("Release all"), command=lambda: self.model.release(key), height=34,
               fill=T.SURFACE, fg=T.TEXT_2, border=T.BORDER, hover_fill=T.INSET,
               hover_fg=T.ACCENT, hover_border=T.ACCENT, padx=14,
               font=T.font(12.5, 600)).pack(side="left")
        # Press every channel of the connected gloves for a second: does the glove work?
        self.trigger_btn = Button(actions, tr("Trigger all"), command=self._trigger, height=34,
                                  fill=T.SURFACE, fg=T.TEXT_2, border=T.BORDER,
                                  hover_fill=T.INSET, hover_fg=T.ACCENT, hover_border=T.ACCENT,
                                  padx=14, font=T.font(12.5, 600))
        self.trigger_btn.pack(side="left", padx=(10, 0))
        Tooltip(self.trigger_btn, self._trigger_hint)
        self._triggered_at = 0.0
        self.recenter_btn = Button(actions, tr("Recenter"), command=self._recenter, height=34,
                                   fill=T.INSET, fg=T.TEXT, border=T.BORDER,
                                   hover_fill=T.ACCENT, hover_fg=T.CANVAS,
                                   hover_border=T.ACCENT, min_width=110)
        self.recenter_btn.pack(side="left", padx=(10, 0))
        Tooltip(self.recenter_btn, lambda: "" if self._can_recenter() else
                tr("Needs HexR 0.10.6 with Allow Recenter."))
        self._recentered_at = 0.0

        # -- which glove each hand connects to, and finding the right one among several
        self.gloves = _GloveFinder(self, self)
        self.gloves.pack(fill="x", pady=(18, 0))

        # -- Details: the numbers
        self.numbers = tk.Label(self, text="", bg=T.SURFACE, fg=T.TEXT_FAINT, font=T.mono(11),
                                anchor="w", justify="left")

        self._view_wanted = False
        self._aspect = 1.0
        self._video_retry_at = 0.0
        self._sound_retry_at = 0.0
        self._last_stream = R.StreamState()
        self._unavailable = R.video_available()
        self._fit = self._inline_fit()
        self.full: FullView | None = None
        self.recorder: REC.Recorder | None = None
        self._saving: REC.Recorder | None = None
        self._saved: REC.Recorder | None = None
        self._saved_at = 0.0
        self._last_r: HeadsetRow | None = None
        self.show_details(screen.details)

    # -- updates from the screen's tick -------------------------------------------------------

    def update(self, r: HeadsetRow):
        self._last_r = r
        s = r.status
        self._title = r.title
        self._nickname = r.nickname
        self._manual = r.manual
        if not self.rename_box.winfo_manager():
            self.title.configure(text=r.title)

        # What the gloves' panels say. A new tuple, never a changed one: the video and the
        # recording threads read it.
        badges = tuple((h, GloveBadge(g.state, g.battery_pct)) for h in R.HANDS
                       if s and (g := s.gloves.get(h)))
        if badges != self.compositor.badges:
            self.compositor.badges = self._idle.badges = badges

        can_trigger = bool(s and r.link == "connected" and not s.paused and s.allow_glove_control
                           and s.glove_search is not None
                           and any(g.connected for g in s.gloves.values()))
        pressing = time.monotonic() - self._triggered_at < 1.2 and not r.error
        self.trigger_btn.set(disabled=not can_trigger, glyph="✓" if pressing else "",
                             fg=T.SUCCESS if pressing else T.TEXT_2)

        usable = bool(s and r.link == "connected" and self._can_recenter() and not s.paused)
        just = time.monotonic() - self._recentered_at < 3.0 and not r.error
        self.recenter_btn.set(disabled=not usable, glyph="✓" if just else "",
                              fg=T.SUCCESS if just else T.TEXT)

        if r.error:
            self.notice.configure(text=r.error)
            if not self.notice.winfo_manager():
                self.notice.pack(fill="x", pady=(8, 0), after=self.rec_btn.master)
        elif self.notice.winfo_manager() and not self._notice_recording():
            self.notice.pack_forget()

        self.gloves.refresh(r)
        self._update_view(r)
        if self.screen_.details:
            self.numbers.configure(text=self._numbers(r))

    def _numbers(self, r: HeadsetRow) -> str:
        s = r.status
        lines = []
        bits = []
        if s:
            bits += [f"{s.app} {s.app_version}".strip(), f"HexR {s.hexr_version}"]
            if s.headset_battery_pct >= 0:
                bits.append(tr("headset {pct}%", pct=s.headset_battery_pct))
            if s.controllers > 1:
                bits.append(tr("{n} controllers", n=s.controllers))
        bits.append(r.host)
        lines.append("   ·   ".join(b for b in bits if b))
        for hand in R.HANDS:
            g = s.gloves.get(hand) if s else None
            if not g:
                continue
            line = [tr(hand.capitalize())]
            if g.battery_pct >= 0:
                line.append(tr("battery {level}", level=f"{g.battery_pct}%"))
            if g.connected and len(g.pressure_kpa) >= 7:
                line.append("kPa " + " ".join(f"{p:.0f}" for p in g.pressure_kpa[:6]) +
                            f"  src {g.pressure_kpa[6]:.0f}")
            if g.message:
                line.append(g.message)
            lines.append("   ·   ".join(line))
        st = s.stream if s else R.StreamState()
        if st.state == "live":
            lines.append(tr("Shared · {w}×{h}", w=st.width, h=st.height) +
                         (tr(" · {n} watching", n=st.viewers) if st.viewers else ""))
        if st.message:
            lines.append(st.message)
        if st.state == "live":
            a = st.audio
            if a.state == "live":
                lines.append(tr("Sound shared") if not (self.sound and self.sound.message)
                             else self.sound.message)
            elif a.message:
                lines.append(a.message)
            elif a.state == "off":
                lines.append(tr("This app sends no sound. Update it to HexR 0.10.5 or newer to "
                                "record its sound."))
        if self.video and self.video.state == "playing" and not self.timeline.exact:
            lines.append(tr("The glove shows the pressure the gloves measure. Update this app to "
                            "HexR 0.10.2 or newer to show every touch and vibration as it is sent."))
        if self.video and self.video.render_error:
            lines.append(tr("The glove could not be drawn: {error}", error=self.video.render_error))
        if self._saved and not self._saved.error:
            text = tr("Saved {name}", name=os.path.basename(self._saved.path))
            if self._saved.dropped:
                text += tr(" · {n} frames dropped", n=self._saved.dropped)
            lines.append(text)
        return "\n".join(lines)

    def show_details(self, on: bool):
        if on:
            self.numbers.pack(fill="x", pady=(14, 0))
            if self._last_r:
                self.numbers.configure(text=self._numbers(self._last_r))
        else:
            self.numbers.pack_forget()

    # -- the gloves ---------------------------------------------------------------------------

    def _glove_clicked(self, hand: str, e=None):
        s = self._last_r.status if self._last_r else None
        g = s.gloves.get(hand) if s else None
        if not s or not g or g.state == "missing" or not s.allow_glove_control or s.paused:
            return
        if g.connected:
            # A menu rather than straight away: a click that ends someone's demo should not
            # be one slip of the mouse.
            m = _menu(self)
            m.add_command(label=tr("Disconnect"),
                          command=lambda: self.model.disconnect_glove(self.key, hand))
            _popup_at(m, e.x_root, e.y_root)
        elif g.state != "connecting":
            self.model.connect_glove(self.key, hand)

    def _glove_hint(self, hand: str) -> str:
        s = self._last_r.status if self._last_r else None
        g = s.gloves.get(hand) if s else None
        if not g:
            return ""
        if g.state == "missing":
            return tr("No glove handler in this app")
        hint = _this_computer_holds(self.app, g)
        word = {"connected": tr("Connected"), "connecting": tr("Connecting…"),
                "disconnected": tr("Not connected")}.get(g.state, g.state)
        click = tr("Click to disconnect") if g.connected else \
            tr("Click to connect") if g.state == "disconnected" else ""
        return "\n".join(filter(None, [word, g.message if g.message != word else "", hint,
                                        click]))

    # -- the heading's ⋯ -----------------------------------------------------------------------

    def _more(self):
        m = _menu(self)
        m.add_command(label=tr("Rename"), command=self._rename)
        if self._manual:
            m.add_command(label=tr("Forget"), command=self._forget)
        _popup(m, self.more_btn)

    def _rename(self):
        self.title.pack_forget()
        self.rename_box.delete(0, "end")
        self.rename_box.insert(0, self._nickname or self._title)
        self.rename_box.pack(side="left", before=self.more_btn, ipady=4)
        self.rename_box.focus_set()
        self.rename_box.select_range(0, "end")

    def _rename_done(self, save: bool):
        if save:
            self.model.rename(self.key, self.rename_box.get())
        self.rename_box.pack_forget()
        self.title.pack(side="left", before=self.more_btn)
        self.focus_set()

    def _forget(self):
        self._stop_video()
        self.model.forget(self.key)

    # -- scene and recenter ---------------------------------------------------------------------

    def _can_recenter(self) -> bool:
        s = self._last_r.status if self._last_r else None
        return bool(s and s.allow_recenter)

    def _trigger(self):
        self._triggered_at = time.monotonic()
        self.model.trigger(self.key)

    def _trigger_hint(self) -> str:
        s = self._last_r.status if self._last_r else None
        if s and s.glove_search is None:
            return tr("Needs HexR 0.10.6.")
        return tr("Presses every finger and the palm for a second, to check the gloves work.")

    def _recenter(self):
        self._recentered_at = time.monotonic()
        self.model.recenter(self.key)

    # -- view -----------------------------------------------------------------------------------

    def _toggle_view(self):
        if self._unavailable:
            return
        if self._view_wanted:
            self._view_wanted = False
            # Ending the share closes every viewer's connection, so only end it if nobody else
            # (a phone, another computer) is watching too; otherwise just leave.
            others = self._last_stream.viewers - (1 if self.video else 0)
            self._stop_video()
            if others <= 0:
                self.model.stop_view(self.key)
        else:
            self._view_wanted = True
            self.model.start_view(self.key)

    def _where(self, e) -> str | None:
        """What a click is on: the view, a glove's panel, or neither."""
        if self._photo is None:
            return None
        x = e.x_root - self.screen.winfo_rootx()
        y = e.y_root - self.screen.winfo_rooty()
        return hit((self._photo.width(), self._photo.height()), LANDSCAPE, x, y, self._aspect)

    def _picture_press(self, e):
        where = self._where(e)
        if where in R.HANDS:
            self._glove_clicked(where, e)
        elif where == "view" and not self._view_wanted and not self._unavailable \
                and not (self.video and self.video.state == "playing"):
            self._toggle_view()

    def _picture_double(self, e):
        if self._where(e) == "view":
            self._open_full()

    def _picture_hint(self) -> str:
        if self._photo is None:
            return ""
        x = self.screen.winfo_pointerx() - self.screen.winfo_rootx()
        y = self.screen.winfo_pointery() - self.screen.winfo_rooty()
        where = hit((self._photo.width(), self._photo.height()), LANDSCAPE, x, y, self._aspect)
        if where in R.HANDS:
            return self._glove_hint(where)
        if where == "view" and self.video and self.video.state == "playing":
            return tr("Double-click for full screen")
        return ""

    def _update_view(self, r: HeadsetRow):
        s = r.status
        st = s.stream if s else R.StreamState()
        self._last_stream = st
        if st.width > 0 and st.height > 0:
            # The view's shape, for the picture before its first frame and for a click on it.
            self._aspect = self.compositor.aspect = self._idle.aspect = st.width / st.height
        live = st.state == "live" and st.port > 0
        allowed = bool(s and s.allow_video) and not self._unavailable
        if live and self._view_wanted and self.video is None:
            self.video = R.VideoReceiver(r.host, st.port, self._render)
        elif live and self._view_wanted and self.video.state in ("failed", "ended")                 and time.monotonic() - self._video_retry_at > VIDEO_RETRY_S:
            # The view dropped but the headset is still sharing it: join again, a recording
            # going on carrying over to the new connection.
            self._video_retry_at = time.monotonic()
            old = self.video
            self.video = R.VideoReceiver(r.host, st.port, self._render)
            self.video.taps = old.taps
            old.stop()
        if not live and self.video is not None and st.state != "requesting":
            self._stop_video()
        self._update_sound(r, st.audio)
        self._update_recording()

        playing = bool(self.video and self.video.state == "playing")
        if not self.full:
            self._fit = self._inline_fit()
        if self._view_wanted or self.video:
            self.view_btn.set(text=tr("Stop watching"), glyph="■", disabled=False,
                              fill=T.INSET, fg=T.DANGER, border=T.DANGER,
                              hover_fill=T.INSET, hover_fg=T.DANGER, hover_border=T.DANGER)
        else:
            self.view_btn.set(text=tr("Watch"), glyph="▶",
                              disabled=not allowed or bool(s and s.paused and not live),
                              fill=T.ACCENT, fg=T.CANVAS, border=T.ACCENT,
                              hover_fill=T.ACCENT_HOVER, hover_fg=T.CANVAS,
                              hover_border=T.ACCENT_HOVER)
        if self.full_btn.disabled == playing:
            self.full_btn.set(disabled=not playing)
        if st.state == "denied" and self._view_wanted:
            self._view_wanted = False

        # One word for the state beside the buttons, and the sentence in the picture.
        if r.link != "connected":
            word, dot, say = tr("Offline"), T.DANGER, tr("Reconnecting…")
        elif s and s.paused and not live:
            word, dot, say = tr("Asleep"), T.ACCENT, tr("Asleep. Put the headset on.")
        elif self._unavailable:
            word, dot, say = tr("No view"), None, self._unavailable
        elif s and not s.allow_video:
            word, dot, say = tr("No view"), None, tr("This app does not share its view.")
        elif self.video and self.video.state == "failed":
            word, dot, say = tr("Failed"), T.DANGER, self.video.message
        elif playing:
            word, dot, say = tr("Live"), T.SUCCESS, ""
        elif self.video:
            word, dot, say = tr("Live"), T.SUCCESS, tr("Connecting to the view…")
        else:
            word, dot, say = {
                "requesting": (tr("Waiting"), T.ACCENT, tr("Waiting for the wearer…")),
                "denied": (tr("Declined"), T.DANGER, tr("The wearer said no.")),
                "unsupported": (tr("No view"), None, tr("This headset cannot share its view.")),
                "error": (tr("Failed"), T.DANGER, tr("Sharing failed.")),
            }.get(st.state, (tr("Off"), None, tr("Watch asks the wearer to share.")))
        self.state_chip.set(word, dot)
        self._say("" if playing else say)

    def _say(self, text: str):
        """The sentence in the view's square while there is no view; empty hides it."""
        if not text:
            if self.say.winfo_manager():
                self.say.place_forget()
            return
        x0, y0, x1, y1 = boxes(frame_size(self._fit, LANDSCAPE), LANDSCAPE, self._aspect).view
        self.say.configure(text=text, wraplength=int((x1 - x0) * .8))
        self.say.place(in_=self.screen, x=(x0 + x1) // 2, y=(y0 + y1) // 2, anchor="center")
        self.say.lift(self.screen)

    def _update_sound(self, r: HeadsetRow, a: R.AudioState):
        """The app's sound, beside the view while there is one, for a recording to take."""
        if self.video is None or a.state != "live" or a.port <= 0:
            self._stop_sound()
            return
        if self.sound is None:
            self.sound = R.AudioReceiver(r.host, a.port)
            self._attach_speaker()
        elif self.sound.state in ("failed", "ended") and \
                time.monotonic() - self._sound_retry_at > VIDEO_RETRY_S:
            # As with the view: join again, a recording going on carrying over.
            self._sound_retry_at = time.monotonic()
            old = self.sound
            self.sound = R.AudioReceiver(r.host, a.port)
            self.sound.taps = old.taps
            old.stop()

    def _stop_sound(self):
        if self.sound:
            self.sound.stop()
            self.sound = None
        if self.speaker:
            self.speaker.close()
            self.speaker = None

    def _attach_speaker(self):
        """Plays the sound here too, when it is on and there is sound coming in."""
        if not self._sound_on or self.sound is None or self.speaker is not None \
                or SPK.available() is not None:
            return
        self.speaker = SPK.Speaker()
        self.sound.taps.append(self.speaker.tap)

    def _toggle_sound(self):
        self._sound_on = not self._sound_on
        data = settings.load("settings.json")
        data["headsetSound"] = self._sound_on
        settings.save("settings.json", data)
        if self._sound_on:
            self._attach_speaker()
        elif self.speaker:
            if self.sound and self.speaker.tap in self.sound.taps:
                self.sound.taps.remove(self.speaker.tap)
            self.speaker.close()
            self.speaker = None
        self._show_sound_btn()

    def _show_sound_btn(self):
        self.sound_btn.set(text=tr("Sound on") if self._sound_on else tr("Sound off"),
                           glyph="♪" if self._sound_on else "×")

    def _sound_hint(self) -> str:
        why = SPK.available()
        if why:
            return tr("This computer cannot play sound: {error}", error=why)
        if self.speaker and self.speaker.error:
            return tr("This computer cannot play sound: {error}", error=self.speaker.error)
        return tr("The headset's sound, played here while you watch. It needs the app's "
                  "Share Sound on.")

    # -- drawing the view -------------------------------------------------------------------------

    def _render(self, frame, pts_us: int, arrived: float):
        """The video thread: one frame as it is shown, the gloves beside it."""
        return self.compositor.compose(frame, pts_us, arrived, self._fit)

    def _inline_fit(self) -> tuple[int, int]:
        """The picture's room in the window: as wide as the column, as tall as leaves the rows
        under it on screen once it is scrolled into view."""
        room = self.winfo_width() - 8 if self.winfo_ismapped() else VIEW_MIN
        view_h = self.screen_._area._canvas.winfo_height()
        tall = max(270, min(720, view_h - 230)) if view_h > 1 else 405
        return int(max(VIEW_MIN, min(room, VIEW_MAX))), tall

    def pump_video(self):
        """Every tick: the newest frame, or while there is none, the gloves as they are now."""
        if self.full:
            return
        if self.video and self.video.state == "playing":
            image = self.video.latest()
        else:
            image = self._idle.idle(self._fit, time.monotonic())
        if image is not None:
            self._show(image)

    def _show(self, image):
        from PIL import ImageTk
        if self._photo is None or (self._photo.width(), self._photo.height()) != image.size:
            self._photo = ImageTk.PhotoImage(image, master=self)
            self.screen.configure(image=self._photo)
        else:
            self._photo.paste(image)

    # -- full screen ------------------------------------------------------------------------------

    def _open_full(self):
        if self.full or not (self.video and self.video.state == "playing"):
            return
        self.full = FullView(self, on_close=self._full_closed, on_record=self._toggle_record)
        self._fit = self.full.size
        self._pump_full()

    def _full_closed(self):
        self.full = None
        self._fit = self._inline_fit()

    def _pump_full(self):
        if not self.full:
            return
        if self.video:
            image = self.video.latest()
            if image is not None:
                self.full.show(image)
        rec = self.recorder
        self.full.set_recording(tr("REC {time}", time=_clock(rec.seconds)) if rec else "")
        try:
            self.after(PUMP_MS, self._pump_full)
        except tk.TclError:
            pass

    # -- recording --------------------------------------------------------------------------------

    def _toggle_record(self):
        if self.recorder:
            self._stop_record()
            return
        if not (self.video and self.video.state == "playing"):
            return
        try:
            path = REC.recording_path(self._title or "Headset")
        except OSError as e:
            self._saved = None
            self.notice.configure(text=tr("Recording failed: {error}", error=e))
            self.notice.pack(fill="x", pady=(8, 0), after=self.rec_btn.master)
            return
        a = self._last_stream.audio
        hears = bool(self.sound and self.sound.state in ("connecting", "playing") and
                     a.sample_rate > 0)
        rec = REC.Recorder(path, self.timeline, lambda: self.compositor.badges,
                           title=self._title,
                           sound=(a.sample_rate, max(1, a.channels)) if hears else None)
        self.recorder = rec
        self._saved = None
        self.saved_link.pack_forget()
        rec.start()
        self.video.taps.append(rec.tap)
        if hears:
            self.sound.taps.append(rec.tap_sound)
        self._update_recording()

    def _stop_record(self):
        rec, self.recorder = self.recorder, None
        if rec is None:
            return
        if self.video and rec.tap in self.video.taps:
            self.video.taps.remove(rec.tap)
        if self.sound and rec.tap_sound in self.sound.taps:
            self.sound.taps.remove(rec.tap_sound)
        rec.stop()
        self._saving = rec
        self._update_recording()

    def _notice_recording(self) -> bool:
        return bool(self._saved and self._saved.error)

    def _update_recording(self):
        rec = self.recorder
        if self._saving and self._saving.done:
            self._saved, self._saving = self._saving, None
            self._saved_at = time.monotonic()
        if rec:
            self.rec_btn.set(text=_clock(rec.seconds), glyph="■", disabled=False, fill=T.INSET,
                             fg=T.DANGER, border=T.DANGER, hover_fg=T.DANGER,
                             hover_border=T.DANGER)
            return
        playing = bool(self.video and self.video.state == "playing")
        self.rec_btn.set(text=tr("Saving…") if self._saving else tr("Record"), glyph="●",
                         disabled=not playing or bool(self._saving), fill=T.INSET, fg=T.TEXT,
                         border=T.BORDER, hover_fg=T.DANGER, hover_border=T.DANGER)
        fresh = self._saved and not self._saved.error and \
            time.monotonic() - self._saved_at < SAVED_SHOWN_S
        if fresh and not self.saved_link.winfo_manager():
            self.saved_link.pack(side="left", padx=(14, 0))
        elif not fresh and self.saved_link.winfo_manager():
            self.saved_link.pack_forget()
        if self._saved and self._saved.error:
            self.notice.configure(text=tr("Recording failed: {error}", error=self._saved.error))
            if not self.notice.winfo_manager():
                self.notice.pack(fill="x", pady=(8, 0), after=self.rec_btn.master)

    def _open_recording(self):
        if self._saved:
            self.app.open_recording(self._saved.path)

    def _stop_video(self):
        self._stop_record()
        if self.full:
            self.full.close()
        if self.video:
            self.video.stop()
            self.video = None
        self._stop_sound()
        self._photo = None

    def destroy(self):
        self._stop_video()
        super().destroy()


# -- helpers -------------------------------------------------------------------------

class _GloveFinder(tk.Frame):
    """Which physical glove each hand of the headset connects to, and finding the right one when
    several are switched on.

    Every left glove advertises the same name, and so does every right one, so with several kits
    on in one room a plain connect takes whichever answers first. Find gloves has the headset list
    every glove in range, nearest first; Connect picks one, and the headset keeps to it from then
    on, across drops and restarts. A glove's name, given here with a double-click, belongs to that
    glove on this computer, so it carries it on every headset. Addresses stay out of sight: a glove
    with no name is told apart by the last four characters of its address."""

    def __init__(self, parent, detail: "_Detail"):
        super().__init__(parent, bg=T.SURFACE)
        self.model = detail.model
        self.key = detail.key
        self._shown = None            # what the section was last drawn from
        self._renaming: str | None = None

        head = tk.Frame(self, bg=T.SURFACE)
        head.pack(fill="x")
        section_label(head, tr("Gloves")).pack(side="left")
        self.find_btn = Button(head, tr("Find gloves"), command=self._find, height=30,
                               fill=T.INSET, fg=T.TEXT, border=T.BORDER, hover_fill=T.INSET,
                               hover_fg=T.ACCENT, hover_border=T.ACCENT, padx=12,
                               font=T.font(12, 600))
        self.find_btn.pack(side="left", padx=(12, 0))
        self.body = tk.Frame(self, bg=T.SURFACE)
        self.body.pack(fill="x", pady=(8, 0))

    def refresh(self, r: HeadsetRow):
        s = r.status
        search = s.glove_search if s else None
        usable = bool(s and r.link == "connected" and s.allow_glove_control and not s.paused
                      and search is not None)
        searching = bool(search and search.state == "searching")
        self.find_btn.set(disabled=not usable or searching,
                          text=tr("Searching…") if searching else tr("Find gloves"))
        saved = tuple((h, g.saved_address, g.state) for h in R.HANDS
                      if s and (g := s.gloves.get(h)))
        found = search.found if search else []
        names = tuple(self.model.glove_name(a) for a in [g.address for g in found] +
                      [a for _h, a, _st in saved if a])
        shown = (s is None, repr(search), saved, names, usable, self._renaming)
        if shown == self._shown:
            return
        self._shown = shown
        for child in self.body.winfo_children():
            child.destroy()
        if s is None:
            return
        if search is None:
            self._line(tr("Update this app to HexR 0.10.6 or later to pick gloves."))
            return

        # Each hand, and the glove it keeps to.
        saved_by = {}
        hands = tk.Frame(self.body, bg=T.SURFACE)
        hands.pack(fill="x")
        for hand, address, _state in saved:
            row = tk.Frame(hands, bg=T.SURFACE)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=tr(hand.capitalize()), bg=T.SURFACE, fg=T.TEXT_MUTED,
                     font=T.font(12.5), width=6, anchor="w").pack(side="left")
            if address:
                saved_by[address.upper()] = hand
                tk.Label(row, text=self._glove_label(address, hand), bg=T.SURFACE, fg=T.TEXT,
                         font=T.font(13, 600), anchor="w").pack(side="left")
                if usable:
                    TextLink(row, tr("Forget"), size=12,
                             command=lambda h=hand: self.model.forget_glove(self.key, h)) \
                        .pack(side="left", padx=(12, 0))
            else:
                tk.Label(row, text=tr("Any glove"), bg=T.SURFACE, fg=T.TEXT_MUTED,
                         font=T.font(13), anchor="w").pack(side="left")

        # The last search: a word while it runs or when it found nothing, then the gloves.
        if search.state == "searching":
            self._line(tr("Looking for gloves…"))
        elif search.state == "failed":
            self._line(search.message, fg=T.DANGER)
        elif search.state == "done" and not found:
            self._line(tr("No gloves found. Switch them on, and disconnect them from other "
                          "headsets."))
        if found:
            card = Surface(self.body)
            card.pack(fill="x", pady=(10, 0))
            for i, g in enumerate(found):
                if i:
                    Divider(card).pack(fill="x")
                self._found_row(card, g, saved_by.get(g.address.upper()), usable)

    def _glove_label(self, address: str, hand: str = "") -> str:
        """The name given to this glove here, or else its own name from its address, the one
        every HEXR Companion gives it."""
        return self.model.glove_name(address) or \
            glovenames.auto_name(address, chinese=language() == "zh")

    def _line(self, text: str, fg=None):
        tk.Label(self.body, text=text, bg=T.SURFACE, fg=fg or T.TEXT_MUTED, font=T.font(12.5),
                 anchor="w", justify="left", wraplength=640).pack(fill="x", pady=(8, 0))

    def _found_row(self, card, g: R.NearbyGlove, saved_for: str | None, usable: bool):
        row = tk.Frame(card, bg=T.RAISED)
        row.pack(fill="x", padx=14, pady=8)
        bars = SignalBars(row)
        bars.set(g.rssi or None)
        bars.pack(side="left", padx=(0, 12))
        if self._renaming == g.address:
            box = _entry(row, width=22)
            box.insert(0, self._glove_label(g.address))
            box.pack(side="left", ipady=3)
            box.bind("<Return>", lambda e: self._rename_done(g.address, box.get()))
            box.bind("<Escape>", lambda e: self._rename_done(None, ""))
            box.bind("<FocusOut>", lambda e: self._rename_done(g.address, box.get()))
            box.after_idle(box.focus_set)
        else:
            name = tk.Label(row, text=self._glove_label(g.address, g.hand), bg=T.RAISED, fg=T.TEXT,
                            font=T.font(13.5, 600), anchor="w", cursor="xterm")
            name.pack(side="left")
            name.bind("<Double-Button-1>", lambda e: self._rename(g.address))
            Tooltip(name, lambda: tr("Double-click to rename"))
        if g.hand:
            tk.Label(row, text=tr(g.hand.capitalize()), bg=T.RAISED, fg=T.TEXT_MUTED,
                     font=T.font(12.5)).pack(side="left", padx=(10, 0))

        # On the right: the glove already chosen, or the button that chooses it.
        if saved_for:
            tk.Label(row, text="✓ " + tr(saved_for.capitalize()), bg=T.RAISED, fg=T.SUCCESS,
                     font=T.font(12.5, 600)).pack(side="right")
            return
        for hand in reversed([g.hand] if g.hand else list(R.HANDS)):
            label = tr("Connect") if g.hand else tr(hand.capitalize())
            b = Button(row, label, height=30, padx=14, font=T.font(12.5, 600),
                       command=lambda h=hand: self.model.connect_glove_to(self.key, h, g.address))
            b.set(disabled=not usable)
            b.pack(side="right", padx=(8, 0))

    def _find(self):
        self.model.search_gloves(self.key)

    def _rename(self, address: str):
        self._renaming = address
        self._shown = None

    def _rename_done(self, address: str | None, name: str):
        if self._renaming is None:
            return
        if address:
            # Typing in the glove's own name is not a rename.
            auto = glovenames.auto_name(address, chinese=language() == "zh")
            self.model.rename_glove(address, "" if name.strip() == auto else name)
        self._renaming = None
        self._shown = None

def _clock(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def _entry(parent, width: int) -> tk.Entry:
    return tk.Entry(parent, width=width, bg=T.INSET, fg=T.TEXT, insertbackground=T.TEXT,
                    relief="flat", highlightthickness=1, highlightbackground=T.BORDER,
                    highlightcolor=T.ACCENT, font=T.font(13), disabledbackground=T.INSET)


def _link_look(r: HeadsetRow) -> tuple[str, str]:
    if r.link != "connected":
        return ((T.ACCENT, tr("connecting")) if r.link == "connecting" else
                (T.DANGER, tr("unreachable")))
    if r.status and r.status.paused:
        return T.DOT_OFF, tr("asleep")
    return T.SUCCESS, tr("ready")


def _this_computer_holds(app, g: R.GloveState) -> str:
    """A glove connects to one thing at a time. If this computer has the same hand connected over
    its own Bluetooth and the headset cannot reach its glove, that may well be why."""
    if g.connected:
        return ""
    state = app.state.get(g.hand.capitalize()) if hasattr(app, "state") else None
    if state is not None and getattr(state, "connected", False):
        return tr("This computer has a glove for this hand; disconnect it here first.")
    return ""
