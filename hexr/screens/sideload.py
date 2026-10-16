"""The APK Sideload screen: install an app on a headset plugged into this computer.

Three steps, one on screen at a time, with few words: plug in the headset, choose the APK,
install. The screen moves on by itself as each is done: a headset that allows this computer
goes to the APK, and an APK chosen, or remembered from last time, goes to Install. After an
install the APK stays chosen, so the next headset is unplug, plug in, Install.

It does what SideQuest does for this, with the adb the app carries (hexr/sideload.py), so it
needs no internet. A headset that does not appear is nearly always one of a few things, kept
behind "Not showing up?". A failed install says why, and offers the fix when there is one. What
adb printed, the headset's serial and which adb it is are under Details.
"""

from __future__ import annotations

import os
import sys
import time
import tkinter as tk
from tkinter import filedialog

from .. import settings
from .. import sideload as S
from .. import theme as T
from ..i18n import N_, tr
from ..widgets import Button, Dot, Progress, StepBadge, Surface, TextLink
from .base import SETTINGS_FILE, Screen

STEPS = (N_("Headset"), N_("APK"), N_("Install"))
LIST_EVERY = 4            # ticks between refreshes: 20 Hz / 4 = 5 Hz, faster than adb is asked
DOTS_EVERY = 8            # ticks per step of the searching dots: 20 Hz / 8 = 0.4 s
SWEEP_S = 1.6             # one pass of the busy bar
WRAP = 640


class SideloadScreen(Screen):
    title_text = N_("APK Sideload")
    key = "sideload"
    has_details = True

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.model: S.Sideload = app.sideload
        self._ticks = 0
        self._dots = 0
        self._step = 0
        self._back_to_apk = False          # "Change" was pressed: step 2 until an APK is chosen
        self._help = False
        self._rows: dict[str, tk.Frame] = {}
        self._fix_kind = ""

        # -- where you are: 1 · 2 · 3
        bar = tk.Frame(self.body, bg=T.SURFACE)
        bar.pack(anchor="w")
        self._marks = []
        for i, label in enumerate(STEPS, 1):
            if i > 1:
                tk.Frame(bar, bg=T.BORDER, width=40, height=1).pack(side="left", padx=12)
            badge = StepBadge(bar, i)
            badge.pack(side="left")
            word = tk.Label(bar, text=tr(label), bg=T.SURFACE, font=T.font(13, 600))
            word.pack(side="left", padx=(8, 0))
            self._marks.append((badge, word))

        self.cards = {n: Surface(self.body) for n in (1, 2, 3)}
        self._build_headset(self._inner(1))
        self._build_apk(self._inner(2))
        self._build_install(self._inner(3))

        # -- Details: which adb, the headset's serial, and what adb said
        self.numbers = tk.Label(self.body, text="", bg=T.SURFACE, fg=T.TEXT_FAINT,
                                font=T.mono(11), anchor="w", justify="left", wraplength=WRAP + 120)
        self._refresh()
        self.show_details(self.details)

    def _inner(self, n: int) -> tk.Frame:
        inner = tk.Frame(self.cards[n], bg=T.RAISED)
        inner.pack(fill="x", padx=28, pady=24)
        return inner

    # -- step 1: the headset ---------------------------------------------------------------------

    def _build_headset(self, c: tk.Frame):
        self.h_title = _title(c)
        self.h_sub = _line(c)
        self.h_rows = tk.Frame(c, bg=T.RAISED)
        self.h_looking = tk.Label(c, text="", bg=T.RAISED, fg=T.TEXT_FAINT, font=T.font(12.5),
                                  anchor="w")
        self.h_link = TextLink(c, tr("Not showing up?"), command=self._toggle_help, bg=T.RAISED,
                               fg=T.TEXT_FAINT, size=12.5)
        self.h_help = tk.Frame(c, bg=T.RAISED)
        for i, text in enumerate(_help(), 1):
            item = tk.Frame(self.h_help, bg=T.RAISED)
            item.pack(fill="x", pady=(6, 0))
            tk.Label(item, text=f"{i}", bg=T.RAISED, fg=T.ACCENT, font=T.font(12.5, 700),
                     width=2, anchor="w").pack(side="left", anchor="n")
            tk.Label(item, text=text, bg=T.RAISED, fg=T.TEXT_MUTED, font=T.font(12.5),
                     anchor="w", justify="left", wraplength=WRAP).pack(side="left", fill="x")

    def _show_headset(self):
        m = self.model
        devices = m.devices
        d = m.device(m.selected)
        title, sub, colour, waiting = "", "", T.TEXT, False
        if m.problem == "missing":
            title, colour = tr("adb is missing from this build, and none was found on this "
                               "computer."), T.DANGER
        elif m.problem == "broken":
            title, colour = tr("adb would not run: {error}",
                               error=_last_line(m.problem_text)), T.DANGER
        elif len(devices) > 1 and d is None:
            title = tr("Pick a headset")
        elif d is not None and d.state == "unauthorized":
            title, sub = tr("Put on the headset and choose Allow"), \
                tr("Tick Always allow from this computer.")
        elif d is not None and d.state in ("authorizing", "connecting"):
            title = tr("Waiting for the headset…")
        elif d is not None and not d.ready:
            title = tr("Not responding. Unplug it and plug it in again.")
        else:
            title, sub, waiting = tr("Plug in the headset"), tr("Use a USB-C cable."), True
        self.h_title.configure(text=title, fg=colour)
        self.h_sub.configure(text=sub)
        self._sync_rows(devices if len(devices) > 1 else [])
        # The dots keep a fixed width, so the words do not shuffle as they count up.
        self.h_looking.configure(text=tr("Looking for a headset") + "." * self._dots +
                                 " " * (3 - self._dots))
        _arrange(self.h_title, [
            (self.h_sub, bool(sub), dict(fill="x", pady=(6, 0))),
            (self.h_rows, len(devices) > 1, dict(fill="x", pady=(16, 0))),
            (self.h_looking, waiting, dict(fill="x", pady=(18, 0))),
            (self.h_link, not m.problem, dict(anchor="w", pady=(6 if waiting else 18, 0))),
            (self.h_help, self._help and not m.problem, dict(fill="x", pady=(4, 0))),
        ])

    def _sync_rows(self, devices: list[S.Device]):
        if [d.serial for d in devices] != list(self._rows):
            for row in self._rows.values():
                row.destroy()
            self._rows.clear()
            for d in devices:
                row = tk.Frame(self.h_rows, bg=T.INSET, cursor="hand2")
                row.pack(fill="x", pady=(0, 6))
                row.dot = Dot(row, bg=T.INSET)
                row.dot.pack(side="left", padx=(14, 0), pady=(4, 0))
                row.title = tk.Label(row, bg=T.INSET, fg=T.TEXT, font=T.font(13.5, 500),
                                     anchor="w", width=12)
                row.title.pack(side="left", padx=(10, 12), pady=10)
                row.state = tk.Label(row, bg=T.INSET, font=T.font(12.5), anchor="w")
                row.state.pack(side="left")
                for w in (row, row.dot, row.title, row.state):
                    w.bind("<Button-1>", lambda e, s=d.serial: self._pick(s))
                self._rows[d.serial] = row
        for d in devices:
            row = self._rows[d.serial]
            colour, word = _state_look(d)
            row.dot.set(colour)
            row.title.configure(text=d.name or tr("Headset"))
            row.state.configure(text=word, fg=T.TEXT_2 if d.ready else colour)

    def _pick(self, serial: str):
        if not self.model.busy:
            self.model.selected = serial
            self._refresh()

    def _toggle_help(self):
        self._help = not self._help
        self._refresh()

    # -- step 2: the APK ---------------------------------------------------------------------------

    def _build_apk(self, c: tk.Frame):
        _title(c).configure(text=tr("Choose the APK"))
        Button(c, tr("Choose APK…"), command=self._choose, height=44, font=T.font(14, 600),
               min_width=220).pack(anchor="w", pady=(20, 0))
        # After "Change", the way back to the APK already chosen.
        self.a_back = TextLink(c, tr("Back"), command=self._keep_apk, bg=T.RAISED,
                               fg=T.TEXT_FAINT, size=12.5)

    def _keep_apk(self):
        self._back_to_apk = False
        self._refresh()

    def _choose(self):
        m = self.model
        start = os.path.dirname(m.apk) if m.apk else settings.load(SETTINGS_FILE).get("apk_folder")
        if not (isinstance(start, str) and os.path.isdir(start)):
            start = os.path.expanduser("~/Downloads")
        path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(), title=tr("Choose an APK"), initialdir=start,
            filetypes=[(tr("Android app"), "*.apk"), (tr("All files"), "*")])
        if path:
            m.choose(os.path.normpath(path))
            self._back_to_apk = False
            self._refresh()

    # -- step 3: install ---------------------------------------------------------------------------

    def _build_install(self, c: tk.Frame):
        self.i_title = _title(c)
        what = tk.Frame(c, bg=T.RAISED)
        what.pack(fill="x", pady=(6, 0))
        self.i_apk = tk.Label(what, text="", bg=T.RAISED, fg=T.TEXT_MUTED, font=T.font(13),
                              anchor="w")
        self.i_apk.pack(side="left")
        self.i_change = TextLink(what, tr("Change"), command=self._change_apk, bg=T.RAISED,
                                 size=12.5)
        self.i_change.pack(side="left", padx=(12, 0))
        self.i_other = TextLink(what, tr("Other headset"), command=self._other_headset,
                                bg=T.RAISED, size=12.5)
        self.install_btn = Button(c, tr("Install"), command=self._install_clicked, height=44,
                                  font=T.font(14, 600), min_width=220)
        self.install_btn.pack(anchor="w", pady=(20, 0))
        self.progress = Progress(c, bg=T.RAISED)
        self.status = tk.Label(c, text="", bg=T.RAISED, font=T.font(13.5, 500), anchor="w",
                               justify="left", wraplength=WRAP)
        self.hint = tk.Label(c, text="", bg=T.RAISED, fg=T.TEXT_MUTED, font=T.font(12.5),
                             anchor="w", justify="left", wraplength=WRAP)
        self.fix_btn = Button(c, "", command=self._fix, height=34, fill=T.INSET, fg=T.TEXT,
                              border=T.BORDER, hover_fill=T.INSET, hover_fg=T.ACCENT,
                              hover_border=T.ACCENT, padx=16, font=T.font(12.5, 600))

    def _show_install(self):
        m = self.model
        d = m.device(m.selected)
        job = m.install if self._result_shown() else None
        name = (job.name if job else "") or (d.name if d else "") or tr("Headset")
        self.i_title.configure(text=tr("Install on {name}", name=name))
        self.i_apk.configure(text=f"{os.path.basename(m.apk)} · {_size(m.apk)}" if m.apk else "")
        busy = m.busy
        _show(self.i_change, not busy, side="left", padx=(12, 0))
        _show(self.i_other, not busy and len(m.devices) > 1, side="left", padx=(12, 0))

        if busy:
            self.install_btn.set(text=tr("Stop"), glyph="■", disabled=False, fill=T.INSET,
                                 fg=T.DANGER, border=T.DANGER, hover_fill=T.INSET,
                                 hover_fg=T.DANGER, hover_border=T.DANGER)
        else:
            self.install_btn.set(text=tr("Install"), glyph="",
                                 disabled=not (m.cmd and m.apk and d and d.ready), fill=T.ACCENT,
                                 fg=T.CANVAS, border=T.ACCENT, hover_fill=T.ACCENT_HOVER,
                                 hover_fg=T.CANVAS, hover_border=T.ACCENT_HOVER)

        line, colour, hint, fix = "", T.TEXT_MUTED, "", ""
        if job and not job.done:
            line = tr("Removing the old copy…") if job.phase == "uninstalling" else \
                tr("Installing… {time}", time=_clock(time.monotonic() - job.started))
        elif job and job.outcome is not None:
            line, colour, hint, fix = _explain(job.outcome, name)

        running = bool(job and not job.done)
        if running:
            self.progress.busy((time.monotonic() - job.started) / SWEEP_S)
        self.status.configure(text=line, fg=colour)
        self.hint.configure(text=hint)
        self._fix_kind = fix
        if fix:
            self.fix_btn.set(text=tr("Uninstall and install") if fix == "uninstall" else
                             tr("Install older version"))
        _arrange(self.install_btn, [
            (self.progress, running, dict(fill="x", pady=(18, 0))),
            (self.status, bool(line), dict(fill="x", pady=(14, 0))),
            (self.hint, bool(hint), dict(fill="x", pady=(6, 0))),
            (self.fix_btn, bool(fix), dict(anchor="w", pady=(14, 0))),
        ])

    def _change_apk(self):
        self._back_to_apk = True
        self._refresh()

    def _other_headset(self):
        if not self.model.busy:
            self.model.selected = None
            self._refresh()

    def _install_clicked(self):
        m = self.model
        if m.busy:
            m.install.stop()
        else:
            m.start_install()
        self._refresh()

    def _fix(self):
        job = self.model.install
        if job is None or job.outcome is None:
            return
        if self._fix_kind == "uninstall":
            self.model.start_install(uninstall=job.outcome.package)
        elif self._fix_kind == "downgrade":
            self.model.start_install(downgrade=True)
        self._refresh()

    def _result_shown(self) -> bool:
        """An install going, or one done whose result still belongs on screen: it is for the
        APK chosen and the headset picked. Unplugging that headset keeps it, so "it was
        unplugged" can be read; picking or plugging in another clears it."""
        m, job = self.model, self.model.install
        if job is None or not job.done:
            return job is not None
        unplugged = m.selected is None and m.device(job.serial) is None
        return job.apk == m.apk and (m.selected == job.serial or unplugged)

    # -- which step ---------------------------------------------------------------------------------

    def _current(self) -> int:
        m = self.model
        d = m.device(m.selected)
        if self._result_shown():
            return 3
        if d is None or not d.ready:
            return 1
        if self._back_to_apk or not m.apk:
            return 2
        return 3

    def _refresh(self):
        m = self.model
        if m.selected and m.device(m.selected) is None and not m.busy:
            m.selected = None
        if m.selected is None and len(m.devices) == 1:
            m.selected = m.devices[0].serial

        step = self._current()
        if step != self._step:
            for n, card in self.cards.items():
                card.pack_forget()
            self.cards[step].pack(fill="x", pady=(20, 0), after=self.body.winfo_children()[0])
            self._step = step
        job = m.install
        succeeded = bool(step == 3 and self._result_shown() and job.done and job.outcome
                         and job.outcome.ok)
        for i, (badge, word) in enumerate(self._marks, 1):
            state = "done" if i < step or (i == 3 and succeeded) else \
                "now" if i == step else "todo"
            badge.set(state)
            word.configure(fg={"done": T.TEXT_2, "now": T.TEXT, "todo": T.TEXT_FAINT}[state])

        if step == 1:
            self._show_headset()
        elif step == 2:
            _show(self.a_back, bool(self._back_to_apk and m.apk), anchor="w", pady=(14, 0))
        else:
            self._show_install()
        self._refresh_numbers()

    # -- shown, hidden, ticking ----------------------------------------------------------------------

    def on_show(self):
        self.model.watch(True)
        self._refresh()

    def on_hide(self):
        self.model.watch(False)

    def on_tick(self):
        self._ticks += 1
        if self._ticks % DOTS_EVERY == 0:
            self._dots = (self._dots + 1) % 4
        if self._ticks % LIST_EVERY == 0 or self.model.busy or self.progress.winfo_manager():
            self._refresh()

    def show_details(self, on: bool):
        _show(self.numbers, on, fill="x", pady=(18, 0))
        self._refresh_numbers()

    def _refresh_numbers(self):
        if not self.details:
            return
        m = self.model
        lines = [f"adb  {m.version or '?'}  {m.adb_path or '-'}"]
        if m.selected:
            lines.append(f"headset  {m.selected}")
        job = m.install
        if job is not None and job.outcome is not None and job.outcome.raw.strip():
            lines += ["", job.outcome.raw.strip()]
        self.numbers.configure(text="\n".join(lines))


# -- words ----------------------------------------------------------------------------------------

def _help() -> list[str]:
    lines = [tr("Turn on Developer Mode in the Meta Horizon phone app."),
             tr("Use a cable that carries data. Some only charge."),
             tr("Put the headset on and choose Allow.")]
    if sys.platform == "darwin":
        lines.append(tr("If the Mac asks to allow the accessory, choose Allow."))
    elif sys.platform == "win32":
        lines.append(tr("Install Meta's Quest ADB driver."))
    return lines


def _state_look(d: S.Device) -> tuple[str, str]:
    if d.ready:
        return T.SUCCESS, tr("Ready")
    if d.state == "unauthorized":
        return T.WARN, tr("Put on the headset and choose Allow")
    if d.state in ("authorizing", "connecting"):
        return T.WARN, tr("Waiting for the headset…")
    if d.state == "offline":
        return T.DANGER, tr("Not responding. Unplug it and plug it in again.")
    return T.DOT_OFF, d.state


def _explain(o: S.Outcome, name: str) -> tuple[str, str, str, str]:
    """An install's outcome as a line, its colour, a hint under it, and the fix offered
    ("uninstall", "downgrade" or nothing)."""
    if o.ok:
        return ("✓ " + tr("Installed"), T.SUCCESS,
                tr("Find it in Library → Unknown Sources.") + "\n" + tr("Next headset? Plug it in."),
                "")
    code = o.code
    if code == "INSTALL_FAILED_UPDATE_INCOMPATIBLE":
        if o.package:
            return (tr("A different build is on {name}. Uninstall it first? Its saved data will "
                       "be lost.", name=name), T.DANGER, "", "uninstall")
        return (tr("A different build is on {name}. Uninstall it in the headset first.",
                   name=name), T.DANGER, "", "")
    if code == "INSTALL_FAILED_VERSION_DOWNGRADE":
        return tr("{name} has a newer version.", name=name), T.DANGER, "", "downgrade"
    if code == S.STOPPED:
        return tr("Stopped"), T.TEXT_MUTED, "", ""
    if code == "INSTALL_FAILED_INSUFFICIENT_STORAGE":
        text = tr("{name} is full. Free up space and try again.", name=name)
    elif code == "INSTALL_FAILED_OLDER_SDK":
        text = tr("This app needs a newer headset system. Update {name} first.", name=name)
    elif code == "INSTALL_FAILED_NO_MATCHING_ABIS":
        text = tr("This APK is not made for this headset.")
    elif code.startswith("INSTALL_PARSE_FAILED") or code == "INSTALL_FAILED_INVALID_APK":
        text = tr("This file is not a working APK.")
    elif code == S.NO_FILE:
        text = tr("The APK has moved. Choose it again.")
    elif code == S.DEVICE_GONE:
        text = tr("{name} disconnected. Plug it in and try again.", name=name)
    elif code == S.ADB_FAILED:
        text = tr("adb would not run: {error}", error=_last_line(o.raw))
    else:
        text = tr("Install failed: {error}",
                  error=code if code != S.UNKNOWN else _last_line(o.raw) or code)
    return text, T.DANGER, "", ""


# -- helpers --------------------------------------------------------------------------------------

def _title(parent) -> tk.Label:
    label = tk.Label(parent, text="", bg=T.RAISED, fg=T.TEXT, font=T.font(20, 600), anchor="w",
                     justify="left", wraplength=WRAP)
    label.pack(fill="x")
    return label


def _line(parent) -> tk.Label:
    return tk.Label(parent, text="", bg=T.RAISED, fg=T.TEXT_MUTED, font=T.font(13.5),
                    anchor="w", justify="left", wraplength=WRAP)


def _size(path: str) -> str:
    try:
        mb = os.path.getsize(path) / 1e6
    except OSError:
        return "?"
    if mb >= 1000:
        return f"{mb / 1000:.1f} GB"
    return f"{mb:.0f} MB" if mb >= 10 else f"{mb:.1f} MB"


def _clock(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


def _last_line(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _show(widget, visible: bool, **pack):
    if visible and not widget.winfo_manager():
        widget.pack(**pack)
    elif not visible and widget.winfo_manager():
        widget.pack_forget()


def _arrange(anchor, items):
    """Pack the visible ones after `anchor` in this order, and take the rest away: a card's
    parts come and go without changing places."""
    after = anchor
    for widget, visible, pack in items:
        if visible:
            widget.pack(after=after, **pack)
            after = widget
        elif widget.winfo_manager():
            widget.pack_forget()
