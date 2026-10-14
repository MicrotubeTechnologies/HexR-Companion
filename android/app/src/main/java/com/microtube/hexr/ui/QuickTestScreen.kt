package com.microtube.hexr.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.microtube.hexr.HANDS
import com.microtube.hexr.HexrViewModel
import com.microtube.hexr.QuickTest
import com.microtube.hexr.Tone

/**
 * The canned QA sweep, opened from the Quick test button in the header while testing.
 *
 * Drives every channel to full pressure at once, watches what each one reaches
 * and how fast, then judges it. The Test tab is for exploring; this is for
 * deciding.
 *
 * Three verdicts, matching the desktop tester exactly so a result recorded on a
 * phone means what one recorded on a bench laptop means: Good above 40 kPa,
 * Poor down to 2, Fail below that.
 */

private fun verdictColour(verdict: String?): Color = when (verdict) {
    "Good" -> T.GREEN
    "Poor" -> T.AMBER
    "Fail" -> T.RED
    else -> T.TEXT_4
}

@Composable
fun QuickTestScreen(vm: HexrViewModel) {
    val running = vm.qtPhase == "settle" || vm.qtPhase == "drive"
    val done = vm.qtPhase == "done"
    var legendOpen by remember { mutableStateOf(false) }

    Column(
        Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(T.PAGE_PAD),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        // The panel it opens in carries the title.
        Caption(
            "Drives every channel to full for two seconds and reports what each one " +
                "reached. Take the glove off first.",
            color = T.TEXT_2,
        )

        Column {
            SectionLabel("Glove to test")
            VSpace(8)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                HANDS.forEach { hand ->
                    val g = vm.gloves[hand]
                    val live = g?.connected == true
                    HandCard(
                        hand = hand,
                        sub = if (live) "connected" else "not connected",
                        selected = live && vm.qtHand == hand,
                        enabled = live && !running,
                        modifier = Modifier.weight(1f),
                        onClick = { vm.qtHand = hand },
                    )
                }
            }
        }

        if (running) {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp)) {
                    Label(
                        vm.qtStatus.ifEmpty { "Driving all channels…" },
                        color = T.ACCENT,
                        weight = FontWeight.SemiBold,
                    )
                    VSpace(12)
                    ProgressBar(vm.qtProgress)
                    VSpace(10)
                    Caption("Every channel is at full pressure. Keep the glove off your hand.")
                }
            }
        }

        // The answer, before the evidence.
        if (done) {
            VerdictBanner(
                headline = vm.qtStatus,
                detail = vm.qtSummary,
                ok = vm.qtStatusTone == Tone.Success,
            )
        }

        PrimaryButton(
            when {
                running -> "Stop"
                done -> "Run again"
                else -> "Run quick test"
            },
            Modifier.fillMaxWidth(),
            active = running,
            onClick = vm::toggleQuickTest,
        )
        if (!running && !done && vm.qtStatus.isNotEmpty()) {
            Caption(vm.qtStatus, color = vm.qtStatusTone.color())
        }

        Card(Modifier.fillMaxWidth()) {
            Column {
                vm.qtRows.forEachIndexed { i, row ->
                    TableRow {
                        Column(Modifier.weight(1f)) {
                            Label(row.label, size = Size.BODY, weight = FontWeight.SemiBold)
                            if (row.verdict != null) {
                                Label(
                                    row.verdict +
                                        (row.timeToPeak?.let { " · %.2f s".format(it) } ?: ""),
                                    color = verdictColour(row.verdict),
                                    size = Size.LABEL,
                                    weight = FontWeight.SemiBold,
                                    modifier = Modifier.padding(top = 2.dp),
                                )
                            }
                        }
                        MonoText(
                            row.peak?.let { "%.1f".format(it) } ?: "—",
                            Modifier.width(56.dp),
                            if (row.peak == null) T.TEXT_FAINT else verdictColour(row.verdict),
                            size = Size.BODY,
                            weight = FontWeight.Bold,
                        )
                    }
                    if (i < vm.qtRows.lastIndex) Hairline()
                }
            }
        }

        Disclosure(
            title = "What the verdicts mean",
            expanded = legendOpen,
            onToggle = { legendOpen = !legendOpen },
        ) {
            Card(Modifier.fillMaxWidth()) {
                Column {
                    listOf(
                        "Good" to "above ${QuickTest.GOOD_KPA.toInt()} kPa · full pressure",
                        "Poor" to "${QuickTest.FAIL_KPA.toInt()}–${QuickTest.GOOD_KPA.toInt()} kPa · moved, but never got to full",
                        "Fail" to "under ${QuickTest.FAIL_KPA.toInt()} kPa · not working",
                    ).forEachIndexed { i, (verdict, meaning) ->
                        TableRow {
                            Column {
                                Label(
                                    verdict,
                                    color = verdictColour(verdict),
                                    size = Size.CAPTION,
                                    weight = FontWeight.SemiBold,
                                )
                                Caption(meaning, Modifier.padding(top = 1.dp), size = Size.LABEL)
                            }
                        }
                        if (i < 2) Hairline()
                    }
                }
            }
            VSpace(10)
            Caption(
                "A Poor channel is working but under strength — usually its tubing. If the " +
                    "source itself never develops pressure the summary says so once, rather " +
                    "than blaming six channels for one dead pump.",
            )
        }

        VSpace(8)
    }
}
