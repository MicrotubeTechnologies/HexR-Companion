package com.microtube.hexr.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.microtube.hexr.HexrViewModel
import com.microtube.hexr.LEFT
import com.microtube.hexr.MAX_FREQUENCY_HZ
import com.microtube.hexr.RIGHT

/**
 * The Test tab once a glove is connected: pick channels on the glove itself, set the drive,
 * trigger it. Until then the tab shows [ScanScreen] instead.
 *
 * The whole screen fits 390x844 without scrolling. That is the point of the
 * layout: this is the tab where you are holding a glove in one hand and the
 * phone in the other, and hunting for a control that has scrolled away is worse
 * here than anywhere else in the app.
 *
 * Two explicit actions, no toggle and no latch: Trigger starts, Release all
 * stops. Release all is unconditional and vents every channel, not just the
 * selected ones — a channel deselected mid-drive is still inflated.
 */
@Composable
fun TestScreen(vm: HexrViewModel) {
    val ready = vm.canDrive()
    val g = vm.gloves[vm.hand]

    Column(
        Modifier
            .fillMaxSize()
            .padding(start = T.PAGE_PAD, end = T.PAGE_PAD, top = 14.dp, bottom = T.PAGE_PAD),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {

        HandSegments(
            left = "Left · " + subFor(vm, LEFT),
            right = "Right · " + subFor(vm, RIGHT),
            selected = vm.hand,
            leftEnabled = vm.handConnected(LEFT),
            rightEnabled = vm.handConnected(RIGHT),
            onPick = vm::pickHand,
        )

        // -- the glove ---------------------------------------------------------
        Column(Modifier.weight(1f).fillMaxWidth()) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                SectionLabel("Tap the image to toggle channels", Modifier.weight(1f))
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    ChipButton("All", onClick = vm::selectAll)
                    ChipButton("None", tint = T.TEXT_2, onClick = vm::selectNone)
                }
            }
            Box(
                Modifier.weight(1f).fillMaxWidth(),
                contentAlignment = Alignment.Center,
            ) {
                GloveDiagram(
                    selected = vm.channels,
                    live = { ch -> g?.kpa?.getOrNull(ch) },
                    mirrored = vm.hand == RIGHT,
                    onToggle = vm::toggleChannel,
                )
            }
            Caption(
                "${vm.channels.size} of 6 channels · ${vm.hand.lowercase()} glove" +
                    if (vm.driving) " · driving" else "",
                Modifier.fillMaxWidth(),
                size = Size.MICRO,
            )
        }

        // -- intensity ----------------------------------------------------------
        ControlSlider(
            label = "Intensity",
            value = vm.intensity.toFloat(),
            range = 0f..100f,
            trailing = { MonoText("${vm.intensity}%", color = T.ACCENT) },
            onChange = { vm.intensity = it.toInt() },
        )

        // -- frequency ------------------------------------------------------------
        Column(Modifier.fillMaxWidth()) {
            ControlSlider(
                label = "Frequency",
                value = vm.frequency.toFloat(),
                range = 0f..MAX_FREQUENCY_HZ.toFloat(),
                enabled = vm.frequency > 0,
                trailing = {
                    FrequencyToggle(on = vm.frequency > 0, hz = vm.frequency, onClick = vm::toggleFrequency)
                },
                onChange = { vm.frequency = it.toInt() },
            )
            Caption(
                if (vm.frequency == 0) {
                    "Off · steady pressure, no vibration"
                } else {
                    "Pulsing the channel ${vm.frequency} times a second"
                },
                size = Size.LABEL,
            )
        }

        // -- actions ----------------------------------------------------------------
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            PrimaryButton(
                label = if (vm.driving) "Active" else "Trigger",
                sub = driveSummary(vm),
                enabled = ready,
                active = vm.driving,
                height = 58,
                modifier = Modifier.weight(1f),
                onClick = vm::trigger,
            )
            GhostButton(
                "Release all",
                Modifier.width(88.dp),
                height = 58,
                onClick = vm::release,
            )
        }
    }
}

/**
 * The frequency on/off pill.
 *
 * Zero is a real setting here, not an absent one, so the control reads "Off"
 * rather than "0 Hz" — steady pressure is what the channel does at zero, and a
 * bare zero would suggest nothing happens.
 */
@Composable
private fun FrequencyToggle(on: Boolean, hz: Int, onClick: () -> Unit) {
    Pill(
        text = if (on) "$hz Hz" else "Off",
        color = if (on) T.ACCENT else T.TEXT_2,
        fill = if (on) T.ACCENT.copy(alpha = 0.16f) else T.CARD,
        border = if (on) T.ACCENT else T.BORDER,
        onClick = onClick,
    )
}

private fun subFor(vm: HexrViewModel, hand: String): String =
    if (vm.handConnected(hand)) "connected" else "not connected"

/** Says exactly what Trigger will do, so nobody has to read back up the screen. */
private fun driveSummary(vm: HexrViewModel): String {
    if (!vm.handConnected()) return "${vm.hand.lowercase()} glove not connected"
    val n = vm.channels.size
    if (n == 0) return "no channels selected"
    val shape = if (vm.frequency > 0) "${vm.frequency} Hz" else "steady"
    return "$n channel${if (n == 1) "" else "s"} · ${vm.intensity}% · $shape"
}
