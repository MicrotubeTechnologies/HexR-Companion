"""The application shell: frameless window, title bar, header and nav rail.

Everything here is chrome. Screens are registered into `content` and swapped by
`go()`; the shell owns nothing about gloves.

Three Windows-specific problems are solved in `_apply_win32`, and all three are
consequences of `overrideredirect(True)`:

1. A frameless Tk window is given `WS_EX_TOOLWINDOW`, which removes its taskbar
   button. Cleared here, with `WS_EX_APPWINDOW` set in its place.
2. `iconify()` misbehaves on such a window, so minimise goes through
   `ShowWindow` on the real HWND instead.
3. There is no OS frame to round or shadow, so DWM is asked for both directly.

macOS keeps the native window frame instead. A frameless Tk window there never
takes keyboard focus (so Escape, the panic key, would do nothing) and has no
Dock or Cmd-Tab presence; the traffic lights already provide close, minimise
and zoom, so the custom title bar is simply not built.
"""

from __future__ import annotations

import ctypes
import os
import sys
import tkinter as tk

from . import theme as T
from .widgets import (Button, IconButton, NavRow, StatusPill,
                      paint_maximise, paint_restore)

MAC = sys.platform == "darwin"

# Connect a glove, drive it, then run the canned QA sweep. Testing a single
# channel by hand and running the full sweep are different jobs — one is
# exploratory, one is pass/fail — so they get separate screens.
STEPS = [("01", "Connect", "connect"), ("02", "Test", "test"),
         ("03", "Quick test", "quicktest")]

def _hwnd_of(widget) -> int:
    """The real top-level HWND, not Tk's child window."""
    hwnd = widget.winfo_id()
    if sys.platform != "win32":
        return hwnd
    GA_ROOT = 2
    try:
        return ctypes.windll.user32.GetAncestor(hwnd, GA_ROOT) or hwnd
    except Exception:
        return hwnd


class Shell:
    def __init__(self, root: tk.Tk, on_run=None):
        self.root = root
        self.on_run = on_run
        self.screen = "connect"
        self._screens: dict[str, tk.Frame] = {}
        self._run_state = (None, None)
        # Where the window sits when it is not filling the screen. Restored
        # verbatim, so maximising and unmaximising is lossless.
        self._normal: tuple[int, int, int, int] | None = None

        self._set_window_icon(root)
        root.configure(bg=T.SURFACE)
        self._win_h = T.WIN_H - (T.TITLEBAR_H + 1 if MAC else 0)
        root.geometry(f"{T.WIN_W}x{self._win_h}")
        root.minsize(T.WIN_W, self._win_h)
        if MAC:
            # Cmd-Q and the app menu's Quit bypass WM_DELETE_WINDOW; route
            # them through close() so the gloves are vented on the way out.
            root.createcommand("::tk::mac::Quit", self.close)
        else:
            root.overrideredirect(True)
        root.update_idletasks()
        self._centre()
        self._apply_win32()

        if not MAC:
            self._build_titlebar()
        self._build_header()
        self._build_body()

    # -- window plumbing -----------------------------------------------------

    @staticmethod
    def _set_window_icon(root: tk.Tk):
        """Use the Microtube mark for the taskbar and Alt-Tab.

        The packaged .exe carries the icon in its own resources, but running
        from source would otherwise show Tk's default feather.
        """
        path = T.resource_path("assets", "icon.ico")
        if os.path.exists(path):
            try:
                root.iconbitmap(default=path)
            except tk.TclError:
                pass                    # non-Windows Tk cannot read .ico

    @staticmethod
    def _titlebar_mark():
        """The app mark for the title bar, as a Tk image.

        Loaded from a PNG generated at exactly the size it is drawn — Tk can
        only shrink an image by whole-number division, so handing it the 512 px
        icon and subsampling gives a ragged result. Returns None if the file is
        missing or this Tk was built without PNG support, and the caller falls
        back to a drawn square.
        """
        path = T.resource_path("assets", "icon-16.png")
        if not os.path.exists(path):
            return None
        try:
            return tk.PhotoImage(file=path)
        except tk.TclError:
            return None

    def _centre(self):
        w, h = T.WIN_W, self._win_h
        x = (self.root.winfo_screenwidth() - w) // 2
        y = max(0, (self.root.winfo_screenheight() - h) // 2 - 20)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _apply_win32(self):
        if sys.platform != "win32":
            return
        hwnd = _hwnd_of(self.root)
        u32, dwm = ctypes.windll.user32, ctypes.windll.dwmapi

        # 1. give the frameless window a taskbar button back
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW, WS_EX_TOOLWINDOW = 0x00040000, 0x00000080
        get = getattr(u32, "GetWindowLongPtrW", u32.GetWindowLongW)
        setl = getattr(u32, "SetWindowLongPtrW", u32.SetWindowLongW)
        try:
            ex = get(hwnd, GWL_EXSTYLE)
            setl(hwnd, GWL_EXSTYLE, (ex & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW)
            self.root.withdraw()
            self.root.after(10, self.root.deiconify)
        except Exception:
            pass

        # 2. Win11 rounded corners + a real drop shadow
        try:
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            pref = ctypes.c_int(2)          # DWMWCP_ROUND
            dwm.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                                      ctypes.byref(pref), ctypes.sizeof(pref))

            class MARGINS(ctypes.Structure):
                _fields_ = [("cxLeftWidth", ctypes.c_int),
                            ("cxRightWidth", ctypes.c_int),
                            ("cyTopHeight", ctypes.c_int),
                            ("cyBottomHeight", ctypes.c_int)]
            dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(MARGINS(1, 1, 1, 1)))
        except Exception:
            pass

    def minimise(self):
        if MAC:
            self.root.iconify()
            return
        if sys.platform == "win32":
            try:
                ctypes.windll.user32.ShowWindow(_hwnd_of(self.root), 6)  # SW_MINIMIZE
                return
            except Exception:
                pass
        self.root.overrideredirect(False)       # fallback for non-Windows
        self.root.iconify()
        self.root.bind("<Map>", self._remap)

    def _remap(self, _e):
        self.root.unbind("<Map>")
        self.root.overrideredirect(True)

    @property
    def maximised(self) -> bool:
        return self._normal is not None

    def _work_area(self) -> tuple[int, int, int, int]:
        """The usable rectangle of the monitor the window is on.

        The work area, not the full screen — filling the screen would put the
        title bar's own controls behind the taskbar. Asked of the current
        monitor rather than the primary one, because a bench PC often has two.

        The process is DPI-unaware, so Windows hands it virtualised
        coordinates; these are the same units Tk's geometry strings use and
        need no conversion.
        """
        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32

                class RECT(ctypes.Structure):
                    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

                class MONITORINFO(ctypes.Structure):
                    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                                ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]

                MONITOR_DEFAULTTONEAREST = 2
                hmon = user32.MonitorFromWindow(_hwnd_of(self.root),
                                                MONITOR_DEFAULTTONEAREST)
                mi = MONITORINFO()
                mi.cbSize = ctypes.sizeof(MONITORINFO)
                if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                    r = mi.rcWork
                    return r.left, r.top, r.right - r.left, r.bottom - r.top
            except Exception:
                pass
        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def toggle_maximise(self):
        if self.maximised:
            self._restore()
        else:
            self._maximise()

    def _maximise(self):
        if self.maximised:
            return
        self.root.update_idletasks()
        self._normal = (self.root.winfo_width(), self.root.winfo_height(),
                        self.root.winfo_x(), self.root.winfo_y())
        x, y, w, h = self._work_area()
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.max_btn.set_painter(paint_restore)

    def _restore(self):
        if not self.maximised:
            return
        w, h, x, y = self._normal
        self._normal = None
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.max_btn.set_painter(paint_maximise)

    # -- title bar -----------------------------------------------------------

    def _build_titlebar(self):
        bar = tk.Frame(self.root, bg=T.RAISED, height=T.TITLEBAR_H)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)
        self.titlebar = bar

        left = tk.Frame(bar, bg=T.RAISED)
        left.pack(side="left", padx=(14, 0))
        self._mark_img = self._titlebar_mark()
        if self._mark_img is not None:
            tk.Label(left, image=self._mark_img, bg=T.RAISED,
                     bd=0).pack(side="left")
        else:
            # No PNG to load: fall back to the plain accent square rather than
            # leaving a gap where the mark should be.
            mark = tk.Canvas(left, width=11, height=11, bg=T.RAISED,
                             highlightthickness=0, bd=0)
            from .widgets import draw_round
            draw_round(mark, 0, 0, 11, 11, 3, T.ACCENT)
            mark.pack(side="left")
        tk.Label(left, text="HEXR Window Tester", bg=T.RAISED, fg=T.TEXT_2,
                 font=T.font(12.5)).pack(side="left", padx=(9, 0))

        right = tk.Frame(bar, bg=T.RAISED)
        right.pack(side="right", padx=(0, 6))
        # Right to left, so they end up in the order Windows puts them:
        # minimise, maximise, close.
        IconButton(right, "✕", command=self.close, hover_bg=T.DANGER,
                   hover_fg="#FFFFFF").pack(side="right")
        self.max_btn = IconButton(right, painter=paint_maximise,
                                  command=self.toggle_maximise)
        self.max_btn.pack(side="right")
        IconButton(right, "–", command=self.minimise).pack(side="right")

        # dragging, and double-click to maximise as any title bar does
        for w in (bar, left) + tuple(left.winfo_children()):
            w.bind("<Button-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)
            w.bind("<Double-Button-1>", lambda _e: self.toggle_maximise())

        tk.Frame(self.root, bg=T.BORDER_SOFT, height=1).pack(fill="x")

    def _drag_start(self, e):
        if self.maximised:
            # Pull a maximised window down and it comes loose under the
            # cursor, keeping the same relative grip on its title bar.
            grip = e.x_root / max(1, self.root.winfo_width())
            w = self._normal[0]
            self._restore()
            self.root.geometry(f"+{int(e.x_root - w * grip)}+{max(0, e.y_root - 18)}")
            self.root.update_idletasks()
        self._drag = (e.x_root - self.root.winfo_x(),
                      e.y_root - self.root.winfo_y())

    def _drag_move(self, e):
        if not getattr(self, "_drag", None):
            return
        dx, dy = self._drag
        self.root.geometry(f"+{e.x_root - dx}+{e.y_root - dy}")

    # -- header --------------------------------------------------------------

    def _build_header(self):
        h = tk.Frame(self.root, bg=T.SURFACE, height=T.HEADER_H)
        h.pack(fill="x")
        h.pack_propagate(False)
        self.header = h

        # The wordmark is one line, with the company credit tucked under it.
        # The two halves used to sit 10px apart, which read as two separate
        # words rather than one product name; a single space between them is
        # what the eye expects, so the gap is now the space character's own
        # width and nothing more.
        mark = tk.Frame(h, bg=T.SURFACE)
        mark.pack(side="left", padx=(22, 0))
        word = tk.Frame(mark, bg=T.SURFACE)
        word.pack(anchor="w")
        tk.Label(word, text="HEXR", bg=T.SURFACE, fg=T.ACCENT,
                 font=T.font(20, 700)).pack(side="left")
        tk.Label(word, text=" Window Tester", bg=T.SURFACE, fg=T.TEXT,
                 font=T.font(20, 400)).pack(side="left")
        tk.Label(mark, text="by Microtube Technologies", bg=T.SURFACE,
                 fg=T.TEXT_FAINT, font=T.font(10)).pack(anchor="w")

        right = tk.Frame(h, bg=T.SURFACE)
        right.pack(side="right", padx=(0, 22))

        # The header button is the panic button. A haptics tester can leave a
        # channel inflated against someone's finger, so "All off" has to be
        # reachable from every screen without hunting for it.
        self.run_btn = Button(right, "Connect a glove", command=self._run_clicked,
                              height=34, fill=T.RAISED, fg=T.TEXT_2,
                              border=T.BORDER, glyph="→", padx=20,
                              min_width=190, font=T.font(13, 600))
        self.run_btn.pack(side="right")

        self.status = StatusPill(right)
        self.status.pack(side="right", padx=(0, 12))

        tk.Frame(self.root, bg=T.BORDER_SOFT, height=1).pack(fill="x")

    # -- body: rail + content ------------------------------------------------

    def _build_body(self):
        body = tk.Frame(self.root, bg=T.SURFACE)
        body.pack(fill="both", expand=True)
        self.body = body

        rail = tk.Frame(body, bg=T.RAIL, width=T.RAIL_W)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)
        self.rail = rail

        top = tk.Frame(rail, bg=T.RAIL)
        top.pack(fill="x", pady=(14, 0), padx=10)
        self.nav: dict[str, NavRow] = {}
        for num, label, key in STEPS:
            row = NavRow(top, num, label, command=lambda k=key: self.go(k))
            row.pack(fill="x", pady=1)
            self.nav[key] = row

        foot = tk.Frame(rail, bg=T.RAIL)
        foot.pack(side="bottom", fill="x", padx=22, pady=(0, 14))
        tk.Frame(foot, bg=T.BORDER_SOFT, height=1).pack(fill="x", pady=(0, 6))
        # Read from the VERSION file rather than a literal, so the footer, the
        # exe's properties and the installer can never disagree. The glove
        # reports no firmware version over BLE, so there is nothing else to
        # show here — an empty "fw —" slot would only invite the question.
        self.build_label = tk.Label(foot, text=f"app {T.app_version()}",
                                    bg=T.RAIL,
                                    fg=T.TEXT_OFF, font=T.mono(10.5), anchor="w")
        self.build_label.pack(fill="x", pady=(0, 7))
        help_lbl = tk.Label(foot, text="Help & docs", bg=T.RAIL, fg=T.TEXT_MUTED,
                            font=T.font(12), anchor="w", cursor="hand2")
        help_lbl.pack(fill="x")
        help_lbl.bind("<Enter>", lambda e: help_lbl.configure(fg=T.TEXT))
        help_lbl.bind("<Leave>", lambda e: help_lbl.configure(fg=T.TEXT_MUTED))

        tk.Frame(body, bg=T.BORDER_SOFT, width=1).pack(side="left", fill="y")

        self.content = tk.Frame(body, bg=T.SURFACE)
        self.content.pack(side="left", fill="both", expand=True)

        self.root.after(40, lambda: [r.render() for r in self.nav.values()])

    # -- screens -------------------------------------------------------------

    def register(self, key: str, frame: tk.Frame):
        self._screens[key] = frame

    def go(self, key: str):
        if key not in self._screens:
            return
        for k, f in self._screens.items():
            if k != key:
                f.pack_forget()
        self._screens[key].pack(fill="both", expand=True)
        self.screen = key
        for k, row in self.nav.items():
            row.set(active=(k == key))
        if hasattr(self._screens[key], "on_show"):
            self._screens[key].on_show()

    def mark_done(self, key: str, done: bool = True):
        if key in self.nav:
            self.nav[key].set(done=done)

    # -- header state --------------------------------------------------------

    def set_status(self, dot: str, text: str):
        self.status.set(dot, text)

    def set_run_state(self, state: str, label: str = "Start"):
        """'blocked' | 'ready' | 'running'.

        A blocked button is not disabled. It carries the name of the one thing
        in the way and, when clicked, goes there — a dead grey rectangle
        reading "Connect first" told the user neither what was wrong (it might
        well have been a board connected but nothing taught) nor where to fix
        it, and swallowed the click that asked.
        """
        # sync_header runs on the UI tick, because liveness decays with time
        # and the blocker can change without anyone clicking anything. Redraw
        # only when the button would actually look different.
        if (state, label) == self._run_state:
            return
        self._run_state = (state, label)
        if state == "running":
            self.run_btn.set(text=label, fill=T.INSET, fg=T.DANGER,
                             border=T.DANGER, hover_fill=T.INSET,
                             hover_fg=T.DANGER, hover_border=T.DANGER,
                             glyph="■", disabled=False)
        elif state == "ready":
            self.run_btn.set(text=label, fill=T.ACCENT, fg=T.CANVAS,
                             border=T.ACCENT, hover_fill=T.ACCENT_HOVER,
                             hover_fg=T.CANVAS, hover_border=T.ACCENT_HOVER,
                             glyph="▶", disabled=False)
        else:
            self.run_btn.set(text=label, fill=T.RAISED, fg=T.TEXT_2,
                             border=T.BORDER, hover_fill=T.INSET,
                             hover_fg=T.ACCENT, hover_border=T.ACCENT,
                             glyph="→", disabled=False)

    def _run_clicked(self):
        if self.on_run:
            self.on_run()

    # -- lifecycle -----------------------------------------------------------

    def close(self):
        if getattr(self, "on_close", None):
            self.on_close()
        self.root.destroy()
