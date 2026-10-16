package com.microtube.hexr

import com.microtube.hexr.glove.Verdict
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Every sentence the app shows through tr() has its Chinese, and the Chinese table holds nothing
 * the app no longer shows: the desktop's test_i18n.py, read off the Kotlin source.
 */
class I18nTest {

    @After
    fun english() {
        I18n.language = I18n.EN
    }

    /**
     * tr("…") and N_("…") literals in the app's source, unescaped, with a sentence written as
     * "…" + "…" across lines joined back up. Comments are left out: they quote tr("…") too.
     */
    private fun literals(): Set<String> {
        val src = File("src/main/java")
        assertTrue("run from the app module: ${src.absolutePath}", src.isDirectory)
        val lit = """"(?:[^"\\]|\\.)*""""
        val call = Regex("""\b(?:tr|N_)\(\s*($lit(?:\s*\+\s*$lit)*)""")
        val part = Regex(lit)
        val comments = Regex("""/\*[\s\S]*?\*/|(?m)^\s*//.*$""")
        return src.walkTopDown().filter { it.extension == "kt" }.flatMap { f ->
            call.findAll(f.readText().replace(comments, "")).map { m ->
                part.findAll(m.groupValues[1]).joinToString("") { p ->
                    p.value.drop(1).dropLast(1)
                        .replace("\\\"", "\"").replace("\\$", "$").replace("\\n", "\n").replace("\\\\", "\\")
                }
            }
        }.toSet()
    }

    /** Text that reaches tr() through a value rather than a literal. */
    private val dynamic: Set<String> =
        HANDS.toSet() + Protocol.ALL_FINGERS.map { it.label } + Verdict.entries.map { it.name }

    @Test
    fun everyShownSentence_hasItsChinese() {
        val missing = (literals() + dynamic).filter { it !in ZH }.sorted()
        assertTrue("no Chinese for:\n" + missing.joinToString("\n"), missing.isEmpty())
    }

    @Test
    fun noChinese_isLeftOverFromTextTheAppNoLongerShows() {
        val shown = literals() + dynamic
        val stale = ZH.keys.filter { it !in shown }.sorted()
        assertTrue("stale Chinese for:\n" + stale.joinToString("\n"), stale.isEmpty())
    }

    @Test
    fun placeholders_surviveTheTranslation() {
        val name = Regex("""\{(\w+)\}""")
        for ((en, zh) in ZH) {
            assertEquals(en, name.findAll(en).map { it.value }.toSet(), name.findAll(zh).map { it.value }.toSet())
        }
    }

    @Test
    fun switching_changesTheWordsAndFillsTheirValues() {
        assertEquals("2 poor", tr("{n} poor", "n" to 2))
        I18n.language = I18n.ZH_CN
        assertEquals("2 个偏弱", tr("{n} poor", "n" to 2))
        assertEquals("no such sentence", tr("no such sentence"))
    }
}
