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
import com.microtube.hexr.remote.HapticsTimeline
import com.microtube.hexr.remote.HapticsUpdate
import com.microtube.hexr.remote.HeadsetDiscovery
import com.microtube.hexr.remote.HeadsetLink
import com.microtube.hexr.remote.HeadsetStatus
import com.microtube.hexr.remote.RemoteProtocol
import com.microtube.hexr.remote.VideoPlayer
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
    /** This phone asked to watch: the view shows while the headset shares it. */
    val watching: Boolean = false,
    /** When Recenter was last pressed, on SystemClock.elapsedRealtime(); 0 for never. */
    val recenteredAt: Long = 0,
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
 * each of several headsets. What the gloves are doing goes into each headset's
 * [HapticsTimeline] instead, which the glove panels read as they draw, frame by frame.
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
        @Volatile var recenteredAt: Long = 0
        // Watch was pressed before the headset could be told: ask with its next status.
        @Volatile var askToShare = false
        val timeline = HapticsTimeline()
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

    /** The headsets this phone wants to watch, by key. */
    private var watching by mutableStateOf<Set<String>>(emptySet())

    /**
     * Names given to gloves on this phone, by Bluetooth address. A glove with none goes by its own
     * name from its address (GloveNames), the one every HEXR Companion gives it.
     */
    var gloveNames by mutableStateOf(loadGloveNames())
        private set

    /** Listening and connected: the tab is on screen and the app in front. No view plays otherwise. */
    var online by mutableStateOf(false)
        private set

    private var visible = false
    private var foreground = true

    init {
        viewModelScope.launch {
            while (true) {
                tick()
                delay(TICK_MS)
            }
        }
    }

    // -- when to listen ----------------------------------------------------------

    /** The tab is on screen. Nothing is opened until it is: the app's other tab needs no network. */
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
        if (want == online) return
        online = want
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
            if (entries.putIfAbsent(a.id, entry) == null && online) entry.link.start()
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

    /**
     * For venue Wi-Fi that hides devices from each other: connect by typing the headset's
     * address, with its port after a colon if it is not the usual one. The headset's key, to
     * open it, or null if that is not an address.
     */
    fun addByAddress(address: String): String? {
        val (host, port) = RemoteProtocol.parseAddress(address) ?: return null
        val key = if (port == RemoteProtocol.CONTROL_PORT) "ip:$host" else "ip:$host:$port"
        if (!entries.containsKey(key)) {
            val entry = Entry(key, host, newLink(key, host, port), manual = true)
            entries[key] = entry
            if (online) entry.link.start()
            tick()
        }
        return key
    }

    fun forget(key: String) {
        entries.remove(key)?.link?.stop()
        watching = watching - key
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

    /** What this headset's gloves are doing, for the panels beside its view. */
    fun timeline(key: String): HapticsTimeline? = entries[key]?.timeline

    // -- requests -----------------------------------------------------------------

    fun connectGlove(key: String, hand: String) = send(key, RemoteProtocol.glove("connect", hand))

    fun disconnectGlove(key: String, hand: String) = send(key, RemoteProtocol.glove("disconnect", hand))

    fun release(key: String) = send(key, RemoteProtocol.release())

    /** Every channel of the connected gloves pressed for a second: does the glove work? */
    fun trigger(key: String) = send(key, RemoteProtocol.trigger())

    // -- picking one glove out of several, by its address --------------------------

    /** The headset lists every glove in range; the result comes in its status. */
    fun searchGloves(key: String) = send(key, RemoteProtocol.gloveSearch())

    /** That exact glove, which the headset then keeps to for this hand. */
    fun connectGloveAt(key: String, hand: String, address: String) =
        send(key, RemoteProtocol.connectGloveAt(hand, address))

    /** The headset goes back to taking the first glove of this hand it finds. */
    fun forgetGlove(key: String, hand: String) = send(key, RemoteProtocol.glove("forget", hand))

    /** What this phone calls the glove at this address: the name given here, or its own. */
    fun gloveName(address: String): String =
        gloveNames[address.uppercase()] ?: GloveNames.autoName(address, chinese = I18n.language == I18n.ZH_CN)

    /** Names a glove by its address on this phone. Blank, or its own name, clears it. */
    fun renameGlove(address: String, name: String) {
        val key = address.uppercase()
        val own = GloveNames.autoName(address, chinese = I18n.language == I18n.ZH_CN)
        prefs.edit().apply {
            if (name.isBlank() || name.trim() == own) remove("glove:$key") else putString("glove:$key", name.trim())
        }.apply()
        gloveNames = loadGloveNames()
    }

    private fun loadGloveNames(): Map<String, String> =
        prefs.all.filterKeys { it.startsWith("glove:") }
            .mapNotNull { (k, v) -> (v as? String)?.let { k.removePrefix("glove:") to it } }
            .toMap()

    /** Put the wearer back on the scene's starting spot. The button says it was done, for a moment. */
    fun recenter(key: String) {
        entries[key]?.recenteredAt = SystemClock.elapsedRealtime()
        send(key, RemoteProtocol.recenter())
        tick()
    }

    /**
     * Watch: ask the wearer to share, unless the headset already is (for another phone, or a
     * computer), in which case this phone just joins.
     */
    fun watch(key: String) {
        watching = watching + key
        val entry = entries[key] ?: return
        val stream = entry.status?.stream
        when {
            entry.state != HeadsetLink.State.Connected || stream == null -> entry.askToShare = true
            !stream.live && stream.state != "requesting" -> send(key, RemoteProtocol.stream("start"))
        }
        tick()
    }

    /**
     * Stop watching. Ending the share closes every viewer's connection, so it ends only if no
     * other phone or computer is watching; otherwise this phone just leaves. [joined] is whether
     * this phone's own view was connected, and so one of the viewers the headset counts.
     */
    fun stopWatching(key: String, joined: Boolean) {
        if (key !in watching) return
        watching = watching - key
        entries[key]?.askToShare = false
        val stream = entries[key]?.status?.stream
        if (stream != null && (stream.live || stream.state == "requesting")) {
            val others = stream.viewers - if (joined) 1 else 0
            if (others <= 0) send(key, RemoteProtocol.stream("stop"))
        }
        tick()
    }

    private fun send(key: String, line: String) {
        val entry = entries[key] ?: return
        entry.error = null
        entry.link.send(line)
    }

    // -- from the links' threads ------------------------------------------------------

    override fun onLinkState(key: String, state: HeadsetLink.State) {
        val e = entries[key] ?: return
        // A new connection may be to a headset that restarted, and its clock with it.
        if (state == HeadsetLink.State.Connected && e.state != HeadsetLink.State.Connected) e.timeline.resetClock()
        e.state = state
    }

    override fun onStatus(key: String, status: HeadsetStatus) {
        entries[key]?.apply {
            this.status = status
            lastHeard = SystemClock.elapsedRealtime()
            timeline.onStatus(status, VideoPlayer.nowS())
            if (askToShare) {
                askToShare = false
                if (!status.stream.live && status.stream.state != "requesting") link.send(RemoteProtocol.stream("start"))
            }
        }
    }

    override fun onHaptics(key: String, update: HapticsUpdate) {
        entries[key]?.timeline?.onHaptics(update)
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

        // The wearer said no: that is an answer, not something to keep waiting on.
        val declined = watching.filter { entries[it]?.status?.stream?.state == "denied" }
        if (declined.isNotEmpty()) watching = watching - declined.toSet()

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
                    watching = e.key in watching,
                    recenteredAt = e.recenteredAt,
                )
            }
            .sortedBy { it.title.lowercase() }

        if (selected != null && entries[selected] == null) selected = null
    }

    private fun newLink(key: String, host: String, port: Int) = HeadsetLink(key, host, port, wifi, this)

    /**
     * Headsets of one model share a name ("Quest 3"), so a list of them needs something to tell
     * them apart before anyone has named them: the end of the headset's id, or its address.
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
