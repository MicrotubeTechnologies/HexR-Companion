"""Generate the Google Play store graphics for the Android app.

    python tools/make_play_assets.py            # writes the shipping assets
    python tools/make_play_assets.py --preview  # writes a contact sheet to eyeball

Two files come out, both under android/play/:

    icon-512.png                  512x512, 32-bit PNG, Play's hi-res icon
    feature-graphic-1024x500.png  1024x500, 24-bit PNG, no alpha

This is the Android sibling of make_icon.py, and the two are deliberately not
shared. The desktop mark is a *flat-topped* white hexagon with a round contact
point on an orange tile; the Android mark is a *pointy-topped* orange hexagon
with a hexagonal contact point on the app's own near-black ground. They are
different drawings in different palettes, and the one place this repository has
to get that right is here, where the wrong one would go on the store page.

The geometry below is lifted verbatim from

    android/app/src/main/res/drawable/ic_launcher_foreground.xml

so the store icon and the launcher icon are the same shape rather than two
drawings that drift. The palette comes from ui/Theme.kt. If either changes,
change it here too - nothing checks.
"""

import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "android", "play")

# ui/Theme.kt. Note ACCENT is #F4762A, not the desktop's #F26B21.
ACCENT = (244, 118, 42, 255)      # T.ACCENT
SCREEN = (12, 12, 14, 255)        # T.SCREEN
CARD = (27, 27, 31, 255)          # T.CARD
TEXT = (236, 236, 236, 255)       # T.TEXT
TEXT_2 = (154, 154, 160, 255)     # T.TEXT_2
TEXT_3 = (124, 124, 132, 255)     # T.TEXT_3
LIFT = (23, 23, 27, 255)          # a touch above SCREEN, for the vignette

# ic_launcher_foreground.xml, in its own 108-unit viewport. Both hexagons are
# pointy-topped and share the centre (54, 54).
UNITS = 108.0
OUTER = [(54, 24.3), (81.5, 39.15), (81.5, 68.85),
         (54, 83.7), (26.5, 68.85), (26.5, 39.15)]
INNER = [(54, 43), (66.1, 50.15), (66.1, 57.85),
         (54, 65), (41.9, 57.85), (41.9, 50.15)]
STROKE = 5.0
# Outer hexagon plus half a stroke either side: 60 wide by 64.4 tall.
MARK_H = (83.7 - 24.3) + STROKE

# Everything is drawn at 4x and downsampled. Pillow does not antialias polygons
# or lines, so this is the only thing keeping the hexagon's diagonals from
# looking like a staircase.
SS = 4

# The launcher icon is cropped to the middle 72 of its 108 units, so the mark
# fills 89% of what you actually see. Play's tile is a rounded square with no
# crop, and matching that number literally would look overblown - but scaling
# the 108-unit artwork straight onto 512 px (which would be 60%) reads visibly
# lighter than the launcher next to it. 68% is where the two look like the same
# icon. Checked with --preview, which renders them side by side at four sizes.
ICON_MARK_FRACTION = 0.68

FONT_CANDIDATES = {
    # The app draws HEXR at FontWeight.ExtraBold. Segoe UI Black is the closest
    # thing Windows ships; Arial Bold is the fallback that exists everywhere.
    "black": ("seguibl.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"),
    "semibold": ("seguisb.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"),
    "bold": ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"),
    "regular": ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"),
}
FONT_DIRS = ("C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu",
             "/Library/Fonts", "/System/Library/Fonts")


def font(weight, size):
    """Find a real TTF, or say so. Falling back to Pillow's bitmap default
    would silently produce a store graphic with the wrong typeface in it."""
    for name in FONT_CANDIDATES[weight]:
        for directory in FONT_DIRS:
            path = os.path.join(directory, name)
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
    sys.exit("No " + weight + " font found. Tried "
             + str(FONT_CANDIDATES[weight]) + " in " + str(FONT_DIRS) + ".")


# -- the mark ----------------------------------------------------------------

def _points(pts, cx, cy, scale):
    """Map the 108-unit artwork onto a canvas, centred on (cx, cy)."""
    return [(cx + (x - 54) * scale, cy + (y - 54) * scale) for x, y in pts]


def draw_mark(draw, cx, cy, scale):
    """The HEXR mark: a stroked hexagon with a smaller filled one inside it."""
    outer = _points(OUTER, cx, cy, scale)
    width = max(1, round(STROKE * scale))
    draw.line(outer + [outer[0]], fill=ACCENT, width=width, joint="curve")
    # joint="curve" notches the vertices; the drawable uses round joins, and a
    # disc at each corner is what that looks like.
    cap = width / 2
    for x, y in outer:
        draw.ellipse((x - cap, y - cap, x + cap, y + cap), fill=ACCENT)
    draw.polygon(_points(INNER, cx, cy, scale), fill=ACCENT)


# -- text --------------------------------------------------------------------

def tracked_width(text, fnt, tracking):
    if not text:
        return 0
    return sum(fnt.getlength(c) for c in text) + tracking * (len(text) - 1)


def draw_tracked(draw, x, y, text, fnt, fill, tracking):
    """Pillow has no letter-spacing, and the lockup is nothing without it."""
    for char in text:
        draw.text((x, y), char, font=fnt, fill=fill)
        x += fnt.getlength(char) + tracking


# -- the hi-res icon ---------------------------------------------------------

def render_icon(size=512):
    canvas = size * SS
    img = Image.new("RGBA", (canvas, canvas), SCREEN)
    scale = ICON_MARK_FRACTION * canvas / MARK_H
    draw_mark(ImageDraw.Draw(img), canvas / 2, canvas / 2, scale)
    # Play masks the corners itself, so this ships as a plain square: no
    # rounding, no shadow, no padding of its own.
    return img.resize((size, size), Image.LANCZOS)


def render_launcher(size=512):
    """What the same mark looks like on a phone, for comparison only. The
    adaptive icon shows the middle 72 of 108 units behind a circular mask."""
    canvas = size * SS
    img = Image.new("RGBA", (canvas, canvas), SCREEN)
    draw_mark(ImageDraw.Draw(img), canvas / 2, canvas / 2, canvas / 72.0)
    mask = Image.new("L", (canvas, canvas), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, canvas - 1, canvas - 1), fill=255)
    img.putalpha(mask)
    return img.resize((size, size), Image.LANCZOS)


# -- the feature graphic -----------------------------------------------------

FEATURE_W, FEATURE_H = 1024, 500
TAGLINE = "Test HEXR haptic gloves, and watch HEXR headsets live"


def _vignette(size):
    """A barely-there radial lift behind the mark, so 1024x500 of flat #0C0C0E
    does not read as a rendering failure. Drawn small and scaled up, which is
    the cheapest way to get a smooth gradient out of Pillow."""
    w, h = 64, 32
    ramp = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(ramp)
    for i in range(24, 0, -1):
        r = i / 24
        d.ellipse((w / 2 - 30 * r, h / 2 - 22 * r,
                   w / 2 + 30 * r, h / 2 + 22 * r),
                  fill=int(255 * (1 - r) ** 1.5))
    return ramp.resize(size, Image.LANCZOS)


def render_feature():
    w, h = FEATURE_W * SS, FEATURE_H * SS
    img = Image.new("RGBA", (w, h), SCREEN)
    img = Image.composite(Image.new("RGBA", (w, h), LIFT), img, _vignette((w, h)))

    # The lockup is drawn on its own layer and then centred by its ink, not by
    # its font metrics. Ascent and descent are generous on a black weight, and
    # centring on the line box leaves the whole thing sitting visibly low.
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    mark_h = 168 * SS
    wordmark = font("black", 84 * SS)
    name_font = font("regular", 84 * SS)
    tag_font = font("semibold", 27 * SS)
    word_track, name_track, tag_track = 6 * SS, 1 * SS, 1.2 * SS

    # Measure the lockup row before placing it: HEXR in orange, Companion in
    # white, as the app's header and splash set them.
    word_w = tracked_width("HEXR", wordmark, word_track)
    name_w = tracked_width("Companion", name_font, name_track)
    gap = 22 * SS
    row_w = word_w + gap + name_w
    row_h = wordmark.size

    tag_w = tracked_width(TAGLINE, tag_font, tag_track)

    top = 60 * SS
    draw_mark(d, w / 2, top + mark_h / 2, mark_h / MARK_H)

    row_x = (w - row_w) / 2
    row_y = top + mark_h + 40 * SS
    draw_tracked(d, row_x, row_y, "HEXR", wordmark, ACCENT, word_track)
    # On HEXR's baseline: the two faces have different ascents.
    name_y = row_y + wordmark.getmetrics()[0] - name_font.getmetrics()[0]
    draw_tracked(d, row_x + word_w + gap, name_y, "Companion", name_font, TEXT, name_track)

    # Bigger than the 40 above the wordmark, and it still reads as the smaller
    # of the two gaps: HEXR's line box already ends well below its baseline, so
    # a chunk of this is consumed before any ink appears.
    draw_tracked(d, (w - tag_w) / 2, row_y + row_h + 34 * SS,
                 TAGLINE, tag_font, TEXT_2, tag_track)

    block = layer.crop(layer.getbbox())
    img.alpha_composite(block, ((w - block.width) // 2, (h - block.height) // 2))

    out = img.resize((FEATURE_W, FEATURE_H), Image.LANCZOS)
    # Play rejects an alpha channel here, so flatten rather than just dropping
    # it - a stray transparent pixel would otherwise come out black.
    flat = Image.new("RGB", out.size, SCREEN[:3])
    flat.paste(out, mask=out.split()[3])
    return flat


# -- output ------------------------------------------------------------------

def write_assets():
    os.makedirs(OUT_DIR, exist_ok=True)
    icon = os.path.join(OUT_DIR, "icon-512.png")
    feature = os.path.join(OUT_DIR, "feature-graphic-1024x500.png")
    render_icon().save(icon)
    render_feature().save(feature)
    for path in (icon, feature):
        with Image.open(path) as im:
            print("wrote {}  {}x{} {} {:.0f} KB".format(
                path, im.size[0], im.size[1], im.mode,
                os.path.getsize(path) / 1024))


def write_preview():
    """The store icon beside a launcher render, at the sizes people see them.
    The point is the mark's optical weight: they should look like siblings."""
    pad, gap, cell = 40, 40, 256
    shown = (256, 128, 64, 48)
    rows = (("store icon (Play, square)", render_icon(cell)),
            ("launcher icon (phone, masked)", render_launcher(cell)))
    w = pad * 2 + sum(shown) + gap * (len(shown) - 1)
    h = pad * 2 + len(rows) * (cell + gap + 30) + FEATURE_H // 2 + gap + 30
    sheet = Image.new("RGBA", (w, h), SCREEN)
    d = ImageDraw.Draw(sheet)
    label = font("semibold", 18)
    y = pad + 30
    for name, img in rows:
        d.text((pad, y - 26), name, fill=TEXT, font=label)
        x = pad
        for n in shown:
            sheet.alpha_composite(img.resize((n, n), Image.LANCZOS),
                                  (x, y + cell - n))
            x += n + gap
        y += cell + gap + 30
    d.text((pad, y - 26), "feature graphic (half size)", fill=TEXT, font=label)
    sheet.paste(render_feature().resize((FEATURE_W // 2, FEATURE_H // 2),
                                        Image.LANCZOS), (pad, y))
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "preview.png")
    sheet.save(out)
    print("wrote " + out)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--preview", action="store_true",
                   help="write android/play/preview.png instead of the assets")
    a = p.parse_args()
    write_preview() if a.preview else write_assets()
