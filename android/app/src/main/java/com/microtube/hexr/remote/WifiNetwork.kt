package com.microtube.hexr.remote

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import java.net.Socket

/**
 * The Wi-Fi network the headsets are on, so every socket the Headsets tab opens goes over it.
 *
 * At an event the router is often there only to connect the kit, with no internet behind it.
 * Android notices, prefers mobile data for anything not tied to a network, and a phone that can
 * see the headsets' announcements then fails to connect to them. Binding each socket to the Wi-Fi
 * network is what keeps the conversation on the network the headsets are actually on.
 */
class WifiNetwork(context: Context) {

    private val connectivity = context.applicationContext.getSystemService(ConnectivityManager::class.java)

    @Volatile
    var current: Network? = null
        private set

    private var registered = false

    private val callback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) {
            current = network
        }

        override fun onLost(network: Network) {
            if (current == network) current = null
        }
    }

    fun start() {
        if (registered) return
        // No INTERNET requirement: a router with nothing behind it is the case this exists for.
        val request = NetworkRequest.Builder()
            .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
            .removeCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build()
        registered = runCatching { connectivity.registerNetworkCallback(request, callback) }.isSuccess
    }

    fun stop() {
        if (registered) runCatching { connectivity.unregisterNetworkCallback(callback) }
        registered = false
        current = null
    }

    /** A TCP socket on the Wi-Fi network, or an ordinary one if there is no Wi-Fi to bind to. */
    fun newSocket(): Socket = current?.socketFactory?.createSocket() ?: Socket()
}
