package com.microtube.hexr.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp

/**
 * Design tokens, transcribed from the `design_handoff_hexr_tester` pass.
 *
 * These supersede the values ported from the desktop tester's `hexr/theme.py`.
 * The ground went a shade darker and cooler, surfaces are now neutral greys
 * rather than the desktop's blue-tinted ones, and every border is white at low
 * alpha instead of a fixed grey — which is why they read consistently over both
 * the card and the elevated-card fills.
 *
 * Dark only, deliberately, and it does not follow the system light theme: this
 * is used on a bench and in customers' offices, and pressure readings need
 * consistent contrast rather than a palette that changes with a phone setting.
 */
object T {
    val SCREEN = Color(0xFF0C0C0E)        // the app ground
    val CARD = Color(0xFF1B1B1F)          // cards, controls, segment tracks
    val ELEVATED = Color(0xFF141417)      // panels sitting on top of cards
    val ELEVATED_2 = Color(0xFF141416)
    val CHIP = Color(0xFF26262B)          // All / None pills

    // Borders are white at low alpha so they hold over any of the fills above.
    val BORDER = Color.White.copy(alpha = 0.09f)
    val BORDER_SOFT = Color.White.copy(alpha = 0.07f)
    val BORDER_STRONG = Color.White.copy(alpha = 0.10f)
    val HAIRLINE = Color.White.copy(alpha = 0.05f)

    val TEXT = Color(0xFFECECEC)          // primary
    val TEXT_2 = Color(0xFF9A9AA0)        // secondary
    val TEXT_3 = Color(0xFF7C7C84)        // section labels
    val TEXT_4 = Color(0xFF6C6C74)        // tertiary, unselected values
    val TEXT_5 = Color(0xFF57575E)        // captions, disabled
    val TEXT_FAINT = Color(0xFF3A3A40)    // zero values, idle strokes

    val ACCENT = Color(0xFFF4762A)
    /** Near-black, for labels sitting on an accent fill. */
    val ON_ACCENT = Color(0xFF140B04)

    val GREEN = Color(0xFF4CD07D)         // connected, pass
    val RED = Color(0xFFE8534A)           // disconnect, fail
    val AMBER = Color(0xFFE8B13F)         // a channel that moved but not enough

    val R_CHIP = 8.dp
    val R_CARD = 10.dp
    val R_CTRL = 12.dp
    val R_SHEET = 14.dp
    val R_PILL = 14.dp

    val PAGE_PAD = 16.dp
}

/**
 * The type scale.
 *
 * Sizes are Float because the handoff specifies half-point steps (10.5, 13.5)
 * and rounding them closes the gap between a caption and its label.
 */
object Size {
    const val VERDICT = 22f     // the quick test's one-line answer
    const val TITLE = 21f       // screen headings
    const val WORDMARK = 16f    // HEXR, in the header lockup
    const val ACTION = 15f      // primary button labels
    const val CONTROL = 14f     // secondary buttons, segment labels
    const val BODY = 13.5f
    const val BODY_2 = 13f
    const val CAPTION = 12.5f
    const val MICRO = 11.5f
    const val LABEL = 10.5f     // tracked uppercase section labels
    const val TAG = 10f         // the COMPANION pill
}

/** Monospace for every numeric readout: pressures, percentages, Hz, addresses. */
val Mono = FontFamily.Monospace

private val HexrColors = darkColorScheme(
    primary = T.ACCENT,
    onPrimary = T.ON_ACCENT,
    background = T.SCREEN,
    onBackground = T.TEXT,
    surface = T.CARD,
    onSurface = T.TEXT,
    surfaceVariant = T.ELEVATED,
    onSurfaceVariant = T.TEXT_2,
    error = T.RED,
    outline = T.BORDER,
)

@Composable
fun HexrTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = HexrColors, content = content)
}
