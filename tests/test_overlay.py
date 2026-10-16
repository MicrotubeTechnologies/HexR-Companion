"""The gloves beside the headset view: what they show when (hexr/haptics.py), where the view and
its gloves go (hexr/viewer.py), drawing a glove (hexr/overlay.py), recording the view and what the
gloves did (hexr/recorder.py) and exporting the two as one video (hexr/exporter.py).

Run: python -m pytest tests -q      (or: python tests/test_overlay.py)
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hexr import haptics as HP  # noqa: E402
from hexr.remote import GloveState, HapticChannel, HapticsUpdate, Status, StreamState  # noqa: E402
from hexr import viewer as V  # noqa: E402

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from hexr.overlay import GloveOverlay, OverlayLook  # noqa: E402

T0 = 5_000.0          # seconds on the headset's clock
US = 1_000_000


def update(hand, t, *channels):
    return HapticsUpdate(hand, int(t * US), list(channels))


def status(clock_s=0.0, haptics=True, kpa=None):
    gloves = {h: GloveState(h, "connected", pressure_kpa=(kpa or [0] * 6) + [45])
              for h in ("left", "right")}
    return Status("q", "Quest", "", "quest", "", "", "", False, 80, 0, "", [], gloves,
                  StreamState(), [], True, True, False, False, 1, haptics=haptics,
                  clock_us=int(clock_s * US))


# -- the timeline ----------------------------------------------------------------------

def test_a_press_fills_holds_and_empties_like_air():
    tl = HP.HapticsTimeline()
    tl.on_haptics(update("right", T0, HapticChannel(1, "pressure", 0.8)))
    tl.on_haptics(update("right", T0 + 1, HapticChannel(1, "off")))
    level = lambda t: tl.state("right", int(t * US), 0).levels[1]  # noqa: E731
    assert level(T0 - 0.1) == 0
    assert 0.3 < level(T0 + 0.05) < 0.8             # filling
    assert level(T0 + 0.5) == pytest.approx(0.8, abs=0.01)   # held
    assert 0 < level(T0 + 1.2) < 0.4                 # emptying
    assert level(T0 + 3) == 0
    words = [tl.state("right", int(t * US), 0).word for t in (T0 + 0.1, T0 + 0.6, T0 + 1.3)]
    assert words == [0, 1, 2]                        # PRESS. HOLD. RELEASE.


def test_a_tap_shows_briefly_and_a_vibration_says_its_frequency():
    tl = HP.HapticsTimeline()
    tl.on_haptics(update("left", T0, HapticChannel(5, "vibration", 0.6, 12.0, tap=True)))
    st = tl.state("left", int((T0 + 0.05) * US), 0)
    assert st.levels[5] > 0 and st.vibrating[5] == 12.0
    assert (st.words, st.word) == (1, 2)             # CLICK.
    assert tl.state("left", int((T0 + 2) * US), 0).levels[5] == 0
    tl.on_haptics(update("left", T0 + 5, HapticChannel(2, "vibration", 0.6, 2.0)))
    st = tl.state("left", int((T0 + 5.5) * US), 0)
    assert (st.words, st.word, st.hz) == (1, 0, 2.0)  # PULSE.
    assert tl.hands_used() == ["left"]


def test_frames_use_their_presentation_time_when_it_is_the_headsets_clock():
    tl = HP.HapticsTimeline()
    tl.on_status(status(clock_s=T0), arrived=100.0)          # headset is T0 when we are 100
    assert tl.frame_time(int((T0 + 1) * US), arrived=101.2) == pytest.approx(T0 + 1)
    # A capture stamped on some other clock: placed by when it arrived, less the video's lag.
    assert tl.frame_time(int(3.0 * US), arrived=101.2) == pytest.approx(T0 + 1.2 - HP.VIDEO_LAG_S)
    tl.reset_clock()
    assert tl.offset() is None


def test_an_older_headset_falls_back_to_measured_pressure():
    tl = HP.HapticsTimeline()
    tl.on_status(status(haptics=False, kpa=[0] * 6), arrived=10.0)
    tl.on_status(status(haptics=False, kpa=[0, 45, 0, 0, 0, 0]), arrived=10.2)
    tl.on_status(status(haptics=False, kpa=[0, 45, 0, 0, 0, 0]), arrived=10.4)
    assert not tl.exact
    st = tl.state("right", 0, arrived=10.4 + HP.VIDEO_LAG_S)
    assert st.levels[1] == pytest.approx(1.0) and st.levels[0] == 0
    assert tl.hands_used() == ["left", "right"]


def test_the_log_covers_what_overlaps_the_recording():
    tl = HP.HapticsTimeline()
    tl.on_haptics(update("right", T0, HapticChannel(0, "pressure", 1.0)))
    tl.on_haptics(update("right", T0 + 2, HapticChannel(0, "off")))
    tl.on_haptics(update("right", T0 + 9, HapticChannel(3, "pressure", 1.0)))
    found = tl.segments_between(T0 + 1, T0 + 5)
    assert [(h, f) for h, f, _s in found] == [("right", 0)]


# -- where things go -------------------------------------------------------------------------

def test_each_shape_is_youtubes_and_fits_where_it_is_put():
    assert V.frame_size(None, V.LANDSCAPE) == (1920, 1080)
    assert V.frame_size(None, V.PORTRAIT) == (1080, 1920)
    assert V.frame_size((1000, 400), V.LANDSCAPE) == (710, 400)        # height-bound, even
    assert V.frame_size((300, 2000), V.PORTRAIT) == (300, 532)
    assert V.frame_size((900, 500), V.VIEW) == (500, 500)
    assert V.frame_size(None, V.VIEW, 16 / 9) == (1920, 1080)
    assert V.frame_size(None, V.VIEW) == (1080, 1080)


@pytest.mark.parametrize("layout", [V.LANDSCAPE, V.PORTRAIT])
def test_the_view_comes_first_and_the_gloves_sit_beside_it_left_first(layout):
    w, h = V.SIZE[layout]
    b = V.boxes((w, h), layout)
    if layout == V.LANDSCAPE:          # wide and full height; the gloves a quarter
        assert b.view[:2] == (0, 0) and b.view[3] == h
        assert w - b.view[2] == pytest.approx(w * V.GLOVES_SHARE, abs=20)   # and a gap
    else:                              # a square view across the top, whole
        assert b.view == (0, 0, w, w)
    for cell in (b.left, b.right):
        assert 0 <= cell[0] < cell[2] <= w and 0 <= cell[1] < cell[3] <= h
    if layout == V.LANDSCAPE:
        assert b.left[0] >= b.view[2] and b.left[3] <= b.right[1]        # right of it, above
    else:
        assert b.left[1] >= b.view[3] and b.left[2] <= b.right[0]        # under it, beside
    assert V.hit((w, h), layout, 10, 10) == "view"
    assert V.hit((w, h), layout, (b.right[0] + b.right[2]) / 2, (b.right[1] + b.right[3]) / 2) \
        == "right"
    assert V.boxes((1080, 1080), V.VIEW).left is None


def test_a_square_view_is_cut_wide_keeping_its_lower_part():
    av = pytest.importorskip("av")
    tall = Image.new("RGB", (512, 512), (200, 0, 0))
    tall.paste((0, 0, 200), (0, 0, 512, 64))            # its top eighth, blue
    tall.paste((0, 200, 0), (0, 420, 512, 460))         # low in it, where hands are: green
    img = V.Compositor().draw(av.VideoFrame.from_image(tall), {}, (), V.LANDSCAPE)
    b = V.boxes(img.size, V.LANDSCAPE)
    top = img.getpixel((100, 2))
    assert top[0] > 150 and top[2] < 60                  # the blue top is cut away
    column = [img.getpixel((100, y)) for y in range(b.view[1], b.view[3], 4)]
    assert any(g > 150 and r < 60 for r, g, _b in column)   # the low part is kept
    # More is cut from the top than the bottom: the green sits in the view's lower fifth.
    first = next(i for i, (r, g, _b) in enumerate(column) if g > 150 and r < 60)
    assert first * 4 > (b.view[3] - b.view[1]) * .7


def test_a_landscape_view_still_makes_youtubes_shapes():
    wide = 16 / 9
    p = V.boxes((1080, 1920), V.PORTRAIT, wide)
    assert p.view[:3] == (0, 0, 1080) and p.view[3] == pytest.approx(608, abs=1)  # across the top
    assert p.left[1] >= p.view[3] and p.right[1] >= p.view[3]           # both under it
    assert V.glove_height(p.left) >= V.glove_height(V.boxes((1080, 1920), V.PORTRAIT).left)


def test_the_panels_light_the_finger_that_is_firing_and_dim_a_glove_not_connected():
    av = pytest.importorskip("av")
    frame = av.VideoFrame.from_image(Image.new("RGB", (512, 512), (30, 60, 90)))
    lit = HP.HandState(levels=[0, 1.0, 0, 0, 0, 0])
    badges = (("left", V.GloveBadge("disconnected")), ("right", V.GloveBadge("connected", 85)))
    img = V.Compositor().draw(frame, {"right": lit}, badges, V.LANDSCAPE)
    b = V.boxes(img.size, V.LANDSCAPE)
    assert img.getpixel((200, 200)) == pytest.approx((30, 60, 90), abs=3)   # the view, untouched

    def orange(box):      # glowing: white-hot on the orange glove
        raw = img.crop(box).convert("RGB").tobytes()
        return _white_hot(zip(raw[0::3], raw[1::3], raw[2::3]))

    def brightness(box):
        crop = img.crop(box).convert("L")
        return sum(crop.tobytes()) / (crop.width * crop.height)

    assert orange(b.right) > 50 and orange(b.left) == 0
    assert brightness(b.right) > brightness(b.left)        # the left glove shows faintly


# -- drawing ---------------------------------------------------------------------------------

def _white_hot(pixels) -> int:
    """How many pixels glow as a firing touch point does on the orange glove."""
    return sum(1 for r, g, b in pixels if r > 235 and g > 215 and b > 170)


def test_the_glove_lights_the_finger_that_is_firing():
    from hexr.overlay import touch_points
    look = OverlayLook()
    gh = 300
    lit = HP.HandState(levels=[0, 1.0, 0, 0, 0, 0])
    lit.words, lit.word = 0, 1
    panel = GloveOverlay().panel("right", gh, look, lit).convert("RGB")
    dark = GloveOverlay().panel("right", gh, look, HP.HandState()).convert("RGB")

    def near(img, ch):
        x, y = touch_points("right", gh, look)[ch]
        return [img.getpixel((int(x) + dx, int(y) + dy))
                for dx in range(-16, 17, 2) for dy in range(-16, 17, 2)]
    assert _white_hot(near(panel, 1)) > _white_hot(near(dark, 1)) + 10      # the index glows
    assert _white_hot(near(panel, 4)) == _white_hot(near(dark, 4))         # the pinky does not


@pytest.mark.parametrize("corner", ["tl", "tr", "bl", "br"])
@pytest.mark.parametrize("labels", ["active", "always", "off"])
def test_every_corner_and_label_mode_draws(corner, labels):
    img = Image.new("RGB", (640, 640))
    st = HP.HandState(levels=[.5] * 6, vibrating=[6] * 6, since=[.2] * 6)
    GloveOverlay().draw(img, ["left", "right"], {"left": st, "right": st},
                        OverlayLook(corner=corner, labels=labels, size=.26, backdrop=False))
    assert img.getbbox() is not None


# -- recording -------------------------------------------------------------------------------

def _record(folder: str):
    """1.5 s of a pretend view, the right index pressed from 0.2 s; returns the recorder."""
    av = pytest.importorskip("av")
    from hexr.recorder import Recorder
    tl = HP.HapticsTimeline()
    tl.on_haptics(update("right", T0 + 0.2, HapticChannel(1, "pressure", 0.8)))
    done = []
    badges = (("right", V.GloveBadge("connected", 85)),)
    rec = Recorder(os.path.join(folder, "clip.mp4"), tl, lambda: badges, done.append, "Quest 3")
    rec.start()
    for i in range(45):                 # 1.5 s at 30 fps
        frame = av.VideoFrame.from_image(Image.new("RGB", (512, 512), (i * 5, 40, 90)))
        rec.tap(frame, int((T0 + i / 30) * US), 0.0)
    rec.stop()
    for _ in range(200):
        if done:
            break
        time.sleep(0.05)
    return rec


def test_a_recording_is_the_view_as_it_came_with_what_the_gloves_did():
    av = pytest.importorskip("av")
    from hexr.exporter import GloveTrack
    from hexr.recorder import gloves_path
    with tempfile.TemporaryDirectory() as folder:
        rec = _record(folder)
        assert rec.error == "" and rec.frames == 45
        with av.open(rec.path) as clip:
            stream = clip.streams.video[0]
            assert (stream.width, stream.height) == (512, 512)         # nothing drawn on it
            assert float(clip.duration / 1e6) == pytest.approx(1.5, abs=0.1)
        track = GloveTrack(gloves_path(rec.path))
        states, badges = track.at(0.1)
        assert states["right"].levels[1] == 0 and dict(badges)["right"].battery == 85
        assert track.at(1.0)[0]["right"].levels[1] > 0.5
        assert track.liveliest() > 0.2
        log = json.load(open(rec.log_path, encoding="utf-8"))
        assert log["app"] == "hexr-overlay-studio"
        assert log["events"][0]["finger"] == "index" and log["events"][0]["start"] == 0.2


@pytest.mark.parametrize("layout", [V.LANDSCAPE, V.PORTRAIT, V.VIEW])
def test_a_recording_exports_in_each_shape(layout, monkeypatch):
    av = pytest.importorskip("av")
    from hexr import exporter as X
    with tempfile.TemporaryDirectory() as folder:
        monkeypatch.setenv("HEXR_VIDEOS", folder)
        rec = _record(folder)
        found = X.find_recordings(folder)
        assert [r.title for r in found] == ["Quest 3"]
        job = X.Export(found[0], layout)
        job.start()
        job._thread.join(60)
        assert job.done and job.error == "" and job.progress == 1.0
        assert job.path == os.path.join(folder, "Exports", f"clip ({X.FILE_LABEL[layout]}).mp4")
        with av.open(job.path) as clip:
            stream = clip.streams.video[0]
            assert (stream.width, stream.height) == V.frame_size(None, layout)
            assert float(clip.duration / 1e6) == pytest.approx(1.5, abs=0.1)
        assert rec.frames == 45


def _wait(condition, seconds=5.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.02)
    return False


def test_a_recording_plays_at_its_own_speed_in_the_shape_picked():
    pytest.importorskip("av")
    from hexr import exporter as X
    from hexr.player import Player
    with tempfile.TemporaryDirectory() as folder:
        _record(folder)
        rec = X.find_recordings(folder)[0]
        seconds, thumb = X.probe(rec, 64)
        assert seconds == pytest.approx(1.5, abs=0.1) and max(thumb.size) == 64

        player = Player(rec, V.PORTRAIT, (300, 600))
        try:
            shown = []
            assert _wait(lambda: shown.append(player.latest()) or shown[-1] is not None)
            assert shown[-1].size == V.frame_size((300, 600), V.PORTRAIT)
            assert not player.playing and player.position > 0.2     # opens where it is busy
            player.set_shape(V.LANDSCAPE, (600, 400))
            assert _wait(lambda: shown.append(player.latest()) or shown[-1] is not None)
            assert shown[-1].size == V.frame_size((600, 400), V.LANDSCAPE)

            player.seek(0.0)
            player.play()
            time.sleep(0.6)
            assert 0.3 < player.position < 1.0                       # the clock's pace
            assert _wait(lambda: player.ended, 3.0) and not player.playing
            player.play()                                            # again, from the top
            assert _wait(lambda: player.playing and player.position < 0.5, 2.0)
        finally:
            player.close()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
