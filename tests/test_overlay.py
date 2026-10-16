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
    assert V.frame_size((900, 500), V.SQUARE) == (500, 500)


@pytest.mark.parametrize("layout", [V.LANDSCAPE, V.PORTRAIT])
def test_the_view_is_square_and_the_gloves_sit_beside_it_left_first(layout):
    w, h = V.SIZE[layout]
    b = V.boxes((w, h), layout)
    assert b.view == (0, 0, min(w, h), min(w, h))
    for cell in (b.left, b.right):
        assert 0 <= cell[0] < cell[2] <= w and 0 <= cell[1] < cell[3] <= h
    if layout == V.LANDSCAPE:
        assert b.left[0] >= b.view[2] and b.left[3] <= b.right[1]        # right of it, above
    else:
        assert b.left[1] >= b.view[3] and b.left[2] <= b.right[0]        # under it, beside
    assert V.hit((w, h), layout, 10, 10) == "view"
    assert V.hit((w, h), layout, (b.right[0] + b.right[2]) / 2, (b.right[1] + b.right[3]) / 2) \
        == "right"
    assert V.boxes((1080, 1080), V.SQUARE).left is None


def test_the_panels_light_the_finger_that_is_firing_and_dim_a_glove_not_connected():
    av = pytest.importorskip("av")
    frame = av.VideoFrame.from_image(Image.new("RGB", (512, 512), (30, 60, 90)))
    lit = HP.HandState(levels=[0, 1.0, 0, 0, 0, 0])
    badges = (("left", V.GloveBadge("disconnected")), ("right", V.GloveBadge("connected", 85)))
    img = V.Compositor().draw(frame, {"right": lit}, badges, V.LANDSCAPE)
    b = V.boxes(img.size, V.LANDSCAPE)
    assert img.getpixel((200, 200)) == pytest.approx((30, 60, 90), abs=3)   # the view, untouched

    def orange(box):
        raw = img.crop(box).convert("RGB").tobytes()
        return sum(1 for i in range(0, len(raw), 3)
                   if raw[i] > 200 and 60 < raw[i + 1] < 160 and raw[i + 2] < 90)

    def brightness(box):
        crop = img.crop(box).convert("L")
        return sum(crop.tobytes()) / (crop.width * crop.height)

    assert orange(b.right) > 50 and orange(b.left) == 0
    assert brightness(b.right) > brightness(b.left)        # the left glove shows faintly


# -- drawing ---------------------------------------------------------------------------------

def test_the_glove_lights_the_finger_that_is_firing():
    img = Image.new("RGB", (1024, 576), (20, 20, 20))
    lit = HP.HandState(levels=[0, 1.0, 0, 0, 0, 0])
    lit.words, lit.word = 0, 1
    GloveOverlay().draw(img, ["right"], {"right": lit}, OverlayLook())
    # The index fingertip is the glove's highest touch point, so the brightest orange there.
    gh = round(0.32 * 576)
    w = int(gh * 520 / 885)
    px = img.width - int(min(img.size) * .03) - int(w + w * .46 * 2) + int(w * .46 + .5 * w)
    py = img.height - int(min(img.size) * .03) - int(gh * .12 + gh + gh * .24) + int(gh * .1 + .0758 * gh)
    near = [img.getpixel((px + dx, py + dy)) for dx in range(-14, 15, 2) for dy in range(-14, 15, 2)]
    assert any(r > 200 and 60 < g < 160 and b < 90 for r, g, b in near)


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


@pytest.mark.parametrize("layout", [V.LANDSCAPE, V.PORTRAIT, V.SQUARE])
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
            assert (stream.width, stream.height) == V.SIZE[layout]
            assert float(clip.duration / 1e6) == pytest.approx(1.5, abs=0.1)
        assert rec.frames == 45


def test_a_preview_is_the_export_at_its_busiest_moment():
    pytest.importorskip("av")
    from hexr import exporter as X
    with tempfile.TemporaryDirectory() as folder:
        _record(folder)
        rec = X.find_recordings(folder)[0]
        img = X.still(rec, V.PORTRAIT, (300, 600))
        assert img.size == V.frame_size((300, 600), V.PORTRAIT)
        seconds, thumb = X.probe(rec, 64)
        assert seconds == pytest.approx(1.5, abs=0.1) and max(thumb.size) == 64


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
