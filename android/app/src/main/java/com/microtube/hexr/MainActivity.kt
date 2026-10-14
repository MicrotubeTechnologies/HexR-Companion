package com.microtube.hexr

import android.content.Intent
import android.content.pm.ApplicationInfo
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.microtube.hexr.ui.Caption
import com.microtube.hexr.ui.PrimaryButton
import com.microtube.hexr.ui.Dot
import com.microtube.hexr.ui.GlovesPanel
import com.microtube.hexr.ui.HeadsetsScreen
import com.microtube.hexr.ui.HexrTheme
import com.microtube.hexr.ui.QuickTestScreen
import com.microtube.hexr.ui.ScanScreen
import com.microtube.hexr.ui.Size
import com.microtube.hexr.ui.T
import com.microtube.hexr.ui.TestScreen
import com.microtube.hexr.ui.drawBluetoothRune
import kotlinx.coroutines.delay
import kotlin.math.cos
import kotlin.math.sin

class MainActivity : ComponentActivity() {

    private val vm: HexrViewModel by viewModels()
    private val headsets: HeadsetsViewModel by viewModels()

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) {
        vm.permissionsGranted = vm.engine.hasPermissions()
        // A denial with no rationale left to show means Android will not put
        // the dialog up again. Record it so the screen can offer Settings
        // rather than a button that now does nothing at all.
        vm.mustUseSettings = !vm.permissionsGranted &&
            vm.engine.requiredPermissions.none { shouldShowRequestPermissionRationale(it) }
    }

    /** The app's own page in system Settings, where the grant can be given. */
    private fun openAppSettings() {
        startActivity(
            Intent(
                Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                Uri.fromParts("package", packageName, null),
            ),
        )
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        // Store screenshots, and nothing else. A debuggable build only, and
        // only when a scenario is named on the intent — there is no way here
        // from the UI, and no way at all from the build that goes to Play.
        // See DemoSeed.kt.
        var start = Start(Tab.Test, Panel.None)
        if (applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE != 0) {
            val scenario = intent.getStringExtra("demo")
            scenario?.let(vm::seedDemo)
            start = Start.named(DemoSeed.startTabFor(scenario))
        }
        setContent {
            HexrTheme {
                AppRoot(
                    vm = vm,
                    headsets = headsets,
                    start = start,
                    onRequestPermissions = {
                        if (vm.mustUseSettings) {
                            openAppSettings()
                        } else {
                            permissionLauncher.launch(vm.engine.requiredPermissions)
                        }
                    },
                    onOpenBluetoothSettings = {
                        startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS))
                    },
                )
            }
        }
    }

    /** onResume, not onStart: a permission dialog pauses the activity, it does
     *  not stop it, so onStart never runs on the way back from one. */
    override fun onResume() {
        super.onResume()
        vm.permissionsGranted = vm.engine.hasPermissions()
        if (vm.permissionsGranted) vm.mustUseSettings = false
    }

    /**
     * Vent everything the moment the app stops being visible.
     *
     * A phone gets pocketed mid-test in a way a desktop window does not, and a
     * channel left inflated presses on someone's hand until the battery dies.
     * Costing a technician one re-trigger is much the cheaper mistake.
     */
    override fun onStop() {
        vm.onBackground()
        // Headsets: sockets and the Wi-Fi multicast lock go with the screen. Nothing on that tab
        // keeps working in a pocket, and the lock costs battery.
        headsets.setForeground(false)
        super.onStop()
    }

    override fun onStart() {
        super.onStart()
        headsets.setForeground(true)
    }
}

/**
 * Two tabs: this phone's own gloves, and the headsets on the Wi-Fi.
 *
 * Connecting and the quick test used to be tabs of their own. They are both things you do on
 * the way to testing a glove, so they now live on the Test tab: until a glove connects the tab
 * is the scan, and after that the header carries a Quick test button and a Bluetooth button
 * that open them as panels over the controls.
 */
private enum class Tab(val label: String) {
    Test("Test"),
    Headsets("Headsets"),
}

/** What is open over the Test tab, if anything. */
private enum class Panel(val title: String) {
    None(""),
    Gloves("Gloves"),
    QuickTest("Quick test"),
}

/** Where the app opens: a tab, and on the Test tab perhaps one of its panels. */
private data class Start(val tab: Tab, val panel: Panel) {
    companion object {
        /**
         * A [DemoSeed] scenario's start screen. The scenarios predate the panels and still name
         * the old tabs, so "connect" and "quick" open the panels those tabs became.
         */
        fun named(name: String?): Start = when (name?.lowercase()) {
            "connect" -> Start(Tab.Test, Panel.Gloves)
            "quick" -> Start(Tab.Test, Panel.QuickTest)
            "headsets" -> Start(Tab.Headsets, Panel.None)
            else -> Start(Tab.Test, Panel.None)
        }
    }
}

@Composable
private fun AppRoot(
    vm: HexrViewModel,
    headsets: HeadsetsViewModel,
    start: Start,
    onRequestPermissions: () -> Unit,
    onOpenBluetoothSettings: () -> Unit,
) {
    var tab by remember { mutableStateOf(start.tab) }
    var panel by remember { mutableStateOf(start.panel) }
    // What the panel showed last, so it keeps its content while it slides away. A plain
    // holder, not state: it only changes in a composition that `panel` already caused.
    val lastPanel = remember { arrayOf(start.panel) }
    if (panel != Panel.None) lastPanel[0] = panel
    val shownPanel = lastPanel[0]
    var splash by remember { mutableStateOf(true) }
    var splashFading by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        delay(1600)
        splashFading = true
        delay(400)
        splash = false
    }

    // Ask once, the moment the splash clears. Bluetooth is not a feature of
    // this app, it is the app — there is nothing to show someone who has not
    // granted it, so the request comes to them rather than waiting behind a
    // button they have to find.
    var asked by rememberSaveable { mutableStateOf(false) }
    LaunchedEffect(splash, vm.permissionsGranted, vm.mustUseSettings) {
        if (!splash && !vm.permissionsGranted && !asked && !vm.mustUseSettings) {
            asked = true
            onRequestPermissions()
        }
    }

    val anyGlove = HANDS.any { vm.gloves[it]?.connected == true }
    // Testing: the Test tab with a glove to test. Until then the tab is the scan.
    val testing = tab == Tab.Test && anyGlove

    // Closing the quick test while it runs stops it, as leaving the Test tab
    // vents a drive: otherwise every channel stays at full pressure behind a
    // screen that can no longer stop it.
    val closePanel = {
        if (panel == Panel.QuickTest && vm.qtPhase in RUNNING_PHASES) vm.toggleQuickTest()
        panel = Panel.None
    }
    BackHandler(enabled = panel != Panel.None, onBack = closePanel)

    Box(Modifier.fillMaxSize().background(T.SCREEN)) {
        if (!vm.permissionsGranted) {
            PermissionGate(vm.mustUseSettings, onRequestPermissions)
        } else {
        Scaffold(
            containerColor = T.SCREEN,
            topBar = {
                Header(
                    vm,
                    actions = if (!testing) {
                        null
                    } else {
                        {
                            HeaderButton(
                                label = "Quick test",
                                description = "Quick test",
                                glyph = { drawQuickTestGlyph(it) },
                                onClick = { panel = Panel.QuickTest },
                            )
                            BluetoothButton(vm, onClick = { panel = Panel.Gloves })
                        }
                    },
                )
            },
            bottomBar = {
                BottomBar(tab) { picked ->
                    // Leaving the Test tab is leaving the only screen with a
                    // Release all on it, so the drive ends with the tab. The
                    // alternative is output running behind a screen that cannot
                    // stop it.
                    if (picked != Tab.Test && vm.driving) vm.release()
                    tab = picked
                }
            },
        ) { pad ->
            Box(Modifier.padding(pad).fillMaxSize()) {
                when (tab) {
                    Tab.Test -> if (anyGlove) TestScreen(vm) else ScanScreen(vm, onOpenBluetoothSettings)
                    Tab.Headsets -> HeadsetsScreen(
                        headsets,
                        phoneGloves = HANDS.filter { vm.gloves[it]?.connected == true }.toSet(),
                    )
                }
            }
        }

        AnimatedVisibility(
            visible = panel != Panel.None,
            enter = slideInVertically(tween(220)) { it / 10 } + fadeIn(tween(220)),
            exit = slideOutVertically(tween(180)) { it / 10 } + fadeOut(tween(180)),
        ) {
            PanelSheet(shownPanel.title, onClose = closePanel) {
                when (shownPanel) {
                    Panel.Gloves -> GlovesPanel(vm, onOpenBluetoothSettings)
                    Panel.QuickTest -> QuickTestScreen(vm)
                    Panel.None -> Unit
                }
            }
        }
        }

        if (splash) {
            val fade by animateFloatAsState(
                if (splashFading) 0f else 1f,
                tween(400),
                label = "splashFade",
            )
            Splash(Modifier.alpha(fade))
        }
    }
}

/**
 * The whole app, behind the grant.
 *
 * Not a card on the Connect screen. Every screen here drives or reads a glove
 * over Bluetooth, so a build without the permission has no working surface at
 * all — showing tabs that cannot do anything only invites someone to conclude
 * the app is broken. Gating it also removes a class of bug outright: there is
 * no half-permitted state for the UI to get stuck in.
 */
@Composable
private fun PermissionGate(mustUseSettings: Boolean, onAction: () -> Unit) {
    Column(
        Modifier
            .fillMaxSize()
            .background(T.SCREEN)
            .windowInsetsPadding(WindowInsets.statusBars)
            .padding(horizontal = 32.dp, vertical = 24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Canvas(Modifier.size(56.dp)) { drawMark(2.8.dp.toPx()) }
        Spacer(Modifier.height(24.dp))
        Text(
            "Bluetooth access needed",
            color = T.TEXT,
            fontSize = Size.TITLE.sp,
            fontWeight = FontWeight.Bold,
        )
        Spacer(Modifier.height(10.dp))
        Text(
            "HEXR Tester talks to the glove over Bluetooth. Everything in the app — " +
                "connecting, driving a channel, the quick test — needs permission to find " +
                "and connect to nearby devices.",
            color = T.TEXT_2,
            fontSize = Size.BODY.sp,
            lineHeight = 20.sp,
            textAlign = TextAlign.Center,
        )
        if (mustUseSettings) {
            Spacer(Modifier.height(10.dp))
            Text(
                "Android will not ask again from inside the app. Open its settings and " +
                    "allow Nearby devices.",
                color = T.TEXT_5,
                fontSize = Size.CAPTION.sp,
                lineHeight = 18.sp,
                textAlign = TextAlign.Center,
            )
        }
        Spacer(Modifier.height(28.dp))
        PrimaryButton(
            if (mustUseSettings) "Open app settings" else "Allow Bluetooth",
            Modifier.fillMaxWidth(),
            onClick = onAction,
        )
    }
}

// -- splash ---------------------------------------------------------------------

@Composable
private fun Splash(modifier: Modifier = Modifier) {
    val t = rememberInfiniteTransition(label = "splash")
    val spin by t.animateFloat(
        0f, 360f,
        infiniteRepeatable(tween(2600, easing = LinearEasing), RepeatMode.Restart),
        label = "spin",
    )
    val pulse by t.animateFloat(
        0.94f, 1.06f,
        infiniteRepeatable(tween(900), RepeatMode.Reverse),
        label = "pulse",
    )

    Column(
        modifier.fillMaxSize().background(T.SCREEN),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(Modifier.size(88.dp), contentAlignment = Alignment.Center) {
            // A broken ring turning behind the mark: the dash is what makes the
            // rotation legible on a shape that is otherwise symmetric.
            Canvas(Modifier.size(88.dp).rotate(spin)) {
                drawPath(
                    hexagonPath(size.width / 2f, size.height / 2f, size.width * 0.455f),
                    T.ACCENT,
                    style = Stroke(
                        width = 2.dp.toPx(),
                        join = StrokeJoin.Round,
                        pathEffect = PathEffect.dashPathEffect(
                            floatArrayOf(60f * density / 3f, 200f * density / 3f),
                        ),
                    ),
                )
            }
            Canvas(Modifier.size(60.dp).scale(pulse)) { drawMark(3.dp.toPx()) }
        }

        Spacer(Modifier.height(22.dp))
        Text(
            "HEXR",
            color = T.TEXT,
            fontSize = 26.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = 1.6.sp,
        )
        Spacer(Modifier.height(6.dp))
        Text(
            "BY MICROTUBE TECHNOLOGIES",
            color = T.TEXT_3,
            fontSize = 11.sp,
            fontWeight = FontWeight.SemiBold,
            letterSpacing = 1.5.sp,
        )
    }
}

// -- header ---------------------------------------------------------------------

/**
 * The lockup: mark, wordmark, product tag, and either the connection state or, while testing,
 * the Quick test and Bluetooth buttons in its place. The Bluetooth button's dot says what the
 * state line would have, and there is not room on a phone for both.
 *
 * There is no All off here. Release all on the Test tab is the one stop, and
 * two buttons that both mean stop is one more thing to reason about in the
 * moment you least want to.
 */
@Composable
private fun Header(vm: HexrViewModel, actions: (@Composable RowScope.() -> Unit)? = null) {
    val connected = HANDS.filter { vm.gloves[it]?.connected == true }
    Column(Modifier.fillMaxWidth().background(T.SCREEN)) {
        Box(Modifier.fillMaxWidth().windowInsetsPadding(WindowInsets.statusBars))
        Row(
            Modifier
                .fillMaxWidth()
                .padding(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 10.dp)
                // As tall as the buttons, so the header does not jump when testing starts.
                .height(HEADER_BUTTON.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            Canvas(Modifier.size(22.dp)) { drawMark(1.65.dp.toPx()) }
            Text(
                "HEXR",
                color = T.TEXT,
                fontSize = Size.WORDMARK.sp,
                fontWeight = FontWeight.ExtraBold,
                letterSpacing = 0.5.sp,
            )
            Box(
                Modifier
                    .clip(RoundedCornerShape(5.dp))
                    .background(T.CARD)
                    .padding(horizontal = 6.dp, vertical = 3.dp),
            ) {
                Text(
                    "TESTER",
                    color = T.TEXT_3,
                    fontSize = Size.TAG.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 0.9.sp,
                )
            }
            if (actions == null) {
                Row(
                    Modifier.padding(start = 4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(5.dp),
                ) {
                    Dot(if (connected.isEmpty()) T.TEXT_FAINT else T.GREEN)
                    Caption(
                        when {
                            vm.driving -> "driving"
                            connected.isEmpty() -> "no glove"
                            else -> connected.joinToString(" + ") { it.lowercase() }
                        },
                        color = if (vm.driving) T.ACCENT else T.TEXT_2,
                        size = Size.MICRO,
                    )
                }
            } else {
                Spacer(Modifier.weight(1f))
                actions()
            }
        }
        Box(Modifier.fillMaxWidth().height(1.dp).background(T.BORDER_SOFT))
    }
}

private const val HEADER_BUTTON = 34

/** A quick test that is still driving every channel. */
private val RUNNING_PHASES = setOf("settle", "drive")

/** One of the header's buttons: a glyph, and a word when there is room for one. */
@Composable
private fun HeaderButton(
    label: String?,
    description: String,
    glyph: DrawScope.(Color) -> Unit,
    badge: Color? = null,
    onClick: () -> Unit,
) {
    Box {
        Row(
            Modifier
                .height(HEADER_BUTTON.dp)
                .clip(RoundedCornerShape(T.R_CARD))
                .background(T.CARD)
                .border(1.dp, T.BORDER, RoundedCornerShape(T.R_CARD))
                .clickable(onClickLabel = description, onClick = onClick)
                .semantics { contentDescription = description }
                .padding(horizontal = if (label == null) 8.dp else 11.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Canvas(Modifier.size(18.dp)) { glyph(T.TEXT) }
            if (label != null) {
                Text(label, color = T.TEXT, fontSize = Size.BODY_2.sp, fontWeight = FontWeight.SemiBold)
            }
        }
        if (badge != null) {
            Dot(
                badge,
                Modifier
                    .align(Alignment.TopEnd)
                    .offset(x = 2.dp, y = (-2).dp)
                    .border(2.dp, T.SCREEN, CircleShape),
                size = 10,
            )
        }
    }
}

/**
 * The gloves: what used to be the Connect tab, one tap away while testing. Its dot is the
 * connection state at a glance: green while a glove is connected, orange while a scan or a
 * connect is under way.
 */
@Composable
private fun BluetoothButton(vm: HexrViewModel, onClick: () -> Unit) {
    val busy = vm.scanning || HANDS.any { vm.gloves[it]?.connecting == true }
    val connected = HANDS.filter { vm.gloves[it]?.connected == true }
    HeaderButton(
        label = null,
        description = if (connected.isEmpty()) {
            "Gloves: none connected"
        } else {
            "Gloves: " + connected.joinToString(" and ") { it.lowercase() } + " connected"
        },
        glyph = { drawBluetoothRune(it) },
        badge = when {
            busy -> T.ACCENT
            connected.isNotEmpty() -> T.GREEN
            else -> null
        },
        onClick = onClick,
    )
}

/**
 * A panel over the Test tab: Gloves or Quick test. Full screen, because both are things you
 * look at properly rather than glance at, with its own title and a close button; Back closes it
 * too. It takes every touch, so nothing reaches the controls underneath.
 */
@Composable
private fun PanelSheet(title: String, onClose: () -> Unit, content: @Composable () -> Unit) {
    Column(
        Modifier
            .fillMaxSize()
            .background(T.SCREEN)
            .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null) {},
    ) {
        Box(Modifier.fillMaxWidth().windowInsetsPadding(WindowInsets.statusBars))
        Row(
            Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                title,
                Modifier.weight(1f),
                color = T.TEXT,
                fontSize = Size.TITLE.sp,
                fontWeight = FontWeight.Bold,
            )
            HeaderButton(label = null, description = "Close", glyph = { drawCloseGlyph(it) }, onClick = onClose)
        }
        Box(Modifier.fillMaxWidth().height(1.dp).background(T.BORDER_SOFT))
        Box(
            Modifier
                .weight(1f)
                .fillMaxWidth()
                .windowInsetsPadding(WindowInsets.navigationBars),
        ) { content() }
    }
}

/**
 * The HEXR mark: a hexagon outline with a smaller filled hexagon at its centre
 * — the channel dot, which is what the glove is actually made of.
 */
private fun DrawScope.drawMark(strokeWidth: Float) {
    val cx = size.width / 2f
    val cy = size.height / 2f
    drawPath(
        hexagonPath(cx, cy, size.width * 0.4583f),   // 55/60 of the half-width
        T.ACCENT,
        style = Stroke(width = strokeWidth, join = StrokeJoin.Round),
    )
    drawPath(hexagonPath(cx, cy, size.width * 0.1833f), T.ACCENT)
}

/** A pointy-top hexagon, matching the design's 30,3 / 55,16.5 / … polygon. */
private fun hexagonPath(cx: Float, cy: Float, r: Float): Path {
    val p = Path()
    for (i in 0 until 6) {
        val a = Math.toRadians(60.0 * i - 90.0)
        val x = cx + r * cos(a).toFloat()
        val y = cy + r * sin(a).toFloat()
        if (i == 0) p.moveTo(x, y) else p.lineTo(x, y)
    }
    p.close()
    return p
}

// -- tabs -------------------------------------------------------------------------

@Composable
private fun BottomBar(current: Tab, onPick: (Tab) -> Unit) {
    Column(Modifier.fillMaxWidth().background(T.SCREEN)) {
        Box(Modifier.fillMaxWidth().height(1.dp).background(T.BORDER_SOFT))
        Row(
            Modifier
                .fillMaxWidth()
                .windowInsetsPadding(WindowInsets.navigationBars)
                .padding(vertical = 8.dp),
        ) {
            Tab.entries.forEach { t ->
                val selected = t == current
                val tint = if (selected) T.ACCENT else T.TEXT_4
                Column(
                    Modifier
                        .weight(1f)
                        .clip(RoundedCornerShape(T.R_CARD))
                        .clickable { onPick(t) }
                        .padding(vertical = 6.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(3.dp),
                ) {
                    Canvas(Modifier.size(20.dp)) { drawTabGlyph(t, tint) }
                    Text(
                        t.label,
                        color = tint,
                        fontSize = Size.LABEL.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            }
        }
    }
}

/** Tab glyphs on a 20-unit grid, matching the design source. */
private fun DrawScope.drawTabGlyph(tab: Tab, tint: Color) {
    val u = size.width / 20f
    when (tab) {
        Tab.Test -> {
            // Test: a pressure rise and fall.
            val p = Path().apply {
                moveTo(3 * u, 13 * u)
                lineTo(10 * u, 6 * u)
                lineTo(17 * u, 13 * u)
            }
            drawPath(p, tint, style = Stroke(1.8f * u, cap = StrokeCap.Round, join = StrokeJoin.Round))
        }

        Tab.Headsets -> {
            // Headsets: a visor seen from the front, two lenses under one band.
            val stroke = Stroke(1.6f * u, cap = StrokeCap.Round, join = StrokeJoin.Round)
            drawRoundRect(
                tint,
                topLeft = Offset(2.5f * u, 6f * u),
                size = androidx.compose.ui.geometry.Size(15f * u, 8.5f * u),
                cornerRadius = androidx.compose.ui.geometry.CornerRadius(3f * u, 3f * u),
                style = stroke,
            )
            drawCircle(tint, radius = 1.6f * u, center = Offset(7f * u, 10.2f * u))
            drawCircle(tint, radius = 1.6f * u, center = Offset(13f * u, 10.2f * u))
        }
    }
}

/** Quick test: three channels at three different peaks. Was the Quick test tab's glyph. */
private fun DrawScope.drawQuickTestGlyph(tint: Color) {
    val u = size.width / 20f
    listOf(Triple(4f, 10f, 6f), Triple(8.7f, 6f, 10f), Triple(13.4f, 12f, 4f))
        .forEach { (x, y, h) ->
            drawRect(
                tint,
                topLeft = Offset(x * u, y * u),
                size = androidx.compose.ui.geometry.Size(2.6f * u, h * u),
            )
        }
}

/** Close: a cross, on the same grid. */
private fun DrawScope.drawCloseGlyph(tint: Color) {
    val u = size.width / 20f
    val stroke = 1.8f * u
    drawLine(tint, Offset(5f * u, 5f * u), Offset(15f * u, 15f * u), stroke, StrokeCap.Round)
    drawLine(tint, Offset(15f * u, 5f * u), Offset(5f * u, 15f * u), stroke, StrokeCap.Round)
}
