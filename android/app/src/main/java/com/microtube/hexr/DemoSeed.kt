package com.microtube.hexr

/**
 * Canned state for screenshots: the Play Store's, and checking the screens on an emulator with
 * no glove to hand.
 *
 * It is reachable only from a debuggable build, and only when asked for by name on the launch
 * intent (-S restarts the app, which the demo is read at the start of):
 *
 *     adb shell am start -S -n com.microtube.hexr.tester.debug/com.microtube.hexr.MainActivity \
 *         --es demo driving
 *
 * The headsets scenario can also open one headset, by address, and watch it:
 *
 *     ... --es demo headsets --es host 10.0.2.2 --ez watch true
 *
 * There is no path to it from the UI and none at all from a release build: see the guard in
 * MainActivity.onCreate. It is data, not a mode: the numbers below are handed to the ordinary
 * [Glove] objects and the ordinary tick turns them into the ordinary snapshots, so what ends up
 * on screen is the real UI reading a real model.
 */
object DemoSeed {

    /** One glove's readings: the six channels in [Protocol.Finger] order, then the source. */
    class DemoGlove(
        val hand: String,
        val address: String,
        val battery: Double,
        val kpa: DoubleArray,
        val mtu: Int = 247,
        val connecting: Boolean = false,
    )

    /** A finished quick test. */
    class DemoQuickTest(val peaks: DoubleArray, val timeToPeak: DoubleArray, val source: Double)

    class Scenario(
        val gloves: List<DemoGlove> = emptyList(),
        /** Which screen to open on: "connect", "test", "quick" or "headsets". */
        val startTab: String = "test",
        val hand: String = LEFT,
        val channels: Set<Int> = setOf(Protocol.Finger.Index.channel),
        val settings: TestSettings = TestSettings(),
        val driving: Boolean = false,
        val found: List<Found> = emptyList(),
        val quickTest: DemoQuickTest? = null,
    )

    private const val LEFT_ADDRESS = "C4:19:D1:8A:23:07"
    private const val RIGHT_ADDRESS = "C4:19:D1:8A:24:1B"

    /** A kit sitting connected and idle: channels vented, tank charged. */
    private fun idle(hand: String, address: String, battery: Double, source: Double) =
        DemoGlove(hand, address, battery, doubleArrayOf(0.2, 0.1, 0.3, 0.1, 0.2, 0.1, source))

    /** Mid-drive, deliberately uneven: the glove and the bars exist to show the weak one. */
    private fun driving(hand: String, address: String, battery: Double) =
        DemoGlove(hand, address, battery, doubleArrayOf(33.6, 34.1, 33.9, 21.8, 33.2, 0.4, 46.9))

    val SCENARIOS: Map<String, Scenario> = mapOf(
        // Searching: two left kits heard, no right one yet.
        "search" to Scenario(
            found = listOf(
                Found(LEFT_ADDRESS, "HaptGloveAR Left", LEFT, -58),
                Found("C4:19:D1:8A:31:5C", "HaptGloveAR Left", LEFT, -71),
            ),
        ),
        "connecting" to Scenario(
            gloves = listOf(DemoGlove(LEFT, LEFT_ADDRESS, 0.86, DoubleArray(7), connecting = true)),
            found = listOf(Found(RIGHT_ADDRESS, "HaptGloveAR Right", RIGHT, -64)),
        ),
        "connect" to Scenario(
            startTab = "connect",
            gloves = listOf(idle(LEFT, LEFT_ADDRESS, 0.86, 47.2), idle(RIGHT, RIGHT_ADDRESS, 0.17, 46.4)),
        ),
        "driving" to Scenario(
            gloves = listOf(driving(LEFT, LEFT_ADDRESS, 0.86), idle(RIGHT, RIGHT_ADDRESS, 0.79, 46.4)),
            channels = setOf(0, 1, 2, 3, 4),
            settings = TestSettings(Mode.Pressure, intensity = .6),
            driving = true,
        ),
        "vibration" to Scenario(
            gloves = listOf(idle(LEFT, LEFT_ADDRESS, 0.86, 46.0)),
            channels = setOf(Protocol.Finger.Palm.channel, Protocol.Finger.Index.channel),
            settings = TestSettings(Mode.Vibration, intensity = .7, frequency = 2.0, peakRatio = .35),
            driving = true,
        ),
        "quick-pass" to Scenario(
            startTab = "quick",
            gloves = listOf(idle(LEFT, LEFT_ADDRESS, 0.86, 44.2)),
            quickTest = DemoQuickTest(
                doubleArrayOf(44.1, 43.6, 45.2, 42.8, 43.3, 44.9),
                doubleArrayOf(0.42, 0.38, 0.45, 0.51, 0.40, 0.36), 44.2,
            ),
        ),
        "quick-poor" to Scenario(
            startTab = "quick",
            gloves = listOf(idle(LEFT, LEFT_ADDRESS, 0.86, 44.0)),
            quickTest = DemoQuickTest(
                doubleArrayOf(44.1, 43.6, 45.2, 22.0, 30.1, 44.9),
                doubleArrayOf(0.42, 0.38, 0.45, 1.6, 1.2, 0.36), 44.0,
            ),
        ),
        // The shot that matters most, and the one healthy hardware cannot produce: a blocked
        // line next to good channels, with the source healthy enough to rule the pump out.
        "quick-fail" to Scenario(
            startTab = "quick",
            gloves = listOf(idle(LEFT, LEFT_ADDRESS, 0.86, 43.1)),
            quickTest = DemoQuickTest(
                doubleArrayOf(43.8, 42.1, 44.6, 0.4, 18.6, 43.9),
                doubleArrayOf(0.44, 0.39, 0.41, 0.0, 1.62, 0.37), 43.1,
            ),
        ),
        "quick-pump" to Scenario(
            startTab = "quick",
            gloves = listOf(idle(LEFT, LEFT_ADDRESS, 0.86, 3.6)),
            quickTest = DemoQuickTest(DoubleArray(6) { 0.3 }, DoubleArray(6), 3.6),
        ),
        "headsets" to Scenario(startTab = "headsets"),
    )

    /** The tab a scenario wants, or null if it is not a scenario we know. */
    fun startTabFor(name: String?): String? = SCENARIOS[name]?.startTab
}
