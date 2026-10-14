"""The canned QA sweep, a panel over the Test screen.

Drives every channel to full pressure at once, watches what each one reaches
and how fast, then judges it. This is the pass/fail check you run on a glove
coming off the bench or back from a customer; the Test screen is for
exploring, this is for deciding.

Ported from the Unity app's Quick Test. The verdict thresholds have since been
retuned, so results are not directly comparable with anything the Unity app
recorded.
"""

from __future__ import annotations

import time
import tkinter as tk

from .. import protocol as P
from .. import theme as T
from ..state import HANDS
from ..widgets import Button, Cell, Divider, Progress, Surface
from .base import Screen, section_label

SETTLE_S = 0.6      # vent and let the channels fall back before baselining
DRIVE_S = 2.0       # how long each channel is held at full
# Three words, because three is what a decision needs: the channel is doing its
# job, it is doing some of it, or it is not doing it.
GOOD_KPA = 40.0     # above this the channel is delivering full pressure
FAIL_KPA = 2.0      # below this it is not working at all
# Sensors on a dead channel float on noise rather than reading a clean 0.0,
# which is why the failure line sits at 2 kPa and not at zero.

# If the source/tank never develops pressure, every channel reads Fail for one
# reason — a dead pump — and reporting six dead channels would send someone
# replacing the wrong parts. This does not change any channel's verdict; it
# changes what the summary tells you to go and look at.
SOURCE_MIN_KPA = 10.0

PASSING = ("Good",)

VERDICT_COLOURS = {
    "Good": T.SUCCESS,
    "Poor": T.ACCENT,
    "Fail": T.DANGER,
}


class QuickTestScreen(Screen):
    title_text = "Quick test"
    sub_text = ("Drives every channel to full for two seconds and reports what "
                "each one reached. Take the glove off first.")

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._hand_cells: dict[str, Cell] = {}
        self._rows: dict[int, dict] = {}
        self.hand: str | None = None

        self._phase = "idle"        # idle | settle | drive | done
        self._t0 = 0.0
        self._peak: dict[int, float] = {}
        self._t_peak: dict[int, float] = {}
        self._source_peak = 0.0

        section_label(self.body, "Glove to test").pack(fill="x")
        row = tk.Frame(self.body, bg=T.SURFACE)
        row.pack(fill="x", pady=(8, 0))
        for hand in HANDS:
            c = Cell(row, hand, sub="not connected", command=self._pick_hand,
                     height=52, mono_label=False)
            c.pack(side="left", fill="x", expand=True, padx=(0, 8))
            self._hand_cells[hand] = c

        bar = tk.Frame(self.body, bg=T.SURFACE)
        bar.pack(fill="x", pady=(20, 0))
        self.run_btn = Button(bar, "Run quick test", command=self._toggle,
                              glyph="▶", min_width=180)
        self.run_btn.pack(side="left")
        self.status = tk.Label(bar, text="", bg=T.SURFACE, fg=T.TEXT_MUTED,
                               font=T.font(12.5))
        self.status.pack(side="left", padx=(14, 0))

        self.progress = Progress(self.body)
        self.progress.pack(fill="x", pady=(14, 0))

        self.results = Surface(self.body)
        self.results.pack(fill="x", pady=(20, 0))
        self._build_table()

        self.summary = tk.Label(self.body, text="", bg=T.SURFACE,
                                fg=T.TEXT_MUTED, font=T.font(12.5),
                                anchor="w", justify="left", wraplength=760)
        self.summary.pack(fill="x", pady=(16, 0))

    # -- table ---------------------------------------------------------------

    def _build_table(self):
        head = tk.Frame(self.results, bg=T.RAISED)
        head.pack(fill="x", padx=18, pady=(14, 0))
        for i, (label, width) in enumerate((("Channel", 120), ("Peak", 110),
                                            ("Time to peak", 130),
                                            ("Verdict", None))):
            section_label(head, label, bg=T.RAISED).grid(
                row=0, column=i, sticky="w", padx=(0, 10))
            if width:
                head.grid_columnconfigure(i, minsize=width)
            else:
                head.grid_columnconfigure(i, weight=1)
        Divider(self.results).pack(fill="x", pady=(10, 0))

        for finger in P.ALL_FINGERS:
            row = tk.Frame(self.results, bg=T.RAISED)
            row.pack(fill="x", padx=18)
            cells = {}
            for i, (text, font, width) in enumerate((
                    (P.FINGER_LABELS[finger], T.font(13), 120),
                    ("—", T.mono(11.5), 110),
                    ("—", T.mono(11.5), 130),
                    ("—", T.font(12.5), None))):
                lbl = tk.Label(row, text=text, bg=T.RAISED, fg=T.TEXT_2,
                               font=font, anchor="w")
                lbl.grid(row=0, column=i, sticky="w", padx=(0, 10), pady=9)
                if width:
                    row.grid_columnconfigure(i, minsize=width)
                else:
                    row.grid_columnconfigure(i, weight=1)
                cells[i] = lbl
            self._rows[int(finger)] = cells
        tk.Frame(self.results, bg=T.RAISED, height=8).pack(fill="x")

    # -- run ------------------------------------------------------------------

    def _pick_hand(self, label):
        g = self.app.state.get(label)
        if g and g.connected:
            self.hand = label
            self.refresh()

    def _toggle(self):
        if self._phase in ("settle", "drive"):
            self._abort("Stopped")
            return
        self._start()

    def _start(self):
        g = self.app.state.get(self.hand) if self.hand else None
        if not g or not g.connected:
            self.status.configure(text="Connect a glove first", fg=T.DANGER)
            return
        if not g.is_live():
            self.status.configure(
                text="That glove is not sending telemetry — nothing to measure",
                fg=T.DANGER)
            return
        self._peak = {int(f): 0.0 for f in P.ALL_FINGERS}
        self._t_peak = {int(f): 0.0 for f in P.ALL_FINGERS}
        self._source_peak = 0.0
        for cells in self._rows.values():
            for i in (1, 2, 3):
                cells[i].configure(text="—", fg=T.TEXT_2)
        self.summary.configure(text="")
        self.app.send([self.hand], P.all_off())
        self._phase = "settle"
        self._t0 = time.monotonic()
        self.run_btn.set(text="Stop", glyph="■")
        self.status.configure(text="Venting…", fg=T.TEXT_MUTED)

    def stop_if_running(self):
        """For closing the panel mid-sweep. The sweep advances on this screen's
        tick, which stops when it is hidden, so leaving it running would leave
        every channel at full pressure. Abort instead, which vents the glove."""
        if self._phase in ("settle", "drive"):
            self._abort("Stopped")

    def _abort(self, why: str):
        self._phase = "idle"
        if self.hand:
            self.app.send([self.hand], P.all_off())
        self.progress.set(0.0)
        self.run_btn.set(text="Run quick test", glyph="▶")
        self.status.configure(text=why, fg=T.TEXT_MUTED)

    def on_tick(self):
        self.refresh_hands()
        if self._phase in ("idle", "done"):
            return
        g = self.app.state.get(self.hand) if self.hand else None
        if not g or not g.connected:
            self._abort("Glove disconnected")
            return

        elapsed = time.monotonic() - self._t0
        if self._phase == "settle":
            self.progress.set(min(1.0, elapsed / SETTLE_S), T.TEXT_FAINT)
            if elapsed >= SETTLE_S:
                # Everything at once, exactly as the Unity test did — it also
                # exercises whether the pump can keep up with six channels.
                self.app.send([self.hand], P.batch(
                    P.pressure(f, True, 1.0, 1.0) for f in P.ALL_FINGERS))
                self._phase = "drive"
                self._t0 = time.monotonic()
                self.status.configure(text="Driving all channels…", fg=T.ACCENT)
            return

        # drive
        self.progress.set(min(1.0, elapsed / DRIVE_S), T.ACCENT)
        self._source_peak = max(self._source_peak, g.source_kpa())
        for finger in P.ALL_FINGERS:
            chan = int(finger)
            kpa = g.kpa(chan)
            if kpa > self._peak[chan]:
                self._peak[chan] = kpa
                self._t_peak[chan] = elapsed
        if elapsed >= DRIVE_S:
            self._finish()

    def _finish(self):
        self.app.send([self.hand], P.all_off())
        self._phase = "done"
        self.progress.set(1.0, T.SUCCESS)
        self.run_btn.set(text="Run quick test", glyph="▶")

        pump_dead = self._source_peak < SOURCE_MIN_KPA
        good = poor = failed = 0
        for finger in P.ALL_FINGERS:
            chan = int(finger)
            peak = self._peak[chan]
            verdict = self._verdict(peak)
            if verdict == "Good":
                good += 1
            elif verdict == "Poor":
                poor += 1
            else:
                failed += 1
            cells = self._rows[chan]
            cells[1].configure(text=f"{peak:.1f} kPa")
            cells[2].configure(
                text=f"{self._t_peak[chan]:.2f} s" if peak > 0 else "—")
            cells[3].configure(text=verdict,
                               fg=VERDICT_COLOURS.get(verdict, T.TEXT_2))

        breakdown = f"{good} good, {poor} poor, {failed} failed"
        source = f"Source reached {self._source_peak:.1f} kPa"

        if pump_dead:
            self.status.configure(text="Pump failed", fg=T.DANGER)
            self.summary.configure(
                text=f"The source never rose above {self._source_peak:.1f} kPa, "
                     "so no channel could have reached pressure. This is one "
                     "fault in the pump or its supply, not six failed channels.",
                fg=T.DANGER)
        elif failed:
            self.status.configure(text=f"{failed} of 6 channels failed",
                                  fg=T.DANGER)
            self.summary.configure(
                text=f"{source}, so supply is fine — a channel reading nothing "
                     "with a healthy source is a blocked line, a valve that "
                     f"never opened, or a dead indenter. {breakdown}.",
                fg=T.DANGER)
        elif poor:
            self.status.configure(text=f"{poor} of 6 channels poor", fg=T.ACCENT)
            self.summary.configure(
                text=f"{source}. Every channel moved, but not all of them "
                     "reached full pressure — check the tubing on the weak "
                     f"ones. {breakdown}.",
                fg=T.TEXT_MUTED)
        else:
            self.status.configure(text="All 6 channels good", fg=T.SUCCESS)
            self.summary.configure(text=f"{source}.", fg=T.TEXT_MUTED)

    @staticmethod
    def _verdict(peak: float) -> str:
        """Good / Poor / Fail, from the peak this channel reached.

        The source reading does not enter into it. A channel is judged on what
        it delivered; whether a healthy pump or a dead one is the reason sits in
        the summary, where it can be said once instead of six times.
        """
        if peak > GOOD_KPA:
            return "Good"
        if peak >= FAIL_KPA:
            return "Poor"
        return "Fail"

    # -- rendering -----------------------------------------------------------

    def refresh_hands(self):
        for hand, cell in self._hand_cells.items():
            g = self.app.state.get(hand)
            live = bool(g and g.connected)
            if self.hand == hand and not live:
                self.hand = None
            cell.set(live and self.hand == hand)
            cell.sub = "connected" if live else "not connected"
            cell.render()
        if self.hand is None:
            for hand in HANDS:
                g = self.app.state.get(hand)
                if g and g.connected:
                    self.hand = hand
                    break

    def refresh(self):
        self.refresh_hands()

    def on_show(self):
        self.refresh()
