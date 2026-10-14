"""The Headsets screen: the HEXR headsets on this network.

At an event a facilitator would otherwise have to take a headset off someone to connect their
gloves, and could not see what they were seeing. This lists every headset running a HEXR app
with HexR Remote, and for the one picked: its gloves (connect, disconnect, battery, pressure),
its scene, the app's own commands, and its view once the wearer agrees to share it.

The same thing as the phone's Headsets tab, over the same protocol (see hexr/remote.py).
"""

from __future__ import annotations

import time
import tkinter as tk

from .. import remote as R
from .. import theme as T
from ..headsets import Headsets, HeadsetRow
from ..widgets import Button, Divider, Dot, Panel, Select, Surface
from .base import Screen, section_label

# headset | app · scene | gloves | state | action
COLS = (None, 260, 120, 110, 100)

COMMANDS_W = 900          # the content column, less a margin
LIST_EVERY = 4            # ticks between list refreshes: 20 Hz / 4 = 5 Hz, what a headset sends


class HeadsetsScreen(Screen):
    title_text = "Headsets"
    sub_text = ("Every HEXR headset on this network. Connect its gloves, change its scene and "
                "watch what the wearer sees, without taking the headset off them.")

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.model: Headsets = app.headsets
        self._rows: dict[str, tk.Frame] = {}
        self._selected: str | None = None
        self._detail: _Detail | None = None
        self._viewer: _Viewer | None = None
        self._ticks = 0

        bar = tk.Frame(self.body, bg=T.SURFACE)
        bar.pack(fill="x")
        self.listen_status = tk.Label(bar, text="", bg=T.SURFACE, fg=T.TEXT_MUTED,
                                      font=T.font(12.5), anchor="w")
        self.listen_status.pack(side="left")
        Button(bar, "Add", command=self._add, height=30, fill=T.INSET, fg=T.TEXT,
               border=T.BORDER, hover_fill=T.ACCENT, hover_fg=T.CANVAS,
               hover_border=T.ACCENT, min_width=70).pack(side="right")
        self.address = _entry(bar, width=18)
        self.address.pack(side="right", padx=(0, 8), ipady=4)
        self.address.bind("<Return>", lambda e: self._add())
        tk.Label(bar, text="Headset address", bg=T.SURFACE, fg=T.TEXT_FAINT,
                 font=T.font(12)).pack(side="right", padx=(0, 8))

        self.results = Surface(self.body)
        self.results.pack(fill="x", pady=(18, 0))
        self._build_header()
        self.empty = tk.Label(
            self.results, bg=T.RAISED, fg=T.TEXT_MUTED, font=T.font(12.5), justify="left",
            anchor="w", wraplength=820,
            text=("No headsets yet. Each one needs a HEXR app with HexR Remote running, on the "
                  "same network as this computer. If one is running and still does not appear, "
                  "Windows may be blocking it: allow HEXR Window Tester on private networks in "
                  "Windows Security, make sure this network is set to Private, or type the "
                  "headset's address above."))
        self.empty.pack(fill="x", padx=18, pady=18)

        self.detail_host = tk.Frame(self.body, bg=T.SURFACE)
        self.detail_host.pack(fill="x", pady=(22, 0))

    # -- list --------------------------------------------------------------------

    def _build_header(self):
        head = tk.Frame(self.results, bg=T.RAISED)
        head.pack(fill="x", padx=18, pady=(14, 0))
        for i, (label, width) in enumerate(
                zip(("Headset", "App · scene", "Gloves", "State", ""), COLS)):
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
        elif not self.empty.winfo_ismapped():
            self.empty.pack(fill="x", padx=18, pady=18)
        for r in rows:
            self._update_row(self._rows[r.key], r)

    def _build_row(self, r: HeadsetRow) -> tk.Frame:
        row = tk.Frame(self.results, bg=T.RAISED)
        row.pack(fill="x", padx=18, pady=(0, 2))
        name = tk.Frame(row, bg=T.RAISED)
        name.grid(row=0, column=0, sticky="w", pady=9)
        row.dot = Dot(name, color=T.DOT_OFF, bg=T.RAISED)
        row.dot.pack(side="left", pady=(4, 0))
        row.title = tk.Label(name, text="", bg=T.RAISED, fg=T.TEXT, font=T.font(13))
        row.title.pack(side="left", padx=(8, 0))
        row.app = tk.Label(row, text="", bg=T.RAISED, fg=T.TEXT_2, font=T.font(12),
                           anchor="w")
        row.app.grid(row=0, column=1, sticky="w", padx=(0, 10))
        gloves = tk.Frame(row, bg=T.RAISED)
        gloves.grid(row=0, column=2, sticky="w", padx=(0, 10))
        row.glove_dots = {}
        for hand in R.HANDS:
            tk.Label(gloves, text=hand[0].upper(), bg=T.RAISED, fg=T.TEXT_FAINT,
                     font=T.mono(11)).pack(side="left", padx=(0, 3))
            dot = Dot(gloves, color=T.DOT_OFF, bg=T.RAISED)
            dot.pack(side="left", padx=(0, 10), pady=(3, 0))
            row.glove_dots[hand] = dot
        row.state = tk.Label(row, text="", bg=T.RAISED, fg=T.TEXT_MUTED, font=T.font(12),
                             anchor="w")
        row.state.grid(row=0, column=3, sticky="w", padx=(0, 10))
        row.open = Button(row, "Open", command=lambda k=r.key: self._select(k), height=30,
                          fill=T.INSET, fg=T.TEXT, border=T.BORDER, hover_fill=T.ACCENT,
                          hover_fg=T.CANVAS, hover_border=T.ACCENT, min_width=90)
        row.open.grid(row=0, column=4, sticky="e")
        row.grid_columnconfigure(0, weight=1)
        for i, width in enumerate(COLS):
            if width:
                row.grid_columnconfigure(i, minsize=width)
        return row

    def _update_row(self, row: tk.Frame, r: HeadsetRow):
        colour, word = _link_look(r)
        row.dot.set(colour)
        row.title.configure(text=r.title, fg=T.ACCENT if r.key == self._selected else T.TEXT)
        row.app.configure(text=_app_line(r))
        row.state.configure(text=word, fg=colour if colour != T.DOT_OFF else T.TEXT_MUTED)
        for hand, dot in row.glove_dots.items():
            g = r.status.gloves.get(hand) if r.status else None
            dot.set(_glove_colour(g))

    def _select(self, key: str):
        if key == self._selected:
            return
        self._selected = key
        if self._detail:
            self._detail.destroy()
        self._detail = None

    def _add(self):
        text = self.address.get().strip()
        if text:
            self.model.add_by_address(text)
            self.address.delete(0, "end")

    # -- ticking -----------------------------------------------------------------

    def on_show(self):
        # Listening starts here, not at launch: Windows asks about the firewall the first time,
        # and the question makes sense to someone who has just opened Headsets.
        self.model.start()
        self._refresh()

    def on_tick(self):
        self._ticks += 1
        if self._viewer:
            if self._ticks % LIST_EVERY == 0:
                self._refresh_viewer()
            if self._viewer:
                self._viewer.pump_video()
            return
        if self._ticks % LIST_EVERY == 0:
            self._refresh()

    # -- the viewer ----------------------------------------------------------------

    def open_viewer(self, key: str):
        """Watch: the view takes the screen. Asks the wearer to share if nobody has yet."""
        if self._viewer:
            return
        row = next((r for r in self.model.rows() if r.key == key), None)
        st = row.status.stream if row and row.status else R.StreamState()
        if st.state not in ("live", "requesting"):
            self.model.start_view(key)
        self._area.pack_forget()
        self._viewer = _Viewer(self, self.model, key, self.app, on_close=self.close_viewer)
        self._viewer.pack(fill="both", expand=True)
        self._refresh_viewer()

    def close_viewer(self):
        if self._viewer:
            self._viewer.destroy()
            self._viewer = None
        self._area.pack(fill="both", expand=True)
        self._refresh()

    def _refresh_viewer(self):
        row = next((r for r in self.model.rows() if r.key == self._viewer.key), None)
        if row is None:
            self.close_viewer()
        else:
            self._viewer.update(row)

    def _refresh(self):
        rows = self.model.rows()
        if self.model.discovery_error:
            self.listen_status.configure(text=self.model.discovery_error, fg=T.DANGER)
        elif rows:
            n = len(rows)
            self.listen_status.configure(
                text=f"{n} headset{'' if n == 1 else 's'} on this network", fg=T.SUCCESS)
        else:
            self.listen_status.configure(text="Listening for headsets…", fg=T.TEXT_MUTED)
        self._sync_list(rows)

        row = next((r for r in rows if r.key == self._selected), None)
        if row is None:
            if self._detail:
                self._detail.destroy()
                self._detail = None
            self._selected = None
            return
        if self._detail is None:
            self._detail = _Detail(self.detail_host, self.model, row.key, self.app,
                                   on_watch=self.open_viewer)
            self._detail.pack(fill="x")
        self._detail.update(row)


class _Detail(tk.Frame):
    """The picked headset: gloves, scene, commands and view."""

    def __init__(self, parent, model: Headsets, key: str, app, on_watch):
        super().__init__(parent, bg=T.SURFACE)
        self.model = model
        self.key = key
        self.app = app
        self.on_watch = on_watch
        self._scene_names: list[tuple[int, str]] = []
        self._command_ids: list[str] = []

        # -- heading
        head = tk.Frame(self, bg=T.SURFACE)
        head.pack(fill="x")
        self.title = tk.Label(head, text="", bg=T.SURFACE, fg=T.TEXT, font=T.font(17, 600),
                              anchor="w")
        self.title.pack(side="left")
        self.forget_btn = Button(head, "Forget", command=self._forget, height=30, fill=T.INSET,
                                 fg=T.TEXT_2, border=T.BORDER, hover_fill=T.INSET,
                                 hover_fg=T.DANGER, hover_border=T.DANGER, min_width=80)
        Button(head, "Save name", command=self._rename, height=30, fill=T.INSET, fg=T.TEXT,
               border=T.BORDER, hover_fill=T.ACCENT, hover_fg=T.CANVAS,
               hover_border=T.ACCENT, min_width=100).pack(side="right")
        self.nick = _entry(head, width=16)
        self.nick.pack(side="right", padx=(0, 8), ipady=4)
        self.nick.bind("<Return>", lambda e: self._rename())
        tk.Label(head, text="Name", bg=T.SURFACE, fg=T.TEXT_FAINT,
                 font=T.font(12)).pack(side="right", padx=(0, 8))
        self._nick_shown = None

        self.info = tk.Label(self, text="", bg=T.SURFACE, fg=T.TEXT_FAINT, font=T.mono(11.5),
                             anchor="w")
        self.info.pack(fill="x", pady=(6, 0))
        self.notice = tk.Label(self, text="", bg=T.SURFACE, fg=T.TEXT_MUTED, font=T.font(12.5),
                               anchor="w", justify="left", wraplength=860)
        self.notice.pack(fill="x", pady=(8, 0))

        # -- gloves
        section_label(self, "Gloves, through the headset").pack(fill="x", pady=(18, 8))
        gloves = tk.Frame(self, bg=T.SURFACE)
        gloves.pack(fill="x")
        self.cards = {}
        for hand in R.HANDS:
            card = _glove_card(gloves, hand, lambda h=hand: self._glove_clicked(h))
            card.pack(side="left", padx=(0, 14), anchor="n")
            self.cards[hand] = card
        Button(gloves, "Release all", command=lambda: model.release(key), height=34,
               fill=T.INSET, fg=T.TEXT_2, border=T.BORDER, hover_fill=T.INSET,
               hover_fg=T.ACCENT, hover_border=T.ACCENT, min_width=120).pack(
            side="left", anchor="n")

        # -- scene and commands, in a slot of their own so they keep their place when an app
        # without scenes hides them
        slot = tk.Frame(self, bg=T.SURFACE)
        slot.pack(fill="x")
        self.scene_row = tk.Frame(slot, bg=T.SURFACE)
        section_label(self.scene_row, "Scene").pack(fill="x", pady=(18, 8))
        self.scene_select = Select(self.scene_row, [""], value="", command=self._scene_picked)
        self.scene_select.pack(anchor="w")
        self._picked_at = 0.0
        self.commands = tk.Frame(slot, bg=T.SURFACE)
        self.commands.pack(fill="x", pady=(10, 0))

        # -- view: Watch opens the viewer, the view as big as the window allows
        section_label(self, "View").pack(fill="x", pady=(18, 8))
        vbar = tk.Frame(self, bg=T.SURFACE)
        vbar.pack(fill="x")
        self.view_btn = Button(vbar, "Watch", command=self._watch, glyph="▶",
                               min_width=150)
        self.view_btn.pack(side="left")
        self.view_status = tk.Label(vbar, text="", bg=T.SURFACE, fg=T.TEXT_MUTED,
                                    font=T.font(12.5), anchor="w", justify="left",
                                    wraplength=640)
        self.view_status.pack(side="left", padx=(14, 0))
        self._unavailable = R.video_available()

    # -- updates from the screen's tick -------------------------------------------

    def update(self, r: HeadsetRow):
        s = r.status
        self.title.configure(text=r.title)
        if self._nick_shown != r.nickname and self.focus_get() is not self.nick:
            self.nick.delete(0, "end")
            self.nick.insert(0, r.nickname)
            self._nick_shown = r.nickname
        if r.manual and not self.forget_btn.winfo_ismapped():
            self.forget_btn.pack(side="right", padx=(0, 14))

        bits = []
        if s:
            bits.append(f"{s.app} {s.app_version}".strip())
            bits.append(f"HexR {s.hexr_version}")
            if s.headset_battery_pct >= 0:
                bits.append(f"headset {s.headset_battery_pct}%")
            if s.controllers > 1:
                bits.append(f"{s.controllers} controllers")
        bits.append(r.host)
        self.info.configure(text="   ·   ".join(b for b in bits if b))

        if r.error:
            self.notice.configure(text=r.error, fg=T.DANGER)
        elif r.link != "connected":
            self.notice.configure(text="Not connected to this headset. Trying again…",
                                  fg=T.TEXT_MUTED)
        elif s and s.paused:
            self.notice.configure(
                text=("Nobody is wearing this headset, so it is asleep and refuses commands. "
                      "Someone has to put it on first."), fg=T.ACCENT)
        else:
            self.notice.configure(text="")

        for hand, card in self.cards.items():
            _update_glove_card(card, s.gloves.get(hand) if s else None, s, self.app)

        if s and s.expose_scenes and s.scenes:
            if not self.scene_row.winfo_ismapped():
                self.scene_row.pack(fill="x")
            if s.scenes != self._scene_names:
                self._scene_names = s.scenes
                self.scene_select.set(values=[n for _i, n in s.scenes])
            current = next((n for i, n in s.scenes if i == s.scene_index), s.scene_name)
            # A scene just picked takes a moment to load; until then the headset still reports
            # the old one, and showing that would look like the pick did not take.
            recently_picked = time.monotonic() - self._picked_at < 4.0
            if current and self.scene_select.value != current and not recently_picked:
                self.scene_select.set(value=current)
        elif self.scene_row.winfo_ismapped():
            self.scene_row.pack_forget()

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

        self._update_view(r)

    # -- actions -----------------------------------------------------------------

    def _glove_clicked(self, hand: str):
        card = self.cards[hand]
        if card.connected:
            self.model.disconnect_glove(self.key, hand)
        else:
            self.model.connect_glove(self.key, hand)

    def _scene_picked(self, name: str):
        index = next((i for i, n in self._scene_names if n == name), -1)
        if index >= 0:
            self._picked_at = time.monotonic()
            self.model.load_scene(self.key, index)

    def _rename(self):
        self.model.rename(self.key, self.nick.get())
        self._nick_shown = None
        self.focus_set()

    def _forget(self):
        self.model.forget(self.key)

    # -- view --------------------------------------------------------------------

    def _watch(self):
        if not self._unavailable:
            self.on_watch(self.key)

    def _update_view(self, r: HeadsetRow):
        s = r.status
        st = s.stream if s else R.StreamState()
        live = st.state == "live" and st.port > 0
        if self._unavailable:
            self.view_btn.set(text="Watch", disabled=True)
            self.view_status.configure(text=self._unavailable, fg=T.TEXT_MUTED)
            return
        if s and not s.allow_video:
            self.view_btn.set(text="Watch", disabled=True)
            self.view_status.configure(text="This app does not share its view.",
                                       fg=T.TEXT_MUTED)
            return
        self.view_btn.set(text="Watch", disabled=bool(s and s.paused and not live))
        text, colour = _stream_words(st)
        self.view_status.configure(text=text, fg=colour)


class _Viewer(tk.Frame):
    """One headset's view, as big as the window allows, for an audience to watch, with its
    gloves beside it. Maximise the window, or put it on a projector, and the view grows with it.

    It takes the whole screen while open (the list and the detail come back on Back), and the
    picture is refitted to the space on every resize, keeping the headset's aspect ratio.
    """

    SIDE_W = 270

    def __init__(self, parent, model: Headsets, key: str, app, on_close):
        super().__init__(parent, bg=T.SURFACE)
        self.model, self.key, self.app, self._on_close = model, key, app, on_close
        self.video: R.VideoReceiver | None = None
        self._photo: tk.PhotoImage | None = None
        self._fit = (480, 480)
        self._aspect = 1.0
        self._stream = R.StreamState()
        self._unavailable = R.video_available()

        top = tk.Frame(self, bg=T.SURFACE)
        top.pack(fill="x", padx=24, pady=(18, 12))
        Button(top, "Back", glyph="‹", glyph_px=15, command=self.close, height=32,
               fill=T.RAISED, fg=T.TEXT_2, border=T.BORDER, hover_fill=T.INSET,
               hover_fg=T.TEXT, hover_border=T.ACCENT, min_width=90).pack(side="left")
        self.title = tk.Label(top, text="", bg=T.SURFACE, fg=T.TEXT, font=T.font(17, 600),
                              anchor="w")
        self.title.pack(side="left", padx=(16, 0))
        self.sub = tk.Label(top, text="", bg=T.SURFACE, fg=T.TEXT_MUTED, font=T.font(12.5),
                            anchor="w")
        self.sub.pack(side="left", padx=(12, 0))
        self.share_btn = Button(top, "Ask to share", command=self._ask, glyph="▶", height=32,
                                min_width=150)
        self._share_shown = False

        # The picture and the gloves as one group, centred in whatever space there is, so the
        # gloves stay beside the picture however wide the window gets.
        self.body = tk.Frame(self, bg=T.SURFACE)
        self.body.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        group = tk.Frame(self.body, bg=T.SURFACE)
        group.place(relx=0.5, rely=0.5, anchor="center")
        self.stage = tk.Frame(group, bg=T.CANVAS, width=480, height=480)
        self.stage.pack(side="left", anchor="n")
        self.stage.pack_propagate(False)
        side = tk.Frame(group, bg=T.SURFACE, width=self.SIDE_W, height=480)
        side.pack(side="left", anchor="n", padx=(16, 0))
        side.pack_propagate(False)
        self.side = side
        section_label(side, "Gloves").pack(fill="x", pady=(0, 8))
        self.cards = {}
        for hand in R.HANDS:
            card = _glove_card(side, hand, lambda h=hand: self._glove_clicked(h))
            card.pack(fill="x", pady=(0, 12))
            self.cards[hand] = card
        Button(side, "Release all", command=lambda: model.release(key), height=34,
               fill=T.INSET, fg=T.TEXT_2, border=T.BORDER, hover_fill=T.INSET,
               hover_fg=T.ACCENT, hover_border=T.ACCENT).pack(fill="x")
        self.notice = tk.Label(side, text="", bg=T.SURFACE, fg=T.TEXT_MUTED, font=T.font(12),
                               anchor="w", justify="left", wraplength=self.SIDE_W - 8)
        self.notice.pack(fill="x", pady=(12, 0))

        self.picture = tk.Label(self.stage, bg=T.CANVAS, bd=0)
        self.picture.place(relx=0.5, rely=0.5, anchor="center")
        self.message = tk.Label(self.stage, text="", bg=T.CANVAS, fg=T.TEXT_MUTED,
                                font=T.font(15), wraplength=440, justify="center")
        self.message.place(relx=0.5, rely=0.5, anchor="center")
        self.body.bind("<Configure>", lambda e: self._refit())

    # -- fitting ----------------------------------------------------------------

    def _refit(self):
        w = self.body.winfo_width() - self.SIDE_W - 16
        h = self.body.winfo_height()
        if w < 64 or h < 64:
            return
        fw = min(w, int(h * self._aspect))
        fh = int(fw / self._aspect)
        size = (fw - fw % 2, fh - fh % 2)
        if size != self._fit:
            self._fit = size
            self.stage.configure(width=size[0], height=size[1])
            # The gloves column is as tall as the picture, or as its own cards need.
            self.side.configure(height=max(size[1], self.side.winfo_reqheight(), 440))
            self.message.configure(wraplength=max(240, size[0] - 60))
            if self.video:
                self.video.resize(size)

    # -- from the screen's tick ---------------------------------------------------

    def update(self, r: HeadsetRow):
        s = r.status
        st = s.stream if s else R.StreamState()
        self._stream = st
        self.title.configure(text=r.title)
        self.sub.configure(text=_app_line(r))
        if st.width and st.height and abs(st.width / st.height - self._aspect) > 0.01:
            self._aspect = st.width / st.height
            self._refit()

        for hand, card in self.cards.items():
            _update_glove_card(card, s.gloves.get(hand) if s else None, s, self.app)
        if r.error:
            self.notice.configure(text=r.error, fg=T.DANGER)
        elif r.link != "connected":
            self.notice.configure(text="Not connected to this headset. Trying again…",
                                  fg=T.TEXT_MUTED)
        elif s and s.paused:
            self.notice.configure(text="Nobody is wearing this headset, so it is asleep and "
                                       "refuses commands.", fg=T.ACCENT)
        else:
            self.notice.configure(text="")

        live = st.state == "live" and st.port > 0
        if live and self.video is None and not self._unavailable:
            self.video = R.VideoReceiver(r.host, st.port, self._fit)
        elif not live and self.video is not None and st.state != "requesting":
            self._stop_video()

        # Asking again only makes sense once there is nothing pending or shared.
        can_ask = (not self._unavailable and bool(s) and s.allow_video and not live
                   and st.state not in ("requesting", "unsupported"))
        if can_ask != self._share_shown:
            self._share_shown = can_ask
            if can_ask:
                self.share_btn.pack(side="right")
            else:
                self.share_btn.pack_forget()

        if self.video is not None and self.video.state == "playing" and self._photo:
            self.message.place_forget()
            return
        if self._unavailable:
            text, colour = self._unavailable, T.TEXT_MUTED
        elif s and not s.allow_video:
            text, colour = "This app does not share its view.", T.TEXT_MUTED
        elif self.video and self.video.state == "failed":
            text, colour = self.video.message, T.DANGER
        elif self.video:
            text, colour = "Connecting to the view…", T.TEXT_MUTED
        else:
            text, colour = _stream_words(st)
        self.message.configure(text=text, fg=colour)
        self.message.place(relx=0.5, rely=0.5, anchor="center")

    def pump_video(self):
        if not self.video:
            return
        frame = self.video.latest()
        if frame is None:
            return
        try:
            self._photo = tk.PhotoImage(master=self, data=frame, format="PPM")
        except tk.TclError:
            return
        self.picture.configure(image=self._photo)
        self.message.place_forget()

    # -- actions -------------------------------------------------------------------

    def _ask(self):
        self.model.start_view(self.key)

    def _glove_clicked(self, hand: str):
        card = self.cards[hand]
        if card.connected:
            self.model.disconnect_glove(self.key, hand)
        else:
            self.model.connect_glove(self.key, hand)

    def close(self):
        # Ending the share closes every viewer's connection, so only end it if nobody else (a
        # phone, another computer) is watching too; otherwise just leave.
        others = self._stream.viewers - (1 if self.video else 0)
        self._stop_video()
        if others <= 0 and self._stream.state in ("live", "requesting"):
            self.model.stop_view(self.key)
        self._on_close()

    def _stop_video(self):
        if self.video:
            self.video.stop()
            self.video = None
        self.picture.configure(image="")
        self._photo = None

    def destroy(self):
        self._stop_video()
        super().destroy()


# -- helpers -------------------------------------------------------------------------

def _entry(parent, width: int) -> tk.Entry:
    return tk.Entry(parent, width=width, bg=T.INSET, fg=T.TEXT, insertbackground=T.TEXT,
                    relief="flat", highlightthickness=1, highlightbackground=T.BORDER,
                    highlightcolor=T.ACCENT, font=T.font(13), disabledbackground=T.INSET)


def _app_line(r: HeadsetRow) -> str:
    s = r.status
    if s:
        return s.app + (f" · {s.scene_name}" if s.scene_name else "")
    return r.announce.app if r.announce else r.host


def _link_look(r: HeadsetRow) -> tuple[str, str]:
    if r.link != "connected":
        return (T.ACCENT, "connecting") if r.link == "connecting" else (T.DANGER, "unreachable")
    if r.status and r.status.paused:
        return T.DOT_OFF, "asleep"
    return T.SUCCESS, "ready"


def _glove_card(parent, hand: str, on_click) -> Panel:
    """A glove as the headset reports it, with its Connect/Disconnect. Not packed."""
    card = Panel(parent, bg=T.RAISED, pad=16)
    b = card.body
    top = tk.Frame(b, bg=T.RAISED)
    top.pack(fill="x")
    card.dot = Dot(top, color=T.DOT_OFF, bg=T.RAISED)
    card.dot.pack(side="left", pady=(5, 0))
    tk.Label(top, text=f"{hand.capitalize()} glove", bg=T.RAISED, fg=T.TEXT,
             font=T.font(14, 600)).pack(side="left", padx=(9, 0))
    # A fixed width in characters keeps both cards the same size, and wrapping inside it rather
    # than past it keeps a long status from being cut off.
    card.state = tk.Label(b, text="", bg=T.RAISED, fg=T.TEXT_MUTED, font=T.font(12.5),
                          anchor="w", justify="left", wraplength=200, width=30)
    card.state.pack(fill="x", pady=(8, 0))
    card.numbers = tk.Label(b, text="", bg=T.RAISED, fg=T.TEXT_2, font=T.mono(11),
                            anchor="w", justify="left")
    card.numbers.pack(fill="x", pady=(4, 0))
    card.btn = Button(b, "Connect", command=on_click, height=30, fill=T.INSET, fg=T.TEXT,
                      border=T.BORDER, hover_fill=T.ACCENT, hover_fg=T.CANVAS,
                      hover_border=T.ACCENT, min_width=200)
    card.btn.pack(fill="x", pady=(12, 0))
    card.connected = False
    card.look = None
    return card


def _update_glove_card(card, g: R.GloveState | None, s: R.Status | None, app):
    card.dot.set(_glove_colour(g))
    if g is None:
        card.state.configure(text="—", fg=T.TEXT_MUTED)
        card.numbers.configure(text="")
    else:
        word = {"connected": "Connected", "connecting": "Connecting…",
                "disconnected": "Not connected", "missing": "No glove handler in this app"
                }.get(g.state, g.state)
        text = word + (f"\n{g.message}" if g.message and g.message != word else "")
        card.state.configure(text=text, fg=T.SUCCESS if g.connected else T.TEXT_MUTED)
        numbers = []
        if g.battery_pct >= 0:
            numbers.append(f"battery {g.battery_pct}%")
        if g.connected and len(g.pressure_kpa) >= 7:
            numbers.append("kPa " + " ".join(f"{p:.0f}" for p in g.pressure_kpa[:6]) +
                           f"  src {g.pressure_kpa[6]:.0f}")
        hint = _this_computer_holds(app, g)
        if hint:
            numbers.append(hint)
        card.numbers.configure(text="\n".join(numbers))
    connected = bool(g and g.connected)
    usable = bool(s and s.allow_glove_control and not s.paused and g and g.state != "missing")
    text = ("Disconnect" if connected else
            "Connecting…" if g and g.state == "connecting" else "Connect")
    look = (text, usable, connected)
    if look != card.look:
        card.look = look
        card.connected = connected
        card.btn.set(text=text, disabled=not usable,
                     hover_fg=T.DANGER if connected else T.CANVAS,
                     hover_fill=T.INSET if connected else T.ACCENT,
                     hover_border=T.DANGER if connected else T.ACCENT)


def _stream_words(st: R.StreamState) -> tuple[str, str]:
    text, colour = {
        "off": ("Not shared. Watching asks the wearer to allow it in the headset.",
                T.TEXT_MUTED),
        "requesting": ("Waiting for the wearer to allow screen sharing in the headset…",
                       T.ACCENT),
        "live": (f"Shared · {st.width}×{st.height}" +
                 (f" · {st.viewers} watching" if st.viewers else ""), T.SUCCESS),
        "denied": ("The wearer said no. Ask to share asks again.", T.DANGER),
        "unsupported": ("This headset cannot share its view.", T.TEXT_MUTED),
        "error": ("Sharing failed.", T.DANGER),
    }.get(st.state, (st.state, T.TEXT_MUTED))
    if st.message and st.state in ("error", "denied", "unsupported"):
        text = f"{text} {st.message}"
    return text, colour


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
        return "This computer has a glove for this hand; disconnect it here first."
    return ""
