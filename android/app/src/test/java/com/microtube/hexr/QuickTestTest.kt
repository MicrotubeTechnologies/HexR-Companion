package com.microtube.hexr

import com.microtube.hexr.glove.Verdict
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** The quick test's answer, against the desktop's thresholds and wording (quicktest.py). */
class QuickTestTest {

    @After
    fun english() {
        I18n.language = I18n.EN
    }

    @Test
    fun verdicts_sitOnTheDesktopsLines() {
        assertEquals(Verdict.Good, QuickTest.grade(40.01))
        assertEquals(Verdict.Poor, QuickTest.grade(40.0))
        assertEquals(Verdict.Poor, QuickTest.grade(2.0))
        assertEquals(Verdict.Fail, QuickTest.grade(1.99))
    }

    @Test
    fun aDeadPumpIsOneAnswerNotSixFailures() {
        val j = QuickTest.judge(List(6) { 0.3 }, sourcePeak = 3.0)
        assertEquals(Outcome.PumpFailed, j.outcome)
        assertEquals("Pump failed", j.headline)
        assertTrue(j.weak.isEmpty())
        assertEquals(Verdict.Fail, j.verdict)
    }

    @Test
    fun failedComesBeforePoorAndNamesBoth() {
        val j = QuickTest.judge(listOf(45.0, 45.0, 45.0, 20.0, 30.0, 0.5), sourcePeak = 50.0)
        assertEquals(Outcome.Failed, j.outcome)
        assertEquals("1 failed", j.headline)
        assertEquals(listOf(3, 4, 5), j.weak)
    }

    @Test
    fun poorAndAllGood() {
        val poor = QuickTest.judge(listOf(45.0, 45.0, 45.0, 20.0, 30.0, 45.0), sourcePeak = 50.0)
        assertEquals("2 poor", poor.headline)
        assertEquals(listOf(3, 4), poor.weak)
        assertEquals(Verdict.Poor, poor.verdict)
        val good = QuickTest.judge(List(6) { 46.0 }, sourcePeak = 50.0)
        assertEquals(Outcome.AllGood, good.outcome)
        assertEquals("All good", good.headline)
        assertEquals("The source reached 50.0 kPa.", QuickTest.summary(good, 50.0))
    }

    @Test
    fun theAnswerIsInChineseToo() {
        I18n.language = I18n.ZH_CN
        val poor = QuickTest.judge(listOf(45.0, 45.0, 45.0, 20.0, 30.0, 45.0), sourcePeak = 50.0)
        assertEquals("2 个偏弱", poor.headline)
    }
}
