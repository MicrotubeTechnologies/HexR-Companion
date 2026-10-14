"""Find gloves and connect them: the Test screen until a glove connects, then
the Gloves panel over it.

A kit is a left glove and a right glove, and they are independent BLE
peripherals. Both can be connected at once and the rest of the app treats
them separately throughout, so this screen is a list you connect from rather
than a chooser you pick one out of.
"""

from __future__ import annotations

import tkinter as tk

from .. import protocol as P
from .. import theme as T
from ..state import HANDS
from ..widgets import Button, Dot, Divider, Panel, Surface
from .base import Screen, section_label

# name | hand | address | signal | action
COLS = (None, 90, 150, 80, 130)


SCAN_TITLE = "Connect a HEXR glove"
SCAN_SUB = ("Power on the arm module and press scan. Left and right are "
            "separate devices — connect either, or both. Testing starts as soon "
            "as one connects.")
PANEL_TITLE = "Gloves"
PANEL_SUB = ("Connect the other glove, check battery and pressure, or "
             "disconnect.")


class ConnectScreen(Screen):
    title_text = SCAN_TITLE
    sub_text = SCAN_SUB

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._rows: dict[str, tk.Frame] = {}
        self._cards: dict[str, tk.Frame] = {}

        bar = tk.Frame(self.body, bg=T.SURFACE)
        bar.pack(fill="x")
        self._scan_label = "Scan for HEXR"
        self.scan_btn = Button(bar, self._scan_label, command=self._toggle_scan,
                               glyph="→", min_width=170)
        self.scan_btn.pack(side="left")
        self.scan_status = tk.Label(bar, text="Bluetooth ready", bg=T.SURFACE,
                                    fg=T.TEXT_MUTED, font=T.font(12.5))
        self.scan_status.pack(side="left", padx=(14, 0))

        self.results = Surface(self.body)
        self.results.pack(fill="x", pady=(18, 0))
        self._build_header()
        self.empty = tk.Label(
            self.results,
            text="No gloves yet. Press scan with the arm module switched on.",
            bg=T.RAISED, fg=T.TEXT_MUTED, font=T.font(12.5))
        self.empty.pack(fill="x", padx=18, pady=18)

        self.cards = tk.Frame(self.body, bg=T.SURFACE)
        self.cards.pack(fill="x", pady=(22, 0))

    def set_mode(self, panel: bool, on_close=None):
        """The scan in front of Test while nothing is connected, or the Gloves
        panel over it once something is."""
        self.set_heading(PANEL_TITLE if panel else SCAN_TITLE,
                         PANEL_SUB if panel else SCAN_SUB)
        self.set_close(on_close if panel else None)
        self._scan_label = "Scan for gloves" if panel else "Scan for HEXR"
        if not self.app.engine.scanning:
            self.scan_btn.set(text=self._scan_label, glyph="→")

    # -- results table -------------------------------------------------------

    def _build_header(self):
        head = tk.Frame(self.results, bg=T.RAISED)
        head.pack(fill="x", padx=18, pady=(14, 0))
        for i, (label, width) in enumerate(
                zip(("Device", "Hand", "Address", "Signal", ""), COLS)):
            lbl = section_label(head, label, bg=T.RAISED)
            lbl.grid(row=0, column=i, sticky="w", padx=(0, 10))
            if width:
                head.grid_columnconfigure(i, minsize=width)
            else:
                head.grid_columnconfigure(i, weight=1)
        Divider(self.results).pack(fill="x", pady=(10, 0))

    def add_result(self, found: dict):
        addr = found["address"]
        if addr in self._rows:
            return
        self.empty.pack_forget()
        row = tk.Frame(self.results, bg=T.RAISED)
        row.pack(fill="x", padx=18, pady=(0, 2))
        self._rows[addr] = row

        name = tk.Frame(row, bg=T.RAISED)
        name.grid(row=0, column=0, sticky="w", pady=9)
        Dot(name, color=T.SUCCESS, bg=T.RAISED).pack(side="left", pady=(4, 0))
        tk.Label(name, text=found["name"], bg=T.RAISED, fg=T.TEXT,
                 font=T.font(13)).pack(side="left", padx=(8, 0))

        cells = (found["hand"], found["address"],
                 f"{found['rssi']} dBm" if found.get("rssi") is not None else "—")
        for i, text in enumerate(cells, start=1):
            tk.Label(row, text=text, bg=T.RAISED, fg=T.TEXT_2,
                     font=T.mono(11.5)).grid(row=0, column=i, sticky="w",
                                             padx=(0, 10))

        btn = Button(row, "Connect", command=lambda f=found: self._connect(f),
                     height=30, fill=T.INSET, fg=T.TEXT, border=T.BORDER,
                     hover_fill=T.ACCENT, hover_fg=T.CANVAS,
                     hover_border=T.ACCENT, min_width=110)
        btn.grid(row=0, column=4, sticky="e")
        row.grid_columnconfigure(0, weight=1)
        for i, width in enumerate(COLS):
            if width:
                row.grid_columnconfigure(i, minsize=width)
        found["_button"] = btn

    def _connect(self, found: dict):
        self.app.connect_glove(found)
        btn = found.get("_button")
        if btn:
            btn.set(text="Connecting…", disabled=True)

    # -- scanning ------------------------------------------------------------

    def _toggle_scan(self):
        if self.app.engine.scanning:
            self.app.engine.stop_scan()
            return
        for row in self._rows.values():
            row.destroy()
        self._rows.clear()
        self.empty.pack(fill="x", padx=18, pady=18)
        self.scan_btn.set(text="Stop", glyph="■")
        self.scan_status.configure(text="Listening for gloves…", fg=T.TEXT_MUTED)
        self.app.engine.scan(self._on_result, self._on_done)

    def _on_result(self, found: dict):
        # Straight off the BLE thread — hop to Tk before touching a widget.
        self.after(0, lambda: self._add_safe(found))

    def _add_safe(self, found: dict):
        self.add_result(found)
        self.scan_status.configure(text=f"Found {len(self._rows)}", fg=T.SUCCESS)

    def _on_done(self, error):
        self.after(0, lambda: self._done_safe(error))

    def _done_safe(self, error):
        self.scan_btn.set(text=self._scan_label, glyph="→")
        if error:
            # A disabled adapter is not "no gloves found" — saying so sends
            # people hunting for a hardware fault that is not there.
            self.scan_status.configure(text=f"Bluetooth unavailable — {error}",
                                       fg=T.DANGER)
        elif not self._rows:
            self.scan_status.configure(
                text="Nothing found. Is the arm module switched on?",
                fg=T.TEXT_MUTED)
        else:
            self.scan_status.configure(text=f"Found {len(self._rows)}",
                                       fg=T.SUCCESS)

    # -- connected cards -----------------------------------------------------

    def refresh(self):
        """Rebuild the connected-glove cards. Cheap enough to do wholesale."""
        wanted = [h for h in HANDS
                  if (g := self.app.state.get(h)) and (g.connected or g.connecting)]
        if set(wanted) != set(self._cards):
            for w in self.cards.winfo_children():
                w.destroy()
            self._cards.clear()
            for hand in wanted:
                self._cards[hand] = self._build_card(hand)
        for hand, card in self._cards.items():
            self._update_card(hand, card)

    def _build_card(self, hand: str) -> tk.Frame:
        card = Panel(self.cards, bg=T.RAISED, pad=18)
        card.pack(side="left", padx=(0, 14), pady=(0, 4))
        b = card.body
        top = tk.Frame(b, bg=T.RAISED)
        top.pack(fill="x")
        card.dot = Dot(top, color=T.DOT_OFF, bg=T.RAISED)
        card.dot.pack(side="left", pady=(5, 0))
        tk.Label(top, text=f"{hand} glove", bg=T.RAISED, fg=T.TEXT,
                 font=T.font(15, 600)).pack(side="left", padx=(9, 0))
        card.status = tk.Label(b, text="", bg=T.RAISED, fg=T.TEXT_MUTED,
                               font=T.font(12.5), anchor="w")
        card.status.pack(fill="x", pady=(8, 0))
        card.batt = tk.Label(b, text="", bg=T.RAISED, fg=T.TEXT_2,
                             font=T.mono(11.5), anchor="w")
        card.batt.pack(fill="x", pady=(4, 0))
        Button(b, "Disconnect", command=lambda h=hand: self.app.disconnect(h),
               height=30, fill=T.INSET, fg=T.TEXT_2, border=T.BORDER,
               hover_fill=T.INSET, hover_fg=T.DANGER, hover_border=T.DANGER,
               min_width=140).pack(fill="x", pady=(14, 0))
        return card

    def _update_card(self, hand: str, card):
        g = self.app.state.get(hand)
        if not g:
            return
        live = g.is_live()
        card.dot.set(T.ACCENT if g.connecting else
                     T.SUCCESS if g.connected else T.DANGER)
        if g.connecting:
            card.status.configure(text="Connecting…", fg=T.TEXT_MUTED)
        elif live:
            card.status.configure(text="Connected · streaming", fg=T.SUCCESS)
        elif g.connected:
            # Connected and usable — it simply is not reporting pressure.
            # Flagged quietly, not as a fault: haptics work either way.
            card.status.configure(text="Connected", fg=T.SUCCESS)
        else:
            card.status.configure(text=g.status, fg=T.TEXT_MUTED)
        card.batt.configure(text=f"battery {g.battery_label()}   {g.address}")

    def on_show(self):
        self.refresh()
