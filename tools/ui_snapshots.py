"""Screenshots of every screen, in either language, with pretend gloves and a pretend headset.

For reviewing the UI without a glove or a headset to hand. It runs the real app with its
Bluetooth replaced: a search that "finds" one left and two right gloves, and gloves that
connect, stream pressure and react to the Test screen's Trigger. The Headsets screen watches
tools/fake_headset.py, started here. Settings go to a throwaway folder, so nothing you
have set up is touched.

    python tools/ui_snapshots.py --lang en --out snapshots
    python tools/ui_snapshots.py --lang zh --out snapshots

Each state is a PNG in --out. The run ends with a report: whether Connect, Test and
Quick test fit the window without scrolling, and how long the UI tick takes.
Needs PyAV and Pillow, as the app's view does. Windows: the window appears on screen
while it runs.
"""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import tempfile
import threading
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--lang", choices=("en", "zh"), default="en")
    parser.add_argument("--out", default="snapshots")
    parser.add_argument("--video", help="a clip for the pretend headset to show")
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    # Settings in a folder of their own, before anything reads them.
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="hexr-snapshots-")
    os.environ["HEXR_VIDEOS"] = tempfile.mkdtemp(prefix="hexr-snapshots-videos-")
    from hexr import i18n
    i18n._lang = args.lang

    import tkinter as tk

    from PIL import ImageGrab

    import hexr_tester

    from hexr.engine import Engine

    root = tk.Tk()
    report: list[str] = []
    ticks: list[float] = []
    driving = {"on": False, "t0": 0.0}

    # -- a pretend Bluetooth -------------------------------------------------------------------
    results = [
        {"address": "C0:FF:EE:00:01:0A", "name": "HaptGloveAR Left", "hand": "Left", "rssi": -58},
        {"address": "C0:FF:EE:00:02:0B", "name": "HaptGloveAR Right", "hand": "Right", "rssi": -66},
        {"address": "C0:FF:EE:00:03:0C", "name": "HaptGloveAR Right", "hand": "Right", "rssi": -81},
    ]

    def fake_scan(engine, on_result, on_done):
        if engine.scanning:
            return
        engine.scanning = True

        def run():
            for r in results:
                time.sleep(0.15)
                on_result(dict(r))
            time.sleep(0.5)
            engine.scanning = False
            on_done(None)
        threading.Thread(target=run, daemon=True).start()

    def connect_glove(hand, address, name="", rssi=None, live=True):
        g = app.state.add_glove(hand, address, name, rssi)
        g.connected, g.connecting, g.status = True, False, "Connected"
        g.telemetry.battery = 0.85 if hand == "Left" else 0.62
        g.telemetry.seen = True
        g.last_rx = time.monotonic() if live else 0.0
        g.absolute_pa = False
        return g

    def fake_connect(engine, hand, address, name="", rssi=None):
        g = engine.state.add_glove(hand, address, name, rssi)
        g.connecting, g.status = True, "Connecting…"
        root.after(700, lambda: connect_glove(hand, address, name, rssi))

    # Bluetooth replaced before the app exists: it starts searching the moment it opens.
    Engine.scan = fake_scan
    Engine.stop_scan = lambda engine: setattr(engine, "scanning", False)
    Engine.connect = fake_connect
    Engine.disconnect = lambda engine, hand: engine.state.gloves.pop(hand, None)
    app = hexr_tester.App(root)
    # Kept above other windows: the shots are grabbed from the screen.
    root.attributes("-topmost", True)
    root.update()

    def stream():
        """Telemetry for the pretend gloves: what the pad or the quick test is driving."""
        test = app.screens.get("test")
        quick = app.screens.get("quicktest")
        for hand, g in list(app.state.gloves.items()):
            if not g.connected:
                continue
            if g.last_rx:
                g.last_rx = time.monotonic()
            raw = [0.4] * 6 + [45.0]
            held = test is not None and test.on and hand in app.state.test.hands
            if held:
                for ch in app.state.test.channels:
                    raw[ch] = 15 + 35 * (app.state.test.intensity - .1) / .9
            if quick is not None and quick._phase == "drive" and hand == quick.hand:
                weak = driving.get("weak", {})
                for ch in range(6):
                    raw[ch] = weak.get(ch, 46.0)
                raw[6] = driving.get("source", 52.0)
            if driving["on"]:
                t = time.monotonic() - driving["t0"]
                for ch in range(6):
                    raw[ch] = 25 + 22 * math.sin(t * 3 + ch)
            g.telemetry.pressure_raw = raw
        root.after(50, stream)

    stream()

    # -- timing the UI tick ------------------------------------------------------------------
    original_tick = app._tick

    def timed_tick():
        t = time.perf_counter()
        original_tick()
        ticks.append((time.perf_counter() - t) * 1000)
    app._tick = timed_tick

    # -- capture -------------------------------------------------------------------------------
    def shot(name):
        if root.state() != "normal":           # minimised by something else on the desktop
            print("window was", root.state(), flush=True)
            root.deiconify()
        root.lift()
        root.update()
        full = ImageGrab.grab(all_screens=True)
        scale = full.width / max(1, root.winfo_vrootwidth() or root.winfo_screenwidth())
        x0, y0 = root.winfo_vrootx(), root.winfo_vrooty()
        box = [int((root.winfo_rootx() - x0) * scale), int((root.winfo_rooty() - y0) * scale)]
        box += [box[0] + int(root.winfo_width() * scale), box[1] + int(root.winfo_height() * scale)]
        full.crop(box).save(os.path.join(out, f"{args.lang}-{name}.png"))
        print("shot", name, flush=True)

    def fits(name):
        screen = app.screens[app.shell.screen]
        area = screen._area
        view = area._canvas.winfo_height() - area._pady * 2
        need = screen.root_body.winfo_reqheight()
        report.append(f"{'PASS' if need <= view + 2 else 'FAIL'}  {name}: needs {need}px of {view}px")

    headset = None
    steps = []

    def at(seconds, fn):
        steps.append((seconds, fn))

    def details(screen_key, on):
        s = app.screens[screen_key]
        if s.details != on:
            s.details_toggle.set(on, notify=True)

    def test_screen():
        return app.screens["test"]

    def quick_finish(weak=None, source=52.0):
        q = app.screens["quicktest"]
        driving["weak"], driving["source"] = weak or {}, source
        q._toggle()

    t = 1.0
    at(t, lambda: (app.navigate("test"), None)); t += 2.0
    at(t, lambda: (shot("connect-searching"), fits("Connect"))); t += 0.3
    at(t, lambda: details("connect", True)); t += 0.6
    at(t, lambda: shot("connect-details")); t += 0.3
    at(t, lambda: details("connect", False)); t += 0.2
    at(t, lambda: app.screens["connect"]._button("Left")); t += 0.4
    at(t, lambda: shot("connect-lit")); t += 2.5
    at(t, lambda: (shot("test-one-glove"), fits("Test"))); t += 0.3
    at(t, lambda: test_screen()._select({0, 1, 2})); t += 0.3
    at(t, lambda: test_screen()._trigger()); t += 0.6
    at(t, lambda: shot("test-pressing")); t += 0.3
    at(t, lambda: app.all_off()); t += 0.3
    at(t, lambda: connect_glove("Right", "C0:FF:EE:00:02:0B", "HaptGloveAR Right")); t += 0.5
    at(t, lambda: test_screen()._pick_mode("vibration")); t += 0.3
    at(t, lambda: test_screen()._trigger()); t += 0.5
    at(t, lambda: shot("test-two-gloves-vibrating")); t += 0.2
    at(t, lambda: test_screen()._pick_mode("pressure")); t += 0.2
    at(t, lambda: test_screen()._trigger()); t += 0.3
    at(t, lambda: app.shell.toggle_maximise()); t += 1.2
    at(t, lambda: shot("test-maximised")); t += 0.2
    at(t, lambda: app.shell.toggle_maximise()); t += 0.8
    at(t, lambda: test_screen()._pick_mode("vibration")); t += 0.2
    at(t, lambda: app.all_off()); t += 0.2
    at(t, lambda: details("test", True)); t += 0.3
    at(t, lambda: (driving.update(on=True, t0=time.monotonic()))); t += 1.0
    at(t, lambda: shot("test-details")); t += 4.0
    at(t, lambda: (driving.update(on=False), details("test", False),
                   test_screen()._pick_mode("pressure"))); t += 0.3
    at(t, lambda: app.open_panel("quicktest")); t += 0.6
    at(t, lambda: (shot("quick-idle"), fits("Quick test"))); t += 0.3
    at(t, lambda: quick_finish()); t += 1.6
    at(t, lambda: shot("quick-running")); t += 1.6
    at(t, lambda: shot("quick-all-good")); t += 0.3
    at(t, lambda: quick_finish(weak={3: 22.0, 4: 30.0})); t += 3.0
    at(t, lambda: shot("quick-poor")); t += 0.3
    at(t, lambda: quick_finish(weak={5: 0.5}, source=50.0)); t += 3.0
    at(t, lambda: (details("quicktest", True), None)); t += 0.4
    at(t, lambda: shot("quick-failed-details")); t += 0.3
    at(t, lambda: details("quicktest", False)); t += 0.2
    at(t, lambda: quick_finish(weak={ch: 0.3 for ch in range(6)}, source=3.0)); t += 3.0
    at(t, lambda: shot("quick-pump-failed")); t += 0.3
    at(t, lambda: app.close_panel()); t += 0.3
    at(t, lambda: app.open_panel("connect")); t += 0.8
    at(t, lambda: shot("gloves-panel")); t += 0.3
    at(t, lambda: app.close_panel()); t += 0.2

    def start_headset():
        nonlocal headset
        cmd = [sys.executable, os.path.join(ROOT, "tools", "fake_headset.py")]
        if args.video:
            cmd += ["--video", args.video]
        headset = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    at(t, lambda: app.navigate("headsets")); t += 0.8
    at(t, lambda: shot("headsets-empty")); t += 0.2
    at(t, start_headset); t += 5.0
    at(t, lambda: shot("headsets-listed")); t += 0.3

    def open_first():
        rows = app.headsets.rows()
        if rows:
            app.screens["headsets"]._select(rows[0].key)
    at(t, open_first); t += 1.5
    at(t, lambda: shot("headsets-opened")); t += 0.3
    at(t, lambda: app.screens["headsets"]._detail._toggle_view()); t += 4.5
    at(t, lambda: shot("headsets-live")); t += 0.3
    at(t, lambda: details("headsets", True)); t += 0.8
    at(t, lambda: (app.screens["headsets"].scroll_to(app.screens["headsets"].detail_host),
                   None)); t += 0.5
    at(t, lambda: shot("headsets-details")); t += 0.3
    at(t, lambda: details("headsets", False)); t += 0.3

    # -- a recording, and exporting it
    def detail():
        return app.screens["headsets"]._detail
    at(t, lambda: detail()._toggle_record()); t += 4.0
    at(t, lambda: shot("headsets-recording")); t += 0.2
    at(t, lambda: detail()._toggle_record()); t += 2.5
    at(t, lambda: shot("headsets-saved")); t += 0.2
    at(t, lambda: detail()._open_recording()); t += 2.5
    at(t, lambda: shot("recordings-landscape")); t += 0.2
    recs = lambda: app.screens["recordings"]  # noqa: E731
    at(t, lambda: recs()._play_pause()); t += 1.5
    at(t, lambda: shot("recordings-playing")); t += 0.2
    at(t, lambda: recs()._play_pause()); t += 0.3
    at(t, lambda: (recs().shape.set("portrait"), recs()._pick_shape("portrait"))); t += 2.0
    at(t, lambda: shot("recordings-portrait")); t += 0.2
    at(t, lambda: recs()._export_clicked()); t += 1.0
    at(t, lambda: shot("recordings-exporting")); t += 8.0
    at(t, lambda: shot("recordings-exported")); t += 0.2
    at(t, lambda: (recs().shape.set("view"), recs()._pick_shape("view"))); t += 2.0
    at(t, lambda: shot("recordings-view")); t += 0.2

    def finish():
        if headset:
            headset.terminate()
        hot = sorted(ticks)
        if hot:
            avg = sum(hot) / len(hot)
            report.append(f"tick: average {avg:.1f} ms, 95th percentile "
                          f"{hot[int(len(hot) * .95)]:.1f} ms over {len(hot)} ticks")
        print("\n".join(report), flush=True)
        try:
            app.shutdown()
        except Exception:
            pass
        root.destroy()
    at(t, finish)

    started = time.monotonic()

    def run():
        now = time.monotonic() - started
        while steps and steps[0][0] <= now:
            _, fn = steps.pop(0)
            try:
                fn()
            except Exception:
                print("step failed:\n" + traceback.format_exc(), flush=True)
        if steps:
            root.after(50, run)

    root.after(50, run)
    root.mainloop()


if __name__ == "__main__":
    main()
