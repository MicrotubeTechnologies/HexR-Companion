package com.microtube.hexr

import java.util.Locale
import kotlin.math.ln
import kotlin.math.pow
import kotlin.math.roundToInt

enum class Mode { Pressure, Vibration }

/**
 * How the Test tab drives a glove, as the desktop's Test screen does: a steady pressure or a
 * vibration, how hard (10-100 %, which the glove takes as 15-50 kPa), and how fast. Ramp speed
 * is pressure's fine-tune and peak ratio vibration's. Nothing here sends anything: Trigger does.
 */
data class TestSettings(
    val mode: Mode = Mode.Pressure,
    val intensity: Double = .6,         // 0.1-1.0
    val frequency: Double = 10.0,       // 0.1-40 Hz, vibration only
    val speed: Double = 1.0,            // 0.1-1.0, pressure only
    val peakRatio: Double = .5,         // 0.2-0.8, vibration only
) {
    /** The frames that start (`on`) or stop these fingers as set. */
    fun frames(fingers: List<Protocol.Finger>, on: Boolean): ByteArray = Protocol.batch(
        fingers.map { f ->
            if (mode == Mode.Vibration) Protocol.vibration(f, on, frequency, intensity, peakRatio)
            else Protocol.pressure(f, on, intensity, speed)
        },
    )

    /** Below this the glove vibrates by pulsing the air; at and above it, by driving the motor. */
    val pulse get() = frequency < Protocol.PWM_VIBRATION_HZ

    /**
     * Where a picked finger is set to go, in kPa: the intensity's pressure, or the pressure a
     * pulse swings to. A buzz drives the motor rather than a pressure, so it has none.
     */
    fun targetKpa(): Double? =
        if (mode == Mode.Pressure || pulse) Protocol.intensityToKpa(intensity) else null

    fun intensityLabel(): String =
        "${(intensity * 100).roundToInt()}% · ${Protocol.intensityToKpa(intensity).roundToInt()} kPa"

    fun frequencyLabel(): String = String.format(Locale.US, "%.1f Hz", frequency)

    fun percent(v: Double) = "${(v * 100).roundToInt()}%"

    companion object {
        const val MIN_HZ = 0.1
        const val MAX_HZ = 40.0

        /**
         * A frequency slider on a log scale: the 0.1-5 Hz pulses, where every step feels
         * different, get most of the travel, and the buzzes above share the rest.
         */
        fun hzToSlider(hz: Double): Float =
            (ln(hz.coerceIn(MIN_HZ, MAX_HZ) / MIN_HZ) / ln(MAX_HZ / MIN_HZ)).toFloat()

        fun sliderToHz(t: Float): Double {
            val hz = MIN_HZ * (MAX_HZ / MIN_HZ).pow(t.toDouble().coerceIn(0.0, 1.0))
            return ((hz * 10).roundToInt() / 10.0).coerceIn(MIN_HZ, MAX_HZ)
        }
    }
}
