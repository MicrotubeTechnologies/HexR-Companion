"""A headset's view filling a whole screen, for the audience.

It opens on a second display when there is one (the projector or TV at an event), so the
facilitator keeps the app on the laptop's own screen; with one display it covers that. Only the
picture shows: the view, with the gloves beside it. Keys work while it has focus:

    Esc, F11 or a double-click   leave full screen
    R                            start or stop recording

The recording dot in the corner is on the screen only; the recording itself is the picture.
"""

from __future__ import annotations

import ctypes
import sys
import time
import tkinter as tk

from PIL import ImageTk

from .. import theme as T
from ..i18n import tr

PUMP_MS = 15
HINT_S = 4.0


def displays() -> list[tuple[int, int, int, int]]:
    """Every display as (x, y, width, height), in the units Tk's geometry uses."""
    found = []
    if sys.platform == "win32":
        try:
            user32 = ctypes.windll.user32

            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                            ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            proc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.POINTER(RECT), ctypes.c_ssize_t)

            def each(_hmon, _hdc, rect, _data):
                r = rect.contents
                found.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
                return 1

            user32.EnumDisplayMonitors(None, None, proc(each), 0)
        except Exception:  # noqa: BLE001
            found = []
    elif sys.platform == "darwin":
        # AppKit comes with bleak. Its frames count up from the bottom of the main display (the
        # first screen); Tk counts down from its top. Both are in points, so only y is flipped.
        try:
            from AppKit import NSScreen
            screens = NSScreen.screens()
            top = screens[0].frame().size.height
            for s in screens:
                f = s.frame()
                found.append((int(f.origin.x), int(top - f.origin.y - f.size.height),
                              int(f.size.width), int(f.size.height)))
        except Exception:  # noqa: BLE001
            found = []
    return found


def pick_display(root: tk.Misc) -> tuple[int, int, int, int]:
    """A display the app's window is not on, if there is one; otherwise the one it is on."""
    root.update_idletasks()
    cx = root.winfo_rootx() + root.winfo_width() // 2
    cy = root.winfo_rooty() + root.winfo_height() // 2
    every = displays()
    if not every:
        return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()
    holding = [d for d in every if d[0] <= cx < d[0] + d[2] and d[1] <= cy < d[1] + d[3]]
    others = [d for d in every if d not in holding]
    return (others or holding or every)[0]


class FullView(tk.Toplevel):
    """The full-screen picture. The detail view feeds it frames and is told what keys do."""

    def __init__(self, master, on_close, on_record):
        super().__init__(master, bg="black")
        self.overrideredirect(True)
        x, y, w, h = pick_display(master.winfo_toplevel())
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.size = (w, h)
        self.attributes("-topmost", True)
        self._on_close = on_close
        self._photo: ImageTk.PhotoImage | None = None
        self.picture = tk.Label(self, bg="black", bd=0)
        self.picture.place(relx=0.5, rely=0.5, anchor="center")
        self.rec = tk.Label(self, text="", bg="black", fg=T.DANGER, font=T.font(14, 600))
        self.hint = tk.Label(self, bg="#16171A", fg=T.TEXT_2, font=T.font(13), padx=16, pady=8,
                             text=tr("Esc to leave full screen · R to record"))
        self.hint.place(relx=0.5, rely=1.0, y=-40, anchor="s")
        self._hint_until = time.monotonic() + HINT_S

        for key in ("<Escape>", "<F11>", "<Double-Button-1>"):
            self.bind(key, lambda e: self.close())
        self.bind("<KeyPress-r>", lambda e: on_record())
        self.bind("<KeyPress-R>", lambda e: on_record())
        self.picture.bind("<Double-Button-1>", lambda e: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(50, self._grab_focus)

    def _grab_focus(self):
        try:
            self.focus_force()
        except tk.TclError:
            pass

    def show(self, image):
        """Main thread: put the newest picture up."""
        if self._photo is None or (self._photo.width(), self._photo.height()) != image.size:
            self._photo = ImageTk.PhotoImage(image, master=self)
            self.picture.configure(image=self._photo)
        else:
            self._photo.paste(image)
        if self._hint_until and time.monotonic() > self._hint_until:
            self._hint_until = 0
            self.hint.place_forget()

    def set_recording(self, text: str):
        if text:
            self.rec.configure(text=text)
            self.rec.place(x=24, y=18)
        else:
            self.rec.place_forget()

    def close(self):
        if self._on_close:
            callback, self._on_close = self._on_close, None
            callback()
        try:
            self.destroy()
        except tk.TclError:
            pass
