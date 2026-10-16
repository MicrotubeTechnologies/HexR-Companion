package com.microtube.hexr.remote

import com.microtube.hexr.glove.FINGERS
import com.microtube.hexr.glove.HandState
import com.microtube.hexr.glove.levelFromKpa
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.tanh

/**
 * What a headset's gloves are doing to the wearer's hands, moment by moment, for the glove panels
 * beside its view. A line-for-line port of the desktop's `hexr/haptics.py`, so the two light up
 * the same way. Two sources, the better one used when the headset has it:
 *
 * - Exact: a headset with HexR 0.10.2 or later sends a "haptics" line for every command, stamped
 *   on the clock its video frames are stamped with, so each touch lands on the frame showing it.
 * - Measured: every status carries each glove's measured pressure five times a second. Enough to
 *   show a press and a hold; too slow to show a vibration or a tap.
 *
 * Levels are worked out from the history for whatever moment is asked about. Times are passed in
 * (seconds, on one monotonic clock for "arrived"), never read here, so it is tested on the JVM.
 * Fed from the control link's thread, read from the UI's: everything is under one lock.
 */
class HapticsTimeline {

    class Segment(val t0: Double, var t1: Double?, val mode: String, val intensity: Double, val hz: Double)

    private val lock = Any()
    private val segments = HashMap<Pair<String, Int>, ArrayList<Segment>>()
    private val pressure = HashMap<String, ArrayDeque<Pair<Double, DoubleArray>>>()
    private val offsets = ArrayDeque<Double>()          // headset clock - ours, seconds
    private val used = HashSet<String>()

    @Volatile
    var exact = false
        private set

    // -- feeding ---------------------------------------------------------------------------

    /** A status: the clocks' offset, and the measured pressure for the fallback. */
    fun onStatus(status: HeadsetStatus, arrived: Double) = synchronized(lock) {
        if (status.haptics) exact = true
        if (status.clockUs != 0L) push(offsets, status.clockUs / 1e6 - arrived, MAX_OFFSETS)
        for (hand in HANDS) {
            val g = status.glove(hand)
            val kpa = if (g != null && g.connected && g.pressureDeciKPa.size >= FINGERS) {
                DoubleArray(FINGERS) { g.pressureDeciKPa[it] / 10.0 }
            } else {
                DoubleArray(FINGERS)
            }
            push(pressure.getOrPut(hand) { ArrayDeque() }, arrived to kpa, MAX_SAMPLES)
            if ((kpa.maxOrNull() ?: 0.0) > QUIET_KPA * 3) used += hand
        }
    }

    /** A haptics line from the headset. */
    fun onHaptics(update: HapticsUpdate) = synchronized(lock) {
        val t = update.tUs / 1e6
        exact = true
        for (c in update.channels) {
            val segs = segments.getOrPut(update.hand to c.finger) { ArrayList() }
            val last = segs.lastOrNull()
            if (last != null && last.t1 == null) last.t1 = max(last.t0, t)
            if (c.mode != "off") {
                segs += Segment(t, if (c.tap) t + TAP_S else null, c.mode, max(0.1, c.intensity), c.hz)
                used += update.hand
            }
            while (segs.isNotEmpty() && segs[0].t1.let { it != null && it < t - KEEP_S }) segs.removeAt(0)
        }
    }

    /** Forget the clock's offset: the headset may have restarted, and its clock with it. */
    fun resetClock() = synchronized(lock) { offsets.clear() }

    // -- reading ---------------------------------------------------------------------------

    fun handsUsed(): List<String> = synchronized(lock) { HANDS.filter { it in used } }

    /** Headset clock minus ours. The largest sample is the one that waited least on the way. */
    fun offset(): Double? = synchronized(lock) { offsets.maxOrNull() }

    /**
     * When a frame was made, on the headset's clock: its presentation time, if that is on the
     * headset's clock as it should be, or else when it arrived, less the video's usual lag.
     */
    fun frameTime(ptsUs: Long, arrived: Double): Double {
        val pts = ptsUs / 1e6
        val off = offset()
        if (off == null || kotlin.math.abs(pts - (arrived + off)) < SAME_CLOCK_S) return pts
        return arrived + off - VIDEO_LAG_S
    }

    /** The glove as the frame with this presentation time, which arrived then, shows it. */
    fun state(hand: String, ptsUs: Long, arrived: Double): HandState =
        if (exact) exactState(hand, frameTime(ptsUs, arrived)) else measuredState(hand, arrived - VIDEO_LAG_S)

    /** The glove as it is now, with no frame to go by: what a panel shows before the view. */
    fun stateNow(hand: String, now: Double): HandState {
        val off = offset()
        return if (exact && off != null) exactState(hand, now + off - VIDEO_LAG_S)
        else measuredState(hand, now - VIDEO_LAG_S)
    }

    private fun exactState(hand: String, t: Double): HandState = synchronized(lock) {
        val levels = FloatArray(FINGERS)
        val vibrating = FloatArray(FINGERS)
        val since = FloatArray(FINGERS)
        var active: Segment? = null
        var fading: Segment? = null
        for (f in 0 until FINGERS) {
            val segs = segments[hand to f] ?: continue
            for (s in segs.asReversed()) {
                val end = s.t1
                if (end != null && end < t - RELEASE_S * 8) break
                val level = segmentLevel(s, t).toFloat()
                if (level > levels[f]) {
                    levels[f] = level
                    val on = s.mode != "pressure" && t >= s.t0 && (end == null || t <= end)
                    vibrating[f] = if (on) s.hz.toFloat() else 0f
                    since[f] = (t - s.t0).toFloat()
                }
                if (s.t0 <= t && (end == null || t <= end)) {
                    if (active == null || s.t0 > active.t0) active = s
                } else if (end != null && t - end >= 0 && t - end < RELEASE_WORD_S) {
                    if (fading == null || end > (fading.t1 ?: 0.0)) fading = s
                }
            }
        }
        var words = 0
        var word = -1
        var hz = 0f
        val cur = active ?: fading
        if (cur != null) {
            if (cur.mode == "pressure") {
                word = if (cur !== active) 2 else if (t - cur.t0 < PRESS_S) 0 else 1
            } else {
                words = 1
                val short = cur.t1 != null && cur.t1!! - cur.t0 < 0.2
                word = if (short) 2 else if (cur.hz <= 3) 0 else 1
                hz = cur.hz.toFloat()
            }
        }
        HandState(levels.toList(), vibrating.toList(), since.toList(), words, word, hz)
    }

    private fun measuredState(hand: String, t: Double): HandState {
        val samples = synchronized(lock) { pressure[hand]?.toList() } ?: return HandState()
        if (samples.isEmpty()) return HandState()
        val now = pressureAt(samples, t)
        val before = pressureAt(samples, t - 0.25)
        val levels = now.map { levelFromKpa(it) }
        val total = levels.sum()
        val was = before.sumOf { levelFromKpa(it).toDouble() }.toFloat()
        var word = -1
        if (total > .15f || was > .15f) {
            word = when {
                total > was + .15f -> 0
                total < was - .15f -> 2
                total > .15f -> 1
                else -> 2
            }
        }
        return HandState(levels = levels, words = 0, word = word)
    }

    companion object {
        val HANDS = listOf("left", "right")
        const val ATTACK_S = 0.09
        const val RELEASE_S = 0.25
        const val TAP_S = 0.12
        const val PRESS_S = 0.3
        const val RELEASE_WORD_S = 0.7
        const val KEEP_S = 60.0
        const val VIDEO_LAG_S = 0.15
        const val SAME_CLOCK_S = 5.0
        const val QUIET_KPA = 2.0
        private const val MAX_SAMPLES = 600
        private const val MAX_OFFSETS = 40

        /** How full one actuator is drawn at `t`: fills while on, empties after, as air does. */
        fun segmentLevel(s: Segment, t: Double): Double {
            if (t < s.t0) return 0.0
            val end = s.t1 ?: t
            val filled = 1 - exp(-max(0.0, min(t, end) - s.t0) / ATTACK_S)
            var level = if (t <= end) filled else filled * exp(-(t - end) / RELEASE_S)
            level *= s.intensity
            if (s.mode != "pressure" && t <= end) {
                level *= if (s.hz <= 5) {
                    // Slow enough to see each pulse.
                    val phase = ((t - s.t0) * s.hz) % 1
                    0.2 + 0.8 * (0.5 + 0.5 * tanh(5 * cos(2 * PI * phase)))
                } else {
                    // Faster than the eye can follow: a steady glow with a shimmer; the rings say so.
                    0.86 + 0.14 * sin((t - s.t0) * 2 * PI * 7)
                }
            }
            return if (level > 0.003) level else 0.0
        }

        /** The measured pressure at `t`, between the two readings around it. */
        internal fun pressureAt(samples: List<Pair<Double, DoubleArray>>, t: Double): List<Double> {
            if (t <= samples[0].first) return samples[0].second.toList()
            for (i in 0 until samples.size - 1) {
                val (ta, a) = samples[i]
                val (tb, b) = samples[i + 1]
                if (t in ta..tb) {
                    val k = if (tb > ta) (t - ta) / (tb - ta) else 1.0
                    return a.indices.map { a[it] + (b[it] - a[it]) * k }
                }
            }
            return samples.last().second.toList()
        }

        private fun <E> push(q: ArrayDeque<E>, e: E, maxLen: Int) {
            q.addLast(e)
            while (q.size > maxLen) q.removeFirst()
        }
    }
}
