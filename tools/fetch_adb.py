"""Put Google's adb in assets/adb, for the build to ship inside the app.

    python tools/fetch_adb.py                    # for the platform this runs on
    python tools/fetch_adb.py --platform mac     # or windows

The APK Sideload screen installs apps with adb, and the app carries its own: a computer behind a
firewall that stops SideQuest fetching adb (and with it, seeing the headset at all) needs nothing
from the internet once the app is installed. The build stops if this has not been run
(HexR-Companion.spec), so a release cannot quietly ship without it.

One release of Android SDK Platform-Tools is pinned, and its download checked against the
SHA-256 here before anything is unpacked. To move to a newer one: Google lists every archive with
its SHA-1 in https://dl.google.com/android/repository/repository2-3.xml (under
path="platform-tools"); download the new ones, check them against that, and pin their SHA-256.

Only adb and what it loads are kept, with Google's NOTICE.txt, the licences of what adb is built
from. Nothing else in Platform-Tools (fastboot and the rest) is shipped.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "adb")
URL = "https://dl.google.com/android/repository/"

VERSION = "37.0.1"
ARCHIVES = {
    # AdbWinApi.dll is what adb.exe talks to the USB driver through; it loads AdbWinUsbApi.dll.
    "windows": ("platform-tools_r37.0.1-win.zip",
                "45f4d63113e895ebde0c90f194099a4676b6ac653bd28d54314a9e022bbc1a99",
                ("adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll")),
    # One universal binary, Apple silicon and Intel, that needs nothing but macOS itself.
    "mac": ("platform-tools_r37.0.1-darwin.zip",
            "ee39ad5967e95c2a07f04dbcbde96b1a0c916ba376096db5d2f498b7727a5d1d",
            ("adb",)),
}
NOTICE = "NOTICE.txt"
STAMP = "VERSION.txt"


def fetched(platform: str) -> bool:
    """True when assets/adb already holds this release for this platform."""
    try:
        with open(os.path.join(OUT, STAMP), encoding="utf-8") as f:
            if f.read().strip() != f"{VERSION} {platform}":
                return False
    except OSError:
        return False
    return all(os.path.isfile(os.path.join(OUT, n)) for n in ARCHIVES[platform][2])


def fetch(platform: str):
    name, sha256, keep = ARCHIVES[platform]
    print(f"Downloading {name}...", flush=True)
    with urllib.request.urlopen(URL + name, timeout=120) as r:
        data = r.read()
    got = hashlib.sha256(data).hexdigest()
    if got != sha256:
        sys.exit(f"{name}: SHA-256 is {got}, expected {sha256}. Not unpacking it.")

    os.makedirs(OUT, exist_ok=True)
    for old in os.listdir(OUT):
        os.remove(os.path.join(OUT, old))
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for member in keep + (NOTICE,):
            target = os.path.join(OUT, member)
            with open(target, "wb") as f:
                f.write(z.read(f"platform-tools/{member}"))
            if platform == "mac" and member == "adb":
                os.chmod(target, 0o755)         # a zip does not carry the executable bit here
    with open(os.path.join(OUT, STAMP), "w", encoding="utf-8") as f:
        f.write(f"{VERSION} {platform}\n")
    print(f"adb {VERSION} for {platform} is in {os.path.relpath(OUT, ROOT)}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--platform", choices=sorted(ARCHIVES),
                        default="mac" if sys.platform == "darwin" else "windows")
    args = parser.parse_args()
    if fetched(args.platform):
        print(f"adb {VERSION} for {args.platform} is already in {os.path.relpath(OUT, ROOT)}")
        return
    fetch(args.platform)


if __name__ == "__main__":
    main()
