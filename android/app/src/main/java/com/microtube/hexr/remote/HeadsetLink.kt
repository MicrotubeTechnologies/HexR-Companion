package com.microtube.hexr.remote

import android.os.SystemClock
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import kotlin.concurrent.thread

/**
 * One headset's control connection: requests out, status and errors in.
 *
 * A headset sends its status five times a second, and at least once a second even while asleep,
 * so four seconds of silence means it has gone, and the link reconnects on its own with a
 * growing pause. The headset in turn drops a phone it has not heard from in fifteen seconds,
 * which the ping every five seconds prevents.
 */
class HeadsetLink(
    val key: String,
    host: String,
    port: Int,
    private val wifi: WifiNetwork,
    private val listener: Listener,
) {

    enum class State { Connecting, Connected, Lost }

    interface Listener {
        fun onLinkState(key: String, state: State)
        fun onStatus(key: String, status: HeadsetStatus)
        fun onError(key: String, request: String, message: String)
    }

    @Volatile
    var host: String = host
        private set

    @Volatile
    var port: Int = port
        private set

    @Volatile
    private var running = false

    // Each start gets a new number, so a loop left over from before a stop (asleep in its
    // backoff) sees it is stale and ends instead of running beside the new one.
    @Volatile
    private var generation = 0

    @Volatile
    private var socket: Socket? = null

    // Writes go through one thread, in order, and never on the caller's (the UI's) thread.
    @Volatile
    private var writer: ExecutorService? = null

    @Synchronized
    fun start() {
        if (running) return
        running = true
        val mine = ++generation
        writer = Executors.newSingleThreadExecutor { r -> Thread(r, "HexRHeadsetWrite").apply { isDaemon = true } }
        thread(name = "HexRHeadsetLink", isDaemon = true) { run(mine) }
    }

    @Synchronized
    fun stop() {
        running = false
        generation++
        runCatching { socket?.close() }
        writer?.shutdownNow()
        writer = null
    }

    /** Points the link at a new address, after the headset's app restarted somewhere else. */
    fun retarget(newHost: String, newPort: Int) {
        if (newHost == host && newPort == port) return
        host = newHost
        port = newPort
        runCatching { socket?.close() }
    }

    fun send(line: String) {
        val s = socket ?: return
        val w = writer ?: return
        runCatching {
            w.execute {
                runCatching {
                    s.getOutputStream().apply {
                        write((line + "\n").toByteArray(Charsets.UTF_8))
                        flush()
                    }
                }
            }
        }
    }

    private fun run(mine: Int) {
        fun current() = running && generation == mine
        var backoff = INITIAL_BACKOFF_MS
        while (current()) {
            listener.onLinkState(key, State.Connecting)
            try {
                val s = wifi.newSocket()
                socket = s
                s.tcpNoDelay = true
                s.connect(InetSocketAddress(host, port), CONNECT_TIMEOUT_MS)
                s.soTimeout = SILENCE_TIMEOUT_MS
                send(RemoteProtocol.hello(CLIENT))
                listener.onLinkState(key, State.Connected)
                backoff = INITIAL_BACKOFF_MS

                val reader = BufferedReader(InputStreamReader(s.getInputStream(), Charsets.UTF_8))
                var lastPing = SystemClock.elapsedRealtime()
                while (current()) {
                    val line = reader.readLine() ?: break
                    when (val message = RemoteProtocol.parseLine(line)) {
                        is Message.Status -> listener.onStatus(key, message.status)
                        is Message.Error -> listener.onError(key, message.request, message.message)
                        else -> Unit
                    }

                    val now = SystemClock.elapsedRealtime()
                    if (now - lastPing > PING_EVERY_MS) {
                        send(RemoteProtocol.ping())
                        lastPing = now
                    }
                }
            } catch (e: Exception) {
                // Unreachable, timed out, or the headset's app closed. Retried below.
            }

            if (!current()) break
            runCatching { socket?.close() }
            socket = null
            listener.onLinkState(key, State.Lost)
            Thread.sleep(backoff)
            backoff = (backoff * 2).coerceAtMost(MAX_BACKOFF_MS)
        }
    }

    companion object {
        const val CLIENT = "HexR Companion (Android)"
        private const val CONNECT_TIMEOUT_MS = 3000
        private const val SILENCE_TIMEOUT_MS = 4000
        private const val PING_EVERY_MS = 5000L
        private const val INITIAL_BACKOFF_MS = 500L
        private const val MAX_BACKOFF_MS = 5000L
    }
}
