"""Installing an app on a headset plugged into this computer: adb, as the APK Sideload screen uses it.

The app carries Google's adb (tools/fetch_adb.py puts it in assets/adb before a build), so
installing needs no internet and nothing else on the computer. A partner behind a firewall that
stops SideQuest fetching adb, and so seeing the headset at all, has it already. Run from source,
an adb on PATH or in the Android SDK does as well.

adb runs as a program of its own and this reads what it prints. Its output goes to a temporary
file rather than a pipe: starting adb's server leaves it running after the command, holding a
pipe open, so reading one to its end would wait for the server to exit.

adb is one server per computer, shared by every program that uses it, and on a developer's
computer others do (Unity polls it every few seconds, with its own adb). One that finds a server
it did not start may stop it and start its own, and two programs that each restart their own
are SideQuest's "it keeps losing the headset". So this never fights for it:

* Every command names the server by address (`-H 127.0.0.1`), and adb only starts a server on
  its own when it is named "localhost". So no command here ever starts one by accident.
* When there is no server, another program gets a moment to start its own; only then is this
  app's started. If that one goes, someone took it over: theirs is given longer still.
* This app never stops the server, not even on the way out. Whichever is running serves it:
  adb's protocol has not changed in years, so any adb talks to any other's server.

This app's server starts with adb's Wi-Fi discovery (mDNS) off: installing is over USB, and on
Windows that discovery is what makes the firewall ask about adb.

Nothing here touches Tk. Threads write the fields; the screen reads them on its own tick.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass

from . import settings
from . import theme as T

# A command to run instead of the adb found: a .py runs with this Python. Tests and
# tools/ui_snapshots.py point it at tests/fake_adb.py.
ADB_ENV = "HEXR_ADB"
POLL_S = 1.0
START_AFTER_S = 2.0         # no server when first looking: another program's to start, for this long
RESTART_AFTER_S = 8.0       # this app's server went: another program took adb over, most likely
LOCAL = ["-H", "127.0.0.1"]     # the server by address, which no command starts by itself
NO_SERVER = "cannot connect to daemon"
WIN = sys.platform == "win32"
# The app has no console, so without this every adb command would flash one up on Windows.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if WIN else 0
SETTINGS_FILE = "settings.json"

# What `adb devices -l` lists a device as. "no" is the start of "no permissions", on Linux.
STATES = {"device", "unauthorized", "offline", "authorizing", "connecting", "recovery",
          "rescue", "sideload", "bootloader", "no"}

# Ours, beside Android's INSTALL_FAILED_… codes.
DEVICE_GONE = "DEVICE_GONE"     # unplugged, asleep, or no longer allowing this computer
NO_FILE = "NO_FILE"             # the APK is not where it was chosen
STOPPED = "STOPPED"
ADB_FAILED = "ADB_FAILED"       # adb itself would not run
UNKNOWN = "UNKNOWN"

_FAILURE = re.compile(r"Failure \[([A-Z][A-Z0-9_]*)(?::\s*([^\]]*))?\]")
_PACKAGE = re.compile(r"\b[Pp]ackage:?\s+([A-Za-z]\w*(?:\.[A-Za-z_]\w*)+)")
_GONE = ("device offline", "unauthorized", "no devices", "not found", "error: closed",
         "protocol fault", "failed to write", "failed to read", "connection reset",
         "device still authorizing", NO_SERVER)


@dataclass(frozen=True)
class Device:
    serial: str
    state: str
    model: str = ""             # "Quest_3"; adb only knows it once the headset allows this computer
    product: str = ""

    @property
    def name(self) -> str:
        return self.model.replace("_", " ")

    @property
    def ready(self) -> bool:
        return self.state == "device"


@dataclass
class Outcome:
    ok: bool
    code: str = ""              # INSTALL_FAILED_… as Android says it, or one of ours above
    package: str = ""           # the app's package, when the failure names it
    raw: str = ""               # everything adb printed


def parse_devices(text: str) -> list[Device]:
    """`adb devices -l` into devices. The server's own lines ("* daemon started successfully")
    and anything else that is not a device are left out."""
    found = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2 or parts[1] not in STATES or line.startswith(("*", "List of")):
            continue
        fields = dict(p.split(":", 1) for p in parts[2:] if ":" in p)
        found.append(Device(parts[0], parts[1], fields.get("model", ""),
                            fields.get("product", "")))
    return found


def outcome(code: int | None, text: str) -> Outcome:
    """What `adb install` (or `uninstall`) printed, and its exit code, as an Outcome."""
    if code == 0 and "Success" in text:
        return Outcome(True, raw=text)
    m = _FAILURE.search(text)
    if m:
        package = _PACKAGE.search(m.group(2) or "")
        return Outcome(False, m.group(1), package.group(1) if package else "", text)
    low = text.lower()
    if "failed to stat" in low or "no such file" in low or "failed to open" in low:
        return Outcome(False, NO_FILE, raw=text)
    if any(words in low for words in _GONE):
        return Outcome(False, DEVICE_GONE, raw=text)
    return Outcome(False, UNKNOWN, raw=text)


def find_adb() -> list[str] | None:
    """The command that runs adb: the app's own, else one this computer already has."""
    env = os.environ.get(ADB_ENV)
    if env:
        return [sys.executable, env] if env.endswith(".py") else [env]
    name = "adb.exe" if WIN else "adb"
    places = [T.resource_path("assets", "adb", name), shutil.which("adb")]
    if WIN:
        places.append(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk",
                                   "platform-tools", name))
    else:
        places.append(os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"))
    for path in places:
        if path and os.path.isfile(path):
            return [os.path.abspath(path)]
    return None


def _spawn(cmd: list[str], args: list[str], out, env=None) -> subprocess.Popen:
    return subprocess.Popen(cmd + args, stdin=subprocess.DEVNULL, stdout=out,
                            stderr=subprocess.STDOUT, creationflags=_NO_WINDOW, env=env)


def _read(out) -> str:
    out.seek(0)
    return out.read().decode("utf-8", "replace").replace("\r\n", "\n")


def run(cmd: list[str], args: list[str], timeout: float = 20.0,
        env=None) -> tuple[int | None, str]:
    """adb with these arguments: its exit code (None if it took too long) and what it printed."""
    with tempfile.TemporaryFile() as out:
        p = _spawn(cmd, args, out, env)
        try:
            code = p.wait(timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
            code = None
        return code, _read(out)


class Install:
    """One install on one headset, on its own thread: `done`, then `outcome`.

    `-r` replaces a copy already there, `-t` lets a development build in, and `-g` grants the
    app's permissions now, so a HEXR app is not left waiting on a Bluetooth question in the
    headset before it can reach its gloves. `uninstall` first removes a copy signed with another
    key, which Android will not replace; `downgrade` lets an older version replace a newer one.
    """

    def __init__(self, cmd: list[str], serial: str, apk: str, downgrade: bool = False,
                 uninstall: str = "", name: str = ""):
        self.cmd, self.serial, self.apk = cmd, serial, apk
        self.name = name                    # the headset's, for saying how it went once it is gone
        self.downgrade, self.uninstall = downgrade, uninstall
        self.phase = "uninstalling" if uninstall else "installing"
        self.started = time.monotonic()
        self.done = False
        self.outcome: Outcome | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="hexr-install", daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        try:
            if self.uninstall:
                # Whatever it says, the install after it gives the answer that matters.
                run(self.cmd, LOCAL + ["-s", self.serial, "uninstall", self.uninstall], 60)
                self.phase = "installing"
            if not os.path.isfile(self.apk):
                self.outcome = Outcome(False, NO_FILE)
                return
            args = LOCAL + ["-s", self.serial, "install", "-r", "-t", "-g"]
            if self.downgrade:
                args.append("-d")
            with tempfile.TemporaryFile() as out:
                p = _spawn(self.cmd, args + [self.apk], out)
                while p.poll() is None:
                    if self._stop.wait(0.2):
                        p.terminate()
                        p.wait()
                        self.outcome = Outcome(False, STOPPED, raw=_read(out))
                        return
                self.outcome = outcome(p.returncode, _read(out))
        except OSError as e:
            self.outcome = Outcome(False, ADB_FAILED, raw=str(e))
        finally:
            self.done = True


class Sideload:
    """The adb this app runs, the headsets plugged in, the APK chosen and the install going.

    Kept on the app rather than the screen, so a language switch, which rebuilds the screens,
    loses neither the APK nor an install half done. Nothing runs until `watch(True)`, when the
    screen is first shown.
    """

    def __init__(self):
        self.cmd = find_adb()
        self.devices: list[Device] = []
        self.problem = "" if self.cmd else "missing"    # missing | broken
        self.problem_text = ""                          # what adb said, when broken
        self.version = ""                               # adb's own: "37.0.1-15733141"
        data = settings.load(SETTINGS_FILE)
        apk = data.get("apk")
        self.apk = apk if isinstance(apk, str) and os.path.isfile(apk) else ""
        self.selected: str | None = None                # a device's serial
        self.install: Install | None = None
        self._active = threading.Event()
        self._closing = threading.Event()
        self._thread: threading.Thread | None = None
        self._started_server = False                    # ever, by this app
        self._no_server_since: float | None = None

    @property
    def adb_path(self) -> str:
        return self.cmd[-1] if self.cmd else ""

    # -- headsets -------------------------------------------------------------------------------

    def watch(self, on: bool):
        """Look for headsets while the screen is shown, and stop looking when it is not."""
        if not on:
            self._active.clear()
            return
        self._active.set()
        if self._thread is None and self.cmd:
            self._thread = threading.Thread(target=self._run, name="hexr-adb", daemon=True)
            self._thread.start()

    def _run(self):
        try:
            _code, text = run(self.cmd, ["version"], 10)
            self.version = next((ln.split(None, 1)[-1] for ln in text.splitlines()
                                 if ln.startswith("Version ")), "")
        except OSError:
            pass
        while not self._closing.is_set():
            self._active.wait()
            if self._closing.is_set():
                break
            self._look()
            self._closing.wait(POLL_S)

    def _look(self):
        try:
            code, text = run(self.cmd, LOCAL + ["devices", "-l"], 30)
        except OSError as e:
            code, text = None, str(e)
        if code == 0:
            self.devices = parse_devices(text)
            self.problem, self.problem_text = "", ""
            self._no_server_since = None
            return
        self.devices = []
        if NO_SERVER not in text:
            self.problem = "broken"
            self.problem_text = text.strip() or "adb did not answer"
            return
        # No server. Another program may be about to start one; this app's is only started
        # when none has come, and if this app's went, whoever stopped it is given longer.
        now = time.monotonic()
        if self._no_server_since is None:
            self._no_server_since = now
        if now - self._no_server_since >= (RESTART_AFTER_S if self._started_server
                                           else START_AFTER_S):
            self._start_server()
            self._no_server_since = None

    def _start_server(self):
        env = dict(os.environ, ADB_MDNS="0")
        try:
            code, text = run(self.cmd, ["start-server"], 30, env=env)
        except OSError as e:
            code, text = None, str(e)
        if code == 0:
            self._started_server = True
        else:
            self.problem = "broken"
            self.problem_text = text.strip() or "adb did not start"

    def device(self, serial: str | None) -> Device | None:
        return next((d for d in self.devices if d.serial == serial), None)

    # -- the APK, and installing it -------------------------------------------------------------

    def choose(self, apk: str):
        """The APK to install, remembered for the next run, and its folder for the next choice."""
        self.apk = apk
        data = settings.load(SETTINGS_FILE)
        data["apk"] = apk
        data["apk_folder"] = os.path.dirname(apk)
        settings.save(SETTINGS_FILE, data)

    def start_install(self, downgrade: bool = False, uninstall: str = "") -> bool:
        """Install the chosen APK on the selected headset. False if either is missing, or an
        install is already going."""
        d = self.device(self.selected)
        if not self.cmd or not self.apk or d is None or not d.ready or self.busy:
            return False
        self.install = Install(self.cmd, d.serial, self.apk, downgrade, uninstall, d.name)
        self.install.start()
        return True

    @property
    def busy(self) -> bool:
        return self.install is not None and not self.install.done

    def shutdown(self):
        """Stop looking, and stop an install half done. adb's server is left running: another
        program may be using it by now (see the top of this file)."""
        self._closing.set()
        self._active.set()
        if self.install and not self.install.done:
            self.install.stop()
