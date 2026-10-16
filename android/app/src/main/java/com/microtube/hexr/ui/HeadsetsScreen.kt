package com.microtube.hexr.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.microtube.hexr.HeadsetRow
import com.microtube.hexr.HeadsetsViewModel
import com.microtube.hexr.LEFT
import com.microtube.hexr.RIGHT
import com.microtube.hexr.remote.GloveState
import com.microtube.hexr.remote.HeadsetLink
import com.microtube.hexr.tr

/**
 * The Headsets tab: the HexR headsets on this Wi-Fi, and one of them live.
 *
 * For running a demo rather than testing a glove: the facilitator stands beside someone in a
 * headset, connects their gloves from here, and watches what they see. Every headset with a HexR
 * app that has HexR Remote in it appears on its own; the gloves are the headset's, connected by
 * the headset, so nothing here uses this phone's Bluetooth.
 *
 * [phoneGloves] are the hands this phone itself holds on the Test tab. A glove talks to one
 * device at a time, so a headset cannot reach a glove this phone is holding, and the screen says
 * so rather than leave the headset's connect failing for no visible reason.
 *
 * [onImmersive] is told when a headset opens and closes: it has the screen to itself, without
 * the app's header and tab bar.
 */
@Composable
fun HeadsetsScreen(vm: HeadsetsViewModel, phoneGloves: Set<String>, onImmersive: (Boolean) -> Unit = {}) {
    DisposableEffect(Unit) {
        vm.setVisible(true)
        onDispose {
            vm.setVisible(false)
            onImmersive(false)
        }
    }
    val open = vm.selected?.let { key -> vm.rows.firstOrNull { it.key == key } }
    LaunchedEffect(open != null) { onImmersive(open != null) }
    if (open == null) {
        HeadsetList(vm)
    } else {
        HeadsetLive(vm, open, phoneGloves, onLeave = { vm.select(null) })
    }
}

@Composable
private fun HeadsetList(vm: HeadsetsViewModel) {
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .imePadding()
            .padding(horizontal = T.PAGE_PAD, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text(tr("Headsets"), color = T.TEXT, fontSize = P.HEAD.sp, fontWeight = FontWeight.Bold)
        Text(tr("Same Wi-Fi as this phone."), color = T.TEXT_2, fontSize = P.BODY.sp)
        Spacer(Modifier.height(6.dp))

        if (vm.rows.isEmpty()) {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(searchingWord(tr("Searching for headsets")), color = T.TEXT, fontSize = P.BODY.sp, fontWeight = FontWeight.SemiBold)
                    Caption(tr("Start a HexR app on a headset on this Wi-Fi."), color = T.TEXT_2, size = P.SMALL)
                }
            }
        }
        for (row in vm.rows) HeadsetCard(row) { vm.select(row.key) }

        AddByAddress(onAdd = { address -> vm.addByAddress(address)?.also(vm::select) != null })
    }
}

/** One headset: its name and app, a word for its state, and its two gloves. */
@Composable
private fun HeadsetCard(row: HeadsetRow, onOpen: () -> Unit) {
    val s = row.status
    val (word, dot) = listWord(row)
    Card(Modifier.fillMaxWidth(), fill = T.CARD, radius = T.R_CTRL) {
        Row(
            Modifier
                .fillMaxWidth()
                .heightIn(min = 72.dp)
                .clickable(onClick = onOpen)
                .padding(start = 14.dp, end = 8.dp, top = 12.dp, bottom = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(row.title, color = T.TEXT, fontSize = 16.sp, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(appLine(row), color = T.TEXT_4, fontSize = P.SMALL.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                if (s != null) {
                    Spacer(Modifier.height(4.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        GloveChip("L", s.glove(LEFT))
                        GloveChip("R", s.glove(RIGHT))
                    }
                }
            }
            Spacer(Modifier.width(8.dp))
            StateChip(word, dot)
            Canvas(Modifier.padding(start = 4.dp).size(20.dp)) {
                val u = size.width / 20f
                drawLine(T.TEXT_4, Offset(7.5f * u, 4f * u), Offset(13.5f * u, 10f * u), 2f * u, StrokeCap.Round)
                drawLine(T.TEXT_4, Offset(13.5f * u, 10f * u), Offset(7.5f * u, 16f * u), 2f * u, StrokeCap.Round)
            }
        }
    }
}

/** "L ●  85%": a hand, a dot for its state, and its battery once connected. */
@Composable
private fun GloveChip(letter: String, glove: GloveState?) {
    val colour = when {
        glove == null || glove.missing -> T.TEXT_FAINT
        glove.connected -> T.GREEN
        glove.connecting -> T.ACCENT
        else -> T.TEXT_5
    }
    Row(
        Modifier
            .clip(RoundedCornerShape(T.R_CHIP))
            .background(T.ELEVATED)
            .padding(horizontal = 8.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(5.dp),
    ) {
        Text(letter, color = T.TEXT_2, fontSize = 12.sp, fontWeight = FontWeight.Bold)
        Box(Modifier.size(7.dp).clip(CircleShape).background(colour))
        val battery = glove?.batteryPct?.takeIf { it >= 0 && glove.connected }
        if (battery != null) {
            Text("$battery%", color = if (battery < 20) T.AMBER else T.TEXT_2, fontSize = 12.sp, fontFamily = Mono)
        }
    }
}

/** For venue Wi-Fi that hides devices from each other: the headset's address, typed in. */
@Composable
private fun AddByAddress(onAdd: (String) -> Boolean) {
    var open by rememberSaveable { mutableStateOf(false) }
    var address by rememberSaveable { mutableStateOf("") }
    var wrong by rememberSaveable { mutableStateOf(false) }
    val add = {
        if (onAdd(address)) {
            address = ""
            open = false
            wrong = false
        } else {
            wrong = true
        }
    }
    if (!open) {
        TextLink("+  " + tr("Add by address"), color = T.TEXT_3) { open = true }
        return
    }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(tr("Add by address"), color = T.TEXT, fontSize = P.BODY.sp, fontWeight = FontWeight.SemiBold)
            Caption(tr("On the headset: Settings › Wi-Fi › the network shows its IP address."), color = T.TEXT_2, size = P.SMALL)
            OutlinedTextField(
                value = address,
                onValueChange = {
                    address = it
                    wrong = false
                },
                singleLine = true,
                placeholder = { Text("192.168.1.20", color = T.TEXT_5) },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { add() }),
                colors = fieldColours(),
                isError = wrong,
                modifier = Modifier.fillMaxWidth(),
            )
            if (wrong) Caption(tr("That is not an address."), color = T.RED, size = P.SMALL)
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                ActionButton(tr("Cancel"), Modifier.weight(1f), style = ActionStyle.Ghost, height = P.TOUCH) {
                    open = false
                    wrong = false
                }
                ActionButton(tr("Add"), Modifier.weight(1f), enabled = address.isNotBlank(), height = P.TOUCH, onClick = add)
            }
        }
    }
}

/** The list's word for a headset, as the desktop's: connecting, unreachable, asleep, live, ready. */
private fun listWord(row: HeadsetRow): Pair<String, Color?> = when {
    row.link == HeadsetLink.State.Connecting && row.status == null -> tr("Connecting…") to T.ACCENT
    row.link != HeadsetLink.State.Connected -> tr("Offline") to T.RED
    row.status?.paused == true -> tr("Asleep") to null
    row.status?.stream?.live == true -> tr("Live") to T.GREEN
    else -> tr("Ready") to T.GREEN
}
