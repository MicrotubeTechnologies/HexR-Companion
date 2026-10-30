"""Every glove's own name, from its address.

The reference names are shared with the Android app's GloveNamesTest.kt: every HEXR Companion has
to give a glove the same name, so a change to the recipe or the word lists is a change in both,
and renames every glove in the field. Do not.

Run: python -m pytest tests -q      (or: python tests/test_glovenames.py)
"""

from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hexr.glovenames import ADJECTIVES, ANIMALS, auto_name  # noqa: E402

REFERENCE = {
    "D4:3D:39:A1:B2:C3": ("Fiery Panther 3", "火焰黑豹3号"),
    "D4:3D:39:D4:E5:F6": ("Velvet Finch 5", "丝绒雀鸟5号"),
    "00:00:00:00:00:00": ("Swift Finch 1", "飞速雀鸟1号"),
    "FF:FF:FF:FF:FF:FF": ("Swift Squirrel 2", "飞速松鼠2号"),
    "C8:F0:9E:12:34:56": ("Zesty Kiwi 2", "热情几维鸟2号"),
}


def test_names_match_the_reference_every_companion_uses():
    for address, (english, chinese) in REFERENCE.items():
        assert auto_name(address) == english, address
        assert auto_name(address, chinese=True) == chinese, address


def test_the_way_an_address_is_written_does_not_change_the_name():
    assert auto_name("d4:3d:39:a1:b2:c3") == auto_name("D43D39A1B2C3") == "Fiery Panther 3"
    assert auto_name("D4-3D-39-A1-B2-C3") == "Fiery Panther 3"


def test_the_words_are_all_different():
    for words in (ADJECTIVES, ANIMALS):
        assert len({e for e, _z in words}) == len({z for _e, z in words}) == 64


def test_a_room_of_gloves_rarely_shares_a_name():
    rng = random.Random(7)
    clashes = 0
    for _ in range(2000):
        room = {":".join(f"{rng.randrange(256):02X}" for _ in range(6)) for _ in range(10)}
        names = [auto_name(a) for a in room]
        clashes += len(names) != len(set(names))
    # Ten gloves among 40960 names: about one room in a thousand has two alike.
    assert clashes < 10, clashes


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
    print("\nAll glove name tests passed" if not failures else f"\n{failures} failed")
    sys.exit(1 if failures else 0)
