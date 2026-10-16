"""Test the glove by hand: tap its fingertips, then press and hold to feel them.

The glove is the screen. Tap a touch point to pick it; press and hold the pad and the
glove presses back, for as long as the pad is held, the way a hand meets an object.
The same glove lights up with what the glove measures, so what was asked for and
what the hardware did are one picture rather than two columns. The numbers behind it
(kPa, the source, how the firmware drives a vibration) are under Details.

"Keep on" turns the pad into a switch for longer runs. Escape, Release all, leaving
the screen and the window losing focus all let go.
"""

from __future__ import annotations

import time
import tkinter as tk

from .. import protocol as P
from .. import theme as T
from ..gloveview import GloveView, pad_state
from ..i18n import N_, tr
from ..state import HANDS
from ..widgets import (Button, Disclosure, HoldButton, Segmented, Slider, StatusChip,
                       TextLink, Toggle)
from .base import Screen

RIGHT_W = 340


class TestScreen(Screen):
    title_text = N_("Test")
    key = "test"
    has_details = True
    fill = True

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.settings = app.state.test
        self._pressed_at = 0.0
        self._released_at: float | None = None
        self.keep = False

        Button(self.head_actions, tr("Quick test"), command=lambda: app.open_panel("quicktest"),
               height=32, fill=T.RAISED, fg=T.TEXT, border=T.BORDER, hover_fill=T.INSET,
               hover_fg=T.ACCENT, hover_border=T.ACCENT, padx=16,
               font=T.font(12.5, 600)).pack(side="right")

        cols = tk.Frame(self.body, bg=T.SURFACE)
        cols.pack(fill="both", expand=True)
        left = tk.Frame(cols, bg=T.SURFACE)
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(cols, bg=T.SURFACE, width=RIGHT_W)
        right.pack(side="left", fill="y", padx=(28, 0))
        right.pack_propagate(False)
        self._build_glove(left)
        self._build_controls(right)
        self.show_details(self.details)
        self.winfo_toplevel().bind("<FocusOut>", self._focus_out, add="+")

    # -- the glove ------------------------------------------------------------------------------

    def _build_glove(self, parent):
        self.glove = GloveView(parent, caption=True, names=True, min_gh=160, max_gh=380,
                               on_toggle=lambda _hand, ch: self._toggle_channel(ch))
        self.glove.pack(fill="both", expand=True)

        under = tk.Frame(parent, bg=T.SURFACE)
        under.pack(fill="x", pady=(8, 0))
        self.hand_chips = tk.Frame(under, bg=T.SURFACE)
        self._chips = {}
        for hand in HANDS:
            chip = StatusChip(self.hand_chips, tr(hand),
                              command=lambda _e, h=hand: self._toggle_hand(h))
            chip.pack(side="left", padx=(0, 8))
            self._chips[hand] = chip
        links = tk.Frame(under, bg=T.SURFACE)
        links.pack(side="right")
        TextLink(links, tr("All"), command=lambda: self._select(set(range(6)))).pack(side="left")
        tk.Label(links, text="·", bg=T.SURFACE, fg=T.TEXT_OFF).pack(side="left", padx=4)
        TextLink(links, tr("None"), command=lambda: self._select(set())).pack(side="left")
        self.hint = tk.Label(under, text=tr("Tap a finger"), bg=T.SURFACE, fg=T.TEXT_FAINT,
                             font=T.font(13))
        self.info = tk.Label(parent, text="", bg=T.SURFACE, fg=T.TEXT_FAINT, font=T.mono(11),
                             anchor="w", justify="left")

    # -- how it feels, and the pad ------------------------------------------------------------

    def _build_controls(self, parent):
        s = self.settings
        self.mode = Segmented(parent, [("pressure", tr("Pressure")), ("vibration", tr("Vibration"))],
                              value=s.mode, command=self._pick_mode, min_width=RIGHT_W)
        self.mode.pack(fill="x")

        self.intensity = self._slider(parent, tr("Intensity"), 0.1, 1.0, s.intensity,
                                      self._set_intensity, pady=(22, 0))
        self.frequency = self._slider(parent, tr("Frequency"), 0.1, 40.0, s.frequency,
                                      self._set_frequency, pady=(18, 0))
        self.kind = tk.Label(self.frequency.head, text="", bg=T.SURFACE, fg=T.ACCENT,
                             font=T.font(11.5, 600))
        self.kind.pack(side="right", padx=(0, 8))

        self.fine = Disclosure(parent, tr("Fine-tune"))
        self.fine.pack(fill="x", pady=(18, 0))
        self.speed = self._slider(self.fine.body, tr("Ramp speed"), 0.1, 1.0, s.speed,
                                  self._set_speed, pady=(0, 0))
        self.peak = self._slider(self.fine.body, tr("Peak ratio"), 0.2, 0.8, s.peak_ratio,
                                 self._set_peak, pady=(0, 0))
        self.regime = tk.Label(parent, text="", bg=T.SURFACE, fg=T.TEXT_FAINT, font=T.font(11.5),
                               anchor="w", justify="left", wraplength=RIGHT_W)

        tk.Frame(parent, bg=T.SURFACE).pack(fill="both", expand=True)

        self.pad = HoldButton(parent, tr("Hold to feel"), on_press=self._press,
                              on_release=self._release, height=72)
        self.pad.pack(fill="x")
        row = tk.Frame(parent, bg=T.SURFACE)
        row.pack(fill="x", pady=(12, 0))
        self.keep_switch = Toggle(row, command=self._toggle_keep)
        self.keep_switch.set(False)
        self.keep_switch.pack(side="left")
        keep = tk.Label(row, text=tr("Keep on"), bg=T.SURFACE, fg=T.TEXT_2, font=T.font(12.5),
                        cursor="hand2")
        keep.pack(side="left", padx=(8, 0))
        keep.bind("<Button-1>", lambda e: self._toggle_keep())
        Button(row, tr("Release all"), command=self.app.all_off, height=32, fill=T.INSET,
               fg=T.TEXT_2, border=T.BORDER, hover_fill=T.INSET, hover_fg=T.DANGER,
               hover_border=T.DANGER, padx=14, font=T.font(12.5, 600)).pack(side="right")

    def _slider(self, parent, label, lo, hi, value, command, pady):
        wrap = tk.Frame(parent, bg=T.SURFACE)
        wrap.pack(fill="x", pady=pady)
        head = tk.Frame(wrap, bg=T.SURFACE)
        head.pack(fill="x")
        tk.Label(head, text=label, bg=T.SURFACE, fg=T.TEXT_2, font=T.font(12.5)).pack(side="left")
        val = tk.Label(head, text="", bg=T.SURFACE, fg=T.TEXT, font=T.font(12.5, 600))
        val.pack(side="right")
        slider = Slider(wrap, value=value, lo=lo, hi=hi, command=command)
        slider.pack(fill="x", pady=(8, 0))
        slider.value_label, slider.wrap, slider.head, slider.pady = val, wrap, head, pady
        return slider

    # -- interaction ----------------------------------------------------------------------------

    def _toggle_hand(self, hand):
        if hand in self.settings.hands:
            self.settings.hands.discard(hand)
        else:
            self.settings.hands.add(hand)
        self.refresh()

    def _toggle_channel(self, chan):
        if chan in self.settings.channels:
            self.settings.channels.discard(chan)
        else:
            self.settings.channels.add(chan)
        self.refresh()

    def _select(self, channels: set):
        self.settings.channels = set(channels)
        self.refresh()

    def _pick_mode(self, mode):
        self.pad.release()
        self.settings.mode = mode
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

    def _toggle_keep(self):
        self.keep = not self.keep
        self.keep_switch.set(self.keep)
        self.pad.set(latched=self.keep)

    def _frames(self, on: bool) -> bytes:
        s = self.settings
        fingers = s.active_fingers()
        if s.mode == "vibration":
            return P.batch(
                P.vibration(f, on, s.frequency, s.intensity, s.peak_ratio)
                for f in fingers)
        return P.batch(P.pressure(f, on, s.intensity, s.speed) for f in fingers)

    def _press(self):
        self._pressed_at = time.monotonic()
        self._released_at = None
        self.app.send(self.settings.hands, self._frames(True))

    def _release(self):
        self._released_at = time.monotonic()
        self.app.send(self.settings.hands, self._frames(False))

    def reset_pad(self):
        """Everything was vented some other way (Escape, Release all): show the pad let go."""
        if self.pad.held:
            self._released_at = time.monotonic()
        self.pad.release(send=False)

    # -- showing it -----------------------------------------------------------------------------

    def _connected(self) -> list[str]:
        return [h for h in HANDS if (g := self.app.state.get(h)) and g.connected]

    def refresh(self):
        s = self.settings
        connected = self._connected()
        self.mode.set(s.mode)
        vibrating = s.mode == "vibration"
        self._show(self.frequency, vibrating, after=self.intensity.wrap)
        self._show(self.speed, not vibrating)
        self._show(self.peak, vibrating)
        pct = f"{round(s.intensity * 100)}%"
        self.intensity.value_label.configure(
            text=f"{pct} · {P.intensity_to_kpa(s.intensity):.0f} kPa" if self.details else pct)
        self.frequency.value_label.configure(text=f"{s.frequency:.1f} Hz")
        self.kind.configure(text=tr("Pulse") if s.frequency < P.PWM_VIBRATION_HZ else tr("Buzz"))
        self.speed.value_label.configure(text=f"{round(s.speed * 100)}%")
        self.peak.value_label.configure(text=f"{round(s.peak_ratio * 100)}%")

        if len(connected) > 1:
            if not self.hand_chips.winfo_manager():
                self.hand_chips.pack(side="left")
            for hand, chip in self._chips.items():
                chip.set(tr(hand), T.ACCENT if hand in s.hands else None)
        elif self.hand_chips.winfo_manager():
            self.hand_chips.pack_forget()
        if not s.channels and not self.hint.winfo_manager():
            self.hint.pack(side="left", expand=True)
        elif s.channels and self.hint.winfo_manager():
            self.hint.pack_forget()

        sending = [h for h in connected if h in s.hands]
        self.pad.set(disabled=not (s.channels and sending))

        if self.details and vibrating:
            hz = f"{P.PWM_VIBRATION_HZ:.0f}"
            self.regime.configure(text=tr(
                "Under {hz} Hz the glove vibrates pneumatically — the pressure target is "
                "pulsed.", hz=hz) if s.frequency < P.PWM_VIBRATION_HZ else tr(
                "At {hz} Hz and above the pressure loop is off and the channel's motor is "
                "driven directly.", hz=hz))
        else:
            self.regime.configure(text="")

    @staticmethod
    def _show(slider, visible: bool, after=None):
        # Packing again puts a widget last; `after` keeps it where it belongs.
        if visible and not slider.wrap.winfo_manager():
            slider.wrap.pack(fill="x", pady=slider.pady, **({"after": after} if after else {}))
        elif not visible and slider.wrap.winfo_manager():
            slider.wrap.pack_forget()

    def show_details(self, on: bool):
        self.details = on
        if on:
            self.regime.pack(fill="x", pady=(10, 0), after=self.fine)
            self.info.pack(fill="x", pady=(8, 0))
        else:
            self.regime.pack_forget()
            self.info.pack_forget()
        self.refresh()

    def on_tick(self):
        """The glove, 20 times a second: what it measures, or what the pad is doing."""
        s = self.settings
        connected = self._connected()
        hands = [h.lower() for h in connected]
        self.glove.set_hands(hands)
        self.glove.set_selected(s.channels)
        self.glove.set_dim({h.lower(): 1.0 if h in s.hands else 0.45 for h in connected})
        now = time.monotonic()
        held = self.pad.held
        states, values, info = {}, {}, []
        for hand in connected:
            g = self.app.state.get(hand)
            live = g.is_live()
            kpa = g.channel_kpa() if live else None
            states[hand.lower()] = pad_state(
                kpa, held and hand in s.hands, now - self._pressed_at,
                None if self._released_at is None else now - self._released_at,
                s.mode, s.intensity, s.frequency, s.channels)
            if self.details:
                values[hand.lower()] = [f"{k:.0f}" for k in kpa] if kpa else ["—"] * 6
                bits = [tr(hand), tr("battery {level}", level=g.battery_label())]
                bits.append(tr("Source {kpa} kPa", kpa=f"{g.source_kpa():.1f}") if live
                            else tr("no telemetry"))
                info.append("  ·  ".join(bits))
                if g.absolute_pa:
                    info.append(tr("This glove reports absolute pressure; readings are "
                                   "converted to gauge kPa."))
        self.glove.set_states(states)
        self.glove.set_values(values if self.details else None)
        if self.details:
            self.info.configure(text="\n".join(info))

    # -- coming and going -------------------------------------------------------------------------

    def on_show(self):
        root = self.winfo_toplevel()
        root.bind("<KeyPress-space>", self._space_down)
        root.bind("<KeyRelease-space>", self._space_up)
        self.refresh()

    def on_hide(self):
        root = self.winfo_toplevel()
        root.unbind("<KeyPress-space>")
        root.unbind("<KeyRelease-space>")
        self.pad.release()

    def _typing(self) -> bool:
        return isinstance(self.focus_get(), (tk.Entry, tk.Text))

    def _space_down(self, _e):
        if not self._typing():
            self.pad.key_down()

    def _space_up(self, _e):
        if not self._typing():
            self.pad.key_up()

    def _focus_out(self, _e):
        # The window losing focus mid-hold would leave the glove pressing.
        if self.winfo_exists():
            self.after(50, self._release_if_away)

    def _release_if_away(self):
        if self.winfo_exists() and self.focus_get() is None:
            self.pad.release()
