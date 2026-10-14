package com.microtube.hexr.ui

import android.graphics.SurfaceTexture
import android.view.Surface
import android.view.TextureView
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.microtube.hexr.HeadsetRow
import com.microtube.hexr.HeadsetsViewModel
import com.microtube.hexr.LEFT
import com.microtube.hexr.RIGHT
import com.microtube.hexr.remote.GloveState
import com.microtube.hexr.remote.HeadsetLink
import com.microtube.hexr.remote.HeadsetStatus
import com.microtube.hexr.remote.VideoPlayer
import com.microtube.hexr.remote.WifiNetwork

/**
 * The Headsets tab: the HexR headsets on this Wi-Fi.
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
 * [onImmersive] is told when the viewer opens and closes, so the app can hide its own header and
 * tab bar and give the view the whole screen.
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

    val viewing = vm.viewing?.let { key -> vm.rows.firstOrNull { it.key == key } }
    LaunchedEffect(viewing != null) { onImmersive(viewing != null) }

    val open = vm.selected?.let { key -> vm.rows.firstOrNull { it.key == key } }
    when {
        viewing != null -> HeadsetViewer(vm, viewing, phoneGloves)
        open == null -> HeadsetList(vm)
        else -> {
            BackHandler { vm.select(null) }
            HeadsetDetail(vm, open, phoneGloves)
        }
    }
}

// -- the list -----------------------------------------------------------------------

@Composable
private fun HeadsetList(vm: HeadsetsViewModel) {
    var address by rememberSaveable { mutableStateOf("") }
    var adding by rememberSaveable { mutableStateOf(false) }

    Column(
        Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(T.PAGE_PAD),
        verticalArrangement = Arrangement.spacedBy(18.dp),
    ) {
        Column {
            Title("Headsets")
            Caption(
                "HexR apps with HexR Remote on this Wi-Fi. Open one to connect its gloves " +
                    "and see what the wearer sees.",
                Modifier.padding(top = 5.dp),
                T.TEXT_2,
            )
        }

        if (vm.rows.isEmpty()) {
            Card(Modifier.fillMaxWidth()) {
                EmptyNote(
                    "Looking for headsets… Start a HexR app on a headset on this Wi-Fi. " +
                        "If one never appears, the network may hide devices from each other: add it by its IP below.",
                )
            }
        }

        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            vm.rows.forEach { row -> HeadsetCard(row) { vm.select(row.key) } }
        }

        Disclosure("Add a headset by IP", adding, onToggle = { adding = !adding }) {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Caption(
                    "On the headset: Settings › Wi-Fi › the network shows its IP address.",
                    color = T.TEXT_2,
                )
                Field(address, "192.168.1.20", KeyboardType.Uri) { address = it }
                PrimaryButton(
                    "Add",
                    Modifier.fillMaxWidth(),
                    enabled = address.isNotBlank(),
                    onClick = {
                        vm.addByAddress(address)
                        address = ""
                        adding = false
                    },
                )
            }
        }
        VSpace(8)
    }
}

@Composable
private fun HeadsetCard(row: HeadsetRow, onOpen: () -> Unit) {
    val s = row.status
    Card(Modifier.fillMaxWidth(), fill = T.CARD, border = T.BORDER_SOFT, radius = T.R_CARD) {
        Column(
            Modifier
                .fillMaxWidth()
                .clickable(onClick = onOpen)
                .padding(horizontal = 14.dp, vertical = 13.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Dot(linkColor(row), size = 7)
                Column(Modifier.weight(1f)) {
                    Label(row.title, size = Size.BODY, weight = FontWeight.SemiBold)
                    Caption(appLine(row), Modifier.padding(top = 2.dp), T.TEXT_2, Size.MICRO)
                }
                when {
                    s == null -> Pill(linkWord(row.link), color = T.TEXT_2)
                    s.paused -> Pill("asleep", color = T.AMBER)
                    s.stream.live -> Pill("viewing", color = T.GREEN, fill = T.GREEN.copy(alpha = 0.12f), border = T.GREEN.copy(alpha = 0.35f))
                    else -> Unit
                }
            }
            if (s != null) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(LEFT, RIGHT).forEach { hand -> GloveChip(hand, s.glove(hand)) }
                }
            }
        }
    }
}

@Composable
private fun GloveChip(hand: String, glove: GloveState?) {
    val (word, color) = gloveWord(glove)
    val battery = glove?.batteryPct?.takeIf { it >= 0 }?.let { " · $it%" } ?: ""
    Pill("$hand $word$battery", color = color)
}

// -- one headset -----------------------------------------------------------------------

@Composable
private fun HeadsetDetail(vm: HeadsetsViewModel, row: HeadsetRow, phoneGloves: Set<String>) {
    val s = row.status
    var renaming by rememberSaveable(row.key) { mutableStateOf(false) }
    var nickname by rememberSaveable(row.key) { mutableStateOf(row.nickname) }

    Column(
        Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(T.PAGE_PAD),
        verticalArrangement = Arrangement.spacedBy(18.dp),
    ) {
        Column {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                ChipButton("‹ Headsets", onClick = { vm.select(null) })
                Box(Modifier.weight(1f))
                Pill(if (renaming) "Done" else "Rename", onClick = {
                    if (renaming) vm.rename(row.key, nickname)
                    renaming = !renaming
                })
            }
            VSpace(12)
            if (renaming) {
                Field(nickname, "Station 1", KeyboardType.Text) { nickname = it }
            } else {
                Title(row.title)
            }
            Caption(appLine(row) + "  ·  " + row.host, Modifier.padding(top = 5.dp), T.TEXT_2)
        }

        if (s == null) {
            Card(Modifier.fillMaxWidth()) {
                EmptyNote(
                    when (row.link) {
                        HeadsetLink.State.Lost -> "Can't reach this headset. Is its HexR app still open, on this Wi-Fi?"
                        else -> "Connecting to the headset…"
                    },
                )
            }
            if (row.manual) GhostButton("Forget this address", Modifier.fillMaxWidth(), onClick = { vm.forget(row.key) })
            return@Column
        }

        if (s.paused) {
            Notice("The headset is asleep or off someone's head. It will take requests again once it is worn.", T.AMBER)
        }
        row.error?.let { Notice(it, T.RED) }

        ViewSection(vm, row, s)
        GloveSection(vm, row, s, phoneGloves)

        if (s.exposeScenes && s.scenes.size > 1) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                SectionLabel("Scene")
                s.scenes.forEach { scene ->
                    HandCard(
                        hand = scene.name,
                        sub = if (scene.index == s.scene.index) "open now" else "tap to switch",
                        selected = scene.index == s.scene.index,
                        enabled = !s.paused && scene.index != s.scene.index,
                        modifier = Modifier.fillMaxWidth(),
                        onClick = { vm.loadScene(row.key, scene.index) },
                    )
                }
            }
        }

        if (s.commands.isNotEmpty()) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                SectionLabel(s.app)
                s.commands.forEach { c ->
                    GhostButton(c.label, Modifier.fillMaxWidth(), enabled = !s.paused, onClick = { vm.runCommand(row.key, c.id) })
                }
            }
        }

        MonoText(
            "hexr ${s.hexrVersion}   app ${s.appVersion}   phones ${s.controllers}" +
                (if (s.headsetBatteryPct >= 0) "   headset ${s.headsetBatteryPct}%" else ""),
            color = T.TEXT_FAINT,
            size = Size.LABEL,
        )
        VSpace(8)
    }
}

@Composable
private fun ViewSection(vm: HeadsetsViewModel, row: HeadsetRow, s: HeadsetStatus) {
    val stream = s.stream
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        SectionLabel("What they see")
        // The view itself is in the viewer, full screen, so it can be shown to an audience.
        val (text, tone) = streamWords(s)
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Caption(text, color = tone, size = Size.BODY_2)
                if (stream.state != "unsupported" && s.allowVideo) {
                    PrimaryButton(
                        if (stream.live) "Watch full screen" else "Share headset view",
                        Modifier.fillMaxWidth(),
                        enabled = stream.live || (!s.paused && stream.state != "requesting"),
                        onClick = { vm.openViewer(row.key) },
                    )
                }
                if (stream.live || stream.state == "requesting") {
                    GhostButton("Stop sharing", Modifier.fillMaxWidth(), tint = T.RED, onClick = { vm.stopView(row.key) })
                }
            }
        }
    }
}

@Composable
private fun GloveSection(vm: HeadsetsViewModel, row: HeadsetRow, s: HeadsetStatus, phoneGloves: Set<String>) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        SectionLabel("Gloves")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(LEFT, RIGHT).forEach { hand ->
                GloveCard(
                    hand = hand,
                    glove = s.glove(hand),
                    canControl = s.allowGloveControl && !s.paused,
                    modifier = Modifier.weight(1f),
                    onConnect = { vm.connectGlove(row.key, hand) },
                    onDisconnect = { vm.disconnectGlove(row.key, hand) },
                )
            }
        }

        val blocked = listOf(LEFT, RIGHT).filter { it in phoneGloves && s.glove(it)?.connected != true }
        if (blocked.isNotEmpty()) {
            Notice(
                "This phone is connected to the ${blocked.joinToString(" and ") { it.lowercase() }} glove " +
                    "on the Connect tab. A glove connects to one device at a time — disconnect it there " +
                    "before the headset can reach it.",
                T.AMBER,
            )
        }

        if (!s.allowGloveControl) {
            Caption("This app doesn't let a phone control its gloves.", color = T.TEXT_5)
        } else {
            GhostButton(
                "Release all haptics",
                Modifier.fillMaxWidth(),
                enabled = !s.paused && s.gloves.any { it.connected },
                onClick = { vm.release(row.key) },
            )
        }
    }
}

@Composable
private fun GloveCard(
    hand: String,
    glove: GloveState?,
    canControl: Boolean,
    modifier: Modifier,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
) {
    val (word, color) = gloveWord(glove)
    Card(modifier) {
        Column(
            Modifier.padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Label(hand, weight = FontWeight.SemiBold, size = Size.BODY_2)
                Pill(word, color = color)
            }

            // The tester's own glove drawing, read-only: every channel "selected" so each one fills
            // with the pressure the headset reports for it.
            GloveDiagram(
                selected = if (glove?.connected == true) (0 until 6).toSet() else emptySet(),
                live = { ch -> glove?.kpa(ch) },
                mirrored = hand == RIGHT,
                widthDp = 126,
                heightDp = 140,
                onToggle = {},
            )

            MonoText(
                glove?.batteryPct?.takeIf { it >= 0 }?.let { "battery $it%" } ?: "battery —",
                color = T.TEXT_2,
                size = Size.LABEL,
            )
            glove?.message?.takeIf { it.isNotBlank() && glove.state != "connected" }?.let {
                Caption(it, color = T.TEXT_5, size = Size.LABEL)
            }

            when {
                glove == null || glove.missing -> Caption("Not on this rig", color = T.TEXT_5, size = Size.LABEL)
                glove.connected -> GhostButton("Disconnect", Modifier.fillMaxWidth(), tint = T.RED, enabled = canControl, height = 38, onClick = onDisconnect)
                else -> PrimaryButton(
                    if (glove.connecting) "Connecting…" else "Connect",
                    Modifier.fillMaxWidth(),
                    enabled = canControl && !glove.connecting,
                    height = 38,
                    onClick = onConnect,
                )
            }
        }
    }
}

// -- the viewer ------------------------------------------------------------------------

/**
 * One headset's view, as big as the screen allows, for an audience to watch, with its gloves
 * beside it.
 *
 * The app's header and tab bar step aside while it is open, and the screen stays awake. On a
 * wide screen (a phone turned sideways, a foldable opened out, a tablet) the gloves sit in a
 * column beside the view. Upright on a phone a side column would shrink the view to two-thirds
 * of the width, so there they sit underneath it instead.
 */
@Composable
private fun HeadsetViewer(vm: HeadsetsViewModel, row: HeadsetRow, phoneGloves: Set<String>) {
    val s = row.status
    val stream = s?.stream
    val view = LocalView.current
    DisposableEffect(Unit) {
        view.keepScreenOn = true
        onDispose { view.keepScreenOn = false }
    }
    BackHandler { vm.closeViewer() }

    Column(
        Modifier
            .fillMaxSize()
            .background(T.SCREEN)
            .windowInsetsPadding(WindowInsets.statusBars)
            .windowInsetsPadding(WindowInsets.navigationBars),
    ) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            ChipButton("‹ Back", onClick = { vm.closeViewer() })
            Column(Modifier.weight(1f)) {
                Label(row.title, size = Size.BODY, weight = FontWeight.SemiBold)
                Caption(appLine(row), size = Size.LABEL)
            }
            val canAsk = s != null && s.allowVideo && stream != null && !stream.live &&
                stream.state != "requesting" && stream.state != "unsupported"
            if (canAsk) {
                Pill("Ask to share", color = T.ACCENT, onClick = { vm.startView(row.key) })
            }
        }

        BoxWithConstraints(Modifier.weight(1f).fillMaxWidth()) {
            if (maxWidth > maxHeight) {
                Row(
                    Modifier.fillMaxSize().padding(start = 8.dp, end = 8.dp, bottom = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    ViewerStage(row, s, Modifier.weight(1f).fillMaxHeight())
                    Column(
                        Modifier.width(210.dp).fillMaxHeight().verticalScroll(rememberScrollState()),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        ViewerGloves(vm, row, s, phoneGloves, vertical = true)
                    }
                }
            } else {
                Column(
                    Modifier.fillMaxSize().padding(start = 8.dp, end = 8.dp, bottom = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    ViewerStage(row, s, Modifier.fillMaxWidth().weight(1f))
                    ViewerGloves(vm, row, s, phoneGloves, vertical = false)
                }
            }
        }
    }
}

/** The picture, fitted to the space it is given, or what is happening instead of one. */
@Composable
private fun ViewerStage(row: HeadsetRow, s: HeadsetStatus?, modifier: Modifier) {
    val stream = s?.stream
    BoxWithConstraints(modifier.background(Color.Black), contentAlignment = Alignment.Center) {
        if (stream != null && stream.live) {
            val ratio = if (stream.width > 0 && stream.height > 0) stream.width.toFloat() / stream.height else 1f
            val w = minOf(maxWidth, maxHeight * ratio)
            // A new session can come back on another port: start a fresh view for it.
            key(row.host, stream.port) {
                HeadsetVideo(row.host, stream.port, Modifier.size(w, w / ratio))
            }
        } else {
            val (text, tone) = if (s == null) {
                "Connecting to the headset…" to T.TEXT_2
            } else {
                streamWords(s)
            }
            Text(
                text,
                Modifier.padding(24.dp),
                color = tone,
                fontSize = Size.BODY.sp,
                textAlign = TextAlign.Center,
            )
        }
    }
}

/** The headset's gloves for the viewer: a column beside the view, or a row under it. */
@Composable
private fun ViewerGloves(
    vm: HeadsetsViewModel,
    row: HeadsetRow,
    s: HeadsetStatus?,
    phoneGloves: Set<String>,
    vertical: Boolean,
) {
    if (s == null) return
    val canControl = s.allowGloveControl && !s.paused
    val cards: @Composable (Modifier) -> Unit = { m ->
        listOf(LEFT, RIGHT).forEach { hand ->
            ViewerGlove(
                hand = hand,
                glove = s.glove(hand),
                held = hand in phoneGloves,
                canControl = canControl,
                modifier = m,
                onConnect = { vm.connectGlove(row.key, hand) },
                onDisconnect = { vm.disconnectGlove(row.key, hand) },
            )
        }
    }
    if (vertical) {
        cards(Modifier.fillMaxWidth())
    } else {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { cards(Modifier.weight(1f)) }
    }
    if (s.paused) {
        Caption("Asleep: nobody is wearing it, so it takes no requests.", color = T.AMBER, size = Size.LABEL)
    }
    row.error?.let { Caption(it, color = T.RED, size = Size.LABEL) }
}

@Composable
private fun ViewerGlove(
    hand: String,
    glove: GloveState?,
    held: Boolean,
    canControl: Boolean,
    modifier: Modifier,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
) {
    val (word, color) = gloveWord(glove)
    Card(modifier) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Label(hand, Modifier.weight(1f), size = Size.BODY_2, weight = FontWeight.SemiBold)
                Pill(word, color = color)
            }
            MonoText(
                (glove?.batteryPct?.takeIf { it >= 0 }?.let { "battery $it%" } ?: "battery —") +
                    (glove?.kpa(6)?.takeIf { glove.connected }?.let { "  ·  src %.0f kPa".format(it) } ?: ""),
                color = T.TEXT_2,
                size = Size.LABEL,
            )
            if (held && glove?.connected != true) {
                Caption("This phone holds this glove on the Test tab.", color = T.AMBER, size = Size.LABEL)
            }
            when {
                glove == null || glove.missing -> Unit
                glove.connected -> GhostButton("Disconnect", Modifier.fillMaxWidth(), tint = T.RED, enabled = canControl, height = 36, onClick = onDisconnect)
                else -> PrimaryButton(
                    if (glove.connecting) "Connecting…" else "Connect",
                    Modifier.fillMaxWidth(),
                    enabled = canControl && !glove.connecting,
                    height = 36,
                    onClick = onConnect,
                )
            }
        }
    }
}

/** What the share is doing, in words, and the colour to say it in. */
private fun streamWords(s: HeadsetStatus): Pair<String, Color> {
    val stream = s.stream
    return when {
        stream.live -> "Shared · ${stream.width}×${stream.height}" +
            (if (stream.viewers > 1) " · ${stream.viewers} watching" else "") to T.GREEN
        stream.state == "requesting" -> "Ask the person in the headset to allow screen sharing in the prompt in front of them." to T.ACCENT
        stream.state == "denied" -> "Screen sharing was not allowed in the headset. Ask again when they're ready." to T.AMBER
        stream.state == "unsupported" -> stream.message.ifEmpty { "This headset can't share its view." } to T.TEXT_5
        stream.state == "error" -> stream.message.ifEmpty { "Sharing the view failed." } to T.RED
        !s.allowVideo -> "This app doesn't share its view." to T.TEXT_5
        s.paused -> "The headset is asleep. Sharing can be asked for once someone is wearing it." to T.AMBER
        else -> stream.message.ifEmpty { "Sharing needs the wearer's OK in the headset each time." } to T.TEXT_2
    }
}

/**
 * The headset's view, decoded onto a TextureView.
 *
 * A TextureView rather than a SurfaceView so it scrolls and clips with the rest of the screen.
 * The player starts when its surface exists and stops before the surface is handed back, so the
 * decoder never renders into a surface that has gone.
 */
@Composable
private fun HeadsetVideo(host: String, port: Int, modifier: Modifier) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val wifi = remember { WifiNetwork(context).also { it.start() } }
    var state by remember(host, port) { mutableStateOf<VideoPlayer.VideoState>(VideoPlayer.VideoState.Connecting) }
    val holder = remember(host, port) { PlayerHolder() }

    DisposableEffect(host, port) {
        onDispose { holder.release() }
    }
    DisposableEffect(Unit) {
        onDispose { wifi.stop() }
    }

    Box(modifier.background(Color.Black)) {
        AndroidView(
            factory = { ctx ->
                TextureView(ctx).apply {
                    surfaceTextureListener = object : TextureView.SurfaceTextureListener {
                        override fun onSurfaceTextureAvailable(texture: SurfaceTexture, w: Int, h: Int) {
                            holder.start(Surface(texture), host, port, wifi) { s -> post { state = s } }
                        }

                        override fun onSurfaceTextureSizeChanged(texture: SurfaceTexture, w: Int, h: Int) = Unit

                        override fun onSurfaceTextureDestroyed(texture: SurfaceTexture): Boolean {
                            holder.release()
                            return true
                        }

                        override fun onSurfaceTextureUpdated(texture: SurfaceTexture) = Unit
                    }
                }
            },
            modifier = Modifier.fillMaxSize(),
        )

        val overlay = when (val s = state) {
            is VideoPlayer.VideoState.Connecting -> "Connecting to the view…"
            is VideoPlayer.VideoState.Failed -> s.message
            is VideoPlayer.VideoState.Playing -> null
        }
        if (overlay != null) {
            Text(
                overlay,
                Modifier.align(Alignment.Center).padding(16.dp),
                color = T.TEXT_2,
                fontSize = Size.CAPTION.sp,
            )
        }
    }
}

/** One player and the surface it draws on, released together. */
private class PlayerHolder {
    private var player: VideoPlayer? = null
    private var surface: Surface? = null

    fun start(s: Surface, host: String, port: Int, wifi: WifiNetwork, onState: (VideoPlayer.VideoState) -> Unit) {
        release()
        surface = s
        player = VideoPlayer(host, port, s, wifi, onState).also { it.start() }
    }

    fun release() {
        player?.stop()
        player = null
        surface?.release()
        surface = null
    }
}

// -- small pieces --------------------------------------------------------------------

@Composable
private fun Notice(text: String, tone: Color) {
    Box(
        Modifier
            .fillMaxWidth()
            .background(tone.copy(alpha = 0.08f), androidx.compose.foundation.shape.RoundedCornerShape(T.R_CTRL))
            .padding(14.dp),
    ) {
        Caption(text, color = tone, size = Size.BODY_2)
    }
}

@Composable
private fun Field(value: String, placeholder: String, type: KeyboardType, onChange: (String) -> Unit) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        singleLine = true,
        placeholder = { Text(placeholder, color = T.TEXT_5) },
        keyboardOptions = KeyboardOptions(keyboardType = type),
        colors = OutlinedTextFieldDefaults.colors(
            focusedTextColor = T.TEXT,
            unfocusedTextColor = T.TEXT,
            focusedBorderColor = T.ACCENT,
            unfocusedBorderColor = T.BORDER,
            cursorColor = T.ACCENT,
            focusedContainerColor = T.CARD,
            unfocusedContainerColor = T.CARD,
        ),
        modifier = Modifier.fillMaxWidth(),
    )
}

private fun appLine(row: HeadsetRow): String {
    val s = row.status
    val app = s?.app ?: row.announce?.app ?: "HexR headset"
    val scene = s?.scene?.name?.takeIf { it.isNotEmpty() }
    return if (scene != null) "$app · $scene" else app
}

private fun linkColor(row: HeadsetRow): Color = when {
    row.status?.paused == true -> T.AMBER
    row.link == HeadsetLink.State.Connected -> T.GREEN
    row.link == HeadsetLink.State.Lost -> T.RED
    else -> T.TEXT_FAINT
}

private fun linkWord(state: HeadsetLink.State) = when (state) {
    HeadsetLink.State.Connecting -> "connecting"
    HeadsetLink.State.Connected -> "connected"
    HeadsetLink.State.Lost -> "unreachable"
}

private fun gloveWord(glove: GloveState?): Pair<String, Color> = when {
    glove == null || glove.missing -> "none" to T.TEXT_5
    glove.connected -> "connected" to T.GREEN
    glove.connecting -> "connecting" to T.ACCENT
    else -> "off" to T.TEXT_4
}
