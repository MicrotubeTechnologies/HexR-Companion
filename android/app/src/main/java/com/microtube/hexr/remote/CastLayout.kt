package com.microtube.hexr.remote

import com.microtube.hexr.glove.GloveLook
import com.microtube.hexr.glove.fitGh
import kotlin.math.max
import kotlin.math.min

/** A rectangle, in whatever unit the caller works in (dp on the phone). */
data class Box(val x: Float, val y: Float, val w: Float, val h: Float) {
    val right get() = x + w
    val bottom get() = y + h
}

data class CastBoxes(val view: Box, val left: Box, val right: Box)

/**
 * Where a headset's view and its two glove panels go on the phone: the desktop's `viewer.py`,
 * shaped for a phone held either way.
 *
 * - Landscape: the view takes three quarters of the width, top to bottom; a square view is cut
 *   to it, keeping its lower part, where hands are. The gloves have the last quarter.
 * - Portrait: the view runs across the top, as tall as leaves the gloves their room under it.
 *
 * The two panels share the gloves' room side by side or one above the other, whichever draws the
 * glove bigger; the left hand is the first, so on the left or on top. Pure, so it is tested.
 */
object CastLayout {
    const val VIEW_SHARE = .75f     // landscape: the view's share of the width
    const val CUT_LOW = .35f        // where a view cut to fit is cut: -1 its top, 0 middle, 1 bottom
    const val GLOVES_SHARE = .42f   // portrait: the least of the height the gloves keep

    fun landscape(w: Float, h: Float, gap: Float, head: Float, pad: Float): CastBoxes {
        val vw = w * VIEW_SHARE - gap / 2
        val room = Box(vw + gap, 0f, w - vw - gap, h)
        val (l, r) = twoPanels(room, gap, head, pad)
        return CastBoxes(Box(0f, 0f, vw, h), l, r)
    }

    fun portrait(w: Float, h: Float, aspect: Float, gap: Float, minPanels: Float, head: Float, pad: Float): CastBoxes {
        val vh = max(0f, min(w / aspect, h - max(h * GLOVES_SHARE, minPanels) - gap))
        val room = Box(0f, vh + gap, w, h - vh - gap)
        val (l, r) = twoPanels(room, gap, head, pad)
        return CastBoxes(Box(0f, 0f, w, vh), l, r)
    }

    /** The gloves' room in two: side by side or stacked, whichever draws the glove taller. */
    fun twoPanels(room: Box, gap: Float, head: Float, pad: Float): Pair<Box, Box> {
        val halfW = (room.w - gap) / 2
        val halfH = (room.h - gap) / 2
        val beside = Box(room.x, room.y, halfW, room.h) to Box(room.x + halfW + gap, room.y, halfW, room.h)
        val stacked = Box(room.x, room.y, room.w, halfH) to Box(room.x, room.y + halfH + gap, room.w, halfH)
        return if (gloveHeight(stacked.first, head, pad) >= gloveHeight(beside.first, head, pad)) stacked else beside
    }

    /** The glove's height in a panel, under its heading. */
    fun gloveHeight(cell: Box, head: Float, pad: Float): Float =
        fitGh(cell.w - pad * 2, cell.h - head - pad * 2, GloveLook.CAST)

    /**
     * Where the whole video frame goes so that it shows in `box`: filling it and cut top and
     * bottom (low, by [CUT_LOW]) when the video is taller than the box; otherwise whole and
     * centred. In the box's own coordinates.
     */
    fun videoRect(box: Box, videoW: Int, videoH: Int): Box {
        if (videoW <= 0 || videoH <= 0 || box.w <= 0 || box.h <= 0) return Box(0f, 0f, box.w, box.h)
        val va = videoW.toFloat() / videoH
        val ba = box.w / box.h
        return if (va < ba - .01f) {
            val h = box.w / va
            val top = (h - box.h) / 2 * (1 + CUT_LOW)
            Box(0f, -top, box.w, h)
        } else {
            val s = min(box.w / videoW, box.h / videoH)
            val w = videoW * s
            val h = videoH * s
            Box((box.w - w) / 2, (box.h - h) / 2, w, h)
        }
    }
}
