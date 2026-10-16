"""APK Sideload: reading what adb prints, and installing, against a pretend adb (tests/fake_adb.py).

The device lines are as this computer's adb printed them for a Quest 3; the failures are the
forms Android's package manager gives, as adb passes them on.

Run: python -m pytest tests -q      (or: python tests/test_sideload.py)
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hexr import settings  # noqa: E402
from hexr import sideload as S  # noqa: E402

FAKE = os.path.join(ROOT, "tests", "fake_adb.py")
QUEST = "2G0YC1ZF9602Q1"
# Settings go to a throwaway folder: these tests choose APKs, and the app remembers the last one.
_SETTINGS = tempfile.mkdtemp(prefix="hexr-sideload-test-")
settings._base = lambda: _SETTINGS


# -- reading adb -----------------------------------------------------------------------------

def test_devices_as_adb_lists_them():
    text = ("* daemon not running; starting now at tcp:5037\n"
            "* daemon started successfully\n"
            "List of devices attached\n"
            f"{QUEST}         device product:eureka model:Quest_3 device:eureka transport_id:1\n"
            "1WMHH815K21234         unauthorized usb:1-1 transport_id:2\n"
            "340YC10G9A0123\toffline transport_id:3\n"
            "\n")
    found = S.parse_devices(text)
    assert [(d.serial, d.state) for d in found] == [
        (QUEST, "device"), ("1WMHH815K21234", "unauthorized"), ("340YC10G9A0123", "offline")]
    quest, locked, _ = found
    assert quest.ready and quest.name == "Quest 3" and quest.product == "eureka"
    # A headset that has not yet allowed this computer does not say what it is.
    assert not locked.ready and locked.name == ""


def test_no_devices():
    assert S.parse_devices("List of devices attached\n\n") == []
    assert S.parse_devices("") == []


def test_install_outcomes():
    def check(text, code, package="", exit_code=1):
        o = S.outcome(exit_code, text)
        assert (o.ok, o.code, o.package) == (code == "", code, package), (text, o)

    check("Performing Streamed Install\r\nSuccess\r\n", "", exit_code=0)
    check("adb: failed to install C:\\apps\\HexR.apk: Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: "
          "Package com.microtube.hexrdemo signatures do not match previously installed version; "
          "ignoring!]", "INSTALL_FAILED_UPDATE_INCOMPATIBLE", "com.microtube.hexrdemo")
    # The wording before Android 11.
    check("Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: Existing package com.foo.bar signatures do "
          "not match newer version; ignoring!]", "INSTALL_FAILED_UPDATE_INCOMPATIBLE", "com.foo.bar")
    check("adb: failed to install x.apk: Failure [INSTALL_FAILED_VERSION_DOWNGRADE: Downgrade "
          "detected: Update version code 5 is older than current 7]",
          "INSTALL_FAILED_VERSION_DOWNGRADE")
    check("Failure [INSTALL_FAILED_INSUFFICIENT_STORAGE]", "INSTALL_FAILED_INSUFFICIENT_STORAGE")
    # "installPackageLI" is not a package name.
    check("Failure [INSTALL_FAILED_OLDER_SDK: Failed parse during installPackageLI: "
          "/data/app/vmdl123.tmp/base.apk (at Binary XML file line #7): Requires newer sdk "
          "version #34 (current version is #32)]", "INSTALL_FAILED_OLDER_SDK")
    check("adb: failed to install x.apk: Failure [INSTALL_PARSE_FAILED_NOT_APK: Failed to parse "
          "/data/app/vmdl.tmp/base.apk]", "INSTALL_PARSE_FAILED_NOT_APK")
    check("Failure [INSTALL_FAILED_NO_MATCHING_ABIS: Failed to extract native libraries, "
          "res=-113]", "INSTALL_FAILED_NO_MATCHING_ABIS")
    check("adb: failed to stat C:\\gone.apk: No such file or directory", S.NO_FILE)
    for gone in ("adb: device 'ABC' not found", "adb: device offline",
                 "adb: device unauthorized.\nThis adb server's $ADB_VENDOR_KEYS is not set",
                 "error: no devices/emulators found", "adb: error: failed to read copy response",
                 # adb's server stopped mid-install, by another program
                 "adb: failed to check server version: cannot connect to daemon at "
                 "tcp:127.0.0.1:5037"):
        check(gone, S.DEVICE_GONE)
    check("adb: something odd happened", S.UNKNOWN)
    # A zero exit without "Success" is not a success.
    check("Performing Streamed Install\n", S.UNKNOWN, exit_code=0)


def test_find_adb_follows_the_environment():
    was = os.environ.get(S.ADB_ENV)
    try:
        os.environ[S.ADB_ENV] = FAKE
        assert S.find_adb() == [sys.executable, FAKE]
        os.environ[S.ADB_ENV] = "C:\\tools\\adb.exe"
        assert S.find_adb() == ["C:\\tools\\adb.exe"]
    finally:
        if was is None:
            os.environ.pop(S.ADB_ENV, None)
        else:
            os.environ[S.ADB_ENV] = was


# -- against the pretend adb -----------------------------------------------------------------

class Fake:
    """tests/fake_adb.py, told what to pretend through a file of its own. `server` is whose adb
    server is running when it starts: "other" (another program's), "ours", or None."""

    def __init__(self, server="other", **state):
        self.dir = tempfile.mkdtemp(prefix="hexr-fake-adb-")
        self.path = os.path.join(self.dir, "state.json")
        self.log = os.path.join(self.dir, "calls.txt")
        self.apk = os.path.join(self.dir, "HexR Demo.apk")
        with open(self.apk, "wb") as f:
            f.write(b"PK\x03\x04 not really an apk")
        self.set(devices=[[QUEST, "device", "Quest_3"]], log=self.log, **state)
        self.server(server)
        self._env = {k: os.environ.get(k) for k in (S.ADB_ENV, "HEXR_FAKE_ADB")}
        os.environ[S.ADB_ENV] = FAKE
        os.environ["HEXR_FAKE_ADB"] = self.path

    def set(self, **state):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(state, f)

    def server(self, whose):
        """Pretend adb's server is now `whose`, or not running."""
        if whose is None:
            if os.path.exists(self.path + ".server"):
                os.remove(self.path + ".server")
        else:
            with open(self.path + ".server", "w") as f:
                f.write(whose)

    def calls(self) -> list[list[str]]:
        try:
            with open(self.log, encoding="utf-8") as f:
                return [json.loads(line) for line in f if line.strip()]
        except OSError:
            return []

    def model(self) -> S.Sideload:
        m = S.Sideload()
        m.watch(True)
        assert _until(lambda: m.devices), "the pretend headset never appeared"
        m.selected = m.devices[0].serial
        m.choose(self.apk)
        return m

    def close(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _until(condition, timeout=15.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.05)
    return False


def _install(m: S.Sideload, **kw) -> S.Outcome:
    assert m.start_install(**kw)
    assert _until(lambda: m.install.done), "the install never finished"
    return m.install.outcome


class Quick:
    """The waits for another program's adb server, shortened for a test."""

    def __init__(self, start=0.3, restart=1.5):
        self.was = S.START_AFTER_S, S.RESTART_AFTER_S
        S.START_AFTER_S, S.RESTART_AFTER_S = start, restart

    def close(self):
        S.START_AFTER_S, S.RESTART_AFTER_S = self.was


def test_uses_the_server_running_and_never_stops_it():
    fake = Fake(server="other")
    try:
        m = fake.model()
        assert m.devices[0].name == "Quest 3"
        assert _until(lambda: m.version == "99.0.0-fake"), m.version
        m.shutdown()
        calls = fake.calls()
        assert not any("start-server" in c or "kill-server" in c for c in calls), calls
        # Every command names the server by address, so none of them can start one.
        assert all(c[:2] == S.LOCAL for c in calls if "devices" in c), calls
    finally:
        fake.close()


def test_starts_a_server_when_there_is_none():
    fake, quick = Fake(server=None), Quick()
    try:
        m = fake.model()
        assert m.devices[0].name == "Quest 3"
        # adb's Wi-Fi discovery off: Windows Firewall would ask about it.
        assert ["start-server", "ADB_MDNS=0"] in fake.calls()
        m.shutdown()
        assert not any("kill-server" in c for c in fake.calls())
    finally:
        quick.close()
        fake.close()


def test_does_not_fight_another_program_for_the_server():
    fake, quick = Fake(server=None), Quick(start=0.3, restart=2.0)
    try:
        m = fake.model()
        # Another program stops this app's server, and starts its own a moment later.
        fake.server(None)
        assert _until(lambda: not m.devices, 5)
        time.sleep(0.5)
        fake.server("other")
        assert _until(lambda: m.devices, 5)
        time.sleep(2.5)
        starts = [c for c in fake.calls() if "start-server" in c]
        assert len(starts) == 1, f"started its own server again: {starts}"
        m.shutdown()
    finally:
        quick.close()
        fake.close()


def test_installs_replacing_with_permissions():
    fake = Fake(install="success")
    try:
        m = fake.model()
        o = _install(m)
        assert o.ok, o
        assert m.install.name == "Quest 3"
        assert S.LOCAL + ["-s", QUEST, "install", "-r", "-t", "-g", fake.apk] in fake.calls()
        m.shutdown()
    finally:
        fake.close()


def test_another_key_then_uninstall_and_install():
    fake = Fake(install="incompatible")
    try:
        m = fake.model()
        o = _install(m)
        assert o.code == "INSTALL_FAILED_UPDATE_INCOMPATIBLE" and o.package == "com.microtube.hexrdemo"
        o = _install(m, uninstall=o.package)
        assert o.ok, o
        calls = fake.calls()
        after = calls[calls.index(S.LOCAL + ["-s", QUEST, "uninstall", "com.microtube.hexrdemo"]) + 1:]
        assert S.LOCAL + ["-s", QUEST, "install", "-r", "-t", "-g", fake.apk] in after
        m.shutdown()
    finally:
        fake.close()


def test_older_version_needs_downgrade():
    fake = Fake(install="downgrade")
    try:
        m = fake.model()
        assert _install(m).code == "INSTALL_FAILED_VERSION_DOWNGRADE"
        assert _install(m, downgrade=True).ok
        assert S.LOCAL + ["-s", QUEST, "install", "-r", "-t", "-g", "-d", fake.apk] in fake.calls()
        m.shutdown()
    finally:
        fake.close()


def test_stop_unplugged_and_missing_file():
    fake = Fake(install="success", seconds=10)
    try:
        m = fake.model()
        assert m.start_install()
        assert not m.start_install(), "a second install while one is going"
        t = time.monotonic()
        m.install.stop()
        assert _until(lambda: m.install.done, 5)
        assert m.install.outcome.code == S.STOPPED and time.monotonic() - t < 5

        fake.set(devices=[[QUEST, "device", "Quest_3"]], install="gone", log=fake.log)
        assert _install(m).code == S.DEVICE_GONE

        fake.set(devices=[[QUEST, "device", "Quest_3"]], install="success", log=fake.log)
        m.apk = os.path.join(fake.dir, "moved.apk")
        assert _install(m).code == S.NO_FILE
        m.shutdown()
    finally:
        fake.close()


def test_install_needs_a_ready_headset_and_an_apk():
    fake = Fake(install="success")
    try:
        fake.set(devices=[["1WMHH815K21234", "unauthorized"]], log=fake.log)
        m = S.Sideload()
        m.watch(True)
        assert _until(lambda: m.devices)
        m.selected = m.devices[0].serial
        m.choose(fake.apk)
        assert not m.start_install(), "not until the headset allows this computer"
        m.selected = None
        assert not m.start_install()
        m.shutdown()
    finally:
        fake.close()


def test_adb_that_will_not_run():
    was = os.environ.get(S.ADB_ENV)
    try:
        os.environ[S.ADB_ENV] = os.path.join(tempfile.gettempdir(), "no-such-adb.exe")
        m = S.Sideload()
        m.watch(True)
        assert _until(lambda: m.problem == "broken")
        assert m.devices == []
        m.shutdown()
    finally:
        if was is None:
            os.environ.pop(S.ADB_ENV, None)
        else:
            os.environ[S.ADB_ENV] = was


if __name__ == "__main__":
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except AssertionError as e:
                failures += 1
                print(f"  FAIL  {name}: {e}")
    print(f"\n{'FAILED' if failures else 'All sideload tests passed'}"
          f"{f' ({failures} failing)' if failures else ''}")
    sys.exit(1 if failures else 0)
