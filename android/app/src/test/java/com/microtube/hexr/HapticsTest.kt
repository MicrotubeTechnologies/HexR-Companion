package com.microtube.hexr

import com.microtube.hexr.remote.HapticChannel
import com.microtube.hexr.remote.HapticsTimeline
import com.microtube.hexr.remote.HapticsUpdate
import com.microtube.hexr.remote.HeadsetStatus
import com.microtube.hexr.remote.Message
import com.microtube.hexr.remote.RemoteProtocol
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.exp

/**
 * A headset's haptics: the "haptics" line, recentering, and the timeline the glove panels are
 * drawn from. The same cases as the desktop's tests/test_overlay.py, so both light up alike.
 */
class HapticsTest {

    private val t0 = 5_000.0     // seconds on the headset's clock
    private val us = 1_000_000L

    private fun update(hand: String, t: Double, vararg ch: HapticChannel) =
        HapticsUpdate(hand, (t * us).toLong(), ch.toList())

    private fun status(clockS: Double = 0.0, haptics: Boolean = true, rightKpa: List<Int> = List(6) { 0 }): HeadsetStatus {
        val gloves = """[{"hand":"left","state":"connected","pressureDeciKPa":[0,0,0,0,0,0,450]},""" +
            """{"hand":"right","state":"connected","pressureDeciKPa":[${(rightKpa + 450).joinToString(",")}]}]"""
        val line = """{"type":"status","haptics":$haptics,"clockUs":${(clockS * us).toLong()},"gloves":$gloves}"""
        return (RemoteProtocol.parseLine(line) as Message.Status).status
    }

    // -- the line ----------------------------------------------------------------------------

    @Test
    fun aHapticsLineReads() {
        val m = RemoteProtocol.parseLine(
            """{"type":"haptics","hand":"right","t":5000123456,"channels":[{"finger":1,"mode":"pressure","intensityPct":80}]}""",
        ) as Message.Haptics
        assertEquals("right", m.update.hand)
        assertEquals(5_000_123_456L, m.update.tUs)
        assertEquals(listOf(HapticChannel(1, "pressure", .8, 0.0, false)), m.update.channels)
    }

    @Test
    fun whatIsNotUsableIsSkipped() {
        assertEquals(Message.Other, RemoteProtocol.parseLine("""{"type":"haptics","hand":"middle","channels":[]}"""))
        val m = RemoteProtocol.parseLine(
            """{"type":"haptics","hand":"left","t":5,"channels":[""" +
                """{"finger":5,"mode":"vibration","intensityPct":150,"frequencyDeciHz":25,"tap":true},""" +
                """{"finger":9,"mode":"pressure"},{"finger":true,"mode":"pressure"},""" +
                """{"finger":2,"mode":"squeeze"},{"finger":3,"mode":"pulse","tap":1},"junk"]}""",
        ) as Message.Haptics
        assertEquals(
            listOf(HapticChannel(5, "vibration", 1.0, 2.5, true), HapticChannel(3, "pulse", 0.0, 0.0, false)),
            m.update.channels,
        )
    }

    @Test
    fun recenterAndTheNewStatusFieldsDefaultSafely() {
        assertEquals("""{"type":"recenter"}""", RemoteProtocol.recenter())
        val old = (RemoteProtocol.parseLine("""{"type":"status","id":"q"}""") as Message.Status).status
        assertFalse(old.allowRecenter)
        assertFalse(old.haptics)
        assertEquals(0L, old.clockUs)
        val new = (RemoteProtocol.parseLine(
            """{"type":"status","allowRecenter":true,"haptics":true,"clockUs":1791966541289123}""",
        ) as Message.Status).status
        assertTrue(new.allowRecenter && new.haptics)
        assertEquals(1_791_966_541_289_123L, new.clockUs)
    }

    // -- one actuator ------------------------------------------------------------------------

    @Test
    fun anActuatorFillsAndEmptiesAsAirDoes() {
        val s = HapticsTimeline.Segment(10.0, 12.0, "pressure", .8, 0.0)
        assertEquals(0.0, HapticsTimeline.segmentLevel(s, 9.9), 0.0)
        assertEquals(.8 * (1 - exp(-1.0)), HapticsTimeline.segmentLevel(s, 10.09), 1e-6)
        val held = HapticsTimeline.segmentLevel(s, 12.0)
        assertEquals(held * exp(-1.0), HapticsTimeline.segmentLevel(s, 12.25), 1e-6)
        assertEquals(0.0, HapticsTimeline.segmentLevel(s, 20.0), 0.0)
    }

    // -- the timeline ------------------------------------------------------------------------

    @Test
    fun aPressReadsPressHoldRelease() {
        val tl = HapticsTimeline()
        tl.onHaptics(update("right", t0, HapticChannel(1, "pressure", 1.0)))
        tl.onHaptics(update("right", t0 + 2, HapticChannel(1, "off")))
        fun at(t: Double) = tl.state("right", (t * us).toLong(), 0.0)
        assertEquals(0, at(t0 + .1).word)
        assertTrue(at(t0 + .1).levels[1] > .5f)
        assertEquals(1, at(t0 + 1).word)
        assertEquals(2, at(t0 + 2.3).word)
        assertEquals(-1, at(t0 + 3).word)
        assertEquals(listOf("right"), tl.handsUsed())
    }

    @Test
    fun vibrationsReadPulseBuzzClick() {
        val tl = HapticsTimeline()
        tl.onHaptics(update("left", t0, HapticChannel(5, "pulse", .7, 2.0)))
        val pulse = tl.state("left", ((t0 + .5) * us).toLong(), 0.0)
        assertEquals(1, pulse.words)
        assertEquals(0, pulse.word)
        assertEquals(2f, pulse.vibrating[5], 0f)
        tl.onHaptics(update("left", t0 + 1, HapticChannel(5, "vibration", .7, 12.0)))
        assertEquals(1, tl.state("left", ((t0 + 1.5) * us).toLong(), 0.0).word)
        tl.onHaptics(update("left", t0 + 3, HapticChannel(2, "vibration", .7, 12.0, tap = true), HapticChannel(5, "off")))
        assertEquals(2, tl.state("left", ((t0 + 3.05) * us).toLong(), 0.0).word)
    }

    @Test
    fun aFrameIsTimedOnTheHeadsetsClockOrByWhenItArrived() {
        val tl = HapticsTimeline()
        tl.onStatus(status(clockS = t0), arrived = 100.0)
        assertEquals(t0 - 100.0, tl.offset()!!, 1e-6)
        assertEquals(t0, tl.frameTime((t0 * us).toLong(), 100.2), 1e-6)       // on the same clock
        assertEquals(t0 + .05, tl.frameTime(1 * us, 100.2), 1e-6)               // a different one
        tl.resetClock()
        assertEquals(null, tl.offset())
    }

    @Test
    fun withoutHapticsLinesTheGloveFollowsWhatItMeasures() {
        val tl = HapticsTimeline()
        tl.onStatus(status(haptics = false), arrived = 10.0)
        tl.onStatus(status(haptics = false, rightKpa = listOf(0, 400, 0, 0, 0, 0)), arrived = 10.2)
        assertFalse(tl.exact)
        val st = tl.state("right", 0, 10.2 + HapticsTimeline.VIDEO_LAG_S)
        assertEquals(40.0 / 45.0, st.levels[1].toDouble(), 1e-3)
        assertEquals(0, st.word)      // rising: PRESS.
    }
}
