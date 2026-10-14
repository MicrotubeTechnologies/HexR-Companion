package com.microtube.hexr

/**
 * Canned state for the Play Store screenshots.
 *
 * Every screen in this app is a view onto a glove, so on a machine with no
 * glove — an emulator, or any phone without the hardware to hand — there is
 * nothing to photograph: an empty scan list, dashes for every pressure, no
 * verdicts. These scenarios stand in for the hardware long enough to take a
 * picture.
 *
 * It is reachable only from a debuggable build, and only when asked for by
 * name on the launch intent:
 *
 *     adb shell am start -n com.microtube.hexr.tester.debug/com.microtube.hexr.MainActivity \
 *         --es demo driving
 *
 * There is no path to it from the UI and none at all from a release build —
 * see the guard in MainActivity.onCreate. It is data, not a mode: the numbers
 * below are handed to the ordinary [Glove] objects and the ordinary tick turns
 * them into the ordinary snapshots, so what ends up on screen is the real UI
 * reading a real model. Nothing is drawn specially for the store.
 *
 * The values are plausible readings from a healthy kit, chosen to match the
 * verdict bands in [QuickTest]. They are fixed rather than jittered so a
 * screenshot can be retaken and come out the same.
 */
object DemoSeed {

    /**
     * One glove's readings. `kpa` is seven long: the six channels in
     * [Protocol.Finger] order, then the source on index 6. These go into
     * `pressureRaw` as gauge kPa, which is what [Protocol.rawToKpa] passes
     * through unchanged.
     */
    class DemoGlove(
        val hand: String,
        val address: String,
        val battery: Double,
        val kpa: DoubleArray,
        val mtu: Int = 247,
    )

    /** A finished quick test, as [HexrViewModel.finishQuickTest] would leave it. */
    class DemoQuickTest(
        val peaks: DoubleArray,
        val timeToPeak: DoubleArray,
        val status: String,
        val statusTone: Tone,
        val summary: String,
        val summaryTone: Tone,
    )

    class Scenario(
        val gloves: List<DemoGlove>,
        /**
         * Which screen to open on: "connect", "test" or "quick". They name the tabs this
         * app had before connecting and the quick test became panels on the Test tab, and
         * MainActivity opens the panel each one became.
         *
         * Carried here rather than left to the capture script tapping its way
         * across the bottom bar. Tap coordinates are a function of the screen
         * size, the density and the layout, and all three are things a future
         * change is allowed to move without anyone thinking about screenshots.
         */
        val startTab: String = "connect",
        val hand: String = LEFT,
        val channels: Set<Int> = setOf(Protocol.Finger.Index.channel),
        val intensity: Int = 60,
        val frequency: Int = 0,
        val driving: Boolean = false,
        val quickTest: DemoQuickTest? = null,
    )

    private const val LEFT_ADDRESS = "C4:19:D1:8A:23:07"
    private const val RIGHT_ADDRESS = "C4:19:D1:8A:24:1B"

    /** A kit sitting connected and idle: channels vented, tank charged. */
    private fun idle(hand: String, address: String, battery: Double, source: Double) =
        DemoGlove(hand, address, battery,
            doubleArrayOf(0.2, 0.1, 0.3, 0.1, 0.2, 0.1, source))

    /**
     * The same glove mid-drive, all six channels inflated.
     *
     * Deliberately uneven. The diagram ramps each channel's fill with its own
     * pressure, and six identical numbers would hide the one thing that view
     * exists to show.
     */
    private fun driving(hand: String, address: String, battery: Double) =
        DemoGlove(hand, address, battery,
            doubleArrayOf(44.1, 41.3, 46.8, 38.2, 22.4, 45.6, 47.2))

    val SCENARIOS: Map<String, Scenario> = mapOf(
        "connect" to Scenario(
            gloves = listOf(
                idle(LEFT, LEFT_ADDRESS, 0.86, 47.2),
                idle(RIGHT, RIGHT_ADDRESS, 0.79, 46.4),
            ),
        ),

        "driving" to Scenario(
            startTab = "test",
            gloves = listOf(
                driving(LEFT, LEFT_ADDRESS, 0.86),
                idle(RIGHT, RIGHT_ADDRESS, 0.79, 46.4),
            ),
            channels = Protocol.ALL_FINGERS.map { it.channel }.toSet(),
            intensity = 60,
            frequency = 6,
            driving = true,
        ),

        "quick-pass" to Scenario(
            startTab = "quick",
            gloves = listOf(idle(LEFT, LEFT_ADDRESS, 0.86, 44.2)),
            quickTest = DemoQuickTest(
                peaks = doubleArrayOf(44.1, 43.6, 45.2, 42.8, 43.3, 44.9),
                timeToPeak = doubleArrayOf(0.42, 0.38, 0.45, 0.51, 0.40, 0.36),
                status = "All 6 channels good",
                statusTone = Tone.Success,
                summary = "Source reached 44.2 kPa.",
                summaryTone = Tone.Muted,
            ),
        ),

        // The shot that matters most, and the one healthy hardware cannot
        // produce: a blocked line next to five good channels, with the source
        // healthy enough to rule the pump out.
        "quick-fail" to Scenario(
            startTab = "quick",
            gloves = listOf(idle(LEFT, LEFT_ADDRESS, 0.86, 43.1)),
            quickTest = DemoQuickTest(
                peaks = doubleArrayOf(43.8, 42.1, 44.6, 0.4, 18.6, 43.9),
                timeToPeak = doubleArrayOf(0.44, 0.39, 0.41, 0.0, 1.62, 0.37),
                status = "1 of 6 channels failed",
                statusTone = Tone.Danger,
                summary = "Source reached 43.1 kPa, so supply is fine — a channel reading " +
                    "nothing with a healthy source is a blocked line, a valve that never " +
                    "opened, or a dead indenter. 4 good, 1 poor, 1 failed.",
                summaryTone = Tone.Danger,
            ),
        ),
    )

    /** The tab a scenario wants, or null if it is not a scenario we know. */
    fun startTabFor(name: String?): String? = SCENARIOS[name]?.startTab
}
