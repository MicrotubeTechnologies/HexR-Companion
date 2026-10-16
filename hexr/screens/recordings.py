"""The Recordings screen: what was recorded from a headset, made into videos to share.

A recording is the headset's view as it came and what its gloves did (hexr/recorder.py). Pick
one, pick a shape (landscape and portrait are YouTube's two, the gloves beside the view; square
is the view alone) and Export draws the two together into a video in the Exports folder. The
preview shows that shape at the moment the gloves were busiest. The same recording can be
exported in every shape.

Reading thumbnails and drawing previews means decoding video, so it happens on a worker thread
and the screen picks the results up on its tick.
"""

from __future__ import annotations

import datetime
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk

from .. import exporter as X
from .. import recorder as REC
from .. import settings
from .. import theme as T
from ..i18n import N_, tr
from ..viewer import LANDSCAPE, LAYOUTS, PORTRAIT, SQUARE
from ..widgets import Button, Divider, Progress, Segmented, Surface, TextLink
from .base import SETTINGS_FILE, Screen

LIST_W = 330
PREVIEW = (540, 400)          # the room the preview has
THUMB = 56
RESCAN_EVERY = 40             # ticks between looks at the folder: 2 s at 20 Hz
SHAPES = {LANDSCAPE: N_("Landscape"), PORTRAIT: N_("Portrait"), SQUARE: N_("Square")}


class RecordingsScreen(Screen):
    title_text = N_("Recordings")
    key = "recordings"

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.recs: list[X.Recording] = []
        self.selected: str | None = None
        self.layout = _saved_layout()
        self._rows: dict[str, dict] = {}
        self._thumbs: dict[str, tuple[float, object]] = {}    # path -> (seconds, PhotoImage)
        self._export: X.Export | None = None
        self._preview_photo = None
        self._preview_want = None
        self._error = ""
        # Labels are sized in characters until they hold a picture: blanks keep them in pixels.
        self._blank_thumb = tk.PhotoImage(master=self, width=THUMB, height=THUMB)
        self._blank_preview = tk.PhotoImage(master=self, width=PREVIEW[0], height=PREVIEW[1])
        self._ticks = 0
        self._work: queue.Queue = queue.Queue()
        self._results: queue.Queue = queue.Queue()
        threading.Thread(target=self._worker, name="hexr-recordings", daemon=True).start()

        Button(self.head_actions, tr("Open folder"), command=self._open_folder, height=32,
               fill=T.RAISED, fg=T.TEXT, border=T.BORDER, hover_fill=T.INSET,
               hover_fg=T.ACCENT, hover_border=T.ACCENT, padx=16,
               font=T.font(12.5, 600)).pack(side="right")

        # -- nothing recorded yet
        self.empty = tk.Frame(self.body, bg=T.SURFACE)
        tk.Label(self.empty, text=tr("No recordings yet"), bg=T.SURFACE, fg=T.TEXT,
                 font=T.font(16, 600), anchor="w").pack(fill="x")
        tk.Label(self.empty, text=tr("Record a headset's view in Headsets."), bg=T.SURFACE,
                 fg=T.TEXT_FAINT, font=T.font(13), anchor="w").pack(fill="x", pady=(6, 0))
        TextLink(self.empty, tr("Go to Headsets") + " →",
                 command=lambda: app.navigate("headsets")).pack(anchor="w", pady=(14, 0))

        # -- the list, and the chosen one beside it
        self.cols = tk.Frame(self.body, bg=T.SURFACE)
        self.listing = Surface(self.cols)
        self.listing.pack(side="left", anchor="n")
        right = tk.Frame(self.cols, bg=T.SURFACE)
        right.pack(side="left", fill="both", expand=True, padx=(24, 0))

        self.preview = tk.Label(right, bg=T.SURFACE, bd=0, image=self._blank_preview,
                                compound="center", text="", fg=T.TEXT_FAINT, font=T.font(12.5))
        self.preview.pack(anchor="w")
        self.shape = Segmented(right, [(k, tr(v)) for k, v in SHAPES.items()],
                               value=self.layout, command=self._pick_shape)
        self.shape.pack(anchor="w", pady=(16, 0))
        self.export_btn = Button(right, tr("Export"), command=self._export_clicked, height=44,
                                 font=T.font(14, 600), min_width=220)
        self.export_btn.pack(anchor="w", pady=(16, 0))
        self.progress = Progress(right)
        self.status = tk.Label(right, text="", bg=T.SURFACE, fg=T.TEXT_MUTED, font=T.font(12.5),
                               anchor="w", justify="left", wraplength=PREVIEW[0])
        self.done_link = TextLink(right, "", command=self._show_export, fg=T.SUCCESS, hover=T.TEXT)

    # -- the folder ---------------------------------------------------------------------------

    def on_show(self):
        self._rescan()

    def open(self, path: str):
        """Show one recording: the Headsets screen's "Open in Recordings"."""
        self._rescan()
        if any(r.path == path for r in self.recs):
            self._select(path)

    def _rescan(self):
        recs = X.find_recordings()
        if [r.path for r in recs] != [r.path for r in self.recs]:
            self.recs = recs
            self._build_list()
        if self.selected not in {r.path for r in recs}:
            self.selected = None
            if recs:
                self._select(recs[0].path)
        if recs and not self.cols.winfo_manager():
            self.empty.pack_forget()
            self.cols.pack(fill="x")
        elif not recs and not self.empty.winfo_manager():
            self.cols.pack_forget()
            self.empty.pack(fill="x", pady=(24, 0))

    def _build_list(self):
        for w in self.listing.winfo_children():
            if isinstance(w, tk.Frame):        # the rows, not the Surface's corner canvases
                w.destroy()
        self._rows.clear()
        tk.Frame(self.listing, bg=T.RAISED, width=LIST_W, height=1).pack(fill="x")
        for i, rec in enumerate(self.recs):
            if i:
                Divider(self.listing).pack(fill="x")
            row = tk.Frame(self.listing, bg=T.RAISED, cursor="hand2")
            row.pack(fill="x")
            thumb = tk.Label(row, bg=T.INSET, image=self._blank_thumb, bd=0)
            thumb.pack(side="left", padx=(14, 12), pady=10)
            words = tk.Frame(row, bg=T.RAISED)
            words.pack(side="left", fill="x", expand=True)
            title = tk.Label(words, text=rec.title or rec.stem, bg=T.RAISED, fg=T.TEXT,
                             font=T.font(13, 600), anchor="w")
            title.pack(fill="x")
            sub = tk.Label(words, text=_when(rec), bg=T.RAISED, fg=T.TEXT_FAINT,
                           font=T.font(12), anchor="w")
            sub.pack(fill="x", pady=(2, 0))
            for w in (row, thumb, words, title, sub):
                w.bind("<Button-1>", lambda e, p=rec.path: self._select(p))
            self._rows[rec.path] = {"row": row, "thumb": thumb, "title": title, "sub": sub,
                                    "words": words}
            if rec.path in self._thumbs:
                self._fill_thumb(rec.path)
            else:
                self._work.put(("thumb", rec))
        self._paint_rows()

    def _paint_rows(self):
        for path, r in self._rows.items():
            on = path == self.selected
            bg = T.INSET if on else T.RAISED
            for name in ("row", "words", "title", "sub"):
                r[name].configure(bg=bg)
            r["title"].configure(fg=T.ACCENT if on else T.TEXT)

    def _fill_thumb(self, path: str):
        seconds, photo = self._thumbs[path]
        r = self._rows.get(path)
        rec = next((x for x in self.recs if x.path == path), None)
        if not r or not rec:
            return
        if photo is not None:
            r["thumb"].configure(image=photo)
        r["sub"].configure(text=_when(rec, seconds))

    # -- choosing ------------------------------------------------------------------------------

    def _select(self, path: str):
        self.selected = path
        self._error = ""
        self._paint_rows()
        self._ask_preview()
        self._refresh_export()

    def _pick_shape(self, layout: str):
        self.layout = layout
        _save_layout(layout)
        self._ask_preview()
        self._refresh_export()

    def _ask_preview(self):
        rec = self._current()
        if rec is None:
            return
        self._preview_want = (rec.path, self.layout)
        self.preview.configure(image=self._blank_preview, text=tr("Loading…"))
        self._preview_photo = None
        self._work.put(("preview", rec, self.layout))

    def _current(self) -> X.Recording | None:
        return next((r for r in self.recs if r.path == self.selected), None)

    # -- exporting -----------------------------------------------------------------------------

    def _export_clicked(self):
        if self._export and not self._export.done:
            self._export.stop()
            return
        rec = self._current()
        if rec is None:
            return
        self._error = ""
        self._export = X.Export(rec, self.layout)
        self._export.start()
        self._refresh_export()

    def _refresh_export(self):
        """The button, the progress and the line under them, for the recording and shape shown."""
        ex = self._export
        if ex and ex.done:
            self._export = None
            if ex.error:
                self._error = tr("Export failed: {error}", error=ex.error)
        rec = self._current()
        ex = self._export
        here = bool(ex and rec and ex.rec.path == rec.path and ex.layout == self.layout)
        exists = rec is not None and not here and os.path.exists(X.export_path(rec, self.layout))

        if here:
            self.export_btn.set(text=tr("Stop"), glyph="■", disabled=False, fill=T.INSET,
                                fg=T.DANGER, border=T.DANGER, hover_fill=T.INSET,
                                hover_fg=T.DANGER, hover_border=T.DANGER)
            line, colour = tr("Exporting… {pct}%", pct=round(ex.progress * 100)), T.TEXT_MUTED
        else:
            self.export_btn.set(text=tr("Export again") if exists else tr("Export"), glyph="",
                                disabled=rec is None or ex is not None, fill=T.ACCENT,
                                fg=T.CANVAS, border=T.ACCENT, hover_fill=T.ACCENT_HOVER,
                                hover_fg=T.CANVAS, hover_border=T.ACCENT_HOVER)
            line, colour = ((self._error, T.DANGER) if self._error else
                            (tr("Exporting another recording…"), T.TEXT_MUTED) if ex else
                            ("", T.TEXT_MUTED))

        _show(self.progress, here, fill="x", pady=(14, 0), after=self.export_btn)
        if here:
            self.progress.set(ex.progress)
        self.status.configure(text=line, fg=colour)
        _show(self.status, bool(line), fill="x", pady=(10, 0),
              after=self.progress if here else self.export_btn)
        self.done_link.configure(text="✓ " + tr("Exported · Show in folder"))
        _show(self.done_link, exists, anchor="w", pady=(12, 0))

    def _show_export(self):
        rec = self._current()
        if rec is not None:
            show_in_folder(X.export_path(rec, self.layout))

    def _open_folder(self):
        folder = REC.videos_folder()
        try:
            os.makedirs(folder, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(folder)  # noqa: S606
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", folder])
        except OSError:
            pass

    # -- the tick ------------------------------------------------------------------------------

    def on_tick(self):
        self._ticks += 1
        if self._ticks % RESCAN_EVERY == 0:
            self._rescan()
        while True:
            try:
                kind, *rest = self._results.get_nowait()
            except queue.Empty:
                break
            if kind == "thumb":
                path, seconds, img = rest
                from PIL import ImageTk
                photo = ImageTk.PhotoImage(img, master=self) if img is not None else None
                self._thumbs[path] = (seconds, photo)
                self._fill_thumb(path)
            elif kind == "preview":
                want, img, error = rest
                if want == self._preview_want:
                    if img is None:
                        self.preview.configure(image=self._blank_preview,
                                               text=error or tr("No preview"))
                    else:
                        from PIL import ImageTk
                        self._preview_photo = ImageTk.PhotoImage(img, master=self)
                        self.preview.configure(image=self._preview_photo, text="",
                                               width=img.width, height=img.height)
        if self._export:
            self._refresh_export()

    def _worker(self):
        """Decoding, away from the UI: thumbnails and previews, one at a time, newest wish
        first for previews (a click on another shape makes the last one moot)."""
        while True:
            job = self._work.get()
            try:
                if job[0] == "thumb":
                    rec = job[1]
                    seconds, img = X.probe(rec, THUMB)
                    self._results.put(("thumb", rec.path, seconds, img))
                else:
                    _kind, rec, layout = job
                    if (rec.path, layout) != self._preview_want:
                        continue
                    img = X.still(rec, layout, PREVIEW)
                    self._results.put(("preview", (rec.path, layout), img, ""))
            except Exception as e:  # noqa: BLE001
                if job[0] == "preview":
                    self._results.put(("preview", (job[1].path, job[2]), None, str(e)))


# -- helpers ---------------------------------------------------------------------------------

def _when(rec: X.Recording, seconds: float | None = None) -> str:
    try:
        stamp = datetime.datetime.fromisoformat(rec.started).strftime("%d %b %H:%M")
    except ValueError:
        stamp = ""
    if seconds:
        s = int(round(seconds))
        stamp = f"{stamp} · {s // 60}:{s % 60:02d}" if stamp else f"{s // 60}:{s % 60:02d}"
    return stamp


def _show(widget, visible: bool, **pack):
    if visible and not widget.winfo_manager():
        widget.pack(**pack)
    elif not visible and widget.winfo_manager():
        widget.pack_forget()


def _saved_layout() -> str:
    value = settings.load(SETTINGS_FILE).get("export")
    return value if value in LAYOUTS else LANDSCAPE


def _save_layout(layout: str):
    data = settings.load(SETTINGS_FILE)
    data["export"] = layout
    settings.save(SETTINGS_FILE, data)


def show_in_folder(path: str):
    path = os.path.normpath(path)
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", path])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])
    except OSError:
        pass
