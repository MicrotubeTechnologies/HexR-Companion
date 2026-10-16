"""The little the app keeps between runs: headset names and the language.

Each is a JSON file in the app's own folder (%APPDATA%\\HEXR Companion on Windows). The app was
called HEXR Window Tester before 0.4.0, so a file not found under the new name is read from the
old folder, and written back under the new one: nothing set before the rename is lost.
"""

from __future__ import annotations

import json
import os
import sys

FOLDER = "HEXR Companion"
OLD_FOLDER = "HEXR Window Tester"


def _base() -> str:
    if sys.platform == "win32":
        return os.environ.get("APPDATA") or os.path.expanduser("~")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support")
    return os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")


def path(name: str) -> str:
    return os.path.join(_base(), FOLDER, name)


def load(name: str) -> dict:
    for folder in (FOLDER, OLD_FOLDER):
        try:
            with open(os.path.join(_base(), folder, name), encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except OSError:
            continue
        except ValueError:
            return {}
    return {}


def save(name: str, data: dict):
    target = path(name)
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        tmp = target + ".new"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, target)
    except OSError:
        pass  # a setting that does not stick is not worth an error dialog
