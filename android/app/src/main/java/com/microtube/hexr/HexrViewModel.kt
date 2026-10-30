package com.microtube.hexr

import android.app.Application
import android.os.SystemClock
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** How often the UI samples the model. Telemetry arrives far faster; see [Glove]. */
private const val TICK_MS = 100L

private fun other(hand: String) = if (hand == LEFT) RIGHT else LEFT

/** Severity of a status line, mapped to a colour by the UI. */
enum class Tone { Muted, Accent, Success, Danger }

/** An immutable read of one glove, refreshed on the UI tick. */
data class GloveSnapshot(
    val hand: String,
    val address: String,
    val name: String,
    val connected: Boolean,
    val connecting: Boolean,
    val status: String,
    val live: Boolean,
    val battery: String,
    /** 0.0-1.0, or null before the glove has said. */
    val batteryFraction: Double?,
    val kpa: List<Double>,
    val source: Double,
    val absolutePa: Boolean,
    val mtu: Int?,
) {
    /** A connect that ended without a connection. */
    val failed get() = !connected && !connecting && status.startsWith("Error")
}

/** A quick test that is still driving every channel. */
val QT_RUNNING = setOf("settle", "drive")

class HexrViewModel(app: Application) : AndroidViewModel(app) {

    val state = AppState()
    val engine = BleEngine(app, state) { /* snapshots refresh on the tick */ }

    // -- observable UI state -------------------------------------------------

    var gloves by mutableStateOf<Map<String, GloveSnapshot>>(emptyMap())
        private set

    var permissionsGranted by mutableStateOf(engine.hasPermissions())

    /** Whether the phone's Bluetooth radio is on. Polled; the user can flip it. */
    var bluetoothOn by mutableStateOf(engine.bluetoothEnabled())
        private set

    /**
     * True once Android will no longer show the permission dialog. The app cannot prompt again
     * from here, so the gate has to send people to Settings instead.
     */
    var mustUseSettings by mutableStateOf(false)

    // -- the search ----------------------------------------------------------

    /**
     * The gloves heard lately, by address. The Connect screen searches by itself while it is
     * on screen, as the desktop's does: a search, a short pause, another; paused while a glove
     * connects; and a glove not heard for 20 s is forgotten.
     */
    val seen = mutableStateMapOf<String, Seen>()

    var scanning by mutableStateOf(false)
        private set

    /** Why the last search could not run, or null. */
    var scanError by mutableStateOf<String?>(null)
        private set

    private var connectVisible = false
    private var foreground = true
    private var nextScanAt = 0L
    private var demo = false

    // -- the Test tab --------------------------------------------------------

    var channels by mutableStateOf(setOf(Protocol.Finger.Index.channel))

    /** How the Test tab drives: mode, intensity, frequency, ramp speed, peak ratio. */
    var settings by mutableStateOf(TestSettings())
        private set

    /** Which glove the Test tab drives. One at a time, as the phone shows one. */
    var hand by mutableStateOf(LEFT)

    /** Something triggered and not released since. */
    var driving by mutableStateOf(false)
        private set
    var pressedAt by mutableStateOf(0L)
        private set
    var releasedAt by mutableStateOf<Long?>(null)
        private set
    private var onChannels: Set<Int> = emptySet()

    // -- the quick test ------------------------------------------------------

    var qtHand by mutableStateOf<String?>(null)
    var qtPhase by mutableStateOf("idle")           // idle | settle | drive | done
        private set
    var qtProgress by mutableStateOf(0f)
        private set
    /** A line while it runs, or why it could not: Venting…, Glove disconnected. */
    var qtStatus by mutableStateOf("")
        private set
    var qtResult by mutableStateOf<Judgement?>(null)
        private set
    var qtPeaks by mutableStateOf(List(6) { 0.0 })
        private set
    var qtTimes by mutableStateOf(List(6) { 0.0 })
        private set
    var qtSource by mutableStateOf(0.0)
        private set

    private var qtT0 = 0L
    private val peak = DoubleArray(6)
    private val timeToPeak = DoubleArray(6)
    private var sourcePeak = 0.0

    init {
        viewModelScope.launch {
            while (true) {
                tick()
                delay(TICK_MS)
            }
        }
    }

    // -- tick ----------------------------------------------------------------

    private fun tick() {
        val now = SystemClock.elapsedRealtime()

        // Re-read the grant until it lands: a permission dialog pauses the activity without
        // stopping it, so onStart does not fire on the way back.
        if (!permissionsGranted && engine.hasPermissions()) permissionsGranted = true
        if (!demo) bluetoothOn = engine.bluetoothEnabled()
        if (scanning != engine.scanning) scanning = engine.scanning

        gloves = HANDS.mapNotNull { hand ->
            val g = state.get(hand) ?: return@mapNotNull null
            hand to GloveSnapshot(
                hand = g.hand,
                address = g.address,
                name = g.name,
                connected = g.connected,
                connecting = g.connecting,
                status = g.status,
                live = g.isLive(now),
                battery = g.batteryLabel(),
                batteryFraction = g.battery,
                kpa = g.channelKpa(),
                source = g.sourceKpa(),
                absolutePa = g.absolutePa == true,
                mtu = g.mtu,
            )
        }.toMap()

        // A glove that goes away mid-drive clears the flag, or Trigger keeps claiming to drive
        // something that is no longer there.
        if (driving && !handConnected()) driving = false
        if (!handConnected() && handConnected(other(hand))) hand = other(hand)

        val chosen = qtHand
        if (chosen != null && gloves[chosen]?.connected != true) qtHand = null
        if (qtHand == null) qtHand = gloves.values.firstOrNull { it.connected }?.hand

        search(now)
        tickQuickTest(now)
    }

    // -- the search ------------------------------------------------------------

    /** The Connect screen is on screen (as the Test tab or the Gloves panel), or no longer. */
    fun setConnectVisible(on: Boolean) {
        connectVisible = on
        if (!on && engine.scanning) engine.stopScan()
    }

    fun setForeground(on: Boolean) {
        foreground = on
    }

    /** After Bluetooth said no: try again now. */
    fun retryScan() {
        scanError = null
        nextScanAt = 0L
    }

    private fun search(now: Long) {
        GloveSearch.prune(seen, now)
        // Searching goes on with both hands connected too, less often, so the list of gloves found
        // shows the next ones to test.
        val wanted = permissionsGranted && bluetoothOn && connectVisible && foreground && !demo &&
            HANDS.none { gloves[it]?.connecting == true }
        if (!wanted) {
            if (engine.scanning) engine.stopScan()
            return
        }
        if (engine.scanning || now < nextScanAt || now < engine.scanAllowedAt()) return
        scanning = true
        engine.scan(
            onResult = { f -> viewModelScope.launch { seen[f.address] = Seen(f, SystemClock.elapsedRealtime()) } },
            onDone = { error ->
                viewModelScope.launch {
                    scanError = error
                    nextScanAt = SystemClock.elapsedRealtime() + when {
                        error != null -> GloveSearch.RETRY_MS
                        HANDS.all { gloves[it]?.connected == true } -> GloveSearch.FULL_RESCAN_MS
                        else -> GloveSearch.RESCAN_MS
                    }
                }
            },
        )
    }

    /** One hand's gloves heard lately, strongest first. */
    fun candidates(hand: String): List<Found> = GloveSearch.candidates(seen.values, hand)

    fun connect(f: Found) {
        if (engine.scanning) engine.stopScan()
        engine.connect(f.hand, f.address, f.name, f.rssi)
    }

    fun disconnect(hand: String) = engine.disconnect(hand)

    /** Every glove heard lately, either hand, strongest first: the list to test from. */
    fun allFound(): List<Found> = seen.values.map { it.found }.sortedByDescending { it.rssi ?: Int.MIN_VALUE }

    /** A glove its hand is letting go of another for, until it can connect. */
    var swapping by mutableStateOf<String?>(null)
        private set

    /** Test this glove: its hand lets go of the glove it has, then takes this one. */
    fun test(f: Found) {
        val g = gloves[f.hand]
        if (g == null || (!g.connected && !g.connecting)) {
            connect(f)
            return
        }
        disconnect(f.hand)
        swapping = f.address
        viewModelScope.launch {
            val until = SystemClock.elapsedRealtime() + 6_000L
            while (SystemClock.elapsedRealtime() < until && gloves[f.hand]?.let { it.connected || it.connecting } == true) {
                kotlinx.coroutines.delay(200)
            }
            swapping = null
            connect(f)
        }
    }

    // -- the Test tab ------------------------------------------------------------

    fun activeFingers(): List<Protocol.Finger> = channels.sorted().map { Protocol.Finger.of(it) }

    fun toggleChannel(channel: Int) {
        channels = if (channel in channels) channels - channel else channels + channel
    }

    fun selectAll() {
        channels = Protocol.ALL_FINGERS.map { it.channel }.toSet()
    }

    fun selectNone() {
        channels = emptySet()
    }

    fun pickHand(which: String) {
        if (which == hand) return
        // Never leave the hand you are walking away from inflated.
        if (driving) release()
        hand = which
    }

    /** Pressure or vibration. What is on was set for the other, so it is let go first. */
    fun pickMode(mode: Mode) {
        if (mode == settings.mode) return
        if (driving) release()
        settings = settings.copy(mode = mode)
    }

    // The sliders only change what Trigger will send. Sending on every step of a drag would
    // queue seconds of writes behind a 100 ms gap, with a Release all waiting at the back.
    fun setIntensity(v: Double) { settings = settings.copy(intensity = v.coerceIn(.1, 1.0)) }
    fun setFrequency(hz: Double) { settings = settings.copy(frequency = hz.coerceIn(TestSettings.MIN_HZ, TestSettings.MAX_HZ)) }
    fun setSpeed(v: Double) { settings = settings.copy(speed = v.coerceIn(.1, 1.0)) }
    fun setPeakRatio(v: Double) { settings = settings.copy(peakRatio = v.coerceIn(.2, .8)) }

    fun handConnected(which: String = hand): Boolean = gloves[which]?.connected == true

    fun canDrive(): Boolean = channels.isNotEmpty() && handConnected()

    /**
     * Fire the picked fingers as set, and leave them on. Pressing again sends what is set now;
     * a finger dropped since it was triggered is let go.
     */
    fun trigger() {
        if (!canDrive()) return
        val dropped = (onChannels - channels).sorted().map { Protocol.Finger.of(it) }
        val data = settings.frames(dropped, false) + settings.frames(activeFingers(), true)
        engine.send(hand, data)
        driving = true
        pressedAt = SystemClock.elapsedRealtime()
        releasedAt = null
        onChannels = channels
    }

    /**
     * Stop output, whatever is picked: every channel, every glove. A finger dropped mid-drive
     * is still inflated, and a targeted release would leave it that way.
     */
    fun release() {
        if (driving) releasedAt = SystemClock.elapsedRealtime()
        driving = false
        onChannels = emptySet()
        engine.sendAllOff()
    }

    /** Vent everything, everywhere, and stop a quick test that is running. */
    fun allOff() {
        if (qtPhase in QT_RUNNING) abortQuickTest(tr("Stopped"))
        release()
    }

    /**
     * Vent on the way to the background. A phone gets pocketed mid-test in a way a desktop
     * window does not, and a channel left inflated presses on someone's hand until the
     * battery dies.
     */
    fun onBackground() {
        foreground = false
        if (qtPhase in QT_RUNNING) abortQuickTest(tr("Stopped"))
        release()
        if (engine.scanning) engine.stopScan()
    }

    override fun onCleared() {
        engine.shutdown()
        super.onCleared()
    }

    // -- the quick test ------------------------------------------------------------

    fun toggleQuickTest() {
        if (qtPhase in QT_RUNNING) abortQuickTest(tr("Stopped")) else startQuickTest()
    }

    private fun startQuickTest() {
        val hand = qtHand
        val snap = hand?.let { gloves[it] }
        if (snap == null || !snap.connected) {
            qtStatus = tr("Connect a glove first")
            return
        }
        if (!snap.live) {
            qtStatus = tr("No readings from this glove")
            return
        }
        if (driving) release()
        peak.fill(0.0)
        timeToPeak.fill(0.0)
        sourcePeak = 0.0
        qtResult = null
        engine.send(hand, Protocol.allOff())
        qtPhase = "settle"
        qtT0 = SystemClock.elapsedRealtime()
        qtProgress = 0f
        qtStatus = tr("Venting…")
    }

    private fun abortQuickTest(why: String) {
        qtPhase = "idle"
        qtHand?.let { engine.sendAllOff(it) }
        qtProgress = 0f
        qtStatus = why
    }

    /** A different glove: what was measured on the last one no longer applies. */
    fun pickQuickTestHand(which: String) {
        if (qtPhase in QT_RUNNING || which == qtHand) return
        qtHand = which
        qtPhase = "idle"
        qtResult = null
        qtStatus = ""
        qtProgress = 0f
    }

    private fun tickQuickTest(now: Long) {
        if (qtPhase !in QT_RUNNING) return
        val hand = qtHand
        val snap = hand?.let { gloves[it] }
        if (hand == null || snap == null || !snap.connected) {
            abortQuickTest(tr("Glove disconnected"))
            return
        }
        val elapsed = (now - qtT0) / 1000.0

        if (qtPhase == "settle") {
            qtProgress = (elapsed / (QuickTest.SETTLE_MS / 1000.0)).coerceAtMost(1.0).toFloat() * .2f
            if (elapsed >= QuickTest.SETTLE_MS / 1000.0) {
                // Everything at once, exactly as the desktop test does: it also exercises whether
                // the pump can keep up with six channels.
                engine.send(hand, Protocol.batch(Protocol.ALL_FINGERS.map { Protocol.pressure(it, true, 1.0, 1.0) }))
                qtPhase = "drive"
                qtT0 = now
                qtStatus = tr("Driving all channels…")
            }
            return
        }

        qtProgress = .2f + .8f * (elapsed / (QuickTest.DRIVE_MS / 1000.0)).coerceAtMost(1.0).toFloat()
        sourcePeak = maxOf(sourcePeak, snap.source)
        for (f in Protocol.ALL_FINGERS) {
            val kpa = snap.kpa.getOrElse(f.channel) { 0.0 }
            if (kpa > peak[f.channel]) {
                peak[f.channel] = kpa
                timeToPeak[f.channel] = elapsed
            }
        }
        if (elapsed >= QuickTest.DRIVE_MS / 1000.0) finishQuickTest(hand)
    }

    private fun finishQuickTest(hand: String) {
        engine.sendAllOff(hand)
        qtPhase = "done"
        qtProgress = 1f
        qtStatus = ""
        qtPeaks = peak.toList()
        qtTimes = timeToPeak.toList()
        qtSource = sourcePeak
        qtResult = QuickTest.judge(qtPeaks, sourcePeak)
    }

    // -- screenshots -------------------------------------------------------------

    /**
     * Load one of [DemoSeed]'s canned scenarios. It seeds [state], not the snapshots: the
     * ordinary tick builds the ordinary [GloveSnapshot]s from it, so every screen renders
     * through its normal path. See DemoSeed.kt for what stops it running in a release build.
     */
    fun seedDemo(name: String) {
        val scenario = DemoSeed.SCENARIOS[name] ?: return
        demo = true
        permissionsGranted = true
        mustUseSettings = false
        bluetoothOn = true
        state.gloves.clear()
        seen.clear()

        for (d in scenario.gloves) {
            val glove = state.addGlove(d.hand, d.address, "HaptGloveAR ${d.hand}")
            glove.connected = !d.connecting
            glove.connecting = d.connecting
            glove.status = if (d.connecting) "Connecting…" else "Connected"
            glove.mtu = d.mtu
            glove.absolutePa = false
            glove.telemetry.battery = d.battery
            glove.telemetry.seen = true
            d.kpa.copyInto(glove.telemetry.pressureRaw)
        }
        val now = SystemClock.elapsedRealtime()
        for (f in scenario.found) seen[f.address] = Seen(f, now)

        hand = scenario.hand
        channels = scenario.channels
        settings = scenario.settings
        if (scenario.driving) {
            driving = true
            pressedAt = now - 2_000
            onChannels = channels
        }

        scenario.quickTest?.let { qt ->
            qtHand = scenario.gloves.first().hand
            qtPhase = "done"
            qtProgress = 1f
            qtPeaks = qt.peaks.toList()
            qtTimes = qt.timeToPeak.toList()
            qtSource = qt.source
            qtResult = QuickTest.judge(qtPeaks, qt.source)
        }

        // Live only while notifications keep arriving, and in a demo none do; keep the found
        // gloves fresh too, or the search forgets them.
        viewModelScope.launch {
            while (true) {
                val t = SystemClock.elapsedRealtime()
                state.gloves.values.forEach { it.lastRx = t }
                seen.keys.toList().forEach { k -> seen[k]?.let { seen[k] = it.copy(seenAt = t) } }
                delay(1_000)
            }
        }
    }
}
