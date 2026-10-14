package com.microtube.hexr

import android.app.Application
import android.content.Context
import android.os.SystemClock
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.microtube.hexr.remote.Announce
import com.microtube.hexr.remote.HeadsetDiscovery
import com.microtube.hexr.remote.HeadsetLink
import com.microtube.hexr.remote.HeadsetStatus
import com.microtube.hexr.remote.RemoteProtocol
import com.microtube.hexr.remote.WifiNetwork
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.util.concurrent.ConcurrentHashMap

/** One headset as the Headsets tab shows it. A snapshot, rebuilt on every tick. */
data class HeadsetRow(
    val key: String,
    val host: String,
    val title: String,
    val nickname: String,
    val announce: Announce?,
    val status: HeadsetStatus?,
    val link: HeadsetLink.State,
    val error: String?,
    val manual: Boolean,
)

/**
 * The Headsets tab: every HexR headset on this Wi-Fi, each one's gloves through the headset, and
 * its view.
 *
 * Kept apart from [HexrViewModel] on purpose. That one drives gloves over this phone's own
 * Bluetooth; this one never touches Bluetooth, and talks to headsets that hold their gloves
 * themselves. A glove connects to one thing at a time, so the two meet only in the hint the
 * screen shows when this phone is holding a glove a headset is trying to reach.
 *
 * Network threads write into [entries]; the UI reads [rows], a snapshot rebuilt on a tick, so a
 * headset reporting five times a second does not recompose the screen five times a second for
 * each of several headsets.
 */
class HeadsetsViewModel(app: Application) : AndroidViewModel(app), HeadsetLink.Listener {

    private class Entry(
        val key: String,
        @Volatile var host: String,
        val link: HeadsetLink,
        val manual: Boolean,
    ) {
        @Volatile var announce: Announce? = null
        @Volatile var status: HeadsetStatus? = null
        @Volatile var state: HeadsetLink.State = HeadsetLink.State.Connecting
        @Volatile var error: String? = null
        @Volatile var errorAt: Long = 0
        @Volatile var lastHeard: Long = SystemClock.elapsedRealtime()
    }

    private val wifi = WifiNetwork(app)
    private val discovery = HeadsetDiscovery(app, wifi, ::onAnnounce)
    private val entries = ConcurrentHashMap<String, Entry>()
    private val prefs = app.getSharedPreferences("headsets", Context.MODE_PRIVATE)

    var rows by mutableStateOf<List<HeadsetRow>>(emptyList())
        private set

    /** The headset open in the detail view, by key. Null shows the list. */
    var selected by mutableStateOf<String?>(null)
        private set

    private var visible = false
    private var foreground = true
    private var active = false

    init {
        viewModelScope.launch {
            while (true) {
                tick()
                delay(TICK_MS)
            }
        }
    }

    // -- when to listen ----------------------------------------------------------

    /** The tab is on screen. Nothing is opened until it is: the tester's other tabs need no network. */
    fun setVisible(on: Boolean) {
        visible = on
        update()
    }

    /** The app is in front. Sockets and the multicast lock are given up the moment it is not. */
    fun setForeground(on: Boolean) {
        foreground = on
        update()
    }

    private fun update() {
        val want = visible && foreground
        if (want == active) return
        active = want
        if (want) {
            wifi.start()
            discovery.start()
            entries.values.forEach { it.link.start() }
        } else {
            discovery.stop()
            entries.values.forEach { it.link.stop() }
            wifi.stop()
        }
    }

    // -- headsets -----------------------------------------------------------------

    private fun onAnnounce(a: Announce, host: String) {
        val existing = entries[a.id]
        if (existing == null) {
            val entry = Entry(a.id, host, newLink(a.id, host, a.control), manual = false)
            entry.announce = a
            if (entries.putIfAbsent(a.id, entry) == null && active) entry.link.start()
            return
        }

        existing.lastHeard = SystemClock.elapsedRealtime()
        val previous = existing.announce
        // The same headset with its app restarted, or a different app on it: follow the newest.
        if (previous == null || a.startedAt >= previous.startedAt) {
            existing.announce = a
            existing.host = host
            existing.link.retarget(host, a.control)
        }
    }

    /** For venue Wi-Fi that hides devices from each other: connect by typing the headset's IP. */
    fun addByAddress(address: String) {
        val host = address.trim()
        if (host.isEmpty()) return
        val key = "ip:$host"
        if (entries.containsKey(key)) return
        val entry = Entry(key, host, newLink(key, host, RemoteProtocol.CONTROL_PORT), manual = true)
        entries[key] = entry
        if (active) entry.link.start()
        tick()
    }

    fun forget(key: String) {
        entries.remove(key)?.link?.stop()
        if (selected == key) selected = null
        tick()
    }

    fun select(key: String?) {
        selected = key
    }

    fun rename(key: String, nickname: String) {
        prefs.edit().apply {
            if (nickname.isBlank()) remove("nick:$key") else putString("nick:$key", nickname.trim())
        }.apply()
        tick()
    }

    // -- requests -----------------------------------------------------------------

    fun connectGlove(key: String, hand: String) = send(key, RemoteProtocol.glove("connect", hand))

    fun disconnectGlove(key: String, hand: String) = send(key, RemoteProtocol.glove("disconnect", hand))

    fun release(key: String) = send(key, RemoteProtocol.release())

    fun loadScene(key: String, index: Int) = send(key, RemoteProtocol.scene(index))

    fun runCommand(key: String, id: String) = send(key, RemoteProtocol.command(id))

    fun startView(key: String) = send(key, RemoteProtocol.stream("start"))

    fun stopView(key: String) = send(key, RemoteProtocol.stream("stop"))

    private fun send(key: String, line: String) {
        val entry = entries[key] ?: return
        entry.error = null
        entry.link.send(line)
    }

    // -- from the links' threads ------------------------------------------------------

    override fun onLinkState(key: String, state: HeadsetLink.State) {
        entries[key]?.state = state
    }

    override fun onStatus(key: String, status: HeadsetStatus) {
        entries[key]?.apply {
            this.status = status
            lastHeard = SystemClock.elapsedRealtime()
        }
    }

    override fun onError(key: String, request: String, message: String) {
        entries[key]?.apply {
            error = message
            errorAt = SystemClock.elapsedRealtime()
        }
    }

    // -- tick ---------------------------------------------------------------------

    private fun tick() {
        val now = SystemClock.elapsedRealtime()

        // A headset that stopped announcing and cannot be reached has gone: switched off, or its
        // app closed. Ones added by hand stay until forgotten; nothing else would bring them back.
        entries.values
            .filter { !it.manual && it.state != HeadsetLink.State.Connected && now - it.lastHeard > FORGET_AFTER_MS }
            .forEach { forget(it.key) }

        rows = entries.values
            .map { e ->
                val nickname = prefs.getString("nick:${e.key}", null).orEmpty()
                val name = e.status?.name ?: e.announce?.name ?: e.host
                HeadsetRow(
                    key = e.key,
                    host = e.host,
                    title = nickname.ifEmpty { "$name · ${shortId(e.key)}" },
                    nickname = nickname,
                    announce = e.announce,
                    status = e.status,
                    link = e.state,
                    error = e.error?.takeIf { now - e.errorAt < ERROR_SHOWN_MS },
                    manual = e.manual,
                )
            }
            .sortedBy { it.title.lowercase() }

        if (selected != null && entries[selected] == null) selected = null
    }

    private fun newLink(key: String, host: String, port: Int) = HeadsetLink(key, host, port, wifi, this)

    /**
     * Headsets of one model share a name ("Quest 3"), so a list of them needs something to tell
     * them apart before anyone has named them: the end of the headset's id, or its IP.
     */
    private fun shortId(key: String) = if (key.startsWith("ip:")) key.removePrefix("ip:") else key.takeLast(4).uppercase()

    override fun onCleared() {
        discovery.stop()
        entries.values.forEach { it.link.stop() }
        wifi.stop()
        super.onCleared()
    }

    private companion object {
        const val TICK_MS = 250L
        const val FORGET_AFTER_MS = 15_000L
        const val ERROR_SHOWN_MS = 8_000L
    }
}
