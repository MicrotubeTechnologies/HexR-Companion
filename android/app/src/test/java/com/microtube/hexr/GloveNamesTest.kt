package com.microtube.hexr

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Every glove's own name, from its address. The reference names are the desktop's
 * tests/test_glovenames.py ones: every HEXR Companion has to give a glove the same name.
 */
class GloveNamesTest {
    private val reference = mapOf(
        "D4:3D:39:A1:B2:C3" to ("Fiery Panther" to "火焰黑豹"),
        "D4:3D:39:D4:E5:F6" to ("Velvet Finch" to "丝绒雀鸟"),
        "00:00:00:00:00:00" to ("Swift Finch" to "飞速雀鸟"),
        "FF:FF:FF:FF:FF:FF" to ("Swift Squirrel" to "飞速松鼠"),
        "C8:F0:9E:12:34:56" to ("Zesty Kiwi" to "热情几维鸟"),
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
        assertEquals("Fiery Panther", GloveNames.autoName("d4:3d:39:a1:b2:c3"))
        assertEquals("Fiery Panther", GloveNames.autoName("D43D39A1B2C3"))
    }

    @Test
    fun theWordsAreAllDifferent() {
        for (words in listOf(GloveNames.ADJECTIVES, GloveNames.ANIMALS)) {
            assertEquals(64, words.map { it.first }.toSet().size)
            assertEquals(64, words.map { it.second }.toSet().size)
        }
    }
}
