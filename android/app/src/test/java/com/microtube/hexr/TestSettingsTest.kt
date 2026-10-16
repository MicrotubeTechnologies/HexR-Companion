package com.microtube.hexr

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** What the Test tab sends, and what it says it is set to. */
class TestSettingsTest {

    private val two = listOf(Protocol.Finger.Thumb, Protocol.Finger.Index)

    @Test
    fun aFingerIsSetToTheIntensitysPressure_andABuzzToNone() {
        assertEquals(34.44, TestSettings(intensity = .6).targetKpa()!!, .01)
        assertEquals(34.44, TestSettings(Mode.Vibration, .6, frequency = 4.9).targetKpa()!!, .01)
        assertNull(TestSettings(Mode.Vibration, .6, frequency = 5.0).targetKpa())
    }

    @Test
    fun labelsSayThePercentAndTheKpa() {
        assertEquals("60% · 34 kPa", TestSettings(intensity = .6).intensityLabel())
        assertEquals("10% · 15 kPa", TestSettings(intensity = .1).intensityLabel())
        assertEquals("100% · 50 kPa", TestSettings(intensity = 1.0).intensityLabel())
        assertEquals("10.0 Hz", TestSettings(frequency = 10.0).frequencyLabel())
        assertTrue(TestSettings(frequency = 4.9).pulse)
        assertTrue(!TestSettings(frequency = 5.0).pulse)
    }

    @Test
    fun framesAreTheProtocolsOwn() {
        val p = TestSettings(Mode.Pressure, .6, speed = .4)
        assertArrayEquals(
            Protocol.batch(two.map { Protocol.pressure(it, true, .6, .4) }), p.frames(two, true),
        )
        val v = TestSettings(Mode.Vibration, .7, frequency = 12.0, peakRatio = .3)
        assertArrayEquals(
            Protocol.batch(two.map { Protocol.vibration(it, false, 12.0, .7, .3) }), v.frames(two, false),
        )
    }

    @Test
    fun theFrequencySliderIsLogarithmicEndToEnd() {
        assertEquals(0.1, TestSettings.sliderToHz(0f), 1e-9)
        assertEquals(40.0, TestSettings.sliderToHz(1f), 1e-9)
        assertEquals(0f, TestSettings.hzToSlider(0.1), 1e-6f)
        assertEquals(1f, TestSettings.hzToSlider(40.0), 1e-6f)
        var last = 0.0
        for (i in 0..100) {
            val hz = TestSettings.sliderToHz(i / 100f)
            assertTrue(hz >= last)
            last = hz
        }
        // The pulses get most of the travel.
        assertTrue(TestSettings.hzToSlider(5.0) > .6f)
    }
}
