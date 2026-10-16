package com.microtube.hexr.glove

import kotlin.math.exp
import kotlin.math.max
import kotlin.math.min

const val FINGERS = 6

/**
 * One glove at one moment, ready to draw: how lit each touch point is, which are vibrating and
 * since when, and which caption word is lit. The same as the desktop's `HandState`
 * (`hexr/haptics.py`). `tints` colours a touch point instead of white-hot: a verdict, or green
 * for "connected". Colours are ARGB ints, so this stays pure.
 */
data class HandState(
    val levels: List<Float> = List(FINGERS) { 0f },
    val vibrating: List<Float> = List(FINGERS) { 0f },      // Hz while vibrating
    val since: List<Float> = List(FINGERS) { 0f },          // s since it started
    val words: Int = 0,                                     // 0 press/hold/release, 1 pulse/buzz/click
    val word: Int = -1,                                     // the word lit, -1 none
    val hz: Float = 0f,
    val tints: List<Int?>? = null,
)

object HandLook {
    const val QUIET_KPA = 2.0       // below this a channel reads as off
    const val FULL_KPA = 45.0       // measured pressure drawn as fully lit
    const val PRESS_S = 0.3f        // how long PRESS. stays lit before HOLD.
    const val RELEASE_WORD_S = 0.7f // and RELEASE. after a release
    const val ATTACK_S = 0.09f      // how fast a lit point fills
    const val RELEASE_S = 0.25f     // and empties

    const val GREEN = 0xFF3ECF8E.toInt()
    const val AMBER = 0xFFE8B04B.toInt()
    const val RED = 0xFFE5484D.toInt()
}

/** Measured pressure as how lit a touch point is drawn: full at [HandLook.FULL_KPA]. */
fun levelFromKpa(kpa: Double): Float =
    if (kpa < HandLook.QUIET_KPA) 0f else min(1.0, kpa / HandLook.FULL_KPA).toFloat()

/**
 * The Test screen's glove: what the glove measures, when it streams; otherwise what it was told
 * to do while something is triggered. The caption follows the trigger: PRESS. then HOLD., and
 * RELEASE. for a moment after; PULSE. or BUZZ. while vibrating. (`gloveview.pad_state`.)
 */
fun padState(
    kpa: List<Double>?, on: Boolean, sincePress: Float, sinceRelease: Float?,
    vibration: Boolean, intensity: Float, hz: Float, channels: Set<Int>,
): HandState {
    val levels = when {
        kpa != null -> kpa.take(FINGERS).map(::levelFromKpa)
        on -> List(FINGERS) { if (it in channels) intensity else 0f }
        else -> List(FINGERS) { 0f }
    }
    return when {
        on && vibration -> HandState(
            levels = levels,
            vibrating = List(FINGERS) { if (it in channels) hz else 0f },
            since = List(FINGERS) { sincePress },
            words = 1, word = if (hz <= 3) 0 else 1, hz = hz,
        )
        on -> HandState(levels = levels, word = if (sincePress < HandLook.PRESS_S) 0 else 1)
        !vibration && sinceRelease != null && sinceRelease < HandLook.RELEASE_WORD_S ->
            HandState(levels = levels, word = 2)
        else -> HandState(levels = levels)
    }
}

/**
 * The Connect screen's glove: lit green to say it is here; a fingertip pressing on something
 * glows white-hot instead. Nothing when it is not connected.
 */
fun connectState(connected: Boolean, kpa: List<Double>?): HandState {
    if (!connected) return HandState()
    val k = kpa?.take(FINGERS)?.map(::levelFromKpa) ?: List(FINGERS) { 0f }
    return HandState(
        levels = k.map { max(.32f, it) },
        tints = k.map { if (it > .32f) null else HandLook.GREEN },
    )
}

enum class Verdict { Good, Poor, Fail }

/** A verdict on the glove: its colour and how brightly. A dead pump shows every point failed. */
fun verdictState(verdicts: List<Verdict>, pumpFailed: Boolean): HandState {
    val looks = (if (pumpFailed) List(FINGERS) { Verdict.Fail } else verdicts).map {
        when (it) {
            Verdict.Good -> HandLook.GREEN to 1f
            Verdict.Poor -> HandLook.AMBER to .75f
            Verdict.Fail -> HandLook.RED to .6f
        }
    }
    return HandState(levels = looks.map { it.second }, tints = looks.map { it.first })
}

/**
 * One step of easing a shown level towards where it should be, so a glow fed at 10 Hz by
 * telemetry rises and falls smoothly at 60: as fast as air fills, slower as it empties.
 */
fun ease(shown: Float, target: Float, dtS: Float): Float {
    if (dtS <= 0f) return shown
    val tau = if (target > shown) HandLook.ATTACK_S else HandLook.RELEASE_S
    val k = 1f - exp(-dtS / tau)
    val next = shown + (target - shown) * k
    return if (kotlin.math.abs(next - target) < .002f) target else next
}
