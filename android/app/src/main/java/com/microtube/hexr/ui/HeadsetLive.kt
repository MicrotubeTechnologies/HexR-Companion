package com.microtube.hexr.ui

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.content.pm.ActivityInfo
import android.content.res.Configuration
import android.graphics.Matrix
import android.graphics.SurfaceTexture
import android.os.SystemClock
import android.view.Surface
import android.view.TextureView
import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.displayCutout
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.microtube.hexr.HeadsetRow
import com.microtube.hexr.HeadsetsViewModel
import com.microtube.hexr.LEFT
import com.microtube.hexr.RIGHT
import com.microtube.hexr.glove.GloveLook
import com.microtube.hexr.glove.fitGh
import com.microtube.hexr.glove.panelSize
import com.microtube.hexr.remote.CastBoxes
import com.microtube.hexr.remote.CastLayout
import com.microtube.hexr.remote.GloveState
import com.microtube.hexr.remote.HapticsTimeline
import com.microtube.hexr.remote.HeadsetLink
import com.microtube.hexr.remote.HeadsetStatus
import com.microtube.hexr.remote.StreamState
import com.microtube.hexr.remote.VideoPlayer
import com.microtube.hexr.remote.WifiNetwork
import com.microtube.hexr.tr
import kotlinx.coroutines.delay

/**
 * One headset, live: what the wearer sees, and their two gloves beside it, lighting up as they
 * are touched. The desktop's headset screen, for a phone.
 *
 * Upright, the view runs across the top with the gloves under it, and Watch, Release all and
 * Recenter sit in a bar along the bottom. Turned sideways (or with full screen, which turns it),
 * the view takes three quarters of the width, the gloves the last quarter, the system bars step
 * aside and the controls float over the view, fading once it plays; a tap brings them back.
 *
 * Tap a glove's panel to connect it; a connected one asks first, from a menu, since ending
 * someone's demo should not be one slip of a thumb. There are no scenes, app commands or
 * recordings here: a phone beside a headset only needs to see and to steer the gloves.
 */
@Composable
fun HeadsetLive(vm: HeadsetsViewModel, row: HeadsetRow, phoneGloves: Set<String>, onLeave: () -> Unit) {
    val s = row.status
    val stream = s?.stream ?: StreamState()
    val context = LocalContext.current
    val activity = remember(context) { context.findActivity() }
    val view = LocalView.current
    val landscape = LocalConfiguration.current.orientation == Configuration.ORIENTATION_LANDSCAPE
    val timeline = remember(row.key) { vm.timeline(row.key) ?: HapticsTimeline() }
    val video = remember(row.key) { CastVideo() }
    var fullScreen by rememberSaveable { mutableStateOf(false) }
    var note by remember { mutableStateOf<String?>(null) }

    val connected = row.link == HeadsetLink.State.Connected && s != null
    val playView = row.watching && stream.live && vm.online
    val look = liveLook(row, if (playView) video.state else null)
    val canWatch = connected && s!!.allowVideo && stream.state != "unsupported" && !(s.paused && !stream.live)
    val canControl = connected && s!!.allowGloveControl && !s.paused

    val leave = {
        vm.stopWatching(row.key, video.joined)
        onLeave()
    }
    BackHandler { if (fullScreen) fullScreen = false else leave() }

    // Awake while there is something to watch: a phone held up for an audience must not sleep.
    DisposableEffect(row.watching || landscape) {
        view.keepScreenOn = row.watching || landscape
        onDispose { view.keepScreenOn = false }
    }
    // Full screen is sideways, whichever way the phone is held; leaving it gives the turning back.
    LaunchedEffect(fullScreen) {
        activity?.requestedOrientation =
            if (fullScreen) ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE else ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
    }
    DisposableEffect(Unit) {
        onDispose { activity?.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED }
    }
    // Sideways, the status and navigation bars go, until swiped back.
    DisposableEffect(landscape) {
        val bars = activity?.window?.let { WindowCompat.getInsetsController(it, view) }
        if (landscape) {
            bars?.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            bars?.hide(WindowInsetsCompat.Type.systemBars())
        } else {
            bars?.show(WindowInsetsCompat.Type.systemBars())
        }
        onDispose { bars?.show(WindowInsetsCompat.Type.systemBars()) }
    }
    // A note from a tap (why Recenter cannot), for a few seconds.
    LaunchedEffect(note) {
        if (note != null) {
            delay(4000)
            note = null
        }
    }

    val recentered by produceState(false, row.recenteredAt) {
        val ago = SystemClock.elapsedRealtime() - row.recenteredAt
        value = row.recenteredAt > 0 && ago < RECENTERED_MS
        if (value) {
            delay(RECENTERED_MS - ago)
            value = false
        }
    }
    val recenterWhyNot = when {
        !connected -> tr("Reconnecting…")
        !s!!.allowRecenter -> tr("Needs HexR 0.11.0 with Allow Recenter.")
        s.paused -> tr("Asleep. Put the headset on.")
        else -> null
    }

    val actions = LiveActions(
        watching = row.watching,
        canWatch = canWatch,
        canRelease = canControl && s!!.gloves.any { it.connected },
        canRecenter = recenterWhyNot == null,
        recentered = recentered && row.error == null,
        playing = video.state is VideoPlayer.VideoState.Playing,
        onWatch = { if (row.watching) vm.stopWatching(row.key, video.joined) else vm.watch(row.key) },
        onRelease = { vm.release(row.key) },
        onRecenter = { vm.recenter(row.key) },
        onRecenterWhyNot = { note = recenterWhyNot },
        onFullScreen = { fullScreen = true },
    )

    Column(Modifier.fillMaxSize().background(T.SCREEN)) {
        if (!landscape) TopBar(vm, row, look, onBack = leave)

        BoxWithConstraints(Modifier.weight(1f).fillMaxWidth()) {
            val boxes = castBoxes(maxWidth.value, maxHeight.value, landscape, stream)
            var controls by remember { mutableStateOf(true) }
            LaunchedEffect(controls, actions.playing, landscape) {
                if (landscape && controls && actions.playing) {
                    delay(4000)
                    controls = false
                }
            }
            CastStage(
                boxes = boxes,
                row = row,
                status = s,
                timeline = timeline,
                video = video,
                playView = playView,
                say = look.say,
                canControl = canControl,
                onTapView = {
                    when {
                        landscape && actions.playing -> controls = !controls
                        !row.watching && canWatch -> vm.watch(row.key)
                        else -> controls = true
                    }
                },
                onConnect = { hand -> vm.connectGlove(row.key, hand) },
                onDisconnect = { hand -> vm.disconnectGlove(row.key, hand) },
            )
            if (landscape) {
                Overlay(
                    boxes = boxes,
                    row = row,
                    look = look,
                    shown = controls || !actions.playing,
                    actions = actions,
                    fullScreen = fullScreen,
                    note = note,
                    onBack = { if (fullScreen) fullScreen = false else leave() },
                )
            }
        }

        if (!landscape) {
            val blocked = listOf(LEFT, RIGHT).filter { it in phoneGloves && s?.glove(it)?.connected != true }
            val (text, tone) = when {
                row.error != null -> row.error to T.RED
                note != null -> note to T.TEXT_2
                s != null && blocked.isNotEmpty() && s.allowGloveControl ->
                    tr("This phone has a glove for this hand; disconnect it on the Test tab first.") to T.AMBER
                s != null && !s.allowGloveControl -> tr("This app does not let a phone connect its gloves.") to T.TEXT_5
                actions.playing && !timeline.exact ->
                    tr("The glove shows the pressure the gloves measure. Update this app to HexR 0.10.2 or newer to show every touch and vibration as it is sent.") to T.TEXT_5
                else -> null to T.TEXT_5
            }
            if (text != null) {
                Caption(text, Modifier.fillMaxWidth().padding(horizontal = T.PAGE_PAD, vertical = 8.dp), tone, P.SMALL)
            }
            ActionBar(actions)
        }
    }
}

private const val RECENTERED_MS = 3000L

/** What the controls can do now, and what they do. */
private class LiveActions(
    val watching: Boolean,
    val canWatch: Boolean,
    val canRelease: Boolean,
    val canRecenter: Boolean,
    val recentered: Boolean,
    val playing: Boolean,
    val onWatch: () -> Unit,
    val onRelease: () -> Unit,
    val onRecenter: () -> Unit,
    val onRecenterWhyNot: () -> Unit,
    val onFullScreen: () -> Unit,
)

// -- the state, in a word and a sentence ------------------------------------------------------

/** A word for the state beside the title, and the sentence in the view while there is no view. */
private class LiveLook(val word: String, val dot: Color?, val say: String)

private fun liveLook(row: HeadsetRow, video: VideoPlayer.VideoState?): LiveLook {
    val s = row.status
    val st = s?.stream ?: StreamState()
    return when {
        s == null -> LiveLook(tr("Connecting…"), T.ACCENT, tr("Connecting to the headset…"))
        row.link != HeadsetLink.State.Connected -> LiveLook(tr("Offline"), T.RED, tr("Reconnecting…"))
        s.paused && !st.live -> LiveLook(tr("Asleep"), T.ACCENT, tr("Asleep. Put the headset on."))
        !s.allowVideo -> LiveLook(tr("No view"), null, tr("This app does not share its view."))
        video is VideoPlayer.VideoState.Failed -> LiveLook(tr("Failed"), T.RED, video.message)
        video is VideoPlayer.VideoState.Playing -> LiveLook(tr("Live"), T.GREEN, "")
        video != null -> LiveLook(tr("Live"), T.GREEN, tr("Connecting to the view…"))
        st.state == "requesting" -> LiveLook(tr("Waiting"), T.ACCENT, tr("Waiting for the wearer…"))
        st.state == "denied" -> LiveLook(tr("Declined"), T.RED, tr("The wearer said no."))
        st.state == "unsupported" -> LiveLook(tr("No view"), null, tr("This headset cannot share its view."))
        st.state == "error" -> LiveLook(tr("Failed"), T.RED, tr("Sharing failed."))
        st.live -> LiveLook(tr("Shared"), T.GREEN, tr("Watch to see what they see."))
        else -> LiveLook(tr("Off"), null, tr("Watch asks the wearer to share."))
    }
}

// -- where things go ----------------------------------------------------------------------------

private const val GAP = 8f
private const val HEAD = 30f
private const val PAD = 10f

/** The view's place and the two panels', in dp, for a stage this big. */
private fun castBoxes(w: Float, h: Float, landscape: Boolean, stream: StreamState): CastBoxes {
    val aspect = if (stream.width > 0 && stream.height > 0) stream.width.toFloat() / stream.height else 1f
    if (landscape) return CastLayout.landscape(w, h, GAP, HEAD, PAD)
    val minPanels = HEAD + PAD * 2 + 110f * panelSize(1f, GloveLook.CAST).height
    val b = CastLayout.portrait(w - 2 * GAP, h - GAP, aspect, GAP, minPanels, HEAD, PAD)
    // Upright, the stage is inset from the screen's edges, as the rest of the app is.
    fun inset(x: com.microtube.hexr.remote.Box) = x.copy(x = x.x + GAP)
    return CastBoxes(inset(b.view), inset(b.left), inset(b.right))
}

/**
 * The view and the two glove panels, in one Layout, so turning the phone moves them and never
 * rebuilds them: the view's TextureView, and the decoder drawing into it, carry on.
 */
@Composable
private fun CastStage(
    boxes: CastBoxes,
    row: HeadsetRow,
    status: HeadsetStatus?,
    timeline: HapticsTimeline,
    video: CastVideo,
    playView: Boolean,
    say: String,
    canControl: Boolean,
    onTapView: () -> Unit,
    onConnect: (String) -> Unit,
    onDisconnect: (String) -> Unit,
) {
    Layout(
        content = {
            ViewBox(row, status, video, playView, say, onTapView)
            for (hand in listOf(LEFT, RIGHT)) {
                GlovePanel(
                    hand = hand,
                    glove = status?.glove(hand),
                    timeline = timeline,
                    video = video,
                    canControl = canControl,
                    onConnect = { onConnect(hand) },
                    onDisconnect = { onDisconnect(hand) },
                )
            }
        },
        modifier = Modifier.fillMaxSize(),
    ) { measurables, constraints ->
        val rects = listOf(boxes.view, boxes.left, boxes.right)
        val placeables = measurables.mapIndexed { i, m ->
            val r = rects[i]
            m.measure(Constraints.fixed(r.w.dp.roundToPx().coerceAtLeast(0), r.h.dp.roundToPx().coerceAtLeast(0)))
        }
        layout(constraints.maxWidth, constraints.maxHeight) {
            placeables.forEachIndexed { i, p -> p.place(rects[i].x.dp.roundToPx(), rects[i].y.dp.roundToPx()) }
        }
    }
}

/** The view's place: the view while it plays, or what is happening instead, in its middle. */
@Composable
private fun ViewBox(
    row: HeadsetRow,
    status: HeadsetStatus?,
    video: CastVideo,
    playView: Boolean,
    say: String,
    onTap: () -> Unit,
) {
    val stream = status?.stream
    Box(
        Modifier
            .clip(RoundedCornerShape(T.R_CARD))
            .background(T.CARD)
            .clickable(onClick = onTap),
        contentAlignment = Alignment.Center,
    ) {
        if (playView && stream != null) {
            // A new share can come back on another port: a fresh view for it.
            androidx.compose.runtime.key(row.host, stream.port) {
                HeadsetVideo(row.host, stream.port, stream.width, stream.height, video)
            }
        }
        val playing = playView && video.state is VideoPlayer.VideoState.Playing
        if (!playing && say.isNotEmpty()) {
            Text(
                say,
                Modifier.padding(24.dp),
                color = T.TEXT_2,
                fontSize = P.BODY.sp,
                lineHeight = 21.sp,
                textAlign = TextAlign.Center,
            )
        }
    }
}

/**
 * One glove: its hand, whether the headset has it and its battery, and the glove itself, lit
 * with what the frame on screen shows the wearer feeling.
 */
@Composable
private fun GlovePanel(
    hand: String,
    glove: GloveState?,
    timeline: HapticsTimeline,
    video: CastVideo,
    canControl: Boolean,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
) {
    var menu by remember { mutableStateOf(false) }
    val connected = glove?.connected == true
    val tappable = canControl && glove != null && !glove.missing && !glove.connecting
    val (word, colour) = badgeWord(glove)
    val battery = glove?.batteryPct?.takeIf { it >= 0 && connected }
    val described = tr("{hand} glove", "hand" to tr(hand)) + ", " + word.lowercase() +
        (battery?.let { ", " + tr("battery {level}", "level" to "$it%") } ?: "")
    val key = hand.lowercase()

    Box(
        Modifier
            .clip(RoundedCornerShape(T.R_CARD))
            .background(T.ELEVATED)
            .border(1.dp, T.BORDER_SOFT, RoundedCornerShape(T.R_CARD))
            .clickable(enabled = tappable) { if (connected) menu = true else onConnect() }
            .semantics { contentDescription = described },
    ) {
        BoxWithConstraints(Modifier.fillMaxSize().padding(PAD.dp)) {
            // Narrow, the badge goes under the hand's name rather than beside it.
            val stacked = maxWidth < 170.dp
            Column(Modifier.fillMaxSize()) {
                if (stacked) {
                    Heading(hand)
                    Badge(word, colour, battery)
                } else {
                    Row(Modifier.fillMaxWidth().height(20.dp), verticalAlignment = Alignment.CenterVertically) {
                        Heading(hand)
                        Spacer(Modifier.weight(1f))
                        Badge(word, colour, battery)
                    }
                }
                BoxWithConstraints(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                    val fit = fitGh(maxWidth.value, maxHeight.value, GloveLook.CAST)
                    if (fit >= 40f) {
                        GloveArt(
                            hand = hand,
                            look = if (fit >= 200f) GloveLook.CAST else GloveLook.CAST_QUIET,
                            gh = fit.dp,
                            stateAt = {
                                val sh = video.shown()
                                if (sh != null) timeline.state(key, sh.ptsUs, sh.arrivedS)
                                else timeline.stateNow(key, VideoPlayer.nowS())
                            },
                            dim = if (connected) 1f else .3f,
                        )
                    }
                }
            }
        }
        DropdownMenu(menu, onDismissRequest = { menu = false }, containerColor = T.CARD) {
            DropdownMenuItem(
                text = { Text(tr("Disconnect"), color = T.RED, fontSize = P.BODY.sp) },
                onClick = {
                    menu = false
                    onDisconnect()
                },
                modifier = Modifier.heightIn(min = P.TOUCH),
            )
        }
    }
}

/** The words drawn with the glove stay English, as on the desktop and the website. */
@Composable
private fun Heading(hand: String) {
    Text(
        if (hand == LEFT) "LEFT HAND" else "RIGHT HAND",
        color = T.TEXT_3, fontSize = 11.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.sp, maxLines = 1,
    )
}

@Composable
private fun Badge(word: String, colour: Color, battery: Int?) {
    Row(Modifier.height(20.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(7.dp).clip(CircleShape).background(colour))
        Spacer(Modifier.width(5.dp))
        Text(word, color = colour, fontSize = 10.5.sp, fontWeight = FontWeight.Bold, maxLines = 1)
        if (battery != null) {
            Text(
                "  ·  $battery%",
                color = if (battery < 20) T.AMBER else T.TEXT_2, fontSize = 10.5.sp, fontWeight = FontWeight.Bold, maxLines = 1,
            )
        }
    }
}

private fun badgeWord(glove: GloveState?): Pair<String, Color> = when {
    glove == null || glove.missing -> "NO GLOVE" to T.TEXT_5
    glove.connected -> "CONNECTED" to T.GREEN
    glove.connecting -> "CONNECTING" to T.ACCENT
    else -> "NOT CONNECTED" to T.TEXT_5
}

// -- the controls -------------------------------------------------------------------------------

/** Upright: the bar along the bottom. Watch and full screen, then Release all and Recenter. */
@Composable
private fun ActionBar(a: LiveActions) {
    Column(Modifier.fillMaxWidth().background(T.SCREEN)) {
        Box(Modifier.fillMaxWidth().height(1.dp).background(T.HAIRLINE))
        Column(
            Modifier
                .fillMaxWidth()
                .windowInsetsPadding(WindowInsets.navigationBars)
                .padding(horizontal = T.PAGE_PAD, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                WatchButton(a, Modifier.weight(1f), P.ACTION)
                FullScreenButton(enabled = a.playing, onClick = a.onFullScreen)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                ReleaseButton(a, Modifier.weight(1f))
                RecenterButton(a, Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun WatchButton(a: LiveActions, modifier: Modifier, height: androidx.compose.ui.unit.Dp) {
    ActionButton(
        if (a.watching) "■  " + tr("Stop watching") else "▶  " + tr("Watch"),
        modifier,
        style = if (a.watching) ActionStyle.DangerOutline else ActionStyle.Primary,
        enabled = a.watching || a.canWatch,
        height = height,
        onClick = a.onWatch,
    )
}

@Composable
private fun ReleaseButton(a: LiveActions, modifier: Modifier) {
    ActionButton(tr("Release all"), modifier, style = ActionStyle.Ghost, enabled = a.canRelease, height = P.TOUCH, onClick = a.onRelease)
}

@Composable
private fun RecenterButton(a: LiveActions, modifier: Modifier) {
    ActionButton(
        if (a.recentered) "✓  " + tr("Recenter") else tr("Recenter"),
        modifier,
        style = ActionStyle.Ghost,
        enabled = a.canRecenter,
        height = P.TOUCH,
        onDisabledClick = a.onRecenterWhyNot,
        onClick = a.onRecenter,
    )
}

/** Four corners drawn outward: full screen. Drawn here, as the app's other glyphs are. */
@Composable
private fun FullScreenButton(enabled: Boolean, onClick: () -> Unit) {
    Box(
        Modifier
            .size(P.ACTION)
            .clip(RoundedCornerShape(T.R_CTRL))
            .background(T.CARD)
            .border(1.dp, T.BORDER, RoundedCornerShape(T.R_CTRL))
            .clickable(enabled = enabled, onClick = onClick)
            .semantics { contentDescription = tr("Full screen") },
        contentAlignment = Alignment.Center,
    ) {
        val tint = if (enabled) T.TEXT else T.TEXT_5
        Canvas(Modifier.size(22.dp)) {
            val u = size.width / 20f
            val w = 1.8f * u
            fun corner(x: Float, y: Float, dx: Float, dy: Float) {
                drawLine(tint, Offset(x * u, y * u), Offset((x + dx) * u, y * u), w, StrokeCap.Round)
                drawLine(tint, Offset(x * u, y * u), Offset(x * u, (y + dy) * u), w, StrokeCap.Round)
            }
            corner(3f, 3f, 5f, 5f)
            corner(17f, 3f, -5f, 5f)
            corner(3f, 17f, 5f, -5f)
            corner(17f, 17f, -5f, -5f)
        }
    }
}

/** The header upright: back, the headset's name and its app, the state, and ⋯. */
@Composable
private fun TopBar(vm: HeadsetsViewModel, row: HeadsetRow, look: LiveLook, onBack: () -> Unit) {
    var menu by remember { mutableStateOf(false) }
    var renaming by remember { mutableStateOf(false) }
    var details by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxWidth().background(T.SCREEN).windowInsetsPadding(WindowInsets.statusBars)) {
        Row(
            Modifier.fillMaxWidth().heightIn(min = 56.dp).padding(horizontal = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            BackButton(onBack)
            Column(Modifier.weight(1f).padding(horizontal = 4.dp)) {
                Text(row.title, color = T.TEXT, fontSize = 16.sp, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(appLine(row), color = T.TEXT_4, fontSize = 12.5.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            StateChip(look.word, look.dot)
            Box {
                MoreButton { menu = true }
                DropdownMenu(menu, onDismissRequest = { menu = false }, containerColor = T.CARD) {
                    MenuItem(tr("Rename")) { menu = false; renaming = true }
                    MenuItem(tr("Details")) { menu = false; details = true }
                    if (row.manual) MenuItem(tr("Forget"), T.RED) { menu = false; vm.forget(row.key) }
                }
            }
        }
        Box(Modifier.fillMaxWidth().height(1.dp).background(T.HAIRLINE))
    }
    if (renaming) RenameDialog(row, onDone = { name -> vm.rename(row.key, name); renaming = false }, onCancel = { renaming = false })
    if (details) DetailsDialog(row, onClose = { details = false })
}

/** Sideways: the controls over the view, fading once it plays. */
@Composable
private fun Overlay(
    boxes: CastBoxes,
    row: HeadsetRow,
    look: LiveLook,
    shown: Boolean,
    actions: LiveActions,
    fullScreen: Boolean,
    note: String?,
    onBack: () -> Unit,
) {
    val v = boxes.view
    AnimatedVisibility(
        shown, enter = fadeIn(), exit = fadeOut(),
        modifier = Modifier.offset(v.x.dp, v.y.dp).size(v.w.dp, v.h.dp),
    ) {
        Box(Modifier.fillMaxSize().clip(RoundedCornerShape(T.R_CARD))) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .background(Brush.verticalGradient(listOf(Color.Black.copy(alpha = .7f), Color.Transparent)))
                    .windowInsetsPadding(WindowInsets.displayCutout)
                    .padding(6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                BackButton(onBack)
                Text(
                    row.title, Modifier.weight(1f), color = T.TEXT, fontSize = 15.sp, fontWeight = FontWeight.SemiBold,
                    maxLines = 1, overflow = TextOverflow.Ellipsis,
                )
                StateChip(look.word, look.dot)
            }
            Column(
                Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .background(Brush.verticalGradient(listOf(Color.Transparent, Color.Black.copy(alpha = .75f))))
                    .windowInsetsPadding(WindowInsets.displayCutout)
                    .padding(horizontal = 12.dp, vertical = 10.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                val say = row.error ?: note
                if (say != null) Caption(say, color = if (row.error != null) T.RED else T.TEXT_2, size = P.SMALL)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    WatchButton(actions, Modifier.weight(1.3f), P.TOUCH)
                    ReleaseButton(actions, Modifier.weight(1f))
                    RecenterButton(actions, Modifier.weight(1f))
                    if (!fullScreen) FullScreenButton(enabled = actions.playing, onClick = actions.onFullScreen)
                }
            }
        }
    }
}

@Composable
private fun BackButton(onClick: () -> Unit) {
    Box(
        Modifier
            .size(P.TOUCH)
            .clip(CircleShape)
            .clickable(onClick = onClick)
            .semantics { contentDescription = tr("Back") },
        contentAlignment = Alignment.Center,
    ) {
        Canvas(Modifier.size(20.dp)) {
            val u = size.width / 20f
            drawLine(T.TEXT, Offset(12.5f * u, 4f * u), Offset(6.5f * u, 10f * u), 2f * u, StrokeCap.Round)
            drawLine(T.TEXT, Offset(6.5f * u, 10f * u), Offset(12.5f * u, 16f * u), 2f * u, StrokeCap.Round)
        }
    }
}

@Composable
private fun MoreButton(onClick: () -> Unit) {
    Box(
        Modifier
            .size(P.TOUCH)
            .clip(CircleShape)
            .clickable(onClick = onClick)
            .semantics { contentDescription = tr("More") },
        contentAlignment = Alignment.Center,
    ) {
        Canvas(Modifier.size(20.dp)) {
            val r = size.width / 20f * 1.6f
            for (y in listOf(4f, 10f, 16f)) drawCircle(T.TEXT_2, r, Offset(size.width / 2, y * size.width / 20f))
        }
    }
}

@Composable
private fun MenuItem(text: String, colour: Color = T.TEXT, onClick: () -> Unit) {
    DropdownMenuItem(
        text = { Text(text, color = colour, fontSize = P.BODY.sp) },
        onClick = onClick,
        modifier = Modifier.heightIn(min = P.TOUCH),
    )
}

@Composable
private fun RenameDialog(row: HeadsetRow, onDone: (String) -> Unit, onCancel: () -> Unit) {
    var name by rememberSaveable(row.key) { mutableStateOf(row.nickname) }
    AlertDialog(
        onDismissRequest = onCancel,
        containerColor = T.CARD,
        title = { Text(tr("Rename"), color = T.TEXT, fontWeight = FontWeight.Bold) },
        text = {
            OutlinedTextField(
                value = name,
                onValueChange = { name = it },
                singleLine = true,
                placeholder = { Text(tr("Station 1"), color = T.TEXT_5) },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text),
                colors = fieldColours(),
                modifier = Modifier.fillMaxWidth(),
            )
        },
        confirmButton = { TextLink(tr("Done"), color = T.ACCENT) { onDone(name) } },
        dismissButton = { TextLink(tr("Cancel")) { onCancel() } },
    )
}

/** The numbers, for a bug report: versions, the share, the haptics. */
@Composable
private fun DetailsDialog(row: HeadsetRow, onClose: () -> Unit) {
    val s = row.status
    AlertDialog(
        onDismissRequest = onClose,
        containerColor = T.CARD,
        title = { Text(tr("Details"), color = T.TEXT, fontWeight = FontWeight.Bold) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                MonoText(row.host, color = T.TEXT_2, size = 12.5f)
                if (s != null) {
                    MonoText(
                        "hexr ${s.hexrVersion}   app ${s.appVersion}   phones ${s.controllers}" +
                            if (s.headsetBatteryPct >= 0) "   headset ${s.headsetBatteryPct}%" else "",
                        color = T.TEXT_2, size = 12.5f,
                    )
                    val st = s.stream
                    if (st.live) {
                        MonoText(
                            tr("Shared · {w}×{h}", "w" to st.width, "h" to st.height) +
                                if (st.viewers > 0) tr(" · {n} watching", "n" to st.viewers) else "",
                            color = T.TEXT_2, size = 12.5f,
                        )
                    }
                    if (st.message.isNotEmpty()) MonoText(st.message, color = T.TEXT_3, size = 12.5f)
                    for (g in s.gloves) {
                        MonoText(
                            "${g.hand}  ${g.state}" + (if (g.batteryPct >= 0) "  ${g.batteryPct}%" else "") +
                                (if (g.message.isNotBlank()) "  ${g.message}" else ""),
                            color = T.TEXT_3, size = 12.5f,
                        )
                    }
                }
            }
        },
        confirmButton = { TextLink(tr("Close")) { onClose() } },
    )
}

@Composable
internal fun fieldColours() = OutlinedTextFieldDefaults.colors(
    focusedTextColor = T.TEXT,
    unfocusedTextColor = T.TEXT,
    focusedBorderColor = T.ACCENT,
    unfocusedBorderColor = T.BORDER,
    cursorColor = T.ACCENT,
    focusedContainerColor = T.ELEVATED,
    unfocusedContainerColor = T.ELEVATED,
)

/** The app on the headset, and its scene: "HexR Demo · Lab". */
internal fun appLine(row: HeadsetRow): String {
    val s = row.status
    val app = s?.app ?: row.announce?.app ?: tr("HexR headset")
    val scene = s?.scene?.name?.takeIf { it.isNotEmpty() }
    return if (scene != null) "$app · $scene" else app
}

private tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
}

// -- the view -----------------------------------------------------------------------------------

/**
 * The player of one view and the frame it has on screen. Held by the screen, not the view, so
 * the glove panels can ask it which frame is showing.
 */
@Stable
private class CastVideo {
    var state by mutableStateOf<VideoPlayer.VideoState?>(null)
        private set

    private var player: VideoPlayer? = null
    private var surface: Surface? = null
    private var host = ""
    private var port = 0
    private var wifi: WifiNetwork? = null
    private var generation = 0

    /** Whether this phone is one of the viewers the headset counts. */
    val joined get() = player != null && state !is VideoPlayer.VideoState.Failed

    /** The frame on screen, while the view plays. */
    fun shown(): VideoPlayer.Shown? = if (state is VideoPlayer.VideoState.Playing) player?.shown else null

    fun start(surface: Surface, host: String, port: Int, wifi: WifiNetwork, post: (Runnable) -> Unit) {
        stopPlayer()
        this.surface = surface
        this.host = host
        this.port = port
        this.wifi = wifi
        play(post)
    }

    /** The view dropped while the headset still shares it: join again, on the same surface. */
    fun rejoin(post: (Runnable) -> Unit) {
        if (surface == null || wifi == null) return
        stopPlayer()
        play(post)
    }

    private fun play(post: (Runnable) -> Unit) {
        val mine = ++generation
        state = VideoPlayer.VideoState.Connecting
        player = VideoPlayer(host, port, surface!!, wifi!!) { st ->
            post(Runnable { if (generation == mine) state = st })
        }.also { it.start() }
    }

    private fun stopPlayer() {
        generation++
        player?.stop()
        player = null
    }

    fun release() {
        stopPlayer()
        surface?.release()
        surface = null
        state = null
    }
}

/**
 * The headset's view, decoded onto a TextureView, fitted to its place by the view's transform:
 * filling it and cut low when the view is taller than the place, whole otherwise. The player
 * starts when the surface exists and stops before it is handed back.
 */
@Composable
private fun HeadsetVideo(host: String, port: Int, streamW: Int, streamH: Int, video: CastVideo) {
    val context = LocalContext.current
    val wifi = remember { WifiNetwork(context).also { it.start() } }
    DisposableEffect(host, port) {
        onDispose {
            video.release()
            wifi.stop()
        }
    }
    val state = video.state
    val (vw, vh) = (state as? VideoPlayer.VideoState.Playing)?.let { it.width to it.height } ?: (streamW to streamH)

    var texture by remember { mutableStateOf<TextureView?>(null) }
    // Dropped while the share goes on: join again after a moment, as the desktop does.
    LaunchedEffect(state) {
        if (state is VideoPlayer.VideoState.Failed) {
            delay(3000)
            texture?.let { tv -> video.rejoin { tv.post(it) } }
        }
    }

    AndroidView(
        factory = { ctx ->
            TextureView(ctx).apply {
                texture = this
                surfaceTextureListener = object : TextureView.SurfaceTextureListener {
                    override fun onSurfaceTextureAvailable(st: SurfaceTexture, w: Int, h: Int) {
                        video.start(Surface(st), host, port, wifi) { post(it) }
                    }

                    override fun onSurfaceTextureSizeChanged(st: SurfaceTexture, w: Int, h: Int) = Unit

                    override fun onSurfaceTextureDestroyed(st: SurfaceTexture): Boolean {
                        video.release()
                        return true
                    }

                    override fun onSurfaceTextureUpdated(st: SurfaceTexture) = Unit
                }
                addOnLayoutChangeListener { v, _, _, _, _, _, _, _, _ -> fit(v as TextureView) }
            }
        },
        update = { tv ->
            tv.tag = vw to vh
            fit(tv)
        },
        modifier = Modifier.fillMaxSize(),
    )
}

/** The view's transform, so the whole frame lands where CastLayout.videoRect puts it. */
private fun fit(tv: TextureView) {
    val size = tv.tag as? Pair<*, *> ?: return
    val vw = size.first as? Int ?: return
    val vh = size.second as? Int ?: return
    val bw = tv.width.toFloat()
    val bh = tv.height.toFloat()
    if (bw <= 0 || bh <= 0) return
    val r = CastLayout.videoRect(com.microtube.hexr.remote.Box(0f, 0f, bw, bh), vw, vh)
    tv.setTransform(Matrix().apply {
        setScale(r.w / bw, r.h / bh)
        postTranslate(r.x, r.y)
    })
}
