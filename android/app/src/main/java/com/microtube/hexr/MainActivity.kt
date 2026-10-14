package com.microtube.hexr

import android.content.Intent
import android.content.pm.ApplicationInfo
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.microtube.hexr.ui.Caption
import com.microtube.hexr.ui.PrimaryButton
import com.microtube.hexr.ui.ConnectScreen
import com.microtube.hexr.ui.Dot
import com.microtube.hexr.ui.HeadsetsScreen
import com.microtube.hexr.ui.HexrTheme
import com.microtube.hexr.ui.QuickTestScreen
import com.microtube.hexr.ui.Size
import com.microtube.hexr.ui.T
import com.microtube.hexr.ui.TestScreen
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
        var startTab = Tab.Connect
        if (applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE != 0) {
            val scenario = intent.getStringExtra("demo")
            scenario?.let(vm::seedDemo)
            startTab = Tab.named(DemoSeed.startTabFor(scenario))
        }
        setContent {
            HexrTheme {
                AppRoot(
                    vm = vm,
                    headsets = headsets,
                    startTab = startTab,
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

private enum class Tab(val label: String) {
    Connect("Connect"),
    Test("Test"),
    Quick("Quick test"),
    Headsets("Headsets");

    companion object {
        /** Resolve a [DemoSeed] scenario's tab name. Anything else is Connect. */
        fun named(name: String?): Tab =
            entries.firstOrNull { it.name.equals(name, ignoreCase = true) } ?: Connect
    }
}

@Composable
private fun AppRoot(
    vm: HexrViewModel,
    headsets: HeadsetsViewModel,
    startTab: Tab,
    onRequestPermissions: () -> Unit,
    onOpenBluetoothSettings: () -> Unit,
) {
    var tab by remember { mutableStateOf(startTab) }
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

    Box(Modifier.fillMaxSize().background(T.SCREEN)) {
        if (!vm.permissionsGranted) {
            PermissionGate(vm.mustUseSettings, onRequestPermissions)
        } else {
        Scaffold(
            containerColor = T.SCREEN,
            topBar = { Header(vm) },
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
                    Tab.Connect -> ConnectScreen(vm, onOpenBluetoothSettings)
                    Tab.Test -> TestScreen(vm)
                    Tab.Quick -> QuickTestScreen(vm)
                    Tab.Headsets -> HeadsetsScreen(
                        headsets,
                        phoneGloves = HANDS.filter { vm.gloves[it]?.connected == true }.toSet(),
                    )
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
 * The lockup: mark, wordmark, product tag, connection state.
 *
 * There is no All off here. Release all on the Test tab is the one stop, and
 * two buttons that both mean stop is one more thing to reason about in the
 * moment you least want to.
 */
@Composable
private fun Header(vm: HexrViewModel) {
    val connected = HANDS.filter { vm.gloves[it]?.connected == true }
    Column(Modifier.fillMaxWidth().background(T.SCREEN)) {
        Box(Modifier.fillMaxWidth().windowInsetsPadding(WindowInsets.statusBars))
        Row(
            Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 12.dp),
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
        }
        Box(Modifier.fillMaxWidth().height(1.dp).background(T.BORDER_SOFT))
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
                    Canvas(Modifier.size(20.dp)) { drawTabGlyph(t.ordinal, tint) }
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
private fun DrawScope.drawTabGlyph(index: Int, tint: Color) {
    val u = size.width / 20f
    when (index) {
        0 -> {
            // Connect: a target — the ring and the thing at its centre.
            drawCircle(tint, radius = 6.5f * u, center = Offset(10 * u, 10 * u), style = Stroke(1.6f * u))
            drawCircle(tint, radius = 2f * u, center = Offset(10 * u, 10 * u))
        }

        1 -> {
            // Test: a pressure rise and fall.
            val p = Path().apply {
                moveTo(3 * u, 13 * u)
                lineTo(10 * u, 6 * u)
                lineTo(17 * u, 13 * u)
            }
            drawPath(p, tint, style = Stroke(1.8f * u, cap = StrokeCap.Round, join = StrokeJoin.Round))
        }

        2 -> {
            // Quick test: three channels at three different peaks.
            listOf(Triple(4f, 10f, 6f), Triple(8.7f, 6f, 10f), Triple(13.4f, 12f, 4f))
                .forEach { (x, y, h) ->
                    drawRect(
                        tint,
                        topLeft = Offset(x * u, y * u),
                        size = androidx.compose.ui.geometry.Size(2.6f * u, h * u),
                    )
                }
        }

        else -> {
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
