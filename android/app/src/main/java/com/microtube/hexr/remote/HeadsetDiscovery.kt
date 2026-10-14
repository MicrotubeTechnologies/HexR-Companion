package com.microtube.hexr.remote

import android.content.Context
import android.net.wifi.WifiManager
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetSocketAddress
import java.net.SocketTimeoutException
import kotlin.concurrent.thread

/**
 * Listens for HexR headsets announcing themselves on the local network.
 *
 * Every headset running a HexR app with HexR Remote broadcasts a small JSON announcement on
 * UDP 47800 every two seconds. The headset's address is taken from where the packet came
 * from; the announcement carries the ports to use.
 *
 * Android's Wi-Fi driver drops broadcast packets to save power unless an app holds a multicast
 * lock, so one is held exactly while the Headsets tab is listening, and released the moment it
 * stops: holding it costs battery.
 */
class HeadsetDiscovery(
    context: Context,
    private val wifi: WifiNetwork,
    private val onAnnounce: (Announce, String) -> Unit,
) {

    private val wifiManager = context.applicationContext.getSystemService(WifiManager::class.java)

    @Volatile
    private var running = false

    @Volatile
    private var socket: DatagramSocket? = null

    private var lock: WifiManager.MulticastLock? = null

    fun start() {
        if (running) return
        running = true
        lock = runCatching {
            wifiManager.createMulticastLock("hexr-headsets").apply {
                setReferenceCounted(false)
                acquire()
            }
        }.getOrNull()
        thread(name = "HexRHeadsetDiscovery", isDaemon = true) { listen() }
    }

    fun stop() {
        running = false
        runCatching { socket?.close() }
        runCatching { lock?.release() }
        lock = null
    }

    private fun listen() {
        val buffer = ByteArray(4096)
        while (running) {
            try {
                DatagramSocket(null).use { s ->
                    socket = s
                    s.reuseAddress = true
                    s.broadcast = true
                    s.bind(InetSocketAddress(RemoteProtocol.DISCOVERY_PORT))
                    val boundTo = wifi.current
                    boundTo?.let { runCatching { it.bindSocket(s) } }
                    s.soTimeout = 1000

                    // Re-open when the Wi-Fi network changes, so the socket follows the phone
                    // from one router to the next rather than listening on one it has left.
                    while (running && wifi.current == boundTo) {
                        val packet = DatagramPacket(buffer, buffer.size)
                        try {
                            s.receive(packet)
                        } catch (e: SocketTimeoutException) {
                            continue
                        }

                        val host = packet.address?.hostAddress ?: continue
                        val text = String(packet.data, packet.offset, packet.length, Charsets.UTF_8)
                        RemoteProtocol.parseAnnounce(text)?.let { onAnnounce(it, host) }
                    }
                }
            } catch (e: Exception) {
                // Port busy or no network yet. Try again shortly rather than give up for good.
                if (running) Thread.sleep(1000)
            }
        }
        socket = null
    }
}
