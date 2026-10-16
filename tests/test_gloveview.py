"""The glove in the app's own screens: where its touch points are, what a click hits, how a
verdict colours it, how the Test pad lights it, the Quick test's answer, and Details being
remembered. No Tk window needed.

Run: python -m pytest tests -q
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytest.importorskip("PIL")

from hexr import gloveview as GV  # noqa: E402
from hexr import settings  # noqa: E402
from hexr import theme as T  # noqa: E402
from hexr.haptics import PRESS_S, HandState  # noqa: E402
from hexr.overlay import (GLOVE_ASPECT, GloveOverlay, OverlayLook, nearest_point,  # noqa: E402
                          panel_size, touch_points)
from hexr.screens import base  # noqa: E402
from hexr.screens.quicktest import judge  # noqa: E402

LOOK = OverlayLook(labels="off", backdrop=False, title=False, margin=.12, caption=False)


# -- where the touch points are ------------------------------------------------------------------

def test_the_left_hand_is_the_right_hand_mirrored():
    w, _h = panel_size(300, LOOK)
    right, left = touch_points("right", 300, LOOK), touch_points("left", 300, LOOK)
    for (rx, ry), (lx, ly) in zip(right, left):
        assert ly == pytest.approx(ry)
        assert lx + rx == pytest.approx(2 * 300 * GLOVE_ASPECT * LOOK.margin + 300 * GLOVE_ASPECT)
        assert 0 < rx < w


def test_the_headset_overlay_keeps_its_old_margin():
    gw = 300 * GLOVE_ASPECT
    index = touch_points("right", 300, OverlayLook())[1]
    assert index == pytest.approx((gw * .46 + .5 * gw, 300 * .1 + .0758 * 300))


# -- what a click hits ------------------------------------------------------------------------------

def test_every_point_hits_itself_and_the_nearer_one_wins():
    pts = touch_points("right", 300, LOOK)
    for i, (x, y) in enumerate(pts):
        assert nearest_point(pts, x + 2, y - 2, 27) == i
    ring, pinky = pts[3], pts[4]
    near_ring = (ring[0] * .7 + pinky[0] * .3, ring[1] * .7 + pinky[1] * .3)
    assert nearest_point(pts, *near_ring, 27) == 3
    assert nearest_point(pts, 0, 0, 27) is None


# -- verdicts colour the glove ---------------------------------------------------------------------

def test_a_tint_paints_a_touch_point_green():
    green = (62, 207, 142)
    st = HandState(levels=[1.0] * 6, tints=[green] * 6)
    img = GloveOverlay().panel("right", 300, LOOK, st)
    x, y = touch_points("right", 300, LOOK)[5]            # the palm
    near = [img.getpixel((int(x) + dx, int(y) + dy)) for dx in range(-12, 13, 3)
            for dy in range(-12, 13, 3)]
    assert any(g > 150 and r < 150 and a > 100 for r, g, _b, a in near)


# -- the Test pad -----------------------------------------------------------------------------------

def test_the_pad_lights_what_it_drives_when_the_glove_does_not_stream():
    st = GV.pad_state(None, True, 0.1, None, "pressure", 0.6, 10.0, {1, 2})
    assert st.levels == [0, .6, .6, 0, 0, 0]
    assert st.word == 0                                   # PRESS.
    assert GV.pad_state(None, True, PRESS_S + .1, None, "pressure", .6, 10, {1}).word == 1
    assert GV.pad_state(None, False, 2.0, 0.2, "pressure", .6, 10, {1}).word == 2


def test_a_streaming_glove_shows_what_it_measures_and_a_vibration_buzzes():
    st = GV.pad_state([0, 45, 0, 0, 0, 0], False, 0, None, "pressure", .6, 10, {1})
    assert st.levels[1] == pytest.approx(1.0) and st.levels[0] == 0
    buzz = GV.pad_state(None, True, 0.5, None, "vibration", .6, 12.0, {0})
    assert buzz.vibrating[0] == 12.0 and (buzz.words, buzz.word) == (1, 1)
    assert GV.pad_state(None, True, 0.5, None, "vibration", .6, 2.0, {0}).word == 0


# -- the Quick test's answer ----------------------------------------------------------------------

def test_the_answer_comes_first():
    good = {ch: 45.0 for ch in range(6)}
    assert judge(good, 50).colour == T.SUCCESS and judge(good, 50).weak == []
    poor = {**good, 3: 20.0, 4: 30.0}
    r = judge(poor, 50)
    assert (r.colour, r.weak) == (T.WARN, [3, 4]) and "2" in r.headline
    failed = {**poor, 5: 0.5}
    r = judge(failed, 50)
    assert r.colour == T.DANGER and r.weak == [3, 4, 5] and "1" in r.headline
    pump = judge({ch: 0.0 for ch in range(6)}, 3)
    assert pump.colour == T.DANGER and pump.weak == []


# -- Details is remembered ----------------------------------------------------------------------

def test_details_is_remembered_per_screen(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_base", lambda: str(tmp_path))
    assert base.details_saved("test") is False
    base.save_details("test", True)
    assert base.details_saved("test") is True
    assert base.details_saved("headsets") is False
    settings.save(base.SETTINGS_FILE, {**settings.load(base.SETTINGS_FILE), "language": "zh"})
    base.save_details("headsets", True)
    assert settings.load(base.SETTINGS_FILE)["language"] == "zh"   # nothing else lost
