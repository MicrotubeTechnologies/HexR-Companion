package com.microtube.hexr.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.microtube.hexr.GloveSearch
import com.microtube.hexr.HeadsetRow
import com.microtube.hexr.HeadsetsViewModel
import com.microtube.hexr.remote.NearbyGlove
import com.microtube.hexr.tr

/**
 * Which physical glove each hand of the headset connects to, and finding the right one when
 * several are switched on: the desktop's Gloves section, for a phone.
 *
 * Every left glove advertises the same name, and so does every right one, so with several kits on
 * in one room a plain connect takes whichever answers first. Find gloves has the headset list
 * every glove in range, nearest first; Connect picks one, and the headset keeps to it from then
 * on. Each glove goes by its own name from its address (the same on every HEXR Companion), or by
 * one given here with a tap.
 */
@Composable
fun GlovesDialog(vm: HeadsetsViewModel, row: HeadsetRow, onClose: () -> Unit) {
    val s = row.status
    var renaming by remember { mutableStateOf<String?>(null) }
    val search = s?.gloveSearch
    val usable = s != null && search != null && s.allowGloveControl && !s.paused
    val searching = search?.state == "searching"
    // Read so a rename redraws the names.
    vm.gloveNames

    AlertDialog(
        onDismissRequest = onClose,
        containerColor = T.CARD,
        title = { Text(tr("Gloves"), color = T.TEXT, fontWeight = FontWeight.Bold) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (s == null || search == null) {
                    Caption(tr("Update this app to HexR 0.10.6 or later to pick gloves."), size = P.SMALL)
                    return@Column
                }

                // Each hand, and the glove it keeps to.
                val savedBy = mutableMapOf<String, String>()
                for (hand in listOf("left", "right")) {
                    val saved = s.glove(hand)?.savedAddress.orEmpty()
                    if (saved.isNotEmpty()) savedBy[saved.uppercase()] = hand
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Label(tr(hand.replaceFirstChar { it.uppercase() }), Modifier.width(64.dp), color = T.TEXT_2)
                        Label(
                            if (saved.isNotEmpty()) vm.gloveName(saved) else tr("Any glove"),
                            Modifier.weight(1f),
                            color = if (saved.isNotEmpty()) T.TEXT else T.TEXT_2,
                            weight = if (saved.isNotEmpty()) FontWeight.SemiBold else FontWeight.Normal,
                        )
                        if (saved.isNotEmpty() && usable) TextLink(tr("Forget")) { vm.forgetGlove(row.key, hand) }
                    }
                }

                ActionButton(
                    if (searching) tr("Searching…") else tr("Find gloves"),
                    Modifier.fillMaxWidth().padding(top = 4.dp),
                    style = ActionStyle.Ghost,
                    enabled = usable && !searching,
                    height = P.TOUCH,
                ) { vm.searchGloves(row.key) }

                when {
                    searching -> Caption(tr("Looking for gloves…"), size = P.SMALL)
                    search.state == "failed" -> Caption(search.message, color = T.RED, size = P.SMALL)
                    search.state == "done" && search.found.isEmpty() ->
                        Caption(tr("No gloves found. Switch them on, and disconnect them from other headsets."), size = P.SMALL)
                    search.found.isNotEmpty() -> Caption(tr("Tap a name to rename it."), size = P.SMALL)
                }

                for (g in search.found) {
                    FoundGlove(vm, row, g, savedBy[g.address.uppercase()], usable) { renaming = g.address }
                }
            }
        },
        confirmButton = { TextLink(tr("Close")) { onClose() } },
    )

    renaming?.let { address ->
        GloveRenameDialog(
            current = vm.gloveName(address),
            onDone = { vm.renameGlove(address, it); renaming = null },
            onCancel = { renaming = null },
        )
    }
}

@Composable
private fun FoundGlove(
    vm: HeadsetsViewModel,
    row: HeadsetRow,
    g: NearbyGlove,
    savedFor: String?,
    usable: Boolean,
    onRename: () -> Unit,
) {
    Row(Modifier.fillMaxWidth().heightIn(min = P.TOUCH), verticalAlignment = Alignment.CenterVertically) {
        SignalBars(GloveSearch.signalBars(g.rssi.takeIf { it != 0 }))
        Column(Modifier.weight(1f).padding(start = 12.dp).clickable(onClick = onRename)) {
            Label(vm.gloveName(g.address), weight = FontWeight.SemiBold)
            if (g.hand.isNotEmpty()) Caption(tr(g.hand.replaceFirstChar { it.uppercase() }), size = P.SMALL)
        }
        if (savedFor != null) {
            Label("✓ " + tr(savedFor.replaceFirstChar { it.uppercase() }), color = T.GREEN, weight = FontWeight.SemiBold)
        } else if (g.hand.isNotEmpty()) {
            TextLink(tr("Connect"), color = if (usable) T.ACCENT else T.TEXT_5) {
                if (usable) vm.connectGloveAt(row.key, g.hand, g.address)
            }
        } else {
            for (hand in listOf("left", "right")) {
                TextLink(tr(hand.replaceFirstChar { it.uppercase() }), color = if (usable) T.ACCENT else T.TEXT_5) {
                    if (usable) vm.connectGloveAt(row.key, hand, g.address)
                }
            }
        }
    }
}

@Composable
private fun GloveRenameDialog(current: String, onDone: (String) -> Unit, onCancel: () -> Unit) {
    var name by remember { mutableStateOf(current) }
    AlertDialog(
        onDismissRequest = onCancel,
        containerColor = T.CARD,
        title = { Text(tr("Rename"), color = T.TEXT, fontWeight = FontWeight.Bold) },
        text = {
            OutlinedTextField(
                value = name,
                onValueChange = { name = it },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text),
                colors = fieldColours(),
                modifier = Modifier.fillMaxWidth(),
            )
        },
        confirmButton = { TextLink(tr("Done"), color = T.ACCENT) { onDone(name) } },
        dismissButton = { TextLink(tr("Cancel")) { onCancel() } },
    )
}
