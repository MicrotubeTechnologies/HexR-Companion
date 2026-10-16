"""A pretend adb, for tests/test_sideload.py and tools/ui_snapshots.py: what the real one prints,
for the few commands the APK Sideload screen runs, with no headset and no real adb server.

Point the app at it with HEXR_ADB=tests/fake_adb.py, and say what it should pretend in a JSON
file named by HEXR_FAKE_ADB:

    {"devices": [["2G0YC1ZF9602Q1", "device", "Quest_3"], ["1WMHH8", "unauthorized"]],
     "install": "success",      # or incompatible, downgrade, storage, gone
     "seconds": 0.5,            # how long an install takes
     "log": "calls.txt"}        # every call's arguments, a JSON list a line

Whether adb's server is running, and whose it is, is the file beside it named <that>.server:
"other" (another program's) or "ours" (started here by start-server). Without it there is no
server, and a command naming the server by address fails as the real one does; start-server
makes one. A test can write or remove it to pretend another program took adb over.

"incompatible" fails until the app has been uninstalled; "downgrade" fails unless -d is passed.
The files are read on every call, so a test can change them between calls.
"""

from __future__ import annotations

import json
import os
import sys
import time

PACKAGE = "com.microtube.hexrdemo"


def main(argv: list[str]) -> int:
    path = os.environ.get("HEXR_FAKE_ADB", "")
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}
    server_file = path + ".server"
    if state.get("log"):
        logged = argv + ([f"ADB_MDNS={os.environ.get('ADB_MDNS')}"]
                         if argv[-1:] == ["start-server"] else [])
        with open(state["log"], "a", encoding="utf-8") as f:
            f.write(json.dumps(logged) + "\n")

    serial, by_address = None, False
    while argv[:1] in (["-s"], ["-H"], ["-P"]):
        if argv[0] == "-s":
            serial = argv[1]
        elif argv[0] == "-H":
            by_address = argv[1] != "localhost"
        argv = argv[2:]
    cmd = argv[0] if argv else ""
    devices = state.get("devices", [])
    server = os.path.exists(server_file)

    if cmd == "version":
        print("Android Debug Bridge version 1.0.41\nVersion 99.0.0-fake\n"
              f"Installed as {os.path.abspath(__file__)}")
        return 0
    if cmd == "start-server":
        if not server:
            with open(server_file, "w") as f:
                f.write("ours")
            print("* daemon not running; starting now at tcp:5037\n* daemon started successfully",
                  file=sys.stderr)
        return 0
    if cmd == "kill-server":
        if server:
            os.remove(server_file)
        return 0
    if not server:
        if by_address:
            print("* cannot start server on remote host\nadb: failed to check server version: "
                  "cannot connect to daemon at tcp:127.0.0.1:5037: cannot connect to "
                  "127.0.0.1:5037: No connection could be made because the target machine "
                  "actively refused it. (10061)", file=sys.stderr)
            return 1
        with open(server_file, "w") as f:
            f.write("ours")
    if cmd == "devices":
        print("List of devices attached")
        for d in devices:
            if d[1] == "device":
                print(f"{d[0]}         device product:eureka model:{d[2]} device:eureka "
                      f"transport_id:1")
            else:
                print(f"{d[0]}         {d[1]} usb:1-1 transport_id:2")
        print()
        return 0

    if serial not in [d[0] for d in devices if d[1] == "device"] or state.get("install") == "gone":
        print(f"adb: device '{serial}' not found", file=sys.stderr)
        return 1
    uninstalled = path + ".uninstalled"
    if cmd == "uninstall":
        open(uninstalled, "w").close()
        print("Success")
        return 0
    if cmd == "install":
        apk = argv[-1]
        if not os.path.isfile(apk):
            print(f"adb: failed to stat {apk}: No such file or directory", file=sys.stderr)
            return 1
        time.sleep(float(state.get("seconds", 0)))
        print("Performing Streamed Install")
        mode = state.get("install", "success")
        failure = None
        if mode == "incompatible" and not os.path.exists(uninstalled):
            failure = (f"INSTALL_FAILED_UPDATE_INCOMPATIBLE: Package {PACKAGE} signatures do not "
                       "match previously installed version; ignoring!")
        elif mode == "downgrade" and "-d" not in argv:
            failure = ("INSTALL_FAILED_VERSION_DOWNGRADE: Downgrade detected: Update version code "
                       "5 is older than current 7")
        elif mode == "storage":
            failure = "INSTALL_FAILED_INSUFFICIENT_STORAGE"
        if failure:
            print(f"adb: failed to install {apk}: Failure [{failure}]", file=sys.stderr)
            return 1
        print("Success")
        return 0
    print(f"adb: unknown command {cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
