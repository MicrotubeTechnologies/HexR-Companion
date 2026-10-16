package com.microtube.hexr

import com.microtube.hexr.glove.GloveGeometry
import com.microtube.hexr.glove.GloveLook
import com.microtube.hexr.glove.HandLook
import com.microtube.hexr.glove.Verdict
import com.microtube.hexr.glove.connectState
import com.microtube.hexr.glove.ease
import com.microtube.hexr.glove.fitGh
import com.microtube.hexr.glove.hitRadius
import com.microtube.hexr.glove.nearestPoint
import com.microtube.hexr.glove.padState
import com.microtube.hexr.glove.panelSize
import com.microtube.hexr.glove.tagOnLeft
import com.microtube.hexr.glove.touchPoints
import com.microtube.hexr.glove.verdictState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** The glove picture: where its touch points are, what a tap hits, and how it is lit. */
class GloveTest {

    @Test
    fun thePanelIsTheGloveItsMarginAndItsCaption() {
        val gw = 100 * GloveGeometry.ASPECT
        val test = panelSize(100f, GloveLook.TEST)
        assertEquals(gw * 1.24f, test.width, 1e-3f)
        assertEquals(136f, test.height, 1e-3f)
        assertEquals(118f, panelSize(100f, GloveLook.CONNECT).height, 1e-3f)
    }

    @Test
    fun theLeftHandIsTheRightHandMirrored() {
        val gh = 300f
        val look = GloveLook.TEST
        val gw = gh * GloveGeometry.ASPECT
        val right = touchPoints("Right", gh, look)
        val left = touchPoints("left", gh, look)
        for (i in 0 until 6) {
            assertEquals(right[i].y, left[i].y, 1e-3f)
            assertEquals(2 * gw * look.margin + gw, right[i].x + left[i].x, 1e-3f)
        }
        assertTrue(tagOnLeft(2, "right") && !tagOnLeft(2, "left"))
    }

    @Test
    fun aTapPicksTheNearestPointNearEnough() {
        val pts = touchPoints("right", 300f, GloveLook.TEST)
        pts.forEachIndexed { i, p -> assertEquals(i, nearestPoint(pts, p.x + 2, p.y - 2, 27f)) }
        val index = pts[1]
        val middle = pts[2]
        val nearIndex = (index.x * .7f + middle.x * .3f) to (index.y * .7f + middle.y * .3f)
        assertEquals(1, nearestPoint(pts, nearIndex.first, nearIndex.second, 60f))
        assertNull(nearestPoint(pts, 0f, 0f, 27f))
        assertEquals(24f, hitRadius(100f, 24f), 1e-6f)
        assertEquals(36f, hitRadius(400f, 24f), 1e-6f)
    }

    @Test
    fun theGloveFitsItsRoomEitherWay() {
        val unit = panelSize(1f, GloveLook.TEST)
        assertEquals(100f / unit.width, fitGh(100f, 1000f, GloveLook.TEST), 1e-3f)
        assertEquals(200f / unit.height, fitGh(1000f, 200f, GloveLook.TEST), 1e-3f)
    }

    @Test
    fun theTestGloveFollowsTheTrigger() {
        val press = padState(null, on = true, sincePress = .1f, sinceRelease = null,
            vibration = false, intensity = .6f, hz = 10f, channels = setOf(1, 2))
        assertEquals(listOf(0f, .6f, .6f, 0f, 0f, 0f), press.levels)
        assertEquals(0, press.word)
        assertEquals(1, padState(null, true, .5f, null, false, .6f, 10f, setOf(1)).word)
        assertEquals(2, padState(null, false, 2f, .2f, false, .6f, 10f, setOf(1)).word)
        val buzz = padState(null, true, .5f, null, true, .6f, 12f, setOf(0))
        assertEquals(12f, buzz.vibrating[0], 0f)
        assertEquals(1, buzz.words)
        assertEquals(1, buzz.word)
        assertEquals(0, padState(null, true, .5f, null, true, .6f, 2f, setOf(0)).word)
        // A glove that streams shows what it measures.
        val measured = padState(listOf(0.0, 45.0, 0.0, 0.0, 0.0, 0.0), false, 0f, null, false, .6f, 10f, setOf(1))
        assertEquals(1f, measured.levels[1], 1e-6f)
    }

    @Test
    fun connectedIsGreenAndAPressShowsThrough() {
        assertEquals(List(6) { 0f }, connectState(false, null).levels)
        val st = connectState(true, listOf(0.0, 40.0, 0.0, 0.0, 0.0, 0.0))
        assertEquals(.32f, st.levels[0], 1e-6f)
        assertEquals(HandLook.GREEN, st.tints!![0])
        assertNull(st.tints!![1])
    }

    @Test
    fun verdictsColourTheGlove() {
        val st = verdictState(listOf(Verdict.Good, Verdict.Poor, Verdict.Fail, Verdict.Good, Verdict.Good, Verdict.Good), false)
        assertEquals(listOf(HandLook.GREEN, HandLook.AMBER, HandLook.RED), st.tints!!.take(3))
        assertEquals(.75f, st.levels[1], 1e-6f)
        val pump = verdictState(List(6) { Verdict.Good }, pumpFailed = true)
        assertTrue(pump.tints!!.all { it == HandLook.RED })
    }

    @Test
    fun easingRisesFastAndFallsSlower() {
        val up = ease(0f, 1f, .09f)
        val down = 1f - ease(1f, 0f, .09f)
        assertTrue(up > down)
        assertEquals(.5f, ease(.5f, 1f, 0f), 0f)
        assertEquals(1f, ease(.999f, 1f, 1f), 0f)
    }
}
