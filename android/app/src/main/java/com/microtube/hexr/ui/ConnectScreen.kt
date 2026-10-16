package com.microtube.hexr.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.microtube.hexr.Found
import com.microtube.hexr.GloveSearch
import com.microtube.hexr.GloveSnapshot
import com.microtube.hexr.HANDS
import com.microtube.hexr.HexrViewModel
import com.microtube.hexr.R
import com.microtube.hexr.glove.GloveLook
import com.microtube.hexr.glove.connectState
import com.microtube.hexr.glove.panelSize
import com.microtube.hexr.tr
import kotlinx.coroutines.delay

/**
 * Connect: the Test tab until a glove connects, and the Gloves panel after.
 *
 * Two gloves, left and right, dimmed until each is found and lit when it connects, the way the
 * desktop's Connect screen shows them. It searches by itself while it is on screen; there is no
 * Scan button. Under each glove one word says where it is, and one button does the next thing.
 */
@Composable
fun ConnectScreen(vm: HexrViewModel, panel: Boolean, onOpenBluetoothSettings: () -> Unit) {
    DisposableEffect(Unit) {
        vm.setConnectVisible(true)
        onDispose { vm.setConnectVisible(false) }
    }
    var details by remember { mutableStateOf(false) }

    BoxWithConstraints(Modifier.fillMaxSize()) {
        val viewH = maxHeight.value
        Column(
            Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = T.PAGE_PAD, vertical = 16.dp),
        ) {
            if (!panel) {
                Text(tr("Connect a glove"), color = T.TEXT, fontSize = P.HEAD.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(4.dp))
                Text(tr("Switch on the arm module."), color = T.TEXT_2, fontSize = P.BODY.sp)
                Spacer(Modifier.height(16.dp))
            }
            if (!vm.bluetoothOn) {
                BluetoothOff(onOpenBluetoothSettings)
                Spacer(Modifier.height(16.dp))
            }
            BoxWithConstraints(Modifier.fillMaxWidth()) {
                val slotW = (maxWidth.value - 12f) / 2
                val unit = panelSize(1f, GloveLook.CONNECT)
                val gh = minOf(slotW / unit.width, (viewH - if (panel) 190f else 260f) / unit.height).coerceIn(110f, 300f)
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    for (hand in HANDS) {
                        Slot(vm, hand, panel, gh, Modifier.weight(1f))
                    }
                }
            }
            Spacer(Modifier.height(20.dp))
            Disclosure(tr("Details"), details, onToggle = { details = !details }) {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    for (hand in HANDS) {
                        val g = vm.gloves[hand]
                        val heard = vm.candidates(hand)
                        val lines = buildList {
                            if (g != null) {
                                add("${tr(hand)}  ${g.address}  ${g.status}")
                                if (g.connected) {
                                    add("   " + tr("battery {level}", "level" to g.battery) +
                                        "   " + tr("source {kpa} kPa", "kpa" to "%.1f".format(g.source)) +
                                        "   MTU ${g.mtu ?: "?"}")
                                }
                            }
                            for (f in heard) add("${tr(hand)}  ${f.address}  ${f.rssi ?: "?"} dBm")
                        }
                        for (l in lines) MonoText(l, color = T.TEXT_4, size = 12.5f)
                    }
                    BuildLine(vm)
                }
            }
        }
    }
}

/** One glove: its picture, a word for where it is, and the one thing to do next. */
@Composable
private fun Slot(vm: HexrViewModel, hand: String, panel: Boolean, gh: Float, modifier: Modifier) {
    val g: GloveSnapshot? = vm.gloves[hand]
    val heard = vm.candidates(hand)
    val connected = g?.connected == true
    val connecting = g?.connecting == true
    val dim by animateFloatAsState(
        when {
            connected -> 1f
            connecting -> .7f
            heard.isNotEmpty() -> .6f
            else -> .3f
        },
        tween(300), label = "dim",
    )
    Column(modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        GloveArt(
            hand = hand, look = GloveLook.CONNECT, gh = gh.dp, dim = dim,
            state = connectState(connected, if (g?.live == true) g.kpa else null),
            description = tr(hand),
        )
        Spacer(Modifier.height(8.dp))
        Text(tr(hand), color = T.TEXT, fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(4.dp))
        Row(Modifier.heightIn(min = 24.dp), verticalAlignment = Alignment.CenterVertically) {
            val (word, dot) = when {
                connected -> (tr("Connected") + if (g?.battery != "—") " · ${g?.battery}" else "") to
                    if ((g?.batteryFraction ?: 1.0) < .2) T.AMBER else T.GREEN
                connecting -> tr("Connecting…") to T.ACCENT
                !vm.bluetoothOn || vm.scanError != null -> tr("Bluetooth unavailable") to T.RED
                g?.failed == true && heard.isEmpty() -> tr("Could not connect") to T.RED
                heard.isNotEmpty() -> tr("Found") to T.GREEN
                else -> searchingWord() to T.TEXT_5
            }
            Box(Modifier.size(8.dp).clip(CircleShape).background(dot))
            Spacer(Modifier.size(6.dp))
            Text(word, color = T.TEXT_2, fontSize = P.VALUE.sp, maxLines = 1)
            if (!connected && !connecting && heard.isNotEmpty()) {
                Spacer(Modifier.size(6.dp))
                SignalBars(GloveSearch.signalBars(heard.first().rssi))
            }
        }
        Spacer(Modifier.height(8.dp))
        when {
            connected && panel -> ActionButton(
                tr("Disconnect"), Modifier.widthIn(min = 132.dp), style = ActionStyle.Ghost,
                height = P.TOUCH, onClick = { vm.disconnect(hand) },
            )
            connected -> Spacer(Modifier.height(P.TOUCH))
            connecting -> ActionButton(
                tr("Connecting…"), Modifier.widthIn(min = 132.dp), enabled = false, height = P.TOUCH, onClick = {},
            )
            vm.scanError != null && heard.isEmpty() -> ActionButton(
                tr("Try again"), Modifier.widthIn(min = 132.dp), style = ActionStyle.Ghost,
                height = P.TOUCH, onClick = vm::retryScan,
            )
            heard.isNotEmpty() -> ConnectButton(heard, onPick = vm::connect)
            else -> Spacer(Modifier.height(P.TOUCH))
        }
    }
}

/** Connect, or with two kits of one hand about, a choice between them, strongest first. */
@Composable
private fun ConnectButton(heard: List<Found>, onPick: (Found) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Box {
        ActionButton(tr("Connect"), Modifier.widthIn(min = 132.dp), height = P.TOUCH, onClick = {
            if (heard.size == 1) onPick(heard.first()) else open = true
        })
        DropdownMenu(open, onDismissRequest = { open = false }, containerColor = T.CARD) {
            for (f in heard) {
                DropdownMenuItem(
                    text = {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("${f.name} · ${GloveSearch.shortAddress(f.address)}", color = T.TEXT, fontSize = P.BODY.sp)
                            Spacer(Modifier.size(10.dp))
                            SignalBars(GloveSearch.signalBars(f.rssi))
                        }
                    },
                    onClick = {
                        open = false
                        onPick(f)
                    },
                    modifier = Modifier.heightIn(min = P.TOUCH),
                )
            }
        }
    }
}

/** "Searching", with dots that count up, at a fixed width so the word does not shuffle. */
@Composable
internal fun searchingWord(word: String = tr("Searching")): String {
    var dots by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(450)
            dots = (dots + 1) % 4
        }
    }
    return word + ".".repeat(dots) + " ".repeat(3 - dots)
}

@Composable
private fun BluetoothOff(onOpenBluetoothSettings: () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(tr("Bluetooth is off."), color = T.TEXT, fontSize = P.BODY.sp, fontWeight = FontWeight.SemiBold)
            ActionButton(
                tr("Open Bluetooth settings"), Modifier.fillMaxWidth(), style = ActionStyle.Ghost,
                height = P.TOUCH, onClick = onOpenBluetoothSettings,
            )
        }
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

/** Build identity and what decides whether a search can run, for a bug report. */
@Composable
private fun BuildLine(vm: HexrViewModel) {
    val ctx = LocalContext.current
    val version = remember {
        runCatching { ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName }.getOrNull() ?: "?"
    }
    MonoText(
        "v$version·${stringResource(R.string.build_sha)}   " +
            "permission ${yn(vm.permissionsGranted)}   bluetooth ${yn(vm.bluetoothOn)}   " +
            "searching ${yn(vm.scanning)}",
        color = T.TEXT_FAINT, size = 11.5f,
    )
}

private fun yn(b: Boolean) = if (b) "yes" else "no"
