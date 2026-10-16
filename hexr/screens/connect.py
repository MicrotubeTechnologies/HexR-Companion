"""Connect gloves: two gloves, left and right, that light up as they connect.

This is the Test screen until a glove connects, and the Gloves panel over it after.
It searches by itself while it is on screen (there is nothing else to do here until a
glove turns up), so the only thing to press is Connect.

A kit is a left glove and a right glove, independent BLE peripherals. Both can be
connected at once and the rest of the app treats them separately throughout.
"""

from __future__ import annotations

import time
import tkinter as tk
from types import SimpleNamespace

from .. import theme as T
from ..gloveview import GloveView
from ..haptics import FINGERS, HandState, level_from_kpa
from ..i18n import N_, tr
from ..state import HANDS
from ..widgets import Button, Dot, SignalBars
from .base import Screen

SCAN_TITLE = N_("Connect a glove")
SCAN_SUB = N_("Switch on the arm module.")
PANEL_TITLE = N_("Gloves")

SCAN_PAUSE_MS = 1500      # between one search and the next
RETRY_MS = 10000          # after Bluetooth failed, try again this much later
FORGET_S = 20.0           # a glove not heard from in this long has gone
DOTS_EVERY = 8            # ticks per step of the searching dots

GREEN = tuple(int(T.SUCCESS[i:i + 2], 16) for i in (1, 3, 5))


class ConnectScreen(Screen):
    title_text = SCAN_TITLE
    sub_text = SCAN_SUB
    key = "connect"
    has_details = True
    fill = True

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.found: dict[str, dict] = {}         # address -> what the search heard, + "seen"
        self.error: str | None = None
        self.panel = False
        self._visible = False
        self._scan_after = None
        self._ticks = 0
        self._dots = 0

        row = tk.Frame(self.body, bg=T.SURFACE)
        row.pack(fill="both", expand=True)
        self.slots = {hand: self._slot(row, hand) for hand in HANDS}
        self.show_details(self.details)

    def _slot(self, parent, hand: str) -> SimpleNamespace:
        col = tk.Frame(parent, bg=T.SURFACE)
        col.pack(side="left", fill="both", expand=True)
        glove = GloveView(col, min_gh=140, max_gh=320)
        glove.set_hands([hand.lower()])
        glove.set_selected(None)
        glove.pack(fill="both", expand=True)
        tk.Label(col, text=tr(hand), bg=T.SURFACE, fg=T.TEXT,
                 font=T.font(16, 600)).pack(pady=(4, 0))
        status = tk.Frame(col, bg=T.SURFACE)
        status.pack(pady=(4, 0))
        dot = Dot(status, color=T.DOT_OFF)
        dot.pack(side="left", pady=(3, 0))
        word = tk.Label(status, text="", bg=T.SURFACE, fg=T.TEXT_MUTED, font=T.font(13))
        word.pack(side="left", padx=(8, 0))
        bars = SignalBars(status)
        holder = tk.Frame(col, bg=T.SURFACE, height=46)
        holder.pack(fill="x", pady=(10, 0))
        holder.pack_propagate(False)
        btn = Button(holder, tr("Connect"), command=lambda h=hand: self._button(h), min_width=150)
        details = tk.Label(col, text="", bg=T.SURFACE, fg=T.TEXT_FAINT, font=T.mono(11),
                           justify="center")
        return SimpleNamespace(hand=hand, glove=glove, dot=dot, word=word, bars=bars,
                               holder=holder, btn=btn, details=details, action=None,
                               look=None)

    def set_mode(self, panel: bool, on_close=None):
        """Connecting, in front of Test while nothing is connected; or the Gloves
        panel over it once something is."""
        self.panel = panel
        self.set_heading(tr(PANEL_TITLE if panel else SCAN_TITLE),
                         "" if panel else tr(SCAN_SUB))
        self.set_close(on_close if panel else None)

    def show_details(self, on: bool):
        for slot in self.slots.values():
            if on:
                slot.details.pack(pady=(6, 0))
            else:
                slot.details.pack_forget()

    # -- searching ----------------------------------------------------------------------------

    def on_show(self):
        self._visible = True
        self.refresh()
        self._kick()

    def on_hide(self):
        self._visible = False
        if self._scan_after:
            self.after_cancel(self._scan_after)
            self._scan_after = None
        if self.app.engine.scanning:
            self.app.engine.stop_scan()

    def _schedule(self, ms: int):
        if self._scan_after:
            self.after_cancel(self._scan_after)
        self._scan_after = self.after(ms, self._kick)

    def _kick(self):
        """Search again, unless there is no need: off screen, both gloves connected, a
        connection being made (searching gets in its way), or a search already running."""
        self._scan_after = None
        if not self._visible or not self.winfo_exists():
            return
        engine = self.app.engine
        gloves = self.app.state.gloves.values()
        busy = any(g.connecting for g in gloves)
        wanted = not all((g := self.app.state.get(h)) and g.connected for h in HANDS)
        if engine.scanning or busy or not wanted:
            self._schedule(SCAN_PAUSE_MS)
            return
        engine.scan(self._on_result, self._on_done)

    def _on_result(self, found: dict):
        # Straight off the BLE thread: hop to Tk before touching anything.
        self.after(0, lambda: self._heard(found))

    def _heard(self, found: dict):
        if not self.winfo_exists():
            return
        self.found[found["address"]] = {**found, "seen": time.monotonic()}
        self.error = None
        self.refresh()

    def _on_done(self, error):
        self.after(0, lambda: self._done(error))

    def _done(self, error):
        if not self.winfo_exists():
            return
        # A disabled adapter is not "no gloves found": saying so sends people hunting
        # for a hardware fault that is not there.
        self.error = error or None
        self._schedule(RETRY_MS if error else SCAN_PAUSE_MS)
        self.refresh()

    def candidates(self, hand: str) -> list[dict]:
        """Gloves of this hand heard lately, strongest first."""
        now = time.monotonic()
        for addr in [a for a, f in self.found.items() if now - f["seen"] > FORGET_S]:
            del self.found[addr]
        return sorted((f for f in self.found.values() if f["hand"] == hand),
                      key=lambda f: f.get("rssi") if f.get("rssi") is not None else -999,
                      reverse=True)

    # -- what each glove's slot says ------------------------------------------------------------

    def _button(self, hand: str):
        action = self.slots[hand].action
        if action == "connect":
            options = self.candidates(hand)
            if len(options) == 1:
                self._connect(options[0])
            elif options:
                self._choose(hand, options)
        elif action == "disconnect":
            self.app.disconnect(hand)
        elif action == "retry":
            self.error = None
            self._schedule(10)
        self.refresh()

    def _choose(self, hand: str, options: list[dict]):
        """Two kits nearby, both "HaptGloveAR Left": pick by the end of the address."""
        m = tk.Menu(self, tearoff=0, bg=T.RAISED, fg=T.TEXT, activebackground=T.ACCENT,
                    activeforeground=T.CANVAS, bd=0, relief="flat", font=T.font(12.5))
        for f in options:
            bars = "▂▄▆█"[:SignalBars.bars(f.get("rssi"))] or "·"
            m.add_command(label=f"{f['name']}  ·  {f['address'][-5:]}   {bars}",
                          command=lambda f=f: self._connect(f))
        btn = self.slots[hand].btn
        try:
            m.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())
        finally:
            m.grab_release()

    def _connect(self, found: dict):
        if self.app.engine.scanning:
            self.app.engine.stop_scan()      # a running search slows the connection down
        self.app.connect_glove(found)
        self.refresh()

    def refresh(self):
        for hand, slot in self.slots.items():
            self._update(hand, slot)

    def _update(self, hand: str, slot: SimpleNamespace):
        g = self.app.state.get(hand)
        options = self.candidates(hand)
        dim, levels, tints = 0.3, [0.0] * FINGERS, None
        details = ""
        if g and g.connected:
            live = g.is_live()
            battery = g.battery_label()
            word, colour = tr("Connected") + ("" if battery == "—" else f" · {battery}"), T.SUCCESS
            action, label = ("disconnect", tr("Disconnect")) if self.panel else (None, "")
            dim = 1.0
            # Lit green to say it is here; a fingertip pressing on something glows orange.
            kpa = [level_from_kpa(k) for k in g.channel_kpa()] if live else [0.0] * FINGERS
            levels = [max(.32, k) for k in kpa]
            tints = [None if k > .32 else GREEN for k in kpa]
            details = "\n".join(filter(None, [
                g.address, tr("battery {level}", level=battery),
                tr("Source {kpa} kPa", kpa=f"{g.source_kpa():.1f}") if live else tr("no telemetry")]))
        elif g and g.connecting:
            word, colour = tr("Connecting…"), T.ACCENT
            action, label, dim = "busy", tr("Connecting…"), 0.7
            details = g.address
        elif g and g.status.startswith("Error: "):
            word, colour = tr("Could not connect"), T.DANGER
            action, label = ("connect", tr("Connect")) if options else (None, "")
            details = g.status[len("Error: "):]
        elif options:
            word, colour = tr("Found"), T.SUCCESS
            action, label, dim = "connect", tr("Connect"), 0.6
            details = "\n".join(f"{f['address']}  {f.get('rssi', '—')} dBm" for f in options)
        elif self.error:
            word, colour = tr("Bluetooth unavailable"), T.DANGER
            action, label = "retry", tr("Try again")
            details = tr("Bluetooth unavailable — {error}", error=self.error)
        else:
            word = tr("Searching") + "." * self._dots + " " * (3 - self._dots)
            colour, action, label = T.DOT_OFF, None, ""

        look = (word, colour, action, label)
        if look != slot.look:
            slot.look = look
            slot.word.configure(text=word, fg=T.TEXT if colour not in (T.DOT_OFF,) else T.TEXT_MUTED)
            slot.dot.set(colour)
            slot.action = action
            if label:
                primary = action == "connect"
                slot.btn.set(text=label, disabled=action == "busy",
                             fill=T.ACCENT if primary else T.INSET,
                             fg=T.CANVAS if primary else T.TEXT,
                             border=T.ACCENT if primary else T.BORDER,
                             hover_fill=T.ACCENT_HOVER if primary else T.INSET,
                             hover_fg=T.CANVAS if primary else (
                                 T.DANGER if action == "disconnect" else T.ACCENT),
                             hover_border=T.ACCENT_HOVER if primary else (
                                 T.DANGER if action == "disconnect" else T.ACCENT))
                slot.btn.place(relx=0.5, rely=0, anchor="n")
            else:
                slot.btn.place_forget()
        if options and not (g and (g.connected or g.connecting)):
            slot.bars.set(options[0].get("rssi"))
            if not slot.bars.winfo_manager():
                slot.bars.pack(side="left", padx=(8, 0), pady=(2, 0))
        elif slot.bars.winfo_manager():
            slot.bars.pack_forget()
        slot.glove.set_dim({hand.lower(): dim})
        slot.glove.set_states({hand.lower(): HandState(levels=levels, tints=tints)})
        slot.details.configure(text=details)

    def on_tick(self):
        self._ticks += 1
        if self._ticks % DOTS_EVERY == 0:
            self._dots = (self._dots + 1) % 4
        self.refresh()
