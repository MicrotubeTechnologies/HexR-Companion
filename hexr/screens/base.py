"""Shared scaffolding for the screens.

Every screen opens the same way: a 22 px title, and at most a short line under it.
The title row's right end holds the screen's own actions: a secondary button, the
ⓘ Details toggle, and Close when the screen is a panel over another.

Details is the one place the numbers live (kPa, addresses, versions): off by
default, and remembered per screen. It only ever adds to a screen; it never moves
what is already there.
"""

from __future__ import annotations

import tkinter as tk

from .. import settings
from .. import theme as T
from ..i18n import tr
from ..widgets import Button, DetailsToggle, ScrollArea

SETTINGS_FILE = "settings.json"


def details_saved(key: str) -> bool:
    try:
        return bool(settings.load(SETTINGS_FILE).get("details", {}).get(key, False))
    except AttributeError:
        return False


def save_details(key: str, on: bool):
    data = settings.load(SETTINGS_FILE)
    details = data.get("details") if isinstance(data.get("details"), dict) else {}
    details[key] = bool(on)
    data["details"] = details
    settings.save(SETTINGS_FILE, data)


class Screen(tk.Frame):
    """Base screen. Build your content into `self.body`. `title_text` and
    `sub_text` are English marked with N_(), and shown translated."""

    title_text = ""
    sub_text = ""
    key = ""                # names this screen's Details setting
    has_details = False     # an ⓘ Details toggle in the title row
    fill = False            # the body fills the window rather than scrolling past it

    def __init__(self, parent, app=None):
        super().__init__(parent, bg=T.SURFACE)
        self.app = app
        self._area = ScrollArea(self, bg=T.SURFACE, fill_height=self.fill)
        self._area.pack(fill="both", expand=True)
        self.root_body = self._area.body

        self.head = tk.Frame(self.root_body, bg=T.SURFACE)
        self.head.pack(fill="x", anchor="w")
        title_row = tk.Frame(self.head, bg=T.SURFACE)
        title_row.pack(fill="x", anchor="w")
        self._title = tk.Label(title_row, text=tr(self.title_text), bg=T.SURFACE,
                               fg=T.TEXT, font=T.font(22, 600), anchor="w",
                               justify="left")
        self._title.pack(side="left", anchor="w")

        # Right to left: Close, then Details, then whatever the screen adds.
        self._close_slot = tk.Frame(title_row, bg=T.SURFACE)
        self._close_slot.pack(side="right")
        self._details_slot = tk.Frame(title_row, bg=T.SURFACE)
        self._details_slot.pack(side="right")
        self.head_actions = tk.Frame(title_row, bg=T.SURFACE)
        self.head_actions.pack(side="right")

        self._close = Button(self._close_slot, tr("Close"), glyph="×", glyph_px=15, height=32,
                             fill=T.RAISED, fg=T.TEXT_2, border=T.BORDER,
                             hover_fill=T.INSET, hover_fg=T.TEXT,
                             hover_border=T.ACCENT, min_width=96)
        self.details = False
        if self.has_details:
            self.details = details_saved(self.key)
            self.details_toggle = DetailsToggle(self._details_slot, value=self.details,
                                                on_change=self._details_changed)
            self.details_toggle.pack(side="right", padx=(10, 0))

        self._sub = tk.Label(self.head, text=tr(self.sub_text), bg=T.SURFACE,
                             fg=T.TEXT_MUTED, font=T.font(13.5), anchor="w",
                             justify="left", wraplength=620)
        if self.sub_text:
            self._sub.pack(fill="x", anchor="w", pady=(4, 0))

        self.body = tk.Frame(self.root_body, bg=T.SURFACE)
        self.body.pack(fill="both", expand=True, pady=(20, 0))
        # Under a filling screen: what Details adds. The screen above keeps its size and the
        # window scrolls to it. Packed by show_details_below.
        self.below = tk.Frame(self.root_body, bg=T.SURFACE)
        self._area.extra = self.below

    def set_heading(self, title=None, sub=None):
        """Already translated: the caller knows its own words. An empty sub hides it."""
        if title is not None:
            self._title.configure(text=title)
        if sub is not None:
            self._sub.configure(text=sub)
            if sub and not self._sub.winfo_manager():
                self._sub.pack(fill="x", anchor="w", pady=(4, 0), after=self._title.master)
            elif not sub:
                self._sub.pack_forget()

    def set_close(self, command=None):
        """Show a Close button at the right of the title row that runs `command`, or hide it."""
        if command is None:
            self._close.pack_forget()
        else:
            self._close.set(command=command)
            if not self._close.winfo_manager():
                self._close.pack(side="right", padx=(10, 0))

    def _details_changed(self, on: bool):
        self.details = on
        save_details(self.key, on)
        self.show_details(on)
        self.update_idletasks()
        self.refit()
        if self.below.winfo_manager():
            self._area.reveal(self.below)
        elif self.fill:
            self._area.to_top()

    def show_details_below(self, on: bool):
        """Show or hide `self.below`, for a screen that keeps its Details there."""
        if on and not self.below.winfo_manager():
            self.below.pack(fill="x", after=self.body)
        elif not on and self.below.winfo_manager():
            self.below.pack_forget()

    def show_details(self, on: bool):
        """Show or hide this screen's numbers. Called with the saved value once built."""

    def refit(self):
        """Keep a filling screen the height of the window, or of its content if taller."""
        self._area.refit()

    def scroll_to(self, widget):
        self._area.scroll_to(widget)

    def reveal(self, widget):
        self._area.reveal(widget)

    def on_show(self):
        """Called each time the screen becomes visible."""

    def on_hide(self):
        """Called when another screen takes its place."""


def section_label(parent, text, bg=T.SURFACE):
    """The design's tracked uppercase micro-label."""
    return tk.Label(parent, text=T.track(text), bg=bg, fg=T.TEXT_FAINT,
                    font=T.font(10), anchor="w")
