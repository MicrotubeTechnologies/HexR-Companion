"""The Headsets screen: the HEXR headsets on this network.

At an event a facilitator would otherwise have to take a headset off someone to connect
their gloves, and could not see what they were seeing. This lists every headset running
a HEXR app with HexR Remote; opening one puts what the wearer sees first, with the glove
drawn over it as it fires, then one row to watch, record and go full screen, its gloves,
and its scene. The numbers behind it (versions, addresses, pressures) are under Details.

The same thing as the phone's Headsets tab, over the same protocol (see hexr/remote.py).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import tkinter as tk

from .. import recorder as REC
from .. import remote as R
from .. import settings
from .. import theme as T
from ..haptics import HapticsTimeline
from ..headsets import Headsets, HeadsetRow
from ..i18n import N_, tr
from ..overlay import OverlayLook
from ..viewer import Compositor, ViewLook
from ..widgets import (Button, Divider, Dot, Select, StatusChip, Surface, TextLink, Tooltip,
                       icon_fullscreen, icon_more)
from .base import Screen, section_label
from .fullview import PUMP_MS, FullView

# headset | app | state | action
COLS = (None, 220, 120, 100)

VIEW_MIN, VIEW_MAX = 480, 1024   # the view's width: grows with the window, to the headset's own
GLOVE_SIZES = ((N_("Small"), 0.26), (N_("Medium"), 0.32), (N_("Large"), 0.40))
COMMANDS_W = 900          # the content column, less a margin
LIST_EVERY = 4            # ticks between list refreshes: 20 Hz / 4 = 5 Hz, what a headset sends
DOTS_EVERY = 8            # ticks per step of the searching dots: 20 Hz / 8 = 0.4 s
SAVED_SHOWN_S = 15.0      # how long "Show in folder" stays after a recording is saved
VIDEO_RETRY_S = 3.0       # a view that dropped while the headset still shares it: join again
VIEW_FILE = "view.json"


def _menu(parent) -> tk.Menu:
    return tk.Menu(parent, tearoff=0, bg=T.RAISED, fg=T.TEXT, activebackground=T.ACCENT,
                   activeforeground=T.CANVAS, selectcolor=T.ACCENT, bd=0, relief="flat",
                   font=T.font(12.5))


def _popup(menu: tk.Menu, widget):
    try:
        menu.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())
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
    """The opened headset: its view first, then watch / record / full screen, its gloves,
    and its scene. The numbers are under Details."""

    def __init__(self, parent, screen: HeadsetsScreen, key: str):
        super().__init__(parent, bg=T.SURFACE)
        self.screen_ = screen
        self.model = screen.model
        self.app = screen.app
        self.key = key
        self.video: R.VideoReceiver | None = None
        self._photo = None
        self._blank: tk.PhotoImage | None = None
        self._scene_names: list[tuple[int, str]] = []
        self._command_ids: list[str] = []
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

        # -- the picture, always there: what the wearer sees, or what is happening instead
        self.look = _load_look()
        self.timeline = self.model.haptics(key) or HapticsTimeline()
        self.compositor = Compositor(self.timeline, self.look)
        self.screen = tk.Label(self, bg=T.CANVAS, bd=0, fg=T.TEXT_2, font=T.font(14),
                               compound="center", cursor="hand2")
        self.screen.pack(anchor="w", pady=(12, 0))
        self.screen.bind("<ButtonPress-1>", self._picture_press)
        self.screen.bind("<B1-Motion>", lambda e: self._drag_frame("move", e.y))
        self.screen.bind("<ButtonRelease-1>", lambda e: self._drag_frame("end", e.y))
        self.screen.bind("<Double-Button-1>", lambda e: self._open_full())
        Tooltip(self.screen, lambda: tr("Drag the picture up or down to frame it.")
                if self.video and self.look.landscape else "")

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
        self.options_btn = Button(bar, "", icon=icon_more, command=self._view_menu,
                                  fill=T.INSET, fg=T.TEXT, border=T.BORDER, hover_fill=T.INSET,
                                  hover_fg=T.ACCENT, hover_border=T.ACCENT)
        self.options_btn.pack(side="left", padx=(10, 0))
        Tooltip(self.options_btn, tr("View"))
        self.state_chip = StatusChip(bar, "")
        self.state_chip.pack(side="left", padx=(14, 0))
        self.saved_link = TextLink(bar, "✓ " + tr("Show in folder"), command=self._show_recording,
                                   fg=T.SUCCESS, hover=T.TEXT)
        self.notice = tk.Label(self, text="", bg=T.SURFACE, fg=T.DANGER, font=T.font(12.5),
                               anchor="w", justify="left", wraplength=720)

        # -- its gloves
        gloves = tk.Frame(self, bg=T.SURFACE)
        gloves.pack(fill="x", pady=(14, 0))
        self.chips = {}
        for hand in R.HANDS:
            chip = StatusChip(gloves, tr("{hand} glove", hand=tr(hand.capitalize())),
                              command=lambda e, h=hand: self._glove_clicked(h, e))
            chip.pack(side="left", padx=(0, 8))
            Tooltip(chip, lambda h=hand: self._glove_hint(h))
            self.chips[hand] = chip
        Button(gloves, tr("Release all"), command=lambda: self.model.release(key), height=32,
               fill=T.SURFACE, fg=T.TEXT_2, border=T.BORDER, hover_fill=T.INSET,
               hover_fg=T.ACCENT, hover_border=T.ACCENT, padx=14,
               font=T.font(12.5, 600)).pack(side="left", padx=(6, 0))

        # -- its scene, recentering, and the app's own commands
        scene = tk.Frame(self, bg=T.SURFACE)
        scene.pack(fill="x", pady=(14, 0))
        self.scene_select = Select(scene, [""], value="", label=tr("Scene"),
                                   command=self._scene_picked)
        self._picked_at = 0.0
        self.recenter_btn = Button(scene, tr("Recenter"), command=self._recenter, height=34,
                                   fill=T.INSET, fg=T.TEXT, border=T.BORDER,
                                   hover_fill=T.ACCENT, hover_fg=T.CANVAS,
                                   hover_border=T.ACCENT, min_width=110)
        self.recenter_btn.pack(side="left")
        Tooltip(self.recenter_btn, lambda: "" if self._can_recenter() else
                tr("Needs HexR 0.11.0 with Allow Recenter."))
        self._recentered_at = 0.0
        self.commands = tk.Frame(self, bg=T.SURFACE)
        self.commands.pack(fill="x", pady=(10, 0))

        # -- Details: the numbers
        self.numbers = tk.Label(self, text="", bg=T.SURFACE, fg=T.TEXT_FAINT, font=T.mono(11),
                                anchor="w", justify="left")

        self._view_wanted = False
        self._video_retry_at = 0.0
        self._last_stream = R.StreamState()
        self._unavailable = R.video_available()
        self._fit = self._inline_fit()
        self.full: FullView | None = None
        self.recorder: REC.Recorder | None = None
        self._saving: REC.Recorder | None = None
        self._saved: REC.Recorder | None = None
        self._saved_at = 0.0
        self._drag: tuple[int, float] | None = None
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

        for hand, chip in self.chips.items():
            g = s.gloves.get(hand) if s else None
            chip.set(tr("{hand} glove", hand=tr(hand.capitalize())), _glove_colour(g)
                     if g and g.state != "disconnected" else None)

        if s and s.expose_scenes and s.scenes:
            if not self.scene_select.winfo_manager():
                self.scene_select.pack(side="left", padx=(0, 10), before=self.recenter_btn)
            if s.scenes != self._scene_names:
                self._scene_names = s.scenes
                self.scene_select.set(values=[n for _i, n in s.scenes])
            current = next((n for i, n in s.scenes if i == s.scene_index), s.scene_name)
            # A scene just picked takes a moment to load; until then the headset still reports
            # the old one, and showing that would look like the pick did not take.
            recently_picked = time.monotonic() - self._picked_at < 4.0
            if current and self.scene_select.value != current and not recently_picked:
                self.scene_select.set(value=current)
        elif self.scene_select.winfo_manager():
            self.scene_select.pack_forget()

        usable = bool(s and r.link == "connected" and self._can_recenter() and not s.paused)
        just = time.monotonic() - self._recentered_at < 3.0 and not r.error
        self.recenter_btn.set(disabled=not usable, glyph="✓" if just else "",
                              fg=T.SUCCESS if just else T.TEXT)

        ids = [c[0] for c in s.commands] if s else []
        if ids != self._command_ids:
            self._command_ids = ids
            for w in self.commands.winfo_children():
                w.destroy()
            # An app can register many commands (the Sandbox has one per demo), so they flow
            # onto as many rows as they need instead of running off the right edge.
            x = y = 0
            for cid, label in (s.commands if s else []):
                btn = Button(self.commands, label or cid,
                             command=lambda c=cid: self.model.run_command(self.key, c),
                             height=30, fill=T.INSET, fg=T.TEXT, border=T.BORDER,
                             hover_fill=T.ACCENT, hover_fg=T.CANVAS, hover_border=T.ACCENT)
                width = btn.winfo_reqwidth()
                if x and x + width > COMMANDS_W:
                    x, y = 0, y + 38
                btn.place(x=x, y=y)
                x += width + 8
            # place() does not size its parent, so the frame is given the rows' height.
            self.commands.configure(height=y + 30 if ids else 1)

        if r.error:
            self.notice.configure(text=r.error)
            if not self.notice.winfo_manager():
                self.notice.pack(fill="x", pady=(8, 0), after=self.rec_btn.master)
        elif self.notice.winfo_manager() and not self._notice_recording():
            self.notice.pack_forget()

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
        if self.video and self.video.state == "playing" and self.look.overlay \
                and not self.timeline.exact:
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

    def _glove_clicked(self, hand: str, _e=None):
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
            _popup(m, self.chips[hand])
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
        return "\n".join(filter(None, [word, g.message if g.message != word else "", hint]))

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

    def _recenter(self):
        self._recentered_at = time.monotonic()
        self.model.recenter(self.key)

    def _scene_picked(self, name: str):
        index = next((i for i, n in self._scene_names if n == name), -1)
        if index >= 0:
            self._picked_at = time.monotonic()
            self.model.load_scene(self.key, index)

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

    def _picture_press(self, e):
        if self.video and self.video.state == "playing":
            self._drag_frame("start", e.y)
        elif not self._view_wanted and not self._unavailable:
            self._toggle_view()

    def _update_view(self, r: HeadsetRow):
        s = r.status
        st = s.stream if s else R.StreamState()
        self._last_stream = st
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
        if not playing:
            self._show_placeholder(say)

    def _show_placeholder(self, text: str):
        w, h = self._fit
        if self._blank is None or (self._blank.width(), self._blank.height()) != (w, h):
            self._blank = tk.PhotoImage(master=self, width=w, height=h)
        self._photo = None
        self.screen.configure(image=self._blank, text=text, fg=T.TEXT_2)

    # -- drawing the view -------------------------------------------------------------------------

    def _render(self, frame, pts_us: int, arrived: float):
        """The video thread: one frame as it is shown, framed and with the glove on top."""
        return self.compositor.compose(frame, pts_us, arrived, self._fit)

    def _inline_fit(self) -> tuple[int, int]:
        """The view's size in the window: as wide as the column, as tall as leaves the rows
        under it on screen once it is scrolled into view."""
        room = self.winfo_width() - 8 if self.winfo_ismapped() else VIEW_MIN
        view_h = self.screen_._area._canvas.winfo_height()
        tall = max(270, min(576, view_h - 230)) if view_h > 1 else 405
        if self.look.landscape:
            w = int(max(VIEW_MIN, min(room, VIEW_MAX, tall * 16 / 9)))
            return w, w * 9 // 16
        side = int(max(360, min(room, tall, 720)))
        return side, side

    def pump_video(self):
        if not self.video or self.full:
            return
        image = self.video.latest()
        if image is None:
            return
        from PIL import ImageTk
        if self._photo is None or (self._photo.width(), self._photo.height()) != image.size:
            self._photo = ImageTk.PhotoImage(image, master=self)
            self.screen.configure(image=self._photo, text="")
        else:
            self._photo.paste(image)

    def _view_menu(self):
        """Frame, glove and size: set once, rarely changed, so out of the way."""
        m = _menu(self)
        self._frame_var = tk.StringVar(self, "16:9" if self.look.landscape else "square")
        self._glove_var = tk.StringVar(self, "on" if self.look.overlay else "off")
        current = min(GLOVE_SIZES, key=lambda x: abs(x[1] - self.look.glove.size))[0]
        self._size_var = tk.StringVar(self, current)
        m.add_command(label=tr("Frame"), state="disabled")
        m.add_radiobutton(label="16:9", value="16:9", variable=self._frame_var,
                          command=lambda: self._set_look(landscape=True))
        m.add_radiobutton(label=tr("Square"), value="square", variable=self._frame_var,
                          command=lambda: self._set_look(landscape=False))
        m.add_separator()
        m.add_command(label=tr("Glove"), state="disabled")
        m.add_radiobutton(label=tr("On"), value="on", variable=self._glove_var,
                          command=lambda: self._set_look(overlay=True))
        m.add_radiobutton(label=tr("Off"), value="off", variable=self._glove_var,
                          command=lambda: self._set_look(overlay=False))
        m.add_separator()
        m.add_command(label=tr("Size"), state="disabled")
        for name, size in GLOVE_SIZES:
            m.add_radiobutton(label=tr(name), value=name, variable=self._size_var,
                              command=lambda v=size: self._set_size(v))
        _popup(m, self.options_btn)

    def _set_look(self, save: bool = True, **changes):
        if self.recorder and changes.get("landscape", self.look.landscape) != self.look.landscape:
            return              # a recording keeps the frame it started with: its size is fixed
        self.look = self.look.but(**changes)
        self.compositor.look = self.look
        self._fit = self.full.size if self.full else self._inline_fit()
        if save:
            _save_look(self.look)

    def _set_size(self, size: float):
        self._set_look(glove=OverlayLook(**{**self.look.glove.__dict__, "size": size}))

    def _toggle_glove(self):
        self._set_look(overlay=not self.look.overlay)

    def _drag_frame(self, phase: str, y: int, host=None):
        """Drag the 16:9 frame up or down the square view it is cut from."""
        if not self.look.landscape:
            return
        if phase == "start":
            self._drag = (y, self.look.offset)
        elif phase == "move" and self._drag:
            shown = host.picture_height() if host else (self._photo.height() if self._photo else 0)
            travel = shown * (16 / 9 - 1) / 2       # the spare height of the square, either side
            if travel > 0:
                y0, start = self._drag
                self._set_look(save=False, offset=max(-1.0, min(1.0, start - (y - y0) / travel)))
        elif phase == "end" and self._drag:
            self._drag = None
            _save_look(self.look)

    def _nudge(self, step: float):
        if self.look.landscape:
            self._set_look(offset=max(-1.0, min(1.0, self.look.offset + step)))

    # -- full screen ------------------------------------------------------------------------------

    def _open_full(self):
        if self.full or not (self.video and self.video.state == "playing"):
            return
        self.full = FullView(self, on_close=self._full_closed, on_record=self._toggle_record,
                             on_glove=self._toggle_glove, on_nudge=self._nudge,
                             on_drag=self._drag_frame)
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
        rec = REC.Recorder(path, self.timeline, lambda: self.look)
        self.recorder = rec
        self._saved = None
        self.saved_link.pack_forget()
        rec.start()
        self.video.taps.append(rec.tap)
        self._update_recording()

    def _stop_record(self):
        rec, self.recorder = self.recorder, None
        if rec is None:
            return
        if self.video and rec.tap in self.video.taps:
            self.video.taps.remove(rec.tap)
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

    def _show_recording(self):
        if not self._saved:
            return
        path = os.path.normpath(self._saved.path)
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", path])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", path])
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(path)])
        except OSError:
            pass

    def _stop_video(self):
        self._stop_record()
        if self.full:
            self.full.close()
        if self.video:
            self.video.stop()
            self.video = None
        self._photo = None

    def destroy(self):
        self._stop_video()
        super().destroy()


# -- helpers -------------------------------------------------------------------------

def _clock(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def _load_look() -> ViewLook:
    """How the view was last set up: its frame, the glove on or off, and the glove's size."""
    try:
        data = settings.load(VIEW_FILE)
        return ViewLook(landscape=bool(data.get("landscape", True)),
                        offset=float(data.get("offset", ViewLook.offset)),
                        overlay=bool(data.get("overlay", True)),
                        glove=OverlayLook(size=float(data.get("gloveSize", 0.32))))
    except (AttributeError, TypeError, ValueError):
        return ViewLook()


def _save_look(look: ViewLook):
    settings.save(VIEW_FILE, {"landscape": look.landscape, "offset": round(look.offset, 3),
                              "overlay": look.overlay, "gloveSize": look.glove.size})


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


def _glove_colour(g: R.GloveState | None) -> str:
    if g is None or g.state in ("disconnected", "missing"):
        return T.DOT_OFF
    return T.SUCCESS if g.connected else T.ACCENT


def _this_computer_holds(app, g: R.GloveState) -> str:
    """A glove connects to one thing at a time. If this computer has the same hand connected over
    its own Bluetooth and the headset cannot reach its glove, that may well be why."""
    if g.connected:
        return ""
    state = app.state.get(g.hand.capitalize()) if hasattr(app, "state") else None
    if state is not None and getattr(state, "connected", False):
        return tr("This computer has a glove for this hand; disconnect it here first.")
    return ""
