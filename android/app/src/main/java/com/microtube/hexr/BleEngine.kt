package com.microtube.hexr

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import androidx.core.content.ContextCompat
import java.util.UUID

/**
 * BLE runtime: one [BluetoothGatt] session per hand, both driven from the main
 * looper.
 *
 * This is the Android counterpart of `hexr/engine.py`, and it is the one part
 * of the app that is genuinely different rather than translated. Bleak on the
 * desktop hides two things that Android makes you handle yourself:
 *
 * 1. **One GATT operation at a time.** Android will silently drop a write
 *    issued while another is outstanding. Every write goes through a per-glove
 *    queue that waits for `onCharacteristicWrite` before sending the next.
 *
 * 2. **The MTU is 23 bytes until you ask for more.** That leaves 20 bytes of
 *    payload, and [Protocol.allOff] is 108 — six 18-byte frames. So the app
 *    requests MTU 247 on connect and, if the glove grants less, splits batches
 *    back into whole frames and packs as many as fit per write. Frames are
 *    self-delimiting by their length byte, so the glove cannot tell the
 *    difference; it just arrives over several writes instead of one.
 *
 * The desktop's 100 ms inter-write gap is kept, for the same reason it exists
 * there: it is not clear whether the firmware needs it, and a stuck channel is
 * a far worse outcome than a slightly late one.
 */
class BleEngine(
    private val context: Context,
    private val state: AppState,
    private val onChange: () -> Unit,
) {
    companion object {
        const val SCAN_MILLIS = 8_000L
        const val MIN_SCAN_GAP_MS = 6_000L       // at most five starts in any thirty seconds
        const val REPORT_EVERY_MS = 1_000L
        const val MIN_SEND_GAP_MS = 100L

        /** Enough for a 108-byte batch plus ATT overhead, with room to spare. */
        const val DESIRED_MTU = 247

        /** ATT header. Usable payload is `mtu - 3`. */
        const val ATT_OVERHEAD = 3
        const val DEFAULT_MTU = 23

        /**
         * A write that never calls back would stall the queue forever, leaving
         * whatever is inflated inflated. After this long the queue gives up on
         * the outstanding write and carries on.
         */
        const val WRITE_TIMEOUT_MS = 2_000L

        /** How long a vent-then-close is allowed to take before forcing it. */
        const val CLOSE_TIMEOUT_MS = 2_500L

        /** MTU negotiation that never answers must not block the connection. */
        const val MTU_TIMEOUT_MS = 2_000L
    }

    private val main = Handler(Looper.getMainLooper())
    private val sessions = HashMap<String, Session>()

    @Volatile var scanning: Boolean = false
        private set

    @Volatile var bleError: String? = null

    private val manager: BluetoothManager? =
        ContextCompat.getSystemService(context, BluetoothManager::class.java)

    private val adapter: BluetoothAdapter? get() = manager?.adapter

    // -- permissions ---------------------------------------------------------

    /**
     * Android 12 split the old blanket BLUETOOTH permission into SCAN and
     * CONNECT, and made them runtime grants. Below 12, a BLE scan needs
     * location instead — the scan results can reveal where you are, so the
     * platform gated it there before the dedicated permissions existed.
     */
    val requiredPermissions: Array<String> =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        } else {
            arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
        }

    fun hasPermissions(): Boolean = requiredPermissions.all {
        ContextCompat.checkSelfPermission(context, it) == PackageManager.PERMISSION_GRANTED
    }

    fun bluetoothEnabled(): Boolean = adapter?.isEnabled == true

    // -- scanning ------------------------------------------------------------

    private var scanCallback: ScanCallback? = null
    private var scanGen = 0
    private var lastScanStart = 0L

    /**
     * When the next search may start. Android quietly stops answering an app that starts more
     * than five scans in thirty seconds, so starts are kept at least this far apart.
     */
    fun scanAllowedAt(): Long = lastScanStart + MIN_SCAN_GAP_MS

    /**
     * Stream discovered gloves to [onResult] as they arrive, then call
     * [onDone] with an error string, or null if the scan simply ended.
     */
    @SuppressLint("MissingPermission")
    fun scan(onResult: (Found) -> Unit, onDone: (String?) -> Unit) {
        // Every exit from this function calls onDone, including this one. The
        // caller flips its own "scanning" flag before calling, so a path that
        // returns silently strands that flag set — and the Scan button then
        // reads "Scanning…" and stays disabled for the life of the process.
        if (scanning || android.os.SystemClock.elapsedRealtime() < scanAllowedAt()) {
            onDone(null)
            return
        }
        bleError = null

        if (!hasPermissions()) {
            onDone("Bluetooth permission not granted")
            return
        }
        val scanner = adapter?.takeIf { it.isEnabled }?.bluetoothLeScanner
        if (scanner == null) {
            // A disabled adapter is not "no gloves found". Saying so sends
            // people hunting for a hardware fault that is not there.
            onDone("Bluetooth is switched off")
            return
        }

        // Each glove again at most once a second, with its signal now: the Connect screen shows
        // live signal bars, and forgets a glove that has gone quiet.
        val lastReport = HashMap<String, Long>()
        val cb = object : ScanCallback() {
            override fun onScanResult(callbackType: Int, result: ScanResult) {
                val name = result.scanRecord?.deviceName ?: runCatching { result.device.name }.getOrNull()
                val hand = Protocol.handFromName(name) ?: return
                val address = result.device.address
                val now = android.os.SystemClock.elapsedRealtime()
                if (now - (lastReport[address] ?: 0L) < REPORT_EVERY_MS) return
                lastReport[address] = now
                onResult(Found(address, name!!, hand, result.rssi))
            }

            override fun onScanFailed(errorCode: Int) {
                bleError = "Scan failed (code $errorCode)"
                stopScan()
                onDone(bleError)
            }
        }
        scanCallback = cb
        scanning = true
        lastScanStart = android.os.SystemClock.elapsedRealtime()
        val gen = ++scanGen

        val settings = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
            .build()
        // Deliberately unfiltered. The hand is carried in the advertised name,
        // and filtering on the service UUID would miss a glove whose
        // advertisement does not include it.
        runCatching { scanner.startScan(null, settings, cb) }
            .onFailure {
                scanning = false
                scanCallback = null
                bleError = it.message ?: it.toString()
                onDone(bleError)
                return
            }

        // Fires whether or not the scan is still running: if something else
        // stopped it early, the caller still needs to hear that it is over.
        main.postDelayed({
            if (scanCallback === cb) stopScan()
            // A search stopped early and replaced by another says nothing about the new one.
            if (gen == scanGen) onDone(bleError)
        }, SCAN_MILLIS)
    }

    @SuppressLint("MissingPermission")
    fun stopScan() {
        val cb = scanCallback ?: run { scanning = false; return }
        scanCallback = null
        scanning = false
        runCatching { adapter?.bluetoothLeScanner?.stopScan(cb) }
    }

    // -- connections ---------------------------------------------------------

    @SuppressLint("MissingPermission")
    fun connect(hand: String, address: String, name: String = "", rssi: Int? = null) {
        val existing = state.get(hand)
        if (existing != null && (existing.connected || existing.connecting)) return
        if (!hasPermissions()) return

        val device = runCatching { adapter?.getRemoteDevice(address) }.getOrNull() ?: return
        val glove = state.addGlove(hand, address, name, rssi)
        glove.connecting = true
        glove.status = "Connecting…"
        onChange()

        val session = Session(glove)
        sessions[hand] = session
        session.gatt = device.connectGatt(context, false, session, BluetoothDevice.TRANSPORT_LE)
    }

    fun disconnect(hand: String) {
        sessions[hand]?.ventAndClose() ?: run {
            state.get(hand)?.let {
                it.connected = false
                it.connecting = false
                it.status = "Not connected"
            }
            onChange()
        }
    }

    fun disconnectAll() = sessions.keys.toList().forEach { disconnect(it) }

    // -- sending -------------------------------------------------------------

    /**
     * Queue a write to one glove. Silently ignored if that hand is not
     * connected, so callers can fire at both hands unconditionally.
     */
    fun send(hand: String, data: ByteArray) {
        if (data.isEmpty()) return
        sessions[hand]?.enqueue(data)
    }

    fun sendHands(hands: Collection<String>, data: ByteArray) = hands.forEach { send(it, data) }

    /**
     * Vent every channel. Anything still waiting to be sent is dropped first: a Release all
     * must never sit in the queue behind a drive that has not gone out yet.
     */
    fun sendAllOff(hand: String? = null) {
        val targets = if (hand != null) listOf(hand) else sessions.keys.toList()
        targets.forEach { sessions[it]?.enqueue(Protocol.allOff(), purge = true) }
    }

    /**
     * Vent every channel and tear down.
     *
     * This is the most important method in the app: leaving the app while a
     * channel is inflated would keep it pressed against someone's finger until
     * the battery died.
     */
    fun shutdown() {
        stopScan()
        disconnectAll()
    }

    // -- one glove -----------------------------------------------------------

    @SuppressLint("MissingPermission")
    private inner class Session(val glove: Glove) : BluetoothGattCallback() {

        var gatt: BluetoothGatt? = null
        private var characteristic: BluetoothGattCharacteristic? = null
        private val decoder = Protocol.FrameDecoder(glove.telemetry)

        private val queue = ArrayDeque<ByteArray>()
        private var busy = false
        private var lastSendAt = 0L
        private var ready = false
        private var closing = false
        private var mtuSettled = false

        private val writeTimeout = Runnable {
            // The write never came back. Assume it is lost rather than holding
            // the rest of the queue — including, quite possibly, an all-off.
            busy = false
            pump()
        }

        private val forceClose = Runnable { teardown("Not connected") }

        // -- queue ------------------------------------------------------------

        fun enqueue(data: ByteArray, purge: Boolean = false) {
            main.post {
                if (closing && queue.isEmpty() && !busy) return@post
                if (purge) queue.clear()
                for (chunk in chunk(data)) queue.addLast(chunk)
                pump()
            }
        }

        /**
         * Split a batch to fit the negotiated MTU, packing whole frames.
         *
         * Frames are never broken across writes: the firmware walks a write
         * using each frame's length byte, so half a frame would desynchronise
         * its parser rather than simply arriving late.
         */
        private fun chunk(data: ByteArray): List<ByteArray> {
            val maxPayload = (glove.mtu ?: DEFAULT_MTU) - ATT_OVERHEAD
            if (data.size <= maxPayload) return listOf(data)

            val out = ArrayList<ByteArray>()
            var current = ArrayList<ByteArray>()
            var currentSize = 0
            for (frame in Protocol.splitFrames(data)) {
                if (currentSize > 0 && currentSize + frame.size > maxPayload) {
                    out.add(Protocol.batch(current))
                    current = ArrayList()
                    currentSize = 0
                }
                current.add(frame)
                currentSize += frame.size
            }
            if (current.isNotEmpty()) out.add(Protocol.batch(current))
            return out
        }

        private fun pump() {
            if (busy || !ready) return
            val g = gatt
            val ch = characteristic
            if (g == null || ch == null) return
            if (queue.isEmpty()) {
                if (closing) teardown("Not connected")
                return
            }

            val since = SystemClock.elapsedRealtime() - lastSendAt
            if (since < MIN_SEND_GAP_MS) {
                main.postDelayed({ pump() }, MIN_SEND_GAP_MS - since)
                return
            }

            val data = queue.removeFirst()
            busy = true
            // The characteristic declares WRITE without WRITE_NO_RESPONSE, so a
            // with-response write is the only legal one here.
            val ok = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                g.writeCharacteristic(
                    ch, data, BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT,
                ) == BluetoothGatt.GATT_SUCCESS
            } else {
                @Suppress("DEPRECATION")
                run {
                    ch.writeType = BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
                    ch.value = data
                    g.writeCharacteristic(ch)
                }
            }
            if (!ok) {
                busy = false
                main.postDelayed({ pump() }, MIN_SEND_GAP_MS)
                return
            }
            lastSendAt = SystemClock.elapsedRealtime()
            main.postDelayed(writeTimeout, WRITE_TIMEOUT_MS)
        }

        // -- lifecycle ---------------------------------------------------------

        fun ventAndClose() {
            main.post {
                if (closing) return@post
                closing = true
                if (ready) {
                    for (c in chunk(Protocol.allOff())) queue.addLast(c)
                    pump()
                    // Even a healthy link gets a deadline. A glove that stops
                    // acknowledging mid-vent must not keep the session alive.
                    main.postDelayed(forceClose, CLOSE_TIMEOUT_MS)
                } else {
                    teardown("Not connected")
                }
            }
        }

        private fun teardown(status: String) {
            main.removeCallbacks(forceClose)
            main.removeCallbacks(writeTimeout)
            ready = false
            queue.clear()
            runCatching { gatt?.disconnect() }
            runCatching { gatt?.close() }
            gatt = null
            characteristic = null
            glove.connected = false
            glove.connecting = false
            glove.status = status
            if (sessions[glove.hand] === this) sessions.remove(glove.hand)
            onChange()
        }

        // -- callbacks ---------------------------------------------------------

        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            main.post {
                if (newState == BluetoothGatt.STATE_CONNECTED) {
                    // Ask for a bigger MTU before discovering services: a
                    // 108-byte all-off does not fit in the default 20-byte
                    // payload, and re-negotiating later would mean the first
                    // writes of the session used a different path from the rest.
                    if (!g.requestMtu(DESIRED_MTU)) onMtuSettled(g, DEFAULT_MTU)
                    main.postDelayed({
                        if (!mtuSettled) onMtuSettled(g, DEFAULT_MTU)
                    }, MTU_TIMEOUT_MS)
                } else if (newState == BluetoothGatt.STATE_DISCONNECTED) {
                    val why = if (status == BluetoothGatt.GATT_SUCCESS) {
                        "Not connected"
                    } else {
                        "Error: disconnected (status $status)"
                    }
                    teardown(why)
                }
            }
        }

        override fun onMtuChanged(g: BluetoothGatt, mtu: Int, status: Int) {
            main.post {
                onMtuSettled(g, if (status == BluetoothGatt.GATT_SUCCESS) mtu else DEFAULT_MTU)
            }
        }

        private fun onMtuSettled(g: BluetoothGatt, mtu: Int) {
            if (mtuSettled) return
            mtuSettled = true
            glove.mtu = mtu
            g.discoverServices()
        }

        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            main.post {
                val service = g.getService(UUID.fromString(Protocol.SERVICE_UUID))
                val ch = service?.getCharacteristic(UUID.fromString(Protocol.CHAR_UUID))
                if (ch == null) {
                    glove.status = "Error: this device has no HEXR service"
                    onChange()
                    teardown(glove.status)
                    return@post
                }
                characteristic = ch

                // Subscribe before reporting connected, so a glove that does
                // stream is already streaming by the time the UI shows it.
                // Actuation does not depend on this — gloves drive fine having
                // never sent a byte — but the pressure readout and the QA sweep
                // do.
                g.setCharacteristicNotification(ch, true)
                val cccd = ch.getDescriptor(UUID.fromString(Protocol.CCCD_UUID))
                if (cccd == null) {
                    // No CCCD means no telemetry, but the glove still actuates.
                    markReady()
                    return@post
                }
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    g.writeDescriptor(cccd, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
                } else {
                    @Suppress("DEPRECATION")
                    run {
                        cccd.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                        g.writeDescriptor(cccd)
                    }
                }
            }
        }

        override fun onDescriptorWrite(g: BluetoothGatt, d: BluetoothGattDescriptor, status: Int) {
            main.post { markReady() }
        }

        private fun markReady() {
            if (ready) return
            ready = true
            glove.connected = true
            glove.connecting = false
            glove.status = "Connected"
            onChange()
            pump()
        }

        override fun onCharacteristicWrite(
            g: BluetoothGatt,
            ch: BluetoothGattCharacteristic,
            status: Int,
        ) {
            main.post {
                main.removeCallbacks(writeTimeout)
                busy = false
                pump()
            }
        }

        override fun onCharacteristicChanged(
            g: BluetoothGatt,
            ch: BluetoothGattCharacteristic,
            value: ByteArray,
        ) = onNotify(value)

        // Kept for API < 33, where the ByteArray overload above is never called.
        @Suppress("DEPRECATION")
        override fun onCharacteristicChanged(g: BluetoothGatt, ch: BluetoothGattCharacteristic) {
            onNotify(ch.value ?: return)
        }

        private fun onNotify(value: ByteArray) {
            // Decoding happens on the binder thread on purpose: at 50 Hz this
            // would otherwise post fifty messages a second to the main looper.
            // Every field it touches is a single volatile assignment, and the
            // UI reads them on its own tick.
            decoder.feed(value)
            glove.lastRx = SystemClock.elapsedRealtime()
            if (glove.absolutePa == null && glove.telemetry.seen) {
                glove.absolutePa = Protocol.looksLikeAbsolutePa(glove.telemetry.pressureRaw)
            }
        }
    }
}
