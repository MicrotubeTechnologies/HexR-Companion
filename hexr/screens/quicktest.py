"""The quick test: is this glove healthy? One button, one answer, shown on the glove.

Drives every channel to full pressure at once, watches what each one reaches and
how fast, then judges it. The answer comes first: one word, and the glove's touch
points in green (good), amber (poor) and red (failed). The evidence (each peak, how
long it took, what the pump managed) is under Details.

This is the pass/fail check you run on a glove coming off the bench or back from a
customer; the Test screen is for exploring, this is for deciding.

Ported from the Unity app's Quick Test. The verdict thresholds have since been
retuned, so results are not directly comparable with anything the Unity app
recorded.
"""

from __future__ import annotations

import time
import tkinter as tk
from dataclasses import dataclass

from .. import protocol as P
from .. import theme as T
from ..gloveview import GloveView
from ..haptics import FINGERS, HandState, level_from_kpa
from ..i18n import N_, tr
from ..state import HANDS
from ..widgets import Button, Divider, Progress, Segmented, Surface
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
# changes what the answer tells you to go and look at.
SOURCE_MIN_KPA = 10.0

RIGHT_W = 340

VERDICT_COLOURS = {
    "Good": T.SUCCESS,
    "Poor": T.WARN,
    "Fail": T.DANGER,
}
# How a verdict shows on the glove: its colour, and how brightly.
VERDICT_LOOK = {"Good": (T.SUCCESS, 1.0), "Poor": (T.WARN, .75), "Fail": (T.DANGER, .6)}


def _rgb(colour: str) -> tuple[int, int, int]:
    return tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))


def verdict(peak: float) -> str:
    """Good / Poor / Fail, from the peak this channel reached.

    The source reading does not enter into it. A channel is judged on what it
    delivered; whether a healthy pump or a dead one is the reason is said once,
    in the answer, instead of six times.
    """
    if peak > GOOD_KPA:
        return "Good"
    if peak >= FAIL_KPA:
        return "Poor"
    return "Fail"


@dataclass
class Judgement:
    verdicts: dict[int, str]
    headline: str            # already translated
    colour: str
    weak: list[int]          # the channels to look at, if the pump is not the reason


def judge(peaks: dict[int, float], source_peak: float) -> Judgement:
    verdicts = {ch: verdict(p) for ch, p in peaks.items()}
    failed = [ch for ch, v in verdicts.items() if v == "Fail"]
    poor = [ch for ch, v in verdicts.items() if v == "Poor"]
    if source_peak < SOURCE_MIN_KPA:
        return Judgement(verdicts, tr("Pump failed"), T.DANGER, [])
    if failed:
        return Judgement(verdicts, tr("{n} failed", n=len(failed)), T.DANGER, sorted(failed + poor))
    if poor:
        return Judgement(verdicts, tr("{n} poor", n=len(poor)), T.WARN, sorted(poor))
    return Judgement(verdicts, tr("All good"), T.SUCCESS, [])


class QuickTestScreen(Screen):
    title_text = N_("Quick test")
    sub_text = N_("Take the glove off first.")
    key = "quicktest"
    has_details = True
    fill = True

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._rows: dict[int, dict] = {}
        self.hand: str | None = None
        self.result: Judgement | None = None

        self._phase = "idle"        # idle | settle | drive | done
        self._t0 = 0.0
        self._peak: dict[int, float] = {}
        self._t_peak: dict[int, float] = {}
        self._source_peak = 0.0

        cols = tk.Frame(self.body, bg=T.SURFACE)
        cols.pack(fill="both", expand=True)
        left = tk.Frame(cols, bg=T.SURFACE)
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(cols, bg=T.SURFACE, width=RIGHT_W)
        right.pack(side="left", fill="y", padx=(28, 0))
        right.pack_propagate(False)

        self.glove = GloveView(left, min_gh=160, max_gh=360, names=True)
        self.glove.set_selected(None)
        self.glove.pack(fill="both", expand=True)
        self.picker = Segmented(left, [(h, tr(h)) for h in HANDS], command=self._pick_hand)

        self.headline = tk.Label(right, text="", bg=T.SURFACE, fg=T.TEXT, font=T.font(28, 600),
                                 anchor="w")
        self.headline.pack(fill="x", pady=(24, 0))
        self.weak = tk.Label(right, text="", bg=T.SURFACE, fg=T.TEXT_2, font=T.font(14),
                             anchor="w", justify="left", wraplength=RIGHT_W)
        self.weak.pack(fill="x", pady=(6, 0))
        tk.Frame(right, bg=T.SURFACE).pack(fill="both", expand=True)
        self.run_btn = Button(right, tr("Run"), command=self._toggle, glyph="▶", height=48,
                              font=T.font(15, 600))
        self.run_btn.pack(fill="x")
        self.progress = Progress(right)
        self.progress.pack(fill="x", pady=(14, 0))
        self.status = tk.Label(right, text="", bg=T.SURFACE, fg=T.TEXT_MUTED, font=T.font(12.5),
                               anchor="w")
        self.status.pack(fill="x", pady=(8, 0))

        # Details: the evidence behind the answer.
        self.evidence = tk.Frame(self.below, bg=T.SURFACE)
        self.evidence.pack(fill="x", pady=(18, 0))
        self.results = Surface(self.evidence)
        self.results.pack(fill="x")
        self._build_table()
        self.summary = tk.Label(self.evidence, text="", bg=T.SURFACE, fg=T.TEXT_MUTED,
                                font=T.font(12.5), anchor="w", justify="left", wraplength=760)
        self.summary.pack(fill="x", pady=(12, 0))
        self.show_details(self.details)

    def show_details(self, on: bool):
        self.show_details_below(on)

    # -- the evidence --------------------------------------------------------------------------

    def _build_table(self):
        head = tk.Frame(self.results, bg=T.RAISED)
        head.pack(fill="x", padx=18, pady=(12, 0))
        for i, (label, width) in enumerate(((tr("Channel"), 120), (tr("Peak"), 110),
                                            (tr("Time to peak"), 130),
                                            (tr("Verdict"), None))):
            section_label(head, label, bg=T.RAISED).grid(
                row=0, column=i, sticky="w", padx=(0, 10))
            if width:
                head.grid_columnconfigure(i, minsize=width)
            else:
                head.grid_columnconfigure(i, weight=1)
        Divider(self.results).pack(fill="x", pady=(8, 0))

        for finger in P.ALL_FINGERS:
            row = tk.Frame(self.results, bg=T.RAISED)
            row.pack(fill="x", padx=18)
            cells = {}
            for i, (text, font, width) in enumerate((
                    (tr(P.FINGER_LABELS[finger]), T.font(13), 120),
                    ("—", T.mono(11.5), 110),
                    ("—", T.mono(11.5), 130),
                    ("—", T.font(12.5), None))):
                lbl = tk.Label(row, text=text, bg=T.RAISED, fg=T.TEXT_2, font=font, anchor="w")
                lbl.grid(row=0, column=i, sticky="w", padx=(0, 10), pady=6)
                if width:
                    row.grid_columnconfigure(i, minsize=width)
                else:
                    row.grid_columnconfigure(i, weight=1)
                cells[i] = lbl
            self._rows[int(finger)] = cells
        tk.Frame(self.results, bg=T.RAISED, height=8).pack(fill="x")

    # -- run ------------------------------------------------------------------------------------

    def _pick_hand(self, hand):
        if self._phase in ("settle", "drive"):
            self.picker.set(self.hand)
            return
        g = self.app.state.get(hand)
        if g and g.connected and hand != self.hand:
            self.hand = hand
            self._clear()

    def _clear(self):
        self.result = None
        self._phase = "idle"
        self.headline.configure(text="")
        self.weak.configure(text="")
        self.status.configure(text="")
        self.progress.set(0.0)
        self.run_btn.set(text=tr("Run"), glyph="▶")
        for cells in self._rows.values():
            for i in (1, 2, 3):
                cells[i].configure(text="—", fg=T.TEXT_2)
        self.summary.configure(text="")

    def _toggle(self):
        if self._phase in ("settle", "drive"):
            self._abort(tr("Stopped"))
            return
        self._start()

    def _start(self):
        g = self.app.state.get(self.hand) if self.hand else None
        if not g or not g.connected:
            self.status.configure(text=tr("Connect a glove first"), fg=T.DANGER)
            return
        if not g.is_live():
            self.status.configure(text=tr("No readings from this glove"), fg=T.DANGER)
            return
        self._clear()
        self._peak = {int(f): 0.0 for f in P.ALL_FINGERS}
        self._t_peak = {int(f): 0.0 for f in P.ALL_FINGERS}
        self._source_peak = 0.0
        self.app.send([self.hand], P.all_off())
        self._phase = "settle"
        self._t0 = time.monotonic()
        self.run_btn.set(text=tr("Stop"), glyph="■")
        self.status.configure(text=tr("Venting…"), fg=T.TEXT_MUTED)

    def stop_if_running(self):
        """For closing the panel mid-sweep. The sweep advances on this screen's
        tick, which stops when it is hidden, so leaving it running would leave
        every channel at full pressure. Abort instead, which vents the glove."""
        if self._phase in ("settle", "drive"):
            self._abort(tr("Stopped"))

    def on_hide(self):
        self.stop_if_running()

    def _abort(self, why: str):
        self._phase = "idle"
        if self.hand:
            self.app.send([self.hand], P.all_off())
        self.progress.set(0.0)
        self.run_btn.set(text=tr("Run"), glyph="▶")
        self.status.configure(text=why, fg=T.TEXT_MUTED)

    def on_tick(self):
        self.refresh_hands()
        self._show_glove()
        if self._phase in ("idle", "done"):
            return
        g = self.app.state.get(self.hand) if self.hand else None
        if not g or not g.connected:
            self._abort(tr("Glove disconnected"))
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
                self.status.configure(text=tr("Driving all channels…"), fg=T.ACCENT)
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
        self.run_btn.set(text=tr("Run again"), glyph="▶")
        self.status.configure(text="")
        result = judge(self._peak, self._source_peak)
        self.result = result
        self.progress.set(1.0, result.colour)
        self.headline.configure(text=result.headline, fg=result.colour)
        self.weak.configure(text=", ".join(tr(P.FINGER_LABELS[P.Finger(ch)]) for ch in result.weak))

        good = sum(v == "Good" for v in result.verdicts.values())
        poor = sum(v == "Poor" for v in result.verdicts.values())
        failed = sum(v == "Fail" for v in result.verdicts.values())
        for chan, v in result.verdicts.items():
            peak = self._peak[chan]
            cells = self._rows[chan]
            cells[1].configure(text=f"{peak:.1f} kPa")
            cells[2].configure(text=f"{self._t_peak[chan]:.2f} s" if peak > 0 else "—")
            cells[3].configure(text=tr(v), fg=VERDICT_COLOURS.get(v, T.TEXT_2))

        breakdown = tr("{good} good, {poor} poor, {failed} failed",
                       good=good, poor=poor, failed=failed)
        kpa = f"{self._source_peak:.1f}"
        if self._source_peak < SOURCE_MIN_KPA:
            text = tr("The source never rose above {kpa} kPa, so no channel could have reached "
                      "pressure. This is one fault in the pump or its supply, not six failed "
                      "channels.", kpa=kpa)
        elif failed:
            text = tr("Source reached {kpa} kPa, so supply is fine — a channel reading nothing "
                      "with a healthy source is a blocked line, a valve that never opened, or a "
                      "dead indenter. {breakdown}.", kpa=kpa, breakdown=breakdown)
        elif poor:
            text = tr("Source reached {kpa} kPa. Every channel moved, but not all of them reached "
                      "full pressure — check the tubing on the weak ones. {breakdown}.",
                      kpa=kpa, breakdown=breakdown)
        else:
            text = tr("Source reached {kpa} kPa.", kpa=kpa)
        self.summary.configure(text=text)

    # -- the glove --------------------------------------------------------------------------------

    def _show_glove(self):
        if not self.hand:
            self.glove.set_states({})
            return
        hand = self.hand.lower()
        self.glove.set_hands([hand])
        g = self.app.state.get(self.hand)
        if self._phase == "done" and self.result:
            if self._source_peak < SOURCE_MIN_KPA:
                looks = [VERDICT_LOOK["Fail"]] * FINGERS
            else:
                looks = [VERDICT_LOOK[self.result.verdicts[ch]] for ch in range(FINGERS)]
            st = HandState(levels=[lv for _c, lv in looks], tints=[_rgb(c) for c, _lv in looks])
        elif self._phase == "drive" and g and g.is_live():
            st = HandState(levels=[level_from_kpa(k) for k in g.channel_kpa()])
        else:
            st = HandState()
        self.glove.set_states({hand: st})

    def refresh_hands(self):
        connected = [h for h in HANDS if (g := self.app.state.get(h)) and g.connected]
        hand = self.hand if self.hand in connected else (connected[0] if connected else None)
        if hand != self.hand:
            self.hand = hand
            self._clear()
        if len(connected) > 1:
            self.picker.set(self.hand)
            if not self.picker.winfo_manager():
                self.picker.pack(pady=(8, 0))
        elif self.picker.winfo_manager():
            self.picker.pack_forget()

    def refresh(self):
        self.refresh_hands()

    def on_show(self):
        self.refresh()
