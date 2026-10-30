package com.microtube.hexr.remote

import org.json.JSONArray
import org.json.JSONObject

/**
 * HexR Remote, protocol version 1: how the Headsets tab talks to a HexR app on a headset.
 *
 * The contract is `Documentation~/RemoteProtocol.md` in the com.microtube.hexr package, and the
 * headset side is that package's C#. Like the glove protocol in [com.microtube.hexr.Protocol],
 * this is one wire format implemented in two languages, so the same reference lines sit in both
 * test suites (RemoteProtocolTest.kt here, RemoteTests.cs there). Change it in both places.
 *
 * Requests are written by hand rather than through JSONObject: Android's JSONObject keeps key
 * order and the JVM one the unit tests run on does not, and the reference lines are exact
 * strings. Replies are parsed with org.json, where order does not matter.
 */
object RemoteProtocol {

    const val VERSION = 1
    const val DISCOVERY_PORT = 47800
    const val CONTROL_PORT = 47801

    // -- requests -------------------------------------------------------------

    fun hello(client: String) = """{"type":"hello","protocol":$VERSION,"client":${str(client)}}"""

    fun ping() = """{"type":"ping"}"""

    fun glove(action: String, hand: String) =
        """{"type":"glove","action":${str(action)},"hand":${str(hand.lowercase())}}"""

    fun release() = """{"type":"release"}"""

    /** Every channel of the connected gloves pressed for a second, then let go (HexR 0.10.6 on). */
    fun trigger() = """{"type":"trigger"}"""

    /** Every glove in range, listed in the status's gloveSearch about 8 s later (HexR 0.10.6 on). */
    fun gloveSearch() = """{"type":"glove","action":"search"}"""

    /** That exact glove for this hand, which the headset then keeps to (HexR 0.10.6 on). */
    fun connectGloveAt(hand: String, address: String) =
        """{"type":"glove","action":"connect","hand":${str(hand.lowercase())},"address":${str(address)}}"""

    fun scene(index: Int) = """{"type":"scene","index":$index}"""

    fun command(id: String) = """{"type":"command","id":${str(id)}}"""

    fun stream(action: String) = """{"type":"stream","action":${str(action)}}"""

    /** Put the wearer back on the scene's starting spot, facing its front (HexR 0.10.6 on). */
    fun recenter() = """{"type":"recenter"}"""

    /**
     * A headset typed in by hand: "192.168.1.20", or "192.168.1.20:47811" for one on another
     * port, as a second app on one headset, or a test headset on a computer, would be. Null for
     * anything that cannot be one.
     */
    fun parseAddress(text: String): Pair<String, Int>? {
        val t = text.trim()
        if (t.isEmpty()) return null
        val colon = t.lastIndexOf(':')
        val (host, port) = if (colon >= 0) {
            t.substring(0, colon) to (t.substring(colon + 1).toIntOrNull() ?: return null)
        } else {
            t to CONTROL_PORT
        }
        if (port !in 1..65535 || !HOST.matches(host)) return null
        return host to port
    }

    private val HOST = Regex("""[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?""")

    /** A JSON string literal: quotes, backslashes and control characters escaped. */
    fun str(s: String): String {
        val out = StringBuilder(s.length + 2).append('"')
        for (c in s) {
            when (c) {
                '"' -> out.append("\\\"")
                '\\' -> out.append("\\\\")
                '\n' -> out.append("\\n")
                '\r' -> out.append("\\r")
                '\t' -> out.append("\\t")
                else -> if (c < ' ') out.append("\\u%04x".format(c.code)) else out.append(c)
            }
        }
        return out.append('"').toString()
    }

    // -- what the headset sends -------------------------------------------------

    /** The UDP announcement. Null for anything that is not one. */
    fun parseAnnounce(text: String): Announce? = runCatching {
        val o = JSONObject(text)
        if (o.optString("type") != "announce" || o.optInt("hexr") < 1) return null
        Announce(
            id = o.optString("id"),
            name = o.optString("name"),
            model = o.optString("model"),
            platform = o.optString("platform"),
            app = o.optString("app"),
            appId = o.optString("appId"),
            hexrVersion = o.optString("hexrVersion"),
            control = o.optInt("control", CONTROL_PORT),
            video = o.optInt("video"),
            startedAt = o.optLong("startedAt"),
        ).takeIf { it.id.isNotEmpty() }
    }.getOrNull()

    /** One control line from the headset. */
    fun parseLine(line: String): Message = try {
        val o = JSONObject(line)
        when (o.optString("type")) {
            "status" -> Message.Status(parseStatus(o))
            "error" -> Message.Error(o.optString("request"), o.optString("message"))
            "hello" -> Message.Welcome(o.optString("id"), o.optInt("control"), o.optInt("video"))
            "haptics" -> parseHaptics(o)?.let { Message.Haptics(it) } ?: Message.Other
            else -> Message.Other
        }
    } catch (e: Exception) {
        Message.Other
    }

    private fun parseStatus(o: JSONObject) = HeadsetStatus(
        id = o.optString("id"),
        name = o.optString("name"),
        model = o.optString("model"),
        platform = o.optString("platform"),
        app = o.optString("app"),
        appVersion = o.optString("appVersion"),
        hexrVersion = o.optString("hexrVersion"),
        paused = o.optBoolean("paused"),
        headsetBatteryPct = o.optInt("headsetBatteryPct", -1),
        scene = o.optJSONObject("scene")?.let(::sceneOf) ?: SceneInfo(-1, ""),
        scenes = o.optJSONArray("scenes").objects().map(::sceneOf),
        gloves = o.optJSONArray("gloves").objects().map { g ->
            GloveState(
                hand = g.optString("hand"),
                state = g.optString("state"),
                message = g.optString("message"),
                batteryPct = g.optInt("batteryPct", -1),
                pressureDeciKPa = g.optJSONArray("pressureDeciKPa").ints(),
                savedAddress = g.optString("savedAddress"),
            )
        },
        stream = o.optJSONObject("stream")?.let { s ->
            StreamState(
                state = s.optString("state", "off"),
                port = s.optInt("port"),
                width = s.optInt("width"),
                height = s.optInt("height"),
                viewers = s.optInt("viewers"),
                message = s.optString("message"),
            )
        } ?: StreamState(),
        commands = o.optJSONArray("commands").objects().map { CommandInfo(it.optString("id"), it.optString("label")) },
        allowGloveControl = o.optBoolean("allowGloveControl"),
        allowVideo = o.optBoolean("allowVideo"),
        exposeScenes = o.optBoolean("exposeScenes"),
        controllers = o.optInt("controllers"),
        allowRecenter = o.optBoolean("allowRecenter", false),
        haptics = o.optBoolean("haptics", false),
        clockUs = longOf(o.opt("clockUs"), 0L),
        gloveSearch = o.optJSONObject("gloveSearch")?.let { gs ->
            RemoteGloveSearch(
                state = gs.optString("state", "idle"),
                message = gs.optString("message"),
                found = gs.optJSONArray("found").objects()
                    .filter { it.optString("address").isNotEmpty() }
                    .map {
                        NearbyGlove(
                            address = it.optString("address"),
                            name = it.optString("name"),
                            hand = it.optString("hand").takeIf { h -> h == "left" || h == "right" }.orEmpty(),
                            rssi = intOf(it.opt("rssi"), 0),
                        )
                    },
            )
        },
    )

    /**
     * A "haptics" line (HexR 0.10.2 on): what one glove's channels started doing at `t`, in
     * microseconds on the clock the video frames are stamped with. Null if it is not usable;
     * a channel that is not one is skipped. The same checks as the desktop's `parse_haptics`.
     */
    fun parseHaptics(o: JSONObject): HapticsUpdate? {
        val hand = o.opt("hand") as? String ?: return null
        if (hand != "left" && hand != "right") return null
        val list = o.optJSONArray("channels")
        val channels = mutableListOf<HapticChannel>()
        if (list != null) {
            for (i in 0 until list.length()) {
                val c = list.opt(i) as? JSONObject ?: continue
                val finger = intOf(c.opt("finger"), -1)
                val mode = c.opt("mode") as? String
                if (finger !in 0..5 || mode !in HAPTIC_MODES) continue
                channels += HapticChannel(
                    finger = finger,
                    mode = mode!!,
                    intensity = intOf(c.opt("intensityPct"), 0).coerceIn(0, 100) / 100.0,
                    hz = maxOf(0, intOf(c.opt("frequencyDeciHz"), 0)) / 10.0,
                    tap = c.opt("tap") == true,
                )
            }
        }
        return HapticsUpdate(hand, longOf(o.opt("t"), 0L), channels)
    }

    private val HAPTIC_MODES = setOf("off", "pressure", "vibration", "pulse")

    /** A JSON number as an Int; anything else (a boolean, a string) is not one. */
    private fun intOf(v: Any?, default: Int): Int = when (v) {
        is Boolean -> default
        is Number -> v.toInt()
        else -> default
    }

    private fun longOf(v: Any?, default: Long): Long = when (v) {
        is Boolean -> default
        is Number -> v.toLong()
        else -> default
    }

    private fun sceneOf(o: JSONObject) = SceneInfo(o.optInt("index", -1), o.optString("name"))

    private fun JSONArray?.objects(): List<JSONObject> =
        if (this == null) emptyList() else (0 until length()).mapNotNull { optJSONObject(it) }

    private fun JSONArray?.ints(): List<Int> =
        if (this == null) emptyList() else (0 until length()).map { optInt(it) }

    // -- video ------------------------------------------------------------------

    /**
     * The video stream, big-endian throughout:
     *   once:        "HXV1"  u16 width  u16 height  u8 codec (1 = H.264)
     *   per packet:  u32 payloadLength  u8 flags (1 config, 2 key)  u64 ptsMicros  payload
     */
    const val VIDEO_HEADER_BYTES = 9
    const val PACKET_HEADER_BYTES = 13
    const val FLAG_CONFIG = 1
    const val FLAG_KEY = 2
    const val CODEC_H264 = 1

    /** A packet larger than this is a broken stream, not a frame. */
    const val MAX_PACKET_BYTES = 8 * 1024 * 1024

    fun parseVideoHeader(b: ByteArray): VideoHeader? {
        if (b.size < VIDEO_HEADER_BYTES) return null
        if (b[0] != 'H'.code.toByte() || b[1] != 'X'.code.toByte() || b[2] != 'V'.code.toByte() || b[3] != '1'.code.toByte()) {
            return null
        }
        return VideoHeader(u16(b, 4), u16(b, 6), b[8].toInt() and 0xFF)
    }

    fun parsePacketHeader(b: ByteArray): PacketHeader {
        val length = (u16(b, 0) shl 16) or u16(b, 2)
        val flags = b[4].toInt() and 0xFF
        var pts = 0L
        for (i in 5 until 13) pts = (pts shl 8) or (b[i].toLong() and 0xFF)
        return PacketHeader(length, flags, pts)
    }

    private fun u16(b: ByteArray, off: Int) = ((b[off].toInt() and 0xFF) shl 8) or (b[off + 1].toInt() and 0xFF)
}

data class Announce(
    val id: String,
    val name: String,
    val model: String,
    val platform: String,
    val app: String,
    val appId: String,
    val hexrVersion: String,
    val control: Int,
    val video: Int,
    val startedAt: Long,
)

sealed class Message {
    data class Status(val status: HeadsetStatus) : Message()
    data class Error(val request: String, val message: String) : Message()
    data class Welcome(val id: String, val control: Int, val video: Int) : Message()
    data class Haptics(val update: HapticsUpdate) : Message()
    data object Other : Message()
}

data class HeadsetStatus(
    val id: String,
    val name: String,
    val model: String,
    val platform: String,
    val app: String,
    val appVersion: String,
    val hexrVersion: String,
    val paused: Boolean,
    val headsetBatteryPct: Int,
    val scene: SceneInfo,
    val scenes: List<SceneInfo>,
    val gloves: List<GloveState>,
    val stream: StreamState,
    val commands: List<CommandInfo>,
    val allowGloveControl: Boolean,
    val allowVideo: Boolean,
    val exposeScenes: Boolean,
    val controllers: Int,
    /** The app lets this phone recenter the wearer (HexR 0.10.6 with Allow Recenter). */
    val allowRecenter: Boolean = false,
    /** The app sends a "haptics" line for every command (HexR 0.10.2 on). */
    val haptics: Boolean = false,
    /** The headset's clock when it sent this, in microseconds: the one its video is stamped with. */
    val clockUs: Long = 0L,
    /** The last search for gloves in range. Null from a headset before HexR 0.10.6, which cannot search. */
    val gloveSearch: RemoteGloveSearch? = null,
) {
    fun glove(hand: String): GloveState? = gloves.firstOrNull { it.hand.equals(hand, ignoreCase = true) }
}

data class SceneInfo(val index: Int, val name: String)

/** One channel of a "haptics" line: what it started doing. */
data class HapticChannel(
    val finger: Int,            // 0 thumb … 4 pinky, 5 palm
    val mode: String,           // off | pressure | vibration | pulse
    val intensity: Double = 0.0,
    val hz: Double = 0.0,
    val tap: Boolean = false,   // on and off again within one headset frame
)

/** What one glove's channels started doing at `tUs`, on the headset's clock. */
data class HapticsUpdate(val hand: String, val tUs: Long, val channels: List<HapticChannel>)

data class CommandInfo(val id: String, val label: String)

/** The headset's last search for every glove in range. */
data class RemoteGloveSearch(
    val state: String = "idle",     // idle | searching | done | failed
    val message: String = "",
    /** Nearest first. */
    val found: List<NearbyGlove> = emptyList(),
)

data class NearbyGlove(
    val address: String,
    /** What it advertises, e.g. "HaptGloveAR Left". */
    val name: String,
    /** left | right from that name, or "" when it does not say. */
    val hand: String = "",
    /** dBm, nearer 0 is closer; 0 when unknown. */
    val rssi: Int = 0,
)

data class GloveState(
    val hand: String,
    val state: String,
    val message: String,
    val batteryPct: Int,
    /** Thumb, index, middle, ring, pinky, palm, then the source tank. Tenths of a kPa, gauge. */
    val pressureDeciKPa: List<Int>,
    /** The glove this hand keeps to (HexR 0.10.6 on); empty when it takes the first it finds. */
    val savedAddress: String = "",
) {
    val connected get() = state == "connected"
    val connecting get() = state == "connecting"
    val missing get() = state == "missing"

    fun kpa(channel: Int): Double? = pressureDeciKPa.getOrNull(channel)?.let { it / 10.0 }
}

data class StreamState(
    val state: String = "off",
    val port: Int = 0,
    val width: Int = 0,
    val height: Int = 0,
    val viewers: Int = 0,
    val message: String = "",
) {
    val live get() = state == "live" && port > 0
}

data class VideoHeader(val width: Int, val height: Int, val codec: Int)

data class PacketHeader(val length: Int, val flags: Int, val ptsUs: Long) {
    val config get() = flags and RemoteProtocol.FLAG_CONFIG != 0
    val key get() = flags and RemoteProtocol.FLAG_KEY != 0
}
