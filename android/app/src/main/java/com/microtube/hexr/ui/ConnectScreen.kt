package com.microtube.hexr.ui

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.microtube.hexr.HANDS
import com.microtube.hexr.HexrViewModel
import com.microtube.hexr.R

/**
 * Finding gloves and connecting them, in the two places the Test tab needs it.
 *
 * [ScanScreen] is the Test tab itself while no glove is connected: there is nothing to test
 * yet, so the one thing on screen is the way to get a glove. The moment one connects, the
 * tab turns into the test controls on its own. [GlovesPanel] is the same list behind the
 * Bluetooth button in the header once testing has started: the second glove, battery and
 * source pressure, MTU, Disconnect.
 *
 * A kit is a left glove and a right glove, and they are independent BLE peripherals. Both can
 * be connected at once and the rest of the app treats them separately throughout, so this is a
 * list you connect from rather than a chooser you pick one out of.
 */
@Composable
fun ScanScreen(vm: HexrViewModel, onOpenBluetoothSettings: () -> Unit) {
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(T.PAGE_PAD),
        verticalArrangement = Arrangement.spacedBy(18.dp),
    ) {
        Column(
            Modifier.fillMaxWidth().padding(top = 28.dp, bottom = 4.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            ScanBeacon(scanning = vm.scanning)
            VSpace(20)
            Title("Connect a HEXR glove")
            Caption(
                "Switch on the arm module, then scan. Left and right are separate devices: " +
                    "connect either, or both. Testing starts as soon as one connects.",
                Modifier.padding(top = 6.dp),
                T.TEXT_2,
                textAlign = TextAlign.Center,
            )
        }

        BluetoothOffCard(vm, onOpenBluetoothSettings)
        ScanButton(vm, "Scan for HEXR", height = 56)
        FoundList(vm)
        GloveCards(vm)

        BuildLine(vm)
        VSpace(8)
    }
}

/** Behind the header's Bluetooth button while testing. */
@Composable
fun GlovesPanel(vm: HexrViewModel, onOpenBluetoothSettings: () -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(T.PAGE_PAD),
        verticalArrangement = Arrangement.spacedBy(18.dp),
    ) {
        BluetoothOffCard(vm, onOpenBluetoothSettings)
        ScanButton(vm, "Scan for gloves")
        FoundList(vm)

        val cards = GloveCards(vm)
        if (vm.found.isEmpty() && !cards) {
            Card(Modifier.fillMaxWidth()) {
                EmptyNote("No gloves yet. Press scan with the arm module switched on.")
            }
        }

        BuildLine(vm)
        VSpace(8)
    }
}

// -- pieces -------------------------------------------------------------------------

/**
 * Permission is handled by the gate in front of the whole app, so the only thing scanning can
 * be blocked on is the radio, which the user can flip at any moment and which is otherwise
 * invisible.
 */
@Composable
private fun BluetoothOffCard(vm: HexrViewModel, onOpenBluetoothSettings: () -> Unit) {
    if (vm.bluetoothOn) return
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Label("Bluetooth is switched off", weight = FontWeight.SemiBold)
            Caption(
                "Turn the phone's radio on and this clears on its own.",
                Modifier.padding(top = 6.dp),
                T.TEXT_2,
            )
            VSpace(14)
            PrimaryButton(
                "Open Bluetooth settings",
                Modifier.fillMaxWidth(),
                onClick = onOpenBluetoothSettings,
            )
        }
    }
}

@Composable
private fun ScanButton(vm: HexrViewModel, label: String, height: Int = 50) {
    Column {
        PrimaryButton(
            if (vm.scanning) "Scanning…" else label,
            Modifier.fillMaxWidth(),
            enabled = vm.bluetoothOn && !vm.scanning,
            height = height,
            onClick = vm::startScan,
        )
        Caption(
            if (vm.bluetoothOn) vm.scanStatus else "Turn Bluetooth on first",
            Modifier.padding(top = 10.dp),
            if (vm.bluetoothOn) vm.scanTone.color() else T.TEXT_5,
        )
    }
}

@Composable
private fun FoundList(vm: HexrViewModel) {
    if (vm.found.isEmpty()) return
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        vm.found.forEach { f ->
            val g = vm.gloves[f.hand]
            val busy = g != null && (g.connected || g.connecting)
            Card(
                Modifier.fillMaxWidth(),
                fill = T.CARD,
                border = T.BORDER_SOFT,
                radius = T.R_CARD,
            ) {
                Row(
                    Modifier
                        .fillMaxWidth()
                        .clickable(enabled = !busy) { vm.connect(f) }
                        .padding(horizontal = 14.dp, vertical = 13.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Dot(if (busy) T.TEXT_FAINT else T.GREEN, size = 7)
                    Column(Modifier.weight(1f)) {
                        Label(f.name, size = Size.BODY, weight = FontWeight.SemiBold)
                        MonoText(
                            f.address + (f.rssi?.let { " · $it dBm" } ?: ""),
                            Modifier.padding(top = 2.dp),
                            T.TEXT_5,
                            Size.LABEL,
                        )
                    }
                    Pill(f.hand)
                    if (!busy) {
                        Label(
                            "Connect",
                            color = T.ACCENT,
                            size = Size.BODY_2,
                            weight = FontWeight.SemiBold,
                        )
                    }
                }
            }
        }
    }
}

/** A card per glove that is connected or connecting. Returns whether there was any. */
@Composable
private fun GloveCards(vm: HexrViewModel): Boolean {
    val cards = HANDS.mapNotNull { vm.gloves[it] }.filter { it.connected || it.connecting }
    if (cards.isEmpty()) return false
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        SectionLabel("Connected")
        cards.forEach { g ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp)) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(9.dp),
                    ) {
                        Label(
                            "${g.hand} glove",
                            Modifier.weight(1f),
                            size = Size.BODY,
                            weight = FontWeight.SemiBold,
                        )
                        when {
                            g.connecting -> Pill("connecting", color = T.TEXT_2)
                            g.live -> Pill(
                                "streaming",
                                color = T.GREEN,
                                fill = T.GREEN.copy(alpha = 0.12f),
                                border = T.GREEN.copy(alpha = 0.35f),
                            )
                            // Connected and usable — it simply is not
                            // reporting pressure. Flagged quietly, not
                            // as a fault: haptics work either way.
                            g.connected -> Pill("connected", color = T.GREEN)
                            else -> Pill(g.status, color = T.TEXT_2)
                        }
                    }

                    VSpace(12)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        StatTile("Battery", g.battery, Modifier.weight(1f))
                        StatTile(
                            "Source kPa",
                            if (g.live) "%.1f".format(g.source) else "—",
                            Modifier.weight(1f),
                        )
                    }

                    VSpace(10)
                    MonoText(
                        g.address + (g.mtu?.let { "   MTU $it" } ?: ""),
                        color = T.TEXT_5,
                        size = Size.LABEL,
                    )
                    if (g.mtu != null && g.mtu < SMALL_MTU) {
                        Caption(
                            "This glove kept a small MTU, so six-channel commands go " +
                                "out as several writes instead of one.",
                            Modifier.padding(top = 8.dp),
                        )
                    }

                    VSpace(14)
                    GhostButton(
                        "Disconnect",
                        Modifier.fillMaxWidth(),
                        tint = T.RED,
                        onClick = { vm.disconnect(g.hand) },
                    )
                }
            }
        }
    }
    return true
}

/**
 * The scan screen's centrepiece: the Bluetooth rune in a ring that breathes while a scan runs,
 * so a scan that is still going looks different from one that found nothing.
 */
@Composable
private fun ScanBeacon(scanning: Boolean) {
    val t = rememberInfiniteTransition(label = "beacon")
    val pulse by t.animateFloat(
        0f, 1f,
        infiniteRepeatable(tween(1400, easing = LinearEasing), RepeatMode.Restart),
        label = "pulse",
    )
    Box(Modifier.size(96.dp), contentAlignment = Alignment.Center) {
        Canvas(Modifier.size(96.dp)) {
            val c = Offset(size.width / 2f, size.height / 2f)
            drawCircle(T.CARD, radius = size.width * 0.36f, center = c)
            drawCircle(T.BORDER, radius = size.width * 0.36f, center = c, style = Stroke(1.dp.toPx()))
            if (scanning) {
                drawCircle(
                    T.ACCENT.copy(alpha = 0.45f * (1f - pulse)),
                    radius = size.width * (0.36f + 0.14f * pulse),
                    center = c,
                    style = Stroke(2.dp.toPx()),
                )
            }
        }
        Canvas(Modifier.size(34.dp)) { drawBluetoothRune(if (scanning) T.ACCENT else T.TEXT) }
    }
}

/**
 * The Bluetooth rune on a 20-unit grid: the stem, and the two arrowheads that cross it. Drawn
 * here, as the tab glyphs are, rather than pulled in from an icon font for one shape.
 */
fun DrawScope.drawBluetoothRune(tint: Color) {
    val u = size.width / 20f
    val p = Path().apply {
        moveTo(5.5f * u, 6.5f * u)
        lineTo(14.5f * u, 13.5f * u)
        lineTo(10f * u, 17.5f * u)
        lineTo(10f * u, 2.5f * u)
        lineTo(14.5f * u, 6.5f * u)
        lineTo(5.5f * u, 13.5f * u)
    }
    drawPath(p, tint, style = Stroke(1.8f * u, cap = StrokeCap.Round, join = StrokeJoin.Round))
}

/**
 * Build identity and the three flags that decide whether a scan can run.
 *
 * A QA tool that cannot say which build it is makes every bug report
 * ambiguous, and the scan gate in particular has several inputs that are
 * invisible from the outside. Small, muted, at the bottom — read when needed
 * and ignored otherwise.
 */
@Composable
private fun BuildLine(vm: HexrViewModel) {
    val ctx = LocalContext.current
    val version = remember {
        runCatching {
            ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName
        }.getOrNull() ?: "?"
    }
    MonoText(
        "v$version·${stringResource(R.string.build_sha)}   " +
            "permission ${yn(vm.permissionsGranted)}   " +
            "bluetooth ${yn(vm.bluetoothOn)}   " +
            "scanning ${yn(vm.scanning)}",
        color = T.TEXT_FAINT,
        size = Size.LABEL,
    )
}

private fun yn(b: Boolean) = if (b) "yes" else "no"

/**
 * Below this, a 108-byte six-channel batch does not fit in one write and the
 * engine splits it. Worth surfacing: it changes how simultaneous the six
 * channels really are, which is exactly what the quick test measures.
 */
private const val SMALL_MTU = 111
