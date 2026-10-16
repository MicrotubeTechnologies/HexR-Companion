"""HEXR Companion — entry point and the mediator that wires everything together.

This is a hardware test and diagnostic tool. It is not the way to build with
HEXR: an application integrates the `com.microtube.hexr` Unity package or the
Python control library, and talks to the glove itself.

The App object owns the UI tick. Nothing else polls: the BLE thread mutates
AppState, and this redraws from it 20 times a second.
"""

from __future__ import annotations

import sys
import tkinter as tk

from hexr import i18n
from hexr import theme as T
from hexr.engine import Engine
from hexr.headsets import Headsets
from hexr.screens.connect import ConnectScreen
from hexr.screens.headsets import HeadsetsScreen
from hexr.screens.quicktest import QuickTestScreen
from hexr.screens.test import TestScreen
from hexr.i18n import tr
from hexr.shell import NAV_OF, Shell
from hexr.state import HANDS, AppState

UI_HZ = 20


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        T.init(root, cjk=i18n.language() == "zh")

        self.state = AppState()
        self.engine = Engine(self.state, on_change=self._engine_changed)
        self.engine.start()
        # HEXR headsets on the network. Nothing listens until the Headsets screen is opened.
        self.headsets = Headsets()

        self.shell = Shell(root, on_nav=self.navigate,
                           on_quick_test=lambda: self.open_panel("quicktest"),
                           on_gloves=lambda: self.open_panel("connect"),
                           on_language=self.set_language)
        self.shell.on_close = self.shutdown
        root.protocol("WM_DELETE_WINDOW", self.shell.close)

        self._build_screens()
        # Gloves or Quick test, when one is open as a panel over Test.
        self.panel: str | None = None
        self.navigate("test")

        # Escape is the panic key. A haptics tester can leave a channel pressed
        # against a finger, and reaching for the mouse is the wrong thing to
        # have to do about that.
        root.bind("<Escape>", lambda e: self.all_off())

        self._tick()

    def _build_screens(self):
        self.screens = {
            "connect": ConnectScreen(self.shell.content, self),
            "test": TestScreen(self.shell.content, self),
            "quicktest": QuickTestScreen(self.shell.content, self),
            "headsets": HeadsetsScreen(self.shell.content, self),
        }
        for key, screen in self.screens.items():
            self.shell.register(key, screen)

    def set_language(self, code: str):
        """Rebuild the whole window in the other language. Only the widgets go:
        gloves stay connected, headsets stay linked, and the Test screen's
        choices live in AppState, so nobody has to set anything up again. A
        scan or a quick test in progress is stopped, as closing its screen
        would."""
        if code == i18n.language():
            return
        i18n.set_language(code)
        T.init(self.root, cjk=code == "zh")
        where, panel = self.shell.screen, self.panel
        headset = self.screens["headsets"]._selected
        self.close_panel(go=False)
        if self.engine.scanning:
            self.engine.stop_scan()
        self.shell.rebuild()
        self._build_screens()
        self.screens["headsets"]._selected = headset
        if panel:
            self.open_panel(panel)
        else:
            self.navigate(NAV_OF.get(where, where))

    # -- glove actions -------------------------------------------------------

    def connect_glove(self, found: dict):
        self.engine.connect(found["hand"], found["address"],
                            found.get("name", ""), found.get("rssi"))

    def disconnect(self, hand: str):
        self.engine.disconnect(hand)

    def send(self, hands, data: bytes):
        self.engine.send_hands(list(hands), data)

    def all_off(self):
        self.engine.send_all_off()

    def shutdown(self):
        self.headsets.stop()
        self.engine.shutdown()

    # -- where the window is -------------------------------------------------

    def navigate(self, key: str):
        """A rail entry. Test is the scan until a glove connects, then the
        controls; it never reopens a panel."""
        self.close_panel(go=False)
        if key == "test":
            self._show_test()
        else:
            self.shell.go(key)

    def _show_test(self):
        if self.state.any_connected():
            self.shell.go("test")
        else:
            self.screens["connect"].set_mode(panel=False)
            self.shell.go("connect")

    def open_panel(self, key: str):
        """Gloves ("connect") or Quick test, over the Test screen."""
        if self.panel == key:
            return
        self.close_panel(go=False)
        self.panel = key
        if key == "connect":
            self.screens["connect"].set_mode(panel=True, on_close=self.close_panel)
        else:
            self.screens["quicktest"].set_close(self.close_panel)
        self.shell.go(key)

    def close_panel(self, go: bool = True):
        if self.panel == "quicktest":
            self.screens["quicktest"].stop_if_running()
        self.panel = None
        if go:
            self._show_test()

    # -- UI tick -------------------------------------------------------------

    def _engine_changed(self):
        """Called from the BLE thread. Hop to Tk before touching a widget."""
        self.root.after(0, self._refresh_screens)

    def _refresh_screens(self):
        for screen in self.screens.values():
            if hasattr(screen, "refresh"):
                screen.refresh()

    def _tick(self):
        self._follow_gloves()
        self._sync_status()
        screen = self.screens.get(self.shell.screen)
        if screen is not None and hasattr(screen, "on_tick"):
            screen.on_tick()
        self.root.after(int(1000 / UI_HZ), self._tick)

    def _sync_status(self):
        gloves = self.state.connected_gloves()
        if not gloves:
            self.shell.set_status(T.DOT_OFF, tr("no glove"))
            return
        # A connected glove is a working glove whether or not it streams, so
        # the pill reports the connection and leaves telemetry to the places
        # that actually need it.
        hands = "+".join(sorted(g.hand[0] for g in gloves))
        batteries = [g.battery for g in gloves if g.battery is not None]
        if batteries:
            self.shell.set_status(T.SUCCESS,
                                  f"{hands}  {round(min(batteries) * 100)}%")
        else:
            self.shell.set_status(T.SUCCESS, hands)

    def _follow_gloves(self):
        """Test turns into the controls the moment a glove connects, and back
        into the scan when the last one goes; and the header's Quick test and
        Gloves buttons are there exactly while there is a glove to test."""
        connected = self.state.any_connected()
        if self.panel is None:
            if self.shell.screen == "connect" and connected:
                self.shell.go("test")
            elif self.shell.screen == "test" and not connected:
                self._show_test()
        testing = connected and self.shell.screen in ("test", "connect", "quicktest")
        gloves = [g for g in (self.state.get(h) for h in HANDS) if g]
        if self.engine.scanning or any(g.connecting for g in gloves):
            dot = T.ACCENT
        elif connected:
            dot = T.SUCCESS
        else:
            dot = None
        self.shell.set_test_actions(testing, dot)


def main():
    root = tk.Tk()
    root.title("HEXR Companion")
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
