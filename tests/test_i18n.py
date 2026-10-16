"""The language switch: every English string the app shows has its Chinese.

The keys are read out of the code itself (each tr("...") and N_("...") written with a literal),
plus the few the code shows from a table it does not own: the glove's channel names, the hands,
the quick test's verdicts and the glove's connection words.

Run: python -m pytest tests -q      (or: python tests/test_i18n.py)
"""

from __future__ import annotations

import ast
import os
import string
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hexr import i18n  # noqa: E402
from hexr import protocol as P  # noqa: E402
from hexr.state import HANDS  # noqa: E402

# Shown through tr(variable): their English comes from elsewhere.
DYNAMIC = (set(P.FINGER_LABELS.values()) | set(HANDS) |
           {"Good", "Poor", "Fail"} |                          # quick test verdicts
           {"Connecting…", "Connected", "Not connected"})      # what the engine sets


def _sources():
    yield os.path.join(ROOT, "hexr_tester.py")
    for folder, _dirs, files in os.walk(os.path.join(ROOT, "hexr")):
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(folder, name)


def _keys_in_code() -> dict[str, str]:
    """Every literal passed to tr() or N_() in the app, and where it is."""
    found = {}
    for path in _sources():
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), path)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ("tr", "N_") and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                found[node.args[0].value] = f"{os.path.relpath(path, ROOT)}:{node.lineno}"
    return found


def _fields(text: str) -> set[str]:
    return {f for _lit, f, _spec, _conv in string.Formatter().parse(text) if f}


def test_every_string_has_its_chinese():
    keys = _keys_in_code()
    missing = sorted(f"{where}  {k!r}" for k, where in keys.items() if k not in i18n.ZH)
    missing += sorted(repr(k) for k in DYNAMIC if k not in i18n.ZH)
    assert not missing, "no Chinese for:\n  " + "\n  ".join(missing)


def test_the_chinese_fills_in_the_same_values():
    wrong = [k for k, v in i18n.ZH.items() if _fields(k) != _fields(v)]
    assert not wrong, f"placeholders differ: {wrong}"


def test_no_translation_is_left_over():
    used = set(_keys_in_code()) | DYNAMIC
    stale = sorted(k for k in i18n.ZH if k not in used)
    assert not stale, f"translated but no longer shown: {stale}"


def test_tr_switches_and_fills_in():
    was = i18n._lang
    try:
        i18n._lang = "en"
        assert i18n.tr("{n} poor", n=2) == "2 poor"
        assert i18n.tr("Not in the table") == "Not in the table"
        i18n._lang = "zh"
        # Chinese wraps between characters, so its spaces do not break; English stays as it is.
        assert i18n.tr("{n} poor", n=2) == "2 个偏弱"
        assert i18n.tr("Bluetooth unavailable — {error}", error="no adapter") == \
            "蓝牙不可用——no adapter"
        assert i18n.tr("Not in the table") == "Not in the table"
    finally:
        i18n._lang = was


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except AssertionError as e:
                failures += 1
                print(f"  FAIL  {name}: {e}")
    print(f"\n{'FAILED' if failures else 'All language tests passed'}"
          f"{f' ({failures} failing)' if failures else ''}")
    sys.exit(1 if failures else 0)
