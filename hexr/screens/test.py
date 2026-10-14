"""The Test screen once a glove is connected: drive channels by hand and watch
what the glove reports back.

Layout is control on the left, truth on the right: what you asked for, next to
what the hardware actually did. Testing a haptic device without the pressure
readout beside the controls means guessing whether a channel is weak or your
finger is just bad at telling 30 kPa from 40.
"""

from __future__ import annotations

import tkinter as tk

from .. import protocol as P
from .. import theme as T
from ..state import HANDS
from ..widgets import (Button, Cell, Divider, Meter, Panel, Readout, Slider,
                       Surface)
from .base import Screen, section_label

CHANNELS = [(int(f), P.FINGER_LABELS[f]) for f in P.ALL_FINGERS]

# The meters are scaled to the firmware's own ceiling, not to the highest
# value seen, so a weak channel looks weak instead of being normalised into
# looking fine.
METER_FULL_KPA = 60.0


class TestScreen(Screen):
    title_text = "Test the haptics"
    sub_text = ("Pick channels, set the strength, and trigger. Release vents "
                "them again — nothing switches itself off.")

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.settings = app.state.test
        self._chan_cells: dict[int, Cell] = {}
        self._hand_cells: dict[str, Cell] = {}
        self._mode_cells: dict[str, Cell] = {}
        self._meters: dict[int, Meter] = {}
        self._values: dict[int, tk.Label] = {}

        cols = tk.Frame(self.body, bg=T.SURFACE)
        cols.pack(fill="both", expand=True)
        left = tk.Frame(cols, bg=T.SURFACE)
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(cols, bg=T.SURFACE, width=430)
        right.pack(side="left", fill="y", padx=(24, 0))
        right.pack_propagate(False)

        self._build_hands(left)
        self._build_channels(left)
        self._build_mode(left)
        self._build_params(left)
        self._build_actions(left)
        self._build_monitor(right)

    # -- left: controls ------------------------------------------------------

    def _build_hands(self, parent):
        section_label(parent, "Hand").pack(fill="x")
        row = tk.Frame(parent, bg=T.SURFACE)
        row.pack(fill="x", pady=(8, 0))
        for hand in HANDS:
            c = Cell(row, hand, sub="not connected", command=self._toggle_hand,
                     height=52, mono_label=False)
            c.pack(side="left", fill="x", expand=True, padx=(0, 8))
            self._hand_cells[hand] = c

    def _build_channels(self, parent):
        head = tk.Frame(parent, bg=T.SURFACE)
        head.pack(fill="x", pady=(20, 0))
        section_label(head, "Channels").pack(side="left", pady=(6, 0))
        # These were grey text links sitting in the corner and nobody found
        # them. Selecting all six is the single most common thing done on this
        # screen, so it gets a real button.
        Button(head, "None", command=lambda: self._select(set()),
               height=28, fill=T.INSET, fg=T.TEXT_2, border=T.BORDER,
               hover_fill=T.INSET, hover_fg=T.TEXT, hover_border=T.TEXT_MUTED,
               padx=14, font=T.font(12, 600)).pack(side="right")
        Button(head, "Select all", command=lambda: self._select(
                   {c for c, _ in CHANNELS}),
               height=28, fill=T.INSET, fg=T.TEXT, border=T.BORDER,
               hover_fill=T.ACCENT, hover_fg=T.CANVAS, hover_border=T.ACCENT,
               padx=14, font=T.font(12, 600)).pack(side="right", padx=(0, 8))

        grid = tk.Frame(parent, bg=T.SURFACE)
        grid.pack(fill="x", pady=(8, 0))
        for i, (chan, label) in enumerate(CHANNELS):
            c = Cell(grid, label, command=self._toggle_channel, height=52,
                     mono_label=False)
            c.grid(row=i // 3, column=i % 3, sticky="ew", padx=(0, 8), pady=(0, 8))
            self._chan_cells[chan] = c
        for col in range(3):
            grid.grid_columnconfigure(col, weight=1)

    def _build_mode(self, parent):
        section_label(parent, "Mode").pack(fill="x", pady=(12, 0))
        row = tk.Frame(parent, bg=T.SURFACE)
        row.pack(fill="x", pady=(8, 0))
        for key, label, sub in (("pressure", "Pressure", "steady squeeze"),
                                ("vibration", "Vibration", "oscillating")):
            c = Cell(row, label, sub=sub, command=self._pick_mode, height=52,
                     mono_label=False)
            c.pack(side="left", fill="x", expand=True, padx=(0, 8))
            self._mode_cells[key] = c

    def _build_params(self, parent):
        self.params = tk.Frame(parent, bg=T.SURFACE)
        self.params.pack(fill="x", pady=(18, 0))

        self.intensity = self._slider("Intensity", 0.1, 1.0,
                                      self.settings.intensity, self._set_intensity)
        self.speed = self._slider("Ramp speed", 0.1, 1.0,
                                  self.settings.speed, self._set_speed)
        self.frequency = self._slider("Frequency", 0.1, 40.0,
                                      self.settings.frequency, self._set_frequency)
        self.peak = self._slider("Peak ratio", 0.2, 0.8,
                                 self.settings.peak_ratio, self._set_peak)

        self.regime = tk.Label(self.params, text="", bg=T.SURFACE,
                               fg=T.TEXT_FAINT, font=T.font(11.5),
                               anchor="w", justify="left", wraplength=430)
        self.regime.pack(fill="x", pady=(4, 0))

    def _slider(self, label, lo, hi, value, command):
        wrap = tk.Frame(self.params, bg=T.SURFACE)
        wrap.pack(fill="x", pady=(0, 14))
        head = tk.Frame(wrap, bg=T.SURFACE)
        head.pack(fill="x")
        section_label(head, label).pack(side="left")
        val = tk.Label(head, text="", bg=T.SURFACE, fg=T.TEXT,
                       font=T.mono(11.5))
        val.pack(side="right")
        s = Slider(wrap, value=value, lo=lo, hi=hi, command=command)
        s.pack(fill="x", pady=(6, 0))
        s.value_label = val
        s.wrap = wrap
        return s

    def _build_actions(self, parent):
        row = tk.Frame(parent, bg=T.SURFACE)
        row.pack(fill="x", pady=(6, 0))
        Button(row, "Trigger", command=self._trigger, glyph="▶",
               min_width=150).pack(side="left")
        Button(row, "Release", command=self._release, fill=T.INSET,
               fg=T.TEXT, border=T.BORDER, hover_fill=T.INSET,
               hover_fg=T.ACCENT, hover_border=T.ACCENT,
               min_width=130).pack(side="left", padx=(10, 0))
        Button(row, "All off", command=self.app.all_off, fill=T.INSET,
               fg=T.DANGER, border=T.BORDER, hover_fill=T.INSET,
               hover_fg=T.DANGER, hover_border=T.DANGER, glyph="■",
               min_width=130).pack(side="left", padx=(10, 0))

    # -- right: live monitor -------------------------------------------------

    def _build_monitor(self, parent):
        section_label(parent, "Live from the glove").pack(fill="x")
        self.monitor_hand = tk.Label(parent, text="", bg=T.SURFACE,
                                     fg=T.TEXT_MUTED, font=T.font(12),
                                     anchor="w")
        self.monitor_hand.pack(fill="x", pady=(6, 0))

        surf = Surface(parent)
        surf.pack(fill="x", pady=(12, 0))
        for chan, label in CHANNELS:
            row = tk.Frame(surf, bg=T.RAISED)
            row.pack(fill="x", padx=16, pady=(11, 0))
            tk.Label(row, text=label, bg=T.RAISED, fg=T.TEXT_2,
                     font=T.font(12), width=7, anchor="w").pack(side="left")
            val = tk.Label(row, text="—", bg=T.RAISED, fg=T.TEXT,
                           font=T.mono(11.5), width=9, anchor="e")
            val.pack(side="right")
            m = Meter(row, height=14)
            m.pack(side="left", fill="x", expand=True, padx=(10, 10))
            m.set(thr=0.0, on=True)
            self._meters[chan] = m
            self._values[chan] = val
        tk.Frame(surf, bg=T.RAISED, height=14).pack(fill="x")

        stats = tk.Frame(parent, bg=T.SURFACE)
        stats.pack(fill="x", pady=(16, 0))
        self.battery = Readout(stats, "Battery", "—")
        self.battery.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.source = Readout(stats, "Source", "—")
        self.source.pack(side="left", fill="x", expand=True)

        self.note = tk.Label(parent, text="", bg=T.SURFACE, fg=T.TEXT_FAINT,
                             font=T.font(11.5), anchor="w", justify="left",
                             wraplength=410)
        self.note.pack(fill="x", pady=(14, 0))

    # -- interaction ---------------------------------------------------------

    def _toggle_hand(self, label):
        if label in self.settings.hands:
            self.settings.hands.discard(label)
        else:
            self.settings.hands.add(label)
        self.refresh()

    def _toggle_channel(self, label):
        chan = next(c for c, l in CHANNELS if l == label)
        if chan in self.settings.channels:
            self.settings.channels.discard(chan)
        else:
            self.settings.channels.add(chan)
        self.refresh()

    def _select(self, channels: set):
        self.settings.channels = set(channels)
        self.refresh()

    def _pick_mode(self, label):
        self.settings.mode = label.lower()
        self.refresh()

    def _set_intensity(self, v):
        self.settings.intensity = v
        self.refresh()

    def _set_speed(self, v):
        self.settings.speed = v
        self.refresh()

    def _set_frequency(self, v):
        self.settings.frequency = v
        self.refresh()

    def _set_peak(self, v):
        self.settings.peak_ratio = v
        self.refresh()

    def _frames(self, on: bool) -> bytes:
        s = self.settings
        fingers = s.active_fingers()
        if s.mode == "vibration":
            return P.batch(
                P.vibration(f, on, s.frequency, s.intensity, s.peak_ratio)
                for f in fingers)
        return P.batch(P.pressure(f, on, s.intensity, s.speed) for f in fingers)

    def _trigger(self):
        self.app.send(self.settings.hands, self._frames(True))

    def _release(self):
        self.app.send(self.settings.hands, self._frames(False))

    # -- rendering -----------------------------------------------------------

    def refresh(self):
        s = self.settings
        for hand, cell in self._hand_cells.items():
            g = self.app.state.get(hand)
            live = bool(g and g.connected)
            cell.set(live and hand in s.hands)
            cell.sub = "connected" if live else "not connected"
            cell.render()
        for chan, cell in self._chan_cells.items():
            cell.set(chan in s.channels)
        for key, cell in self._mode_cells.items():
            cell.set(key == s.mode)

        vibrating = s.mode == "vibration"
        self.speed.wrap.pack_configure(**({} if not vibrating else {}))
        self._show(self.speed, not vibrating)
        self._show(self.frequency, vibrating)
        self._show(self.peak, vibrating)

        self.intensity.value_label.configure(
            text=f"{s.intensity:.2f}  ·  {P.intensity_to_kpa(s.intensity):.0f} kPa")
        self.speed.value_label.configure(text=f"{s.speed:.2f}")
        self.frequency.value_label.configure(text=f"{s.frequency:.1f} Hz")
        self.peak.value_label.configure(text=f"{s.peak_ratio:.2f}")

        if vibrating:
            # The firmware switches technique at 5 Hz, and the two feel nothing
            # alike. Saying which one is running turns a confusing result into
            # an expected one.
            if s.frequency < P.PWM_VIBRATION_HZ:
                self.regime.configure(
                    text=f"Under {P.PWM_VIBRATION_HZ:.0f} Hz the glove vibrates "
                         "pneumatically — the pressure target is pulsed.")
            else:
                self.regime.configure(
                    text=f"At {P.PWM_VIBRATION_HZ:.0f} Hz and above the pressure "
                         "loop is off and the channel's motor is driven directly.")
        else:
            self.regime.configure(text="")

    @staticmethod
    def _show(slider, visible: bool):
        if visible:
            if not slider.wrap.winfo_ismapped():
                slider.wrap.pack(fill="x", pady=(0, 14))
        else:
            slider.wrap.pack_forget()

    def on_tick(self):
        """Called on the app's UI tick — telemetry only, no layout work."""
        hands = [h for h in HANDS
                 if (g := self.app.state.get(h)) and g.connected]
        if not hands:
            self.monitor_hand.configure(text="No glove connected")
            for chan, _ in CHANNELS:
                self._meters[chan].set(value=0.0, over=False, on=False)
                self._values[chan].configure(text="—")
            self.battery.set("—")
            self.source.set("—")
            return

        # One monitor, so show a hand that is actually selected where possible.
        hand = next((h for h in hands if h in self.settings.hands), hands[0])
        g = self.app.state.get(hand)
        self.monitor_hand.configure(
            text=f"{hand} glove" + ("" if g.is_live() else "  ·  no telemetry"))
        for chan, _ in CHANNELS:
            kpa = g.kpa(chan)
            self._meters[chan].set(value=max(0.0, kpa) / METER_FULL_KPA,
                                   over=kpa > 1.0, on=True)
            self._values[chan].configure(text=f"{kpa:5.1f} kPa")
        self.battery.set(g.battery_label())
        self.source.set(f"{g.source_kpa():.1f} kPa")
        if g.absolute_pa:
            self.note.configure(
                text="This glove reports absolute pressure; readings are "
                     "converted to gauge kPa.")
        else:
            self.note.configure(text="")

    def on_show(self):
        self.refresh()
