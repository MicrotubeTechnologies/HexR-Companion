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

VIEW_W = 480
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
        if self._ticks % LIST_EVERY == 0:
            self._refresh()
        if self._detail:
            self._detail.pump_video()

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
            self._detail = _Detail(self.detail_host, self.model, row.key, self.app)
            self._detail.pack(fill="x")
        self._detail.update(row)


class _Detail(tk.Frame):
    """The picked headset: gloves, scene, commands and view."""

    def __init__(self, parent, model: Headsets, key: str, app):
        super().__init__(parent, bg=T.SURFACE)
        self.model = model
        self.key = key
        self.app = app
        self.video: R.VideoReceiver | None = None
        self._photo: tk.PhotoImage | None = None
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
        self.cards = {hand: self._glove_card(gloves, hand) for hand in R.HANDS}
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

        # -- view
        section_label(self, "View").pack(fill="x", pady=(18, 8))
        vbar = tk.Frame(self, bg=T.SURFACE)
        vbar.pack(fill="x")
        self.view_btn = Button(vbar, "Watch", command=self._toggle_view, glyph="▶",
                               min_width=150)
        self.view_btn.pack(side="left")
        self.view_status = tk.Label(vbar, text="", bg=T.SURFACE, fg=T.TEXT_MUTED,
                                    font=T.font(12.5), anchor="w", justify="left",
                                    wraplength=640)
        self.view_status.pack(side="left", padx=(14, 0))
        self.screen = tk.Label(self, bg=T.CANVAS, bd=0)
        self.screen.pack(anchor="w", pady=(12, 0))
        self._view_wanted = False
        self._last_stream = R.StreamState()
        self._unavailable = R.video_available()

    def _glove_card(self, parent, hand: str):
        card = Panel(parent, bg=T.RAISED, pad=16)
        card.pack(side="left", padx=(0, 14), anchor="n")
        b = card.body
        top = tk.Frame(b, bg=T.RAISED)
        top.pack(fill="x")
        card.dot = Dot(top, color=T.DOT_OFF, bg=T.RAISED)
        card.dot.pack(side="left", pady=(5, 0))
        tk.Label(top, text=f"{hand.capitalize()} glove", bg=T.RAISED, fg=T.TEXT,
                 font=T.font(14, 600)).pack(side="left", padx=(9, 0))
        # A fixed width in characters keeps both cards the same size, and wrapping inside it
        # rather than past it keeps a long status from being cut off.
        card.state = tk.Label(b, text="", bg=T.RAISED, fg=T.TEXT_MUTED, font=T.font(12.5),
                              anchor="w", justify="left", wraplength=200, width=30)
        card.state.pack(fill="x", pady=(8, 0))
        card.numbers = tk.Label(b, text="", bg=T.RAISED, fg=T.TEXT_2, font=T.mono(11),
                                anchor="w", justify="left")
        card.numbers.pack(fill="x", pady=(4, 0))
        card.btn = Button(b, "Connect", command=lambda h=hand: self._glove_clicked(h),
                          height=30, fill=T.INSET, fg=T.TEXT, border=T.BORDER,
                          hover_fill=T.ACCENT, hover_fg=T.CANVAS, hover_border=T.ACCENT,
                          min_width=200)
        card.btn.pack(fill="x", pady=(12, 0))
        card.connected = False
        card.look = None
        return card

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
            self._update_card(card, s.gloves.get(hand) if s else None, s)

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

    def _update_card(self, card, g: R.GloveState | None, s: R.Status | None):
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
            hint = _this_computer_holds(self.app, g)
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
        self._stop_video()
        self.model.forget(self.key)

    # -- view --------------------------------------------------------------------

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

    def _update_view(self, r: HeadsetRow):
        if self._unavailable:
            self.view_btn.set(text="Watch", disabled=True)
            self.view_status.configure(text=self._unavailable, fg=T.TEXT_MUTED)
            return
        s = r.status
        st = s.stream if s else R.StreamState()
        self._last_stream = st
        if s and not s.allow_video:
            self.view_btn.set(text="Watch", disabled=True)
            self.view_status.configure(text="This app does not share its view.",
                                       fg=T.TEXT_MUTED)
            return

        live = st.state == "live" and st.port > 0
        if live and self._view_wanted and self.video is None:
            w = VIEW_W
            h = int(VIEW_W * st.height / st.width) // 2 * 2 if st.width else VIEW_W
            self.video = R.VideoReceiver(r.host, st.port, (w, h))
        if not live and self.video is not None and st.state != "requesting":
            self._stop_video()
        if self._view_wanted or self.video:
            self.view_btn.set(text="Stop watching", glyph="■", disabled=False,
                              fill=T.INSET, fg=T.DANGER, border=T.DANGER,
                              hover_fill=T.INSET, hover_fg=T.DANGER, hover_border=T.DANGER)
        else:
            self.view_btn.set(text="Watch" if not live else "Watch (shared now)", glyph="▶",
                              disabled=bool(s and s.paused and not live), fill=T.ACCENT,
                              fg=T.CANVAS, border=T.ACCENT, hover_fill=T.ACCENT_HOVER,
                              hover_fg=T.CANVAS, hover_border=T.ACCENT_HOVER)

        text, colour = {
            "off": ("Not shared. Watch asks the wearer to allow it in the headset.",
                    T.TEXT_MUTED),
            "requesting": ("Waiting for the wearer to allow screen sharing in the headset…",
                           T.ACCENT),
            "live": (f"Shared · {st.width}×{st.height}" +
                     (f" · {st.viewers} watching" if st.viewers else ""), T.SUCCESS),
            "denied": ("The wearer said no. Watch asks again.", T.DANGER),
            "unsupported": ("This headset cannot share its view.", T.TEXT_MUTED),
            "error": ("Sharing failed.", T.DANGER),
        }.get(st.state, (st.state, T.TEXT_MUTED))
        if st.message and st.state in ("error", "denied", "unsupported"):
            text = f"{text} {st.message}"
        if self.video and self.video.state == "failed":
            text, colour = self.video.message, T.DANGER
        elif self.video and self.video.state == "connecting":
            text = "Connecting to the view…"
        self.view_status.configure(text=text, fg=colour)
        if st.state == "denied" and self._view_wanted:
            self._view_wanted = False

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
        self.screen.configure(image=self._photo)

    def _stop_video(self):
        if self.video:
            self.video.stop()
            self.video = None
        self.screen.configure(image="")
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
