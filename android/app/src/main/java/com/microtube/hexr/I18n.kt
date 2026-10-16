package com.microtube.hexr

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/**
 * English and Simplified Chinese, the way the desktop does it (`hexr/i18n.py`): the English
 * sentence is the key, and [ZH] holds its Chinese. `tr("Connect a glove")` gives whichever the
 * user picked; `{name}` in it is filled from the pairs, `tr("{n} poor", "n" to 2)`.
 *
 * The language is Compose state, so switching redraws every screen at once, with no restart
 * and nothing about the gloves or headsets lost. It is kept in SharedPreferences by the
 * activity, and the first run follows the phone's own language.
 *
 * Words drawn into the glove picture (PRESS. HOLD. RELEASE., the finger names) stay English, as
 * they do on the desktop and the website: they are part of the picture.
 *
 * I18nTest checks that every tr("…") in the source has its Chinese and that nothing in [ZH] is
 * left over from text the app no longer shows.
 */
object I18n {
    const val EN = "en"
    const val ZH_CN = "zh"

    var language by mutableStateOf(EN)

    fun tr(text: String, vararg args: Pair<String, Any?>): String {
        var out = if (language == ZH_CN) ZH[text] ?: text else text
        for ((name, value) in args) out = out.replace("{$name}", value.toString())
        return out
    }
}

fun tr(text: String, vararg args: Pair<String, Any?>): String = I18n.tr(text, *args)
