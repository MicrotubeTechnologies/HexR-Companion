"""Generate the HEXR Companion app icon.

    python tools/make_icon.py            # writes the shipping icon
    python tools/make_icon.py --preview  # writes a contact sheet of all styles

The icon is generated rather than checked in as a hand-drawn asset so it can be
re-rendered at any size, and so a colour or style change is a one-line edit
here instead of a round trip through a drawing program.

Everything is drawn on a 1024 px canvas and downsampled, which is what keeps
the curves clean at 16 px. The shapes are deliberately fat: anything thinner
than ~8% of the canvas disappears in a taskbar.
"""

import argparse
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Brand colours, matching hexr/theme.py.
ACCENT = (242, 107, 33, 255)      # #F26B21
CHARCOAL = (17, 18, 20, 255)      # #111214
WHITE = (255, 255, 255, 255)

S = 1024                          # master canvas
# Windows icons sit in a rounded-square tile; ~22% radius matches the platform.
RADIUS = int(S * 0.22)
# Sizes Windows actually asks for: Explorer, taskbar, alt-tab, jumbo view.
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def _canvas(bg):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, S - 1, S - 1), RADIUS, fill=bg)
    return img


def _hexagon(draw, colour, cx, cy, r, width=0):
    """A flat-topped hexagon — the HEX in HEXR, and about the most robust
    shape there is at 16 px. `width=0` fills it, otherwise it is an outline."""
    import math
    pts = []
    for i in range(6):
        a = math.radians(60 * i)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    if width:
        draw.line(pts + [pts[0]], fill=colour, width=width, joint="curve")
        # joint="curve" leaves the vertices slightly notched at small sizes;
        # capping each one keeps the outline continuous when downsampled.
        cap = width / 2
        for x, y in pts:
            draw.ellipse((x - cap, y - cap, x + cap, y + cap), fill=colour)
    else:
        draw.polygon(pts, fill=colour)


def _contact(draw, colour, cx, cy, r):
    """The point of contact at the centre — what the glove is actually for."""
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colour)


def style_hex():
    """Orange tile, white hexagon outline with a solid contact point."""
    img = _canvas(ACCENT)
    d = ImageDraw.Draw(img)
    _hexagon(d, WHITE, S / 2, S / 2, S * 0.33, width=int(S * 0.095))
    _contact(d, WHITE, S / 2, S / 2, S * 0.105)
    return img


def style_solid():
    """Orange tile, solid white hexagon, orange contact point punched out."""
    img = _canvas(ACCENT)
    d = ImageDraw.Draw(img)
    _hexagon(d, WHITE, S / 2, S / 2, S * 0.35)
    _contact(d, ACCENT, S / 2, S / 2, S * 0.135)
    return img


def style_dark():
    """Charcoal tile matching the app window, orange hexagon and point."""
    img = _canvas(CHARCOAL)
    d = ImageDraw.Draw(img)
    _hexagon(d, ACCENT, S / 2, S / 2, S * 0.33, width=int(S * 0.095))
    _contact(d, ACCENT, S / 2, S / 2, S * 0.105)
    return img


STYLES = {"hex": style_hex, "solid": style_solid, "dark": style_dark}
DEFAULT_STYLE = "hex"


# The title bar draws the mark at this size. It is written as its own file,
# properly downsampled from the 1024 master, because Tk's PhotoImage can only
# shrink a PNG by whole-number division (subsample), and 512 -> 16 that way is
# nearest-neighbour: the curves come out ragged. Resampling here once, at build
# time, costs nothing and looks right.
TITLEBAR_PX = 16


def write_icon(style):
    img = STYLES[style]()
    png = os.path.join(ROOT, "assets", "icon.png")
    ico = os.path.join(ROOT, "assets", "icon.ico")
    small = os.path.join(ROOT, "assets", f"icon-{TITLEBAR_PX}.png")
    img.resize((512, 512), Image.LANCZOS).save(png)
    img.resize((TITLEBAR_PX, TITLEBAR_PX), Image.LANCZOS).save(small)
    # Pillow builds every listed size into the one .ico. The old file held a
    # single 16x16 frame, so Windows was upscaling that blur everywhere it
    # needed something bigger.
    img.save(ico, sizes=[(n, n) for n in ICO_SIZES])
    print(f"wrote {png}, {ico} and {small}  "
          f"(style: {style}, {len(ICO_SIZES)} sizes)")


def write_preview():
    """Contact sheet: every style down every size someone will actually see."""
    shown = (256, 48, 32, 16)
    pad, gap, label = 40, 32, 34
    cell = 256
    w = pad * 2 + cell + gap + sum(shown[1:]) + gap * (len(shown) - 2)
    h = pad * 2 + len(STYLES) * (cell + gap + label)
    sheet = Image.new("RGBA", (w, h), (28, 31, 35, 255))
    d = ImageDraw.Draw(sheet)
    y = pad
    for name, fn in STYLES.items():
        img = fn()
        d.text((pad, y - 26), f"{name}{'  (default)' if name == DEFAULT_STYLE else ''}",
               fill=(233, 234, 236, 255))
        x = pad
        for n in shown:
            sheet.alpha_composite(img.resize((n, n), Image.LANCZOS),
                                  (x, y + cell - n))
            x += n + gap
        y += cell + gap + label
    out = os.path.join(ROOT, "assets", "icon-preview.png")
    sheet.save(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--style", choices=sorted(STYLES), default=DEFAULT_STYLE)
    p.add_argument("--preview", action="store_true",
                   help="write assets/icon-preview.png instead of the icon")
    a = p.parse_args()
    if not hasattr(Image, "Resampling") and not hasattr(Image, "LANCZOS"):
        sys.exit("Pillow is required:  pip install pillow")
    write_preview() if a.preview else write_icon(a.style)
