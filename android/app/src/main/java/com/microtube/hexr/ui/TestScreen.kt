package com.microtube.hexr.ui

import android.os.SystemClock
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.microtube.hexr.HexrViewModel
import com.microtube.hexr.LEFT
import com.microtube.hexr.Mode
import com.microtube.hexr.Protocol
import com.microtube.hexr.RIGHT
import com.microtube.hexr.TestSettings
import com.microtube.hexr.glove.GloveLook
import com.microtube.hexr.glove.padState
import com.microtube.hexr.glove.panelSize
import com.microtube.hexr.tr

/**
 * Test the glove by hand: pick fingers, Trigger them, Release all.
 *
 * The glove is the screen: tap a fingertip or the palm to pick it, or tick it in the list under
 * the glove, where each finger also shows its air pressure against where it is set to go. Trigger
 * and Release all sit in a bar along the bottom, within a thumb's reach; what scrolls is above.
 * On a tablet, or a phone on its side wide enough, the controls take a column of their own.
 */
@Composable
fun TestScreen(vm: HexrViewModel, onQuickTest: () -> Unit) {
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val wide = maxWidth >= 600.dp
        val unit = panelSize(1f, GloveLook.TEST)
        if (wide) {
            val gh = minOf((maxWidth.value - 340f - 64f) / unit.width, (maxHeight.value - 72f) / unit.height)
                .coerceIn(150f, 360f)
            Row(Modifier.fillMaxSize()) {
                Column(
                    Modifier.weight(1f).fillMaxHeight().verticalScroll(rememberScrollState()).padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    Glove(vm, gh)
                    Fingers(vm)
                    Details(vm)
                }
                Column(Modifier.width(340.dp).fillMaxHeight()) {
                    Column(
                        Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState()).padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                    ) {
                        TopRow(vm, onQuickTest)
                        Settings(vm)
                    }
                    StickyActionBar { Buttons(vm) }
                }
            }
        } else {
            val gh = minOf((maxWidth.value - 32f) / unit.width, (maxHeight.value - 80f) * .6f / unit.height)
                .coerceIn(150f, 360f)
            Column(Modifier.fillMaxSize()) {
                Column(
                    Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState())
                        .padding(horizontal = T.PAGE_PAD, vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    TopRow(vm, onQuickTest)
                    Glove(vm, gh)
                    Settings(vm)
                    Fingers(vm)
                    Details(vm)
                }
                StickyActionBar { Buttons(vm) }
            }
        }
    }
}

/** Which glove (when both are connected), and the way to the quick test. */
@Composable
private fun TopRow(vm: HexrViewModel, onQuickTest: () -> Unit) {
    val both = vm.handConnected(LEFT) && vm.handConnected(RIGHT)
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        if (both) {
            Segmented(
                listOf(LEFT, RIGHT).map { it to "${tr(it)} · ${vm.gloves[it]?.battery ?: "—"}" },
                vm.hand, Modifier.weight(1f), onPick = vm::pickHand,
            )
        } else {
            val g = vm.gloves[vm.hand]
            Text(
                tr("{hand} glove", "hand" to tr(vm.hand)) + (g?.battery?.takeIf { it != "—" }?.let { " · $it" } ?: ""),
                color = T.TEXT_2, fontSize = P.BODY.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f),
            )
        }
        Spacer(Modifier.width(10.dp))
        ActionButton(tr("Quick test"), style = ActionStyle.Ghost, height = P.TOUCH, onClick = onQuickTest)
    }
}

/** The glove: tap a fingertip to pick it. It glows with what it measures. */
@Composable
private fun Glove(vm: HexrViewModel, gh: Float) {
    val s = vm.settings
    val g = vm.gloves[vm.hand]
    val now = SystemClock.elapsedRealtime()
    val st = padState(
        kpa = if (g?.live == true) g.kpa else null,
        on = vm.driving,
        sincePress = (now - vm.pressedAt) / 1000f,
        sinceRelease = vm.releasedAt?.let { (now - it) / 1000f },
        vibration = s.mode == Mode.Vibration,
        intensity = s.intensity.toFloat(),
        hz = s.frequency.toFloat(),
        channels = vm.channels,
    )
    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
        GloveArt(
            hand = vm.hand, look = GloveLook.TEST, gh = gh.dp, state = st, selected = vm.channels,
            description = tr("{hand} glove", "hand" to tr(vm.hand)), onTap = vm::toggleChannel,
        )
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(
                if (vm.channels.isEmpty()) tr("Pick a finger") else "",
                color = T.TEXT_4, fontSize = P.VALUE.sp, modifier = Modifier.weight(1f),
            )
            TextLink(tr("All"), onClick = vm::selectAll)
            Text("·", color = T.TEXT_5, fontSize = P.VALUE.sp)
            TextLink(tr("None"), onClick = vm::selectNone)
        }
    }
}

/** How it feels: pressure or vibration, how hard, how fast. */
@Composable
private fun Settings(vm: HexrViewModel) {
    val s = vm.settings
    var fine by remember { mutableStateOf(false) }
    Card(Modifier.fillMaxWidth(), fill = T.ELEVATED) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Segmented(
                listOf(Mode.Pressure to tr("Pressure"), Mode.Vibration to tr("Vibration")),
                s.mode, onPick = vm::pickMode,
            )
            Spacer(Modifier.height(4.dp))
            ValueSlider(
                tr("Intensity"), s.intensityLabel(), ((s.intensity - .1) / .9).toFloat(),
                onChange = { vm.setIntensity(.1 + it * .9) },
            )
            if (s.mode == Mode.Vibration) {
                ValueSlider(
                    tr("Frequency"), s.frequencyLabel(), TestSettings.hzToSlider(s.frequency),
                    trailing = {
                        Text(if (s.pulse) tr("Pulse") else tr("Buzz"), color = T.ACCENT, fontSize = P.VALUE.sp, fontWeight = FontWeight.SemiBold)
                    },
                    onChange = { vm.setFrequency(TestSettings.sliderToHz(it)) },
                )
            }
            Disclosure(tr("Fine-tune"), fine, onToggle = { fine = !fine }) {
                if (s.mode == Mode.Pressure) {
                    ValueSlider(
                        tr("Ramp speed"), s.percent(s.speed), ((s.speed - .1) / .9).toFloat(),
                        onChange = { vm.setSpeed(.1 + it * .9) },
                    )
                } else {
                    ValueSlider(
                        tr("Peak ratio"), s.percent(s.peakRatio), ((s.peakRatio - .2) / .6).toFloat(),
                        onChange = { vm.setPeakRatio(.2 + it * .6) },
                    )
                }
            }
        }
    }
}

/** Each finger's air pressure against where it is set to go; tick a row to pick it. */
@Composable
private fun Fingers(vm: HexrViewModel) {
    val g = vm.gloves[vm.hand]
    PressureList(
        kpa = if (g?.live == true) g.kpa else null,
        source = if (g?.live == true) g.source else null,
        picked = vm.channels,
        targetKpa = vm.settings.targetKpa(),
        title = tr("Air pressure"),
        note = if (g?.live == true) null else tr("No readings"),
        onToggle = vm::toggleChannel,
    )
}

@Composable
private fun Details(vm: HexrViewModel) {
    var open by remember { mutableStateOf(false) }
    val g = vm.gloves[vm.hand] ?: return
    Disclosure(tr("Details"), open, onToggle = { open = !open }) {
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            MonoText("${g.name}  ${g.address}", color = T.TEXT_3, size = 12.5f)
            MonoText(
                tr("battery {level}", "level" to g.battery) + "   MTU ${g.mtu ?: "?"}" +
                    if (g.live) "   " + tr("source {kpa} kPa", "kpa" to "%.1f".format(g.source)) else "",
                color = T.TEXT_3, size = 12.5f,
            )
            if (g.absolutePa) {
                Caption(tr("This glove reports absolute pressure; readings are converted to gauge kPa."))
            }
            if (vm.settings.mode == Mode.Vibration) {
                val hz = Protocol.PWM_VIBRATION_HZ.toInt().toString()
                Caption(
                    if (vm.settings.pulse) {
                        tr("Under {hz} Hz the glove vibrates pneumatically: the pressure target is pulsed.", "hz" to hz)
                    } else {
                        tr("At {hz} Hz and above the pressure loop is off and the channel's motor is driven directly.", "hz" to hz)
                    },
                )
            }
        }
    }
}

/** Trigger and Release all, side by side. */
@Composable
private fun androidx.compose.foundation.layout.RowScope.Buttons(vm: HexrViewModel) {
    val s = vm.settings
    val n = vm.channels.size
    ActionButton(
        tr("Trigger"), Modifier.weight(1f),
        sub = if (n == 0) tr("Pick a finger") else tr("{n} fingers", "n" to n) + " · " +
            if (s.mode == Mode.Pressure) s.percent(s.intensity) else s.frequencyLabel(),
        enabled = vm.canDrive(), onClick = vm::trigger,
    )
    ActionButton(
        tr("Release all"), Modifier.weight(1f),
        style = if (vm.driving) ActionStyle.Danger else ActionStyle.Ghost, onClick = vm::release,
    )
}

