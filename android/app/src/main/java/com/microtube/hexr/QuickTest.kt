package com.microtube.hexr

import com.microtube.hexr.glove.Verdict
import java.util.Locale

/**
 * The canned QA sweep, ported from the desktop's `hexr/screens/quicktest.py`.
 *
 * The thresholds here must match the desktop's, or the same glove passes on one and fails on the
 * other. The answer comes first, in one line, the way the desktop gives it: All good, {n} poor,
 * {n} failed, or Pump failed.
 */
object QuickTest {
    const val SETTLE_MS = 600L      // vent and let the channels fall back
    const val DRIVE_MS = 2_000L     // how long each channel is held at full

    /**
     * Three words, because three is what a decision needs: the channel is doing its job, it is
     * doing some of it, or it is not doing it. Sensors on a dead channel float on noise rather
     * than reading a clean 0.0, which is why the failure line sits at 2 kPa and not at zero.
     */
    const val GOOD_KPA = 40.0
    const val FAIL_KPA = 2.0

    /**
     * If the source never develops pressure, every channel reads Fail for one reason, a dead
     * pump, and reporting six dead channels would send someone replacing the wrong parts.
     */
    const val SOURCE_MIN_KPA = 10.0

    /** Good / Poor / Fail, from the peak this channel reached. The source does not enter into it. */
    fun grade(peak: Double): Verdict = when {
        peak > GOOD_KPA -> Verdict.Good
        peak >= FAIL_KPA -> Verdict.Poor
        else -> Verdict.Fail
    }

    /** The same, as the word the table shows. */
    fun verdict(peak: Double): String = grade(peak).name

    fun judge(peaks: List<Double>, sourcePeak: Double): Judgement {
        val verdicts = peaks.map(::grade)
        val failed = verdicts.indices.filter { verdicts[it] == Verdict.Fail }
        val poor = verdicts.indices.filter { verdicts[it] == Verdict.Poor }
        return when {
            sourcePeak < SOURCE_MIN_KPA -> Judgement(verdicts, Outcome.PumpFailed, 0, emptyList())
            failed.isNotEmpty() -> Judgement(verdicts, Outcome.Failed, failed.size, (failed + poor).sorted())
            poor.isNotEmpty() -> Judgement(verdicts, Outcome.Poor, poor.size, poor)
            else -> Judgement(verdicts, Outcome.AllGood, 0, emptyList())
        }
    }

    /** The evidence behind the answer, in a sentence or two, for Details. */
    fun summary(j: Judgement, sourcePeak: Double): String {
        val good = j.verdicts.count { it == Verdict.Good }
        val poor = j.verdicts.count { it == Verdict.Poor }
        val failed = j.verdicts.count { it == Verdict.Fail }
        val kpa = String.format(Locale.US, "%.1f", sourcePeak)
        val breakdown = tr("{good} good, {poor} poor, {failed} failed", "good" to good, "poor" to poor, "failed" to failed)
        return when (j.outcome) {
            Outcome.PumpFailed -> tr(
                "The source never rose above {kpa} kPa, so no channel could have reached " +
                    "pressure. This is one fault in the pump or its supply, not six failed channels.",
                "kpa" to kpa,
            )
            Outcome.Failed -> tr(
                "The source reached {kpa} kPa, so supply is fine: a channel reading nothing with a " +
                    "healthy source is a blocked line, a valve that never opened, or a dead indenter.",
                "kpa" to kpa,
            ) + " " + breakdown + "."
            Outcome.Poor -> tr(
                "The source reached {kpa} kPa. Every channel moved, but not all of them reached " +
                    "full pressure: check the tubing on the weak ones.",
                "kpa" to kpa,
            ) + " " + breakdown + "."
            Outcome.AllGood -> tr("The source reached {kpa} kPa.", "kpa" to kpa)
        }
    }
}

enum class Outcome { AllGood, Poor, Failed, PumpFailed }

data class Judgement(
    val verdicts: List<Verdict>,
    val outcome: Outcome,
    val count: Int,
    /** The fingers to look at, if the pump is not the reason. */
    val weak: List<Int>,
) {
    val headline: String
        get() = when (outcome) {
            Outcome.AllGood -> tr("All good")
            Outcome.Poor -> tr("{n} poor", "n" to count)
            Outcome.Failed -> tr("{n} failed", "n" to count)
            Outcome.PumpFailed -> tr("Pump failed")
        }

    /** The colour the answer is said in. */
    val verdict: Verdict
        get() = when (outcome) {
            Outcome.AllGood -> Verdict.Good
            Outcome.Poor -> Verdict.Poor
            else -> Verdict.Fail
        }
}
