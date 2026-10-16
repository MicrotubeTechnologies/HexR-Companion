package com.microtube.hexr

import com.microtube.hexr.remote.Box
import com.microtube.hexr.remote.CastLayout
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Where a headset's view and its gloves go on the phone, and the Connect screen's search. */
class CastAndSearchTest {

    @Test
    fun landscapeGivesTheViewThreeQuartersAndTheGlovesTheRest() {
        val b = CastLayout.landscape(800f, 400f, gap = 8f, head = 30f, pad = 8f)
        assertEquals(596f, b.view.w, 1e-3f)
        assertEquals(400f, b.view.h, 1e-3f)
        for (cell in listOf(b.left, b.right)) {
            assertTrue(cell.x >= b.view.right && cell.right <= 800.01f && cell.bottom <= 400.01f)
        }
        // Left first: above, or to the left.
        assertTrue(b.left.y < b.right.y || b.left.x < b.right.x)
    }

    @Test
    fun portraitPutsTheViewAcrossTheTopAndTheGlovesUnder() {
        val b = CastLayout.portrait(360f, 600f, aspect = 1f, gap = 8f, minPanels = 170f, head = 30f, pad = 8f)
        assertEquals(Box(0f, 0f, 360f, 340f), b.view)
        assertTrue(b.left.y >= b.view.bottom && b.right.y >= b.view.bottom)
        // A wide view is shown whole and leaves the gloves more.
        val wide = CastLayout.portrait(360f, 600f, aspect = 16f / 9, gap = 8f, minPanels = 170f, head = 30f, pad = 8f)
        assertEquals(202.5f, wide.view.h, 1e-3f)
    }

    @Test
    fun twoPanelsTakeWhicheverShapeDrawsTheGloveBigger() {
        val (l, r) = CastLayout.twoPanels(Box(0f, 0f, 200f, 600f), 8f, 30f, 8f)
        assertTrue(l.y < r.y)                                   // tall room: stacked
        val (l2, r2) = CastLayout.twoPanels(Box(0f, 0f, 600f, 200f), 8f, 30f, 8f)
        assertTrue(l2.x < r2.x)                                 // wide room: side by side
    }

    @Test
    fun aSquareViewIsCutWideLowAndAWideOneShownWhole() {
        val cut = CastLayout.videoRect(Box(0f, 0f, 400f, 300f), 1024, 1024)
        assertEquals(Box(0f, -67.5f, 400f, 400f), cut)          // more off the top than the bottom
        val whole = CastLayout.videoRect(Box(0f, 0f, 400f, 300f), 1920, 1080)
        assertEquals(400f, whole.w, 1e-3f)
        assertEquals(225f, whole.h, 1e-3f)
        assertEquals(37.5f, whole.y, 1e-3f)
    }

    @Test
    fun theSearchForgetsQuietGlovesAndPutsTheStrongestFirst() {
        val seen = mutableMapOf(
            "A" to Seen(Found("AA:BB:CC:DD:23:07", "HaptGloveAR Left", LEFT, -71), 0L),
            "B" to Seen(Found("AA:BB:CC:DD:44:01", "HaptGloveAR Left", LEFT, -58), 15_000L),
            "C" to Seen(Found("AA:BB:CC:DD:55:02", "HaptGloveAR Right", RIGHT, null), 15_000L),
        )
        assertEquals(listOf("B", "A"), GloveSearch.candidates(seen.values, LEFT).map { f -> seen.entries.first { it.value.found == f }.key })
        GloveSearch.prune(seen, 20_500L)
        assertEquals(setOf("B", "C"), seen.keys)
        assertEquals("23:07", GloveSearch.shortAddress("AA:BB:CC:DD:23:07"))
    }

    @Test
    fun signalIsFourBars() {
        assertEquals(listOf(4, 3, 3, 2, 2, 1, 0),
            listOf(-60, -61, -70, -71, -80, -81, null).map(GloveSearch::signalBars))
    }
}
