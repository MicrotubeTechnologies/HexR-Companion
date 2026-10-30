package com.microtube.hexr

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Every glove's own name, from its address. The reference names are the desktop's
 * tests/test_glovenames.py ones: every HEXR Companion has to give a glove the same name.
 */
class GloveNamesTest {
    private val reference = mapOf(
        "D4:3D:39:A1:B2:C3" to ("Fiery Panther 3" to "火焰黑豹3号"),
        "D4:3D:39:D4:E5:F6" to ("Velvet Finch 5" to "丝绒雀鸟5号"),
        "00:00:00:00:00:00" to ("Swift Finch 1" to "飞速雀鸟1号"),
        "FF:FF:FF:FF:FF:FF" to ("Swift Squirrel 2" to "飞速松鼠2号"),
        "C8:F0:9E:12:34:56" to ("Zesty Kiwi 2" to "热情几维鸟2号"),
    )

    @Test
    fun namesMatchTheReferenceEveryCompanionUses() {
        for ((address, names) in reference) {
            assertEquals(address, names.first, GloveNames.autoName(address))
            assertEquals(address, names.second, GloveNames.autoName(address, chinese = true))
        }
    }

    @Test
    fun theWayAnAddressIsWrittenDoesNotChangeTheName() {
        assertEquals("Fiery Panther 3", GloveNames.autoName("d4:3d:39:a1:b2:c3"))
        assertEquals("Fiery Panther 3", GloveNames.autoName("D43D39A1B2C3"))
    }

    @Test
    fun theWordsAreAllDifferent() {
        for (words in listOf(GloveNames.ADJECTIVES, GloveNames.ANIMALS)) {
            assertEquals(64, words.map { it.first }.toSet().size)
            assertEquals(64, words.map { it.second }.toSet().size)
        }
    }
}
