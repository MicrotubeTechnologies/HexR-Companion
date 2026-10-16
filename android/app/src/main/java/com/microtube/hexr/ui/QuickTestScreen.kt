package com.microtube.hexr.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.microtube.hexr.HexrViewModel
import com.microtube.hexr.LEFT
import com.microtube.hexr.Outcome
import com.microtube.hexr.Protocol
import com.microtube.hexr.QT_RUNNING
import com.microtube.hexr.QuickTest
import com.microtube.hexr.RIGHT
import com.microtube.hexr.glove.GloveLook
import com.microtube.hexr.glove.HandState
import com.microtube.hexr.glove.Verdict
import com.microtube.hexr.glove.levelFromKpa
import com.microtube.hexr.glove.panelSize
import com.microtube.hexr.glove.verdictState
import com.microtube.hexr.tr
import java.util.Locale

/** A verdict's colour: green, amber, red. */
fun Verdict.colour(): Color = when (this) {
    Verdict.Good -> T.GREEN
    Verdict.Poor -> T.AMBER
    Verdict.Fail -> T.RED
}

/**
 * The quick test: is this glove healthy? One button, one answer, shown on the glove.
 *
 * It drives all six channels to full for two seconds and judges what each reached, against the
 * desktop's thresholds. The answer comes first, in one line (All good, 2 poor, 1 failed, Pump
 * failed), and the glove shows it: each touch point green, amber or red. The numbers behind it
 * are under Details.
 */
@Composable
fun QuickTestScreen(vm: HexrViewModel) {
    val running = vm.qtPhase in QT_RUNNING
    val hand = vm.qtHand
    val g = hand?.let { vm.gloves[it] }
    val result = vm.qtResult.takeIf { vm.qtPhase == "done" }
    var details by remember { mutableStateOf(false) }

    BoxWithConstraints(Modifier.fillMaxSize()) {
        // A phone on its side: the glove on the left, the answer beside it, so neither scrolls away.
        val side = maxWidth >= 600.dp && maxWidth > maxHeight
        val unit = panelSize(1f, GloveLook.QUICK)
        val gh = if (side) {
            minOf((maxWidth.value / 2 - 32f) / unit.width, (maxHeight.value - 160f) / unit.height)
        } else {
            minOf((maxWidth.value - 32f) / unit.width, (maxHeight.value - 80f) * .5f / unit.height)
        }.coerceIn(120f, 320f)

        val picker = @Composable {
            if (vm.handConnected(LEFT) && vm.handConnected(RIGHT) && hand != null) {
                Segmented(listOf(LEFT, RIGHT).map { it to tr(it) }, hand, onPick = vm::pickQuickTestHand)
            }
        }
        val glove = @Composable {
            if (hand != null) {
                val st = when {
                    result != null -> verdictState(result.verdicts, result.outcome == Outcome.PumpFailed)
                    running && g?.live == true -> HandState(levels = g.kpa.map(::levelFromKpa))
                    else -> HandState()
                }
                GloveArt(hand, GloveLook.QUICK, gh.dp, state = st, description = tr("{hand} glove", "hand" to tr(hand)))
            }
        }
        val answer = @Composable {
            if (result != null) {
                Text(result.headline, color = result.verdict.colour(), fontSize = P.HEADLINE.sp,
                    fontWeight = FontWeight.ExtraBold, modifier = Modifier.fillMaxWidth())
                if (result.weak.isNotEmpty()) {
                    Text(
                        result.weak.joinToString(", ") { tr(Protocol.Finger.of(it).label) },
                        color = T.TEXT_2, fontSize = 16.sp, modifier = Modifier.fillMaxWidth(),
                    )
                }
            }
            if (running || vm.qtProgress > 0f) ProgressBar(vm.qtProgress, if (result != null) result.verdict.colour() else T.ACCENT)
            if (vm.qtStatus.isNotEmpty()) {
                Text(vm.qtStatus, color = T.TEXT_3, fontSize = P.VALUE.sp, modifier = Modifier.fillMaxWidth())
            }
            if (result != null) {
                Disclosure(tr("Details"), details, onToggle = { details = !details }) { Evidence(vm) }
            }
        }
        val hint = @Composable {
            Text(tr("Take the glove off first."), color = T.TEXT_2, fontSize = P.BODY.sp,
                modifier = Modifier.fillMaxWidth())
        }

        Column(Modifier.fillMaxSize()) {
            if (side) {
                Row(Modifier.weight(1f).fillMaxWidth()) {
                    Column(
                        Modifier.weight(1f).fillMaxHeight().padding(horizontal = T.PAGE_PAD, vertical = 12.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterVertically),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        picker()
                        glove()
                    }
                    Column(
                        Modifier.weight(1f).fillMaxHeight().verticalScroll(rememberScrollState())
                            .padding(horizontal = T.PAGE_PAD, vertical = 12.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        hint()
                        answer()
                    }
                }
            } else {
                Column(
                    Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState())
                        .padding(horizontal = T.PAGE_PAD, vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    hint()
                    picker()
                    glove()
                    answer()
                }
            }
            StickyActionBar {
                ActionButton(
                    when {
                        running -> "■  " + tr("Stop")
                        result != null -> "▶  " + tr("Run again")
                        else -> "▶  " + tr("Run")
                    },
                    Modifier.weight(1f),
                    style = if (running) ActionStyle.DangerOutline else ActionStyle.Primary,
                    enabled = g?.connected == true,
                    onClick = vm::toggleQuickTest,
                )
            }
        }
    }
}

/** The table behind the answer, and the sentence that explains it. */
@Composable
private fun Evidence(vm: HexrViewModel) {
    val result = vm.qtResult ?: return
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(horizontal = 14.dp, vertical = 8.dp)) {
            Row(Modifier.fillMaxWidth().heightIn(min = 36.dp), verticalAlignment = Alignment.CenterVertically) {
                SectionLabel(tr("Channel"), Modifier.weight(1f))
                SectionLabel(tr("Peak"), Modifier.width(76.dp))
                SectionLabel(tr("Time"), Modifier.width(64.dp))
                SectionLabel(tr("Verdict"), Modifier.width(64.dp))
            }
            for (f in Protocol.ALL_FINGERS) {
                val ch = f.channel
                val v = result.verdicts[ch]
                Row(Modifier.fillMaxWidth().heightIn(min = 44.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(tr(f.label), color = T.TEXT, fontSize = P.VALUE.sp, modifier = Modifier.weight(1f))
                    MonoText(String.format(Locale.US, "%.1f", vm.qtPeaks[ch]), size = P.VALUE, modifier = Modifier.width(76.dp))
                    MonoText(
                        if (vm.qtPeaks[ch] > 0) String.format(Locale.US, "%.2f s", vm.qtTimes[ch]) else "—",
                        color = T.TEXT_2, size = P.VALUE, modifier = Modifier.width(64.dp),
                    )
                    Text(tr(v.name), color = v.colour(), fontSize = P.VALUE.sp, fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.width(64.dp))
                }
            }
        }
    }
    Spacer(Modifier.height(10.dp))
    Caption(QuickTest.summary(result, vm.qtSource), color = T.TEXT_3, size = P.SMALL)
    Spacer(Modifier.height(6.dp))
    Caption(
        tr("Good above {good} kPa, poor from {fail} kPa, failed under {fail} kPa.",
            "good" to QuickTest.GOOD_KPA.toInt(), "fail" to QuickTest.FAIL_KPA.toInt()),
        color = T.TEXT_5, size = P.SMALL,
    )
}
