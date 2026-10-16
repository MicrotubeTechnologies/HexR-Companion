package com.microtube.hexr.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.microtube.hexr.R
import com.microtube.hexr.glove.GloveGeometry
import com.microtube.hexr.glove.GloveLook
import com.microtube.hexr.glove.HandState
import com.microtube.hexr.glove.Labels
import com.microtube.hexr.glove.hitRadius
import com.microtube.hexr.glove.nearestPoint
import com.microtube.hexr.glove.panelSize
import com.microtube.hexr.glove.tagOnLeft
import com.microtube.hexr.glove.touchPoints
import kotlin.math.max
import kotlin.math.min

/**
 * The orange HEXR glove, decoded once for the whole app: every glove on every screen draws from
 * this one bitmap, with mipmaps so a small glove is still sharp.
 */
object GloveAssets {
    @Volatile private var art: ImageBitmap? = null

    fun art(context: android.content.Context): ImageBitmap = art ?: synchronized(this) {
        art ?: run {
            val options = BitmapFactory.Options().apply {
                inScaled = false
                inPreferredConfig = Bitmap.Config.ARGB_8888
            }
            val bitmap = BitmapFactory.decodeResource(context.resources, R.drawable.glove, options)
            bitmap.setHasMipMap(true)
            bitmap.prepareToDraw()
            bitmap.asImageBitmap().also { art = it }
        }
    }
}

val CaptionFont = FontFamily(Font(R.font.archivo_black))

/**
 * One hand's glove, lit as [state] says: what fires glows white-hot, a vibration sends rings out,
 * each touch point is a dark-ringed dot (tinted for a verdict), picked fingers are ringed in
 * white, and the caption under it reads PRESS. HOLD. RELEASE. or PULSE. BUZZ. CLICK.
 * The same drawing as the desktop's `overlay.py`, sized by the glove's height [gh].
 *
 * [stateAt] instead of [state] draws a fresh state every frame: the headset cast, which follows
 * the video's own clock. [onTap] makes the touch points pickable.
 */
@Composable
fun GloveArt(
    hand: String,
    look: GloveLook,
    gh: Dp,
    modifier: Modifier = Modifier,
    state: HandState = HandState(),
    stateAt: (() -> HandState)? = null,
    selected: Set<Int>? = null,
    dim: Float = 1f,
    description: String = "",
    onTap: ((Int) -> Unit)? = null,
) {
    val context = LocalContext.current
    val art = remember { GloveAssets.art(context) }
    val measurer = rememberTextMeasurer(cacheSize = 32)
    val haptics = LocalHapticFeedback.current
    val tap by rememberUpdatedState(onTap)
    val handNow by rememberUpdatedState(hand)

    // Levels ease towards what the glove reports, so a glow fed ten times a second rises and
    // falls smoothly: as fast as air fills, slower as it empties.
    val eased = (0 until 6).map { ch ->
        val target = state.levels.getOrElse(ch) { 0f }
        animateFloatAsState(
            target, tween(if (target > 0f) 90 else 250), label = "glow$ch",
        )
    }

    // A clock for what moves by itself: rings, and the cast's frames. Read only while drawing,
    // so it redraws the glove without recomposing anything.
    var clock by remember { mutableFloatStateOf(0f) }
    val moving = stateAt != null || state.vibrating.any { it > 0f }
    if (moving) {
        LaunchedEffect(Unit) {
            val start = withFrameNanos { it }
            while (true) withFrameNanos { clock = (it - start) / 1e9f }
        }
    }

    val size = panelSize(gh.value, look)
    Canvas(
        modifier
            .size(size.width.dp, size.height.dp)
            .graphicsLayer(alpha = dim)
            .semantics { contentDescription = description }
            .then(
                if (onTap == null) Modifier else Modifier.pointerInput(look, gh) {
                    detectTapGestures { p ->
                        val ghPx = gh.toPx()
                        val hit = nearestPoint(
                            touchPoints(handNow, ghPx, look), p.x, p.y, hitRadius(ghPx, 24.dp.toPx()),
                        )
                        if (hit != null) {
                            haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                            tap?.invoke(hit)
                        }
                    }
                },
            ),
    ) {
        val ghPx = gh.toPx()
        val st = if (stateAt != null) {
            clock.let { stateAt() }
        } else {
            state.copy(levels = eased.map { it.value })
        }
        drawGlove(art, hand, look, ghPx, st, selected, clock, measurer)
    }
}

private val FIRE = Color(0xFFFFF6E2)
private val DOT = Color(0xFF18191C)
private val TAG = Color(0xFF111214)
private val LIT_WORD = Color(0xFFF2661A)

private fun DrawScope.drawGlove(
    art: ImageBitmap, hand: String, look: GloveLook, gh: Float, st: HandState,
    selected: Set<Int>?, clock: Float, measurer: TextMeasurer,
) {
    val gw = gh * GloveGeometry.ASPECT
    val gx = gw * look.margin
    val gy = gh * .1f
    val left = GloveGeometry.isLeft(hand)

    // The glove, mirrored for the left hand.
    val pivot = Offset(gx + gw / 2, gy + gh / 2)
    scale(if (left) -1f else 1f, 1f, pivot) {
        drawImage(
            art,
            srcOffset = IntOffset.Zero,
            srcSize = IntSize(art.width, art.height),
            dstOffset = IntOffset(gx.toInt(), gy.toInt()),
            dstSize = IntSize(gw.toInt(), gh.toInt()),
            filterQuality = FilterQuality.High,
        )
    }

    val points = touchPoints(hand, gh, look)
    // What fires glows white-hot, or in its verdict's colour.
    points.forEachIndexed { ch, p ->
        val level = st.levels.getOrElse(ch) { 0f }
        if (level <= 0.003f) return@forEachIndexed
        val tint = st.tints?.getOrNull(ch)?.let { Color(it) } ?: FIRE
        val r = gh * .085f * (.55f + .9f * level)
        drawCircle(
            Brush.radialGradient(
                listOf(tint.copy(alpha = .15f + .85f * level), tint.copy(alpha = 0f)), p.offset, r,
            ),
            radius = r, center = p.offset,
        )
    }
    // A vibration sends rings out from its point.
    points.forEachIndexed { ch, p ->
        val hz = st.vibrating.getOrElse(ch) { 0f }
        if (hz <= 0f) return@forEachIndexed
        val rate = min(hz, 2.5f)
        for (k in 0 until 2) {
            val phase = ((clock * rate) + k / 2f) % 1f
            drawCircle(
                FIRE.copy(alpha = (1 - phase) * .9f),
                radius = gh * .03f * (1 + 2.4f * phase), center = p.offset,
                style = Stroke(width = max(1f, gh * .007f)),
            )
        }
    }
    // Each touch point: a dark edge, its colour, a white centre.
    points.forEachIndexed { ch, p ->
        val level = st.levels.getOrElse(ch) { 0f }
        val a = .55f + .45f * level
        val tint = st.tints?.getOrNull(ch)?.let { Color(it) } ?: DOT
        drawCircle(DOT.copy(alpha = .9f * a), radius = gh * .029f, center = p.offset)
        drawCircle(tint.copy(alpha = .9f * a), radius = gh * .024f, center = p.offset)
        drawCircle(Color.White.copy(alpha = a), radius = gh * .016f, center = p.offset)
    }
    // Picked fingers, ringed in white.
    if (selected != null) {
        val r = max(gh * .05f, 10.dp.toPx())
        points.forEachIndexed { ch, p ->
            if (ch in selected) drawCircle(Color.White, r, p.offset, style = Stroke(2.dp.toPx()))
        }
    }
    // A finger's name beside it while it fires: while one or two do. More, and the names would
    // crowd the glove, which says enough by lighting up (the desktop's NAMED_AT_MOST).
    val firing = st.levels.count { it > .08f }
    if (look.labels == Labels.Always || (look.labels == Labels.Active && firing <= 2)) {
        val fs = max(10.sp.toPx(), gh * .04f)
        points.forEachIndexed { ch, p ->
            val level = st.levels.getOrElse(ch) { 0f }
            val show = if (look.labels == Labels.Always) .55f + .45f * min(1f, level * 2)
            else ((level - .08f) * 4).coerceIn(0f, 1f)
            if (show <= 0f) return@forEachIndexed
            val text = measurer.measure(
                GloveGeometry.NAMES[ch],
                TextStyle(color = Color.White.copy(alpha = show), fontSize = (fs / density).sp, fontWeight = FontWeight.Bold),
            )
            val ph = fs * .55f
            val w = text.size.width + ph * 2
            val h = fs * 1.7f
            val off = gh * .045f
            var cx = if (tagOnLeft(ch, hand)) p.x - off - w / 2 else p.x + off + w / 2
            cx = cx.coerceIn(w / 2, size.width - w / 2)
            val top = p.y - h * .3f - h / 2
            drawRoundRect(TAG.copy(alpha = .92f * show), Offset(cx - w / 2, top), Size(w, h), CornerRadius(h / 2))
            drawText(text, topLeft = Offset(cx - text.size.width / 2, top + (h - text.size.height) / 2))
        }
    }
    // The caption under it.
    if (look.caption) drawCaption(st, gh, gy, measurer)
}

private fun DrawScope.drawCaption(st: HandState, gh: Float, gy: Float, measurer: TextMeasurer) {
    val words = GloveGeometry.WORDS[st.words.coerceIn(0, 1)]
    val top = gy + gh + gh * .02f
    var fs = gh * .085f
    fun styles(lit: Int, size: Float) = words.mapIndexed { i, w ->
        measurer.measure(
            w,
            TextStyle(
                color = if (i == lit) LIT_WORD else Color.White.copy(alpha = 60f / 255),
                fontSize = (size / density).sp, fontFamily = CaptionFont,
            ),
        )
    }
    var laid = styles(st.word, fs)
    var space = fs * .3f
    var total = laid.sumOf { it.size.width } + space * 2
    val room = size.width - gh * .12f
    if (total > room && total > 0) {
        fs *= room / total
        laid = styles(st.word, fs)
        space = fs * .3f
        total = laid.sumOf { it.size.width } + space * 2
    }
    if (st.words == 1 && st.word >= 0 && st.hz > 0f) {
        val hz = measurer.measure(
            "${"%.1f".format(java.util.Locale.US, st.hz).removeSuffix(".0")} Hz",
            TextStyle(color = Color(0xFFEBEBED), fontSize = (gh * .045f / density).sp, fontWeight = FontWeight.SemiBold),
        )
        drawText(hz, topLeft = Offset((size.width - hz.size.width) / 2, top + gh * .075f - hz.size.height))
    }
    var x = (size.width - total) / 2
    val baseline = top + gh * .19f
    for (t in laid) {
        drawText(t, topLeft = Offset(x, baseline - t.firstBaseline))
        x += t.size.width + space
    }
}

private val com.microtube.hexr.glove.Point.offset get() = Offset(x, y)

