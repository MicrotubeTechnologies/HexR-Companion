package com.microtube.hexr.remote

import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaFormat
import android.os.Build
import android.util.Log
import android.view.Surface
import java.io.BufferedInputStream
import java.io.DataInputStream
import java.net.InetSocketAddress
import kotlin.concurrent.thread

/**
 * Plays one headset's view: reads its video stream and decodes it straight onto a Surface.
 *
 * The bytes never touch Compose. The headset sends H.264 at up to 30 frames a second, and the
 * only things the UI needs from it are whether it is playing and the picture's size.
 *
 * Every frame is rendered the moment it is decoded rather than at its timestamp: this is a live
 * view of someone's hands, and a smooth picture half a second late is worse than a slightly
 * uneven one that is current.
 *
 * [shown] is the frame on screen: its presentation time and when it arrived. The glove panels
 * beside the view read it to light up with the touch that frame shows (see HapticsTimeline).
 */
class VideoPlayer(
    private val host: String,
    private val port: Int,
    private val surface: Surface,
    private val wifi: WifiNetwork,
    private val onState: (VideoState) -> Unit,
) {

    /** A frame sent to the screen: its presentation time, and when it arrived, in seconds. */
    class Shown(val ptsUs: Long, val arrivedS: Double)

    @Volatile
    var shown: Shown? = null
        private set

    // When each frame still in the decoder arrived, by its presentation time.
    private val arrivals = HashMap<Long, Double>()

    sealed class VideoState {
        data object Connecting : VideoState()
        data class Playing(val width: Int, val height: Int) : VideoState()
        data class Failed(val message: String) : VideoState()
    }

    @Volatile
    private var running = false

    @Volatile
    private var socket: java.net.Socket? = null

    private var worker: Thread? = null

    fun start() {
        if (running) return
        running = true
        worker = thread(name = "HexRVideo", isDaemon = true) { play() }
    }

    /**
     * Stops and waits briefly for the decoder to let go of the surface, so the view can release
     * it afterwards without the decoder rendering into a surface that is gone.
     */
    fun stop() {
        running = false
        runCatching { socket?.close() }
        runCatching { worker?.join(STOP_WAIT_MS) }
    }

    private fun play() {
        var codec: MediaCodec? = null
        try {
            onState(VideoState.Connecting)
            val s = wifi.newSocket()
            socket = s
            s.tcpNoDelay = true
            s.receiveBufferSize = 512 * 1024
            s.connect(InetSocketAddress(host, port), CONNECT_TIMEOUT_MS)
            s.soTimeout = READ_TIMEOUT_MS
            val input = DataInputStream(BufferedInputStream(s.getInputStream(), 256 * 1024))

            val headerBytes = ByteArray(RemoteProtocol.VIDEO_HEADER_BYTES)
            input.readFully(headerBytes)
            val header = RemoteProtocol.parseVideoHeader(headerBytes)
                ?: throw IllegalStateException("That is not a HexR video stream.")
            if (header.codec != RemoteProtocol.CODEC_H264) {
                throw IllegalStateException("The headset sent a video format this phone does not know.")
            }

            val decoder = MediaCodec.createDecoderByType(MIME)
            codec = decoder
            val format = MediaFormat.createVideoFormat(MIME, header.width, header.height)
            format.setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, MAX_INPUT_BYTES)
            if (Build.VERSION.SDK_INT >= 30 && supportsLowLatency(decoder)) {
                format.setInteger(MediaFormat.KEY_LOW_LATENCY, 1)
            }
            decoder.configure(format, surface, null, 0)
            decoder.start()

            val packetHeader = ByteArray(RemoteProtocol.PACKET_HEADER_BYTES)
            val info = MediaCodec.BufferInfo()
            var shown = false
            while (running) {
                input.readFully(packetHeader)
                val packet = RemoteProtocol.parsePacketHeader(packetHeader)
                if (packet.length <= 0 || packet.length > RemoteProtocol.MAX_PACKET_BYTES) {
                    throw IllegalStateException("The video stream is damaged.")
                }

                val data = ByteArray(packet.length)
                input.readFully(data)
                if (!packet.config) {
                    arrivals[packet.ptsUs] = nowS()
                    if (arrivals.size > MAX_ARRIVALS) arrivals.keys.minOrNull()?.let(arrivals::remove)
                }

                // Wait for room rather than drop: a dropped frame breaks the picture until the
                // next keyframe, up to a second away. Draining the output meanwhile is what frees it.
                var index = -1
                while (running && index < 0) {
                    index = decoder.dequeueInputBuffer(INPUT_WAIT_US)
                    if (drain(decoder, info) && !shown) {
                        shown = true
                        onState(VideoState.Playing(width(decoder, header.width), height(decoder, header.height)))
                    }
                }
                if (index < 0) break

                val buffer = decoder.getInputBuffer(index) ?: continue
                buffer.clear()
                if (data.size > buffer.capacity()) {
                    decoder.queueInputBuffer(index, 0, 0, packet.ptsUs, 0)
                    continue
                }
                buffer.put(data)
                decoder.queueInputBuffer(
                    index, 0, data.size, packet.ptsUs,
                    if (packet.config) MediaCodec.BUFFER_FLAG_CODEC_CONFIG else 0,
                )

                if (drain(decoder, info) && !shown) {
                    shown = true
                    onState(VideoState.Playing(width(decoder, header.width), height(decoder, header.height)))
                }
            }
        } catch (e: Exception) {
            if (running) {
                Log.w(TAG, "Video from $host:$port stopped", e)
                onState(VideoState.Failed(e.message ?: "The video connection closed."))
            }
        } finally {
            runCatching { codec?.stop() }
            runCatching { codec?.release() }
            runCatching { socket?.close() }
            socket = null
        }
    }

    /** Renders whatever is decoded. True if at least one frame went to the screen. */
    private fun drain(codec: MediaCodec, info: MediaCodec.BufferInfo): Boolean {
        var rendered = false
        while (true) {
            val out = codec.dequeueOutputBuffer(info, 0)
            when {
                out >= 0 -> {
                    codec.releaseOutputBuffer(out, info.size > 0)
                    if (info.size > 0) {
                        rendered = true
                        shown = Shown(info.presentationTimeUs, arrivals.remove(info.presentationTimeUs) ?: nowS())
                    }
                }
                out == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> Unit
                else -> return rendered
            }
        }
    }

    private fun width(codec: MediaCodec, fallback: Int): Int = runCatching {
        val f = codec.outputFormat
        if (f.containsKey("crop-right")) f.getInteger("crop-right") - f.getInteger("crop-left") + 1 else f.getInteger(MediaFormat.KEY_WIDTH)
    }.getOrDefault(fallback)

    private fun height(codec: MediaCodec, fallback: Int): Int = runCatching {
        val f = codec.outputFormat
        if (f.containsKey("crop-bottom")) f.getInteger("crop-bottom") - f.getInteger("crop-top") + 1 else f.getInteger(MediaFormat.KEY_HEIGHT)
    }.getOrDefault(fallback)

    private fun supportsLowLatency(codec: MediaCodec): Boolean = runCatching {
        codec.codecInfo.getCapabilitiesForType(MIME)
            .isFeatureSupported(MediaCodecInfo.CodecCapabilities.FEATURE_LowLatency)
    }.getOrDefault(false)

    companion object {
        /** The clock frames are timed on: monotonic, in seconds, the one the haptics use too. */
        fun nowS(): Double = android.os.SystemClock.elapsedRealtimeNanos() / 1e9

        private const val MAX_ARRIVALS = 64
        private const val TAG = "HexRVideo"
        private const val MIME = MediaFormat.MIMETYPE_VIDEO_AVC
        private const val CONNECT_TIMEOUT_MS = 3000
        private const val READ_TIMEOUT_MS = 5000
        private const val INPUT_WAIT_US = 10_000L
        private const val MAX_INPUT_BYTES = 2 * 1024 * 1024
        private const val STOP_WAIT_MS = 500L
    }
}
