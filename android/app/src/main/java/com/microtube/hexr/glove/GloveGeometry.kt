package com.microtube.hexr.glove

import kotlin.math.max
import kotlin.math.min

/**
 * The HEXR glove art and where its six touch points are: the same numbers the desktop draws
 * with (`hexr/overlay.py`), so a point lands on the same fingertip on both.
 *
 * The art is a right hand with its palm towards the viewer, fingers spread; the left hand is the
 * same art mirrored. Everything scales with the glove's height `gh`. Pure: no Android, so the
 * maths is unit-tested on the JVM.
 */
object GloveGeometry {
    /** The art's width over its height. */
    const val ASPECT = 768f / 1295f

    /** A tap this close to a touch point (a share of the glove's height) picks it. */
    const val HIT = 0.09f

    /** Thumb, index, middle, ring, pinky, palm: the pads of the fingertips and the palm's middle. */
    val DOTS = listOf(
        Dot(.8802f, .3475f, labelLeft = false),
        Dot(.5951f, .1158f, labelLeft = false),
        Dot(.4232f, .0772f, labelLeft = true),
        Dot(.2591f, .1251f, labelLeft = true),
        Dot(.1042f, .2069f, labelLeft = true),
        Dot(.5469f, .6178f, labelLeft = false),
    )

    /** Drawn into the picture, so English, as on the desktop and the website. */
    val NAMES = listOf("THUMB", "INDEX", "MIDDLE", "RING", "PINKY", "PALM")
    val WORDS = listOf(listOf("PRESS.", "HOLD.", "RELEASE."), listOf("PULSE.", "BUZZ.", "CLICK."))

    fun isLeft(hand: String) = hand.equals("left", ignoreCase = true)
}

data class Dot(val x: Float, val y: Float, val labelLeft: Boolean)

enum class Labels { Off, Active, Always }

/** How one glove is drawn: the room beside it for name tags, and whether a caption sits under it. */
data class GloveLook(val margin: Float, val caption: Boolean, val labels: Labels = Labels.Off) {
    companion object {
        val TEST = GloveLook(.12f, caption = true)
        val CONNECT = GloveLook(.12f, caption = false)
        val QUICK = GloveLook(.12f, caption = false)
        val CAST = GloveLook(.25f, caption = true, labels = Labels.Active)
        val CAST_QUIET = GloveLook(.25f, caption = true)
    }
}

data class PanelSize(val width: Float, val height: Float)

data class Point(val x: Float, val y: Float)

/** One hand's panel for a glove `gh` tall: the glove, room beside it, and the caption under it. */
fun panelSize(gh: Float, look: GloveLook): PanelSize {
    val gw = gh * GloveGeometry.ASPECT
    val cap = gh * (if (look.caption) .24f else .06f)
    return PanelSize(gw + gw * look.margin * 2, gh * .12f + gh + cap)
}

/** Where the six touch points sit in one hand's panel: the drawing and a tap both use these. */
fun touchPoints(hand: String, gh: Float, look: GloveLook): List<Point> {
    val gw = gh * GloveGeometry.ASPECT
    val gx = gw * look.margin
    val gy = gh * .1f
    val left = GloveGeometry.isLeft(hand)
    return GloveGeometry.DOTS.map { Point(gx + (if (left) 1 - it.x else it.x) * gw, gy + it.y * gh) }
}

/** The touch point nearest (x, y), if one is within `radius`. */
fun nearestPoint(points: List<Point>, x: Float, y: Float, radius: Float): Int? {
    var best: Int? = null
    var bestD = radius * radius
    points.forEachIndexed { i, p ->
        val d = (p.x - x) * (p.x - x) + (p.y - y) * (p.y - y)
        if (d <= bestD) {
            best = i
            bestD = d
        }
    }
    return best
}

/** How near a tap has to be: a share of the glove, but never under a finger's width. */
fun hitRadius(gh: Float, minPx: Float) = max(GloveGeometry.HIT * gh, minPx)

/** Whether a finger's name tag goes to its left: the art's side, flipped for the left hand. */
fun tagOnLeft(channel: Int, hand: String) =
    GloveGeometry.DOTS[channel].labelLeft != GloveGeometry.isLeft(hand)

/** The tallest glove whose panel fits inside maxW x maxH. */
fun fitGh(maxW: Float, maxH: Float, look: GloveLook): Float {
    val unit = panelSize(1f, look)
    return max(0f, min(maxW / unit.width, maxH / unit.height))
}
