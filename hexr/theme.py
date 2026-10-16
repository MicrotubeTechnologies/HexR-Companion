"""Design tokens for the HEXR Companion app.

Every colour, size and radius in the app comes from here — the handoff spec is
transcribed once, in one place, so a token change lands everywhere at once.

Two Tkinter realities shape this module:

* Tk sizes fonts in POINTS when the size is positive and PIXELS when negative.
  The design is specified in pixels, so every size here is negative.
* Tk has no letter-spacing. The design's tracked uppercase micro-labels are
  faked by `track()`; see the note there for what that can and cannot do.
"""

from __future__ import annotations

import os
import sys
import tkinter.font as tkfont

# ---------------------------------------------------------------------------
# Colour
# ---------------------------------------------------------------------------

CANVAS = "#0A0B0C"          # desktop behind the window; text on orange fills
SURFACE = "#111214"         # window body, header
RAISED = "#17191C"          # title bar, panels, cards
INSET = "#1C1F23"           # selected rows, chips, keys, readouts
RAIL = "#131417"            # left rail, meter and trace backgrounds, footer

BORDER = "#2A2E34"          # panel and control borders
BORDER_SOFT = "#23262B"     # section dividers, panel outlines
BORDER_ROW = "#1E2126"      # table row separators

TEXT = "#E9EAEC"            # primary
TEXT_2 = "#B7BCC3"          # values, secondary labels
TEXT_MUTED = "#868C94"      # descriptions, idle nav
TEXT_FAINT = "#6E747C"      # section labels, captions
TEXT_OFF = "#5C626A"        # disabled labels
DOT_OFF = "#4A5058"         # disabled dots

ACCENT = "#F26B21"          # brand, active state, firing signal
ACCENT_HOVER = "#FF8442"    # hover on solid accent
ACCENT_FILL = "#26221F"     # assigned-key fill
ACCENT_EDGE = "#5A3A20"     # assigned-key border

SUCCESS = "#3ECF8E"         # connected, calibrated, healthy latency
DANGER = "#E5484D"          # stop, close hover, destructive
WARN = "#E8B04B"            # poor, low battery: worth a look, not a fault

METER_IDLE = "#3A4048"      # below-threshold signal fill
TRACE_IDLE = "#343A42"      # below-threshold trace bar

# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

WIN_W, WIN_H = 1180, 742
TITLEBAR_H = 40
HEADER_H = 62
BODY_H = 640
RAIL_W = 206

R_METER, R_CHIP, R_CELL, R_CTRL, R_PANEL, R_WINDOW = 3, 4, 5, 6, 8, 10

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
#
# IBM Plex ships as one family per weight ("IBM Plex Sans SemiBold" is its own
# family, not a bold variant of "IBM Plex Sans"), so weights are resolved to
# family names rather than to Tk's normal/bold flag.

def _resource_dir(*parts: str) -> str:
    """Locate bundled data both from source and from a PyInstaller build.

    In a onefile build the datas are unpacked to `sys._MEIPASS`, not next to
    this module — without this the bundled fonts would silently fail to load in
    the .exe and every user would get the Segoe UI fallback.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, *parts)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", *parts)


resource_path = _resource_dir       # public alias for other modules


def app_version(default: str = "0.0.0") -> str:
    """The single source of truth for the version: the VERSION file.

    The installer script and the build both read the same file, so a release
    cannot ship an app that disagrees with its own installer about what
    version it is.
    """
    try:
        with open(_resource_dir("VERSION"), encoding="utf-8") as f:
            return f.read().strip() or default
    except OSError:
        return default

FONT_DIR = _resource_dir("assets", "fonts")

_SANS_BY_WEIGHT = {
    400: "IBM Plex Sans",
    500: "IBM Plex Sans Medium",
    600: "IBM Plex Sans SemiBold",
    700: "IBM Plex Sans Bold",
}
_MONO_BY_WEIGHT = {
    400: "IBM Plex Mono",
    500: "IBM Plex Mono Medium",
    600: "IBM Plex Mono SemiBold",
}

# Fallbacks when IBM Plex is unavailable: Windows ships Segoe UI / Consolas,
# macOS ships Helvetica Neue / Menlo.
if sys.platform == "darwin":
    FALLBACK_SANS, FALLBACK_MONO = "Helvetica Neue", "Menlo"
else:
    FALLBACK_SANS, FALLBACK_MONO = "Segoe UI", "Consolas"

# IBM Plex has no Chinese. Left to itself Tk borrows the missing characters
# from whatever font it finds first, often a serif SimSun, so in Chinese the
# sans text is set in the system's own Chinese UI face instead, the first of
# these that is installed. Its Latin is good enough for the English names and
# units mixed in. Mono stays Plex: it carries numbers, not sentences.
CJK_SANS = ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC",
            "Hiragino Sans GB", "Noto Sans CJK SC", "Source Han Sans SC")

# Resolved once by init(); until then everything falls back.
_sans: dict[int, tuple[str, str]] = {}
_mono: dict[int, tuple[str, str]] = {}
_cache: dict[tuple, tkfont.Font] = {}
_cjk_family: str | None = None
_fonts_loaded: int | None = None

HAVE_PLEX = False
FONT_NOTE = "not initialised"


def _load_bundled_fonts() -> int:
    """Register any TTFs in assets/fonts for this process only.

    FR_PRIVATE keeps them out of the user's font list — nothing is installed,
    and they disappear when the process exits.
    """
    if sys.platform != "win32" or not os.path.isdir(FONT_DIR):
        return 0
    import ctypes

    FR_PRIVATE = 0x10
    loaded = 0
    for name in sorted(os.listdir(FONT_DIR)):
        if not name.lower().endswith((".ttf", ".otf")):
            continue
        path = os.path.abspath(os.path.join(FONT_DIR, name))
        try:
            if ctypes.windll.gdi32.AddFontResourceExW(
                    ctypes.c_wchar_p(path), FR_PRIVATE, 0):
                loaded += 1
        except Exception:
            pass
    if loaded:
        # tell the shell the font table changed, so Tk enumerates the new ones
        HWND_BROADCAST, WM_FONTCHANGE = 0xFFFF, 0x001D
        try:
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST, WM_FONTCHANGE, 0, 0, 0, 1000, None)
        except Exception:
            pass
    return loaded


def init(root, cjk: bool = False) -> str:
    """Resolve the font families. Call right after the Tk root exists, and
    again when the language changes: `cjk` sets the sans text in a Chinese
    face. Fonts made before a call are not changed; the caller rebuilds.

    Returns a human-readable note about what was resolved — worth logging,
    because a silent fallback to Segoe UI is otherwise hard to notice.
    """
    global _sans, _mono, HAVE_PLEX, FONT_NOTE, _cjk_family, _fonts_loaded

    if _fonts_loaded is None:
        _fonts_loaded = _load_bundled_fonts()
    loaded = _fonts_loaded
    available = set(tkfont.families(root))
    _cjk_family = next((f for f in CJK_SANS if f in available), None)

    def pick(table: dict[int, str], fallback: str, bold_from: int):
        out = {}
        for weight, family in table.items():
            if family in available:
                out[weight] = (family, "normal")
            elif weight >= bold_from:
                out[weight] = (fallback, "bold")
            else:
                out[weight] = (fallback, "normal")
        return out

    _sans = pick(_SANS_BY_WEIGHT, FALLBACK_SANS, 600)
    if cjk and _cjk_family:
        _sans = {w: (_cjk_family, "bold" if w >= 600 else "normal")
                 for w in _SANS_BY_WEIGHT}
    _mono = pick(_MONO_BY_WEIGHT, FALLBACK_MONO, 600)
    HAVE_PLEX = "IBM Plex Sans" in available

    if HAVE_PLEX:
        FONT_NOTE = f"IBM Plex ({loaded} bundled files loaded)"
    else:
        FONT_NOTE = (f"IBM Plex not found — falling back to {FALLBACK_SANS} / "
                     f"{FALLBACK_MONO}. "
                     f"Drop the OFL TTFs into {os.path.normpath(FONT_DIR)}.")
    _cache.clear()
    return FONT_NOTE


def font(px: float, weight: int = 400, mono: bool = False) -> tkfont.Font:
    """A font at `px` PIXELS. Sizes are cached — Tk font objects are not free."""
    key = (round(px), weight, mono)
    if key in _cache:
        return _cache[key]
    table = _mono if mono else _sans
    if not table:                       # init() not called yet
        family, style = (FALLBACK_MONO if mono else FALLBACK_SANS,
                         "bold" if weight >= 600 else "normal")
    else:
        # snap to the nearest defined weight
        near = min(table, key=lambda w: abs(w - weight))
        family, style = table[near]
    f = tkfont.Font(family=family, size=-round(px), weight=style)
    _cache[key] = f
    return f


def mono(px: float, weight: int = 400) -> tkfont.Font:
    return font(px, weight, mono=True)


def cjk(px: float, weight: int = 400) -> tkfont.Font:
    """The Chinese face whatever the language: for the one word that is always
    in Chinese, the language switch's 中文."""
    key = (round(px), weight, "cjk")
    if key not in _cache:
        _cache[key] = tkfont.Font(family=_cjk_family or FALLBACK_SANS,
                                  size=-round(px),
                                  weight="bold" if weight >= 600 else "normal")
    return _cache[key]


# ---------------------------------------------------------------------------
# Faked letter-spacing
# ---------------------------------------------------------------------------

# U+200A HAIR SPACE is about 1/10 em — the closest single character to the
# design's .11–.12em tracking on the uppercase micro-labels. Tk cannot do real
# letter-spacing, and this is the least-bad substitute: it only works on short
# all-caps labels, and it makes the string unusable for measurement or
# selection. Never apply it to body copy or to anything the user reads as data.
HAIR = " "


def track(text: str, space: str = HAIR) -> str:
    """Fake letter-spacing for a short uppercase label ('PORT' -> 'P␣O␣R␣T').

    Chinese is left alone: its characters are already evenly spaced, and
    hair spaces between them only read as gaps."""
    if any(ord(ch) >= 0x2E80 for ch in text):
        return text
    return space.join(text)


def supports_hair_space(root) -> bool:
    """True if the resolved UI font actually has a hair-space glyph.

    Without this check a missing glyph renders as a tofu box in every section
    label in the app, which looks far worse than no tracking at all.
    """
    f = font(10)
    try:
        return 0 < f.measure(HAIR) < f.measure(" ")
    except Exception:
        return False
