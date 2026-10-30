package com.microtube.hexr

/** A glove the search has heard, and when it last did. */
data class Seen(val found: Found, val seenAt: Long)

/**
 * The Connect screen's search, as the desktop's: gloves heard recently, strongest first, and how
 * strong as bars. A glove not heard for a while has been switched off or carried away.
 */
object GloveSearch {
    const val EXPIRE_MS = 20_000L
    const val RESCAN_MS = 1_500L        // after a search ends, the next one starts this soon
    const val FULL_RESCAN_MS = 6_000L   // or this, with both hands connected: the list stays fresh
    const val RETRY_MS = 10_000L        // or this, after Bluetooth said no

    /** Forget the gloves not heard from in [EXPIRE_MS]. */
    fun prune(seen: MutableMap<String, Seen>, now: Long) {
        seen.entries.removeAll { now - it.value.seenAt > EXPIRE_MS }
    }

    /** One hand's gloves, strongest signal first. */
    fun candidates(seen: Collection<Seen>, hand: String): List<Found> =
        seen.map { it.found }.filter { it.hand == hand }.sortedByDescending { it.rssi ?: Int.MIN_VALUE }

    /** Signal strength as four bars. */
    fun signalBars(rssi: Int?): Int = when {
        rssi == null -> 0
        rssi >= -60 -> 4
        rssi >= -70 -> 3
        rssi >= -80 -> 2
        else -> 1
    }

    /** How two kits of one hand are told apart: the end of the address, e.g. "23:07". */
    fun shortAddress(address: String) = address.takeLast(5)
}
