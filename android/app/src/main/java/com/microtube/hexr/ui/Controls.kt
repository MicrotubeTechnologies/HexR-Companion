package com.microtube.hexr.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * The phone's controls, in the desktop redesign's spirit: few words, one obvious action, big
 * enough for a thumb (48 dp at least), and numbers no smaller than 14 sp.
 */
object P {
    val TOUCH = 48.dp
    val ACTION = 64.dp
    const val BODY = 15f
    const val VALUE = 14f
    const val SMALL = 13f
    const val HEAD = 22f
    const val HEADLINE = 28f
}

/** Two or three choices in one track, one lit: Pressure | Vibration, Left | Right. */
@Composable
fun <K> Segmented(
    options: List<Pair<K, String>>,
    selected: K,
    modifier: Modifier = Modifier,
    enabled: (K) -> Boolean = { true },
    onPick: (K) -> Unit,
) {
    val haptics = LocalHapticFeedback.current
    Row(
        modifier
            .fillMaxWidth()
            .heightIn(min = P.TOUCH)
            .clip(RoundedCornerShape(T.R_CTRL))
            .background(T.CARD)
            .padding(3.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        for ((key, label) in options) {
            val on = key == selected
            val can = enabled(key)
            Box(
                Modifier
                    .weight(1f)
                    .heightIn(min = P.TOUCH - 6.dp)
                    .clip(RoundedCornerShape(T.R_CHIP))
                    .background(if (on) T.ELEVATED_2 else Color.Transparent)
                    .border(1.dp, if (on) T.ACCENT else Color.Transparent, RoundedCornerShape(T.R_CHIP))
                    .clickable(enabled = can && !on, role = Role.RadioButton) {
                        haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                        onPick(key)
                    },
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    label,
                    color = when {
                        !can -> T.TEXT_5
                        on -> T.ACCENT
                        else -> T.TEXT_2
                    },
                    fontSize = P.BODY.sp,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

/** A big action for the sticky bar: Trigger, Release all, Run, Watch. */
@Composable
fun ActionButton(
    label: String,
    modifier: Modifier = Modifier,
    sub: String? = null,
    style: ActionStyle = ActionStyle.Primary,
    enabled: Boolean = true,
    height: Dp = P.ACTION,
    onClick: () -> Unit,
) {
    val haptics = LocalHapticFeedback.current
    val (fill, fg, border) = when (style) {
        ActionStyle.Primary -> Triple(T.ACCENT, T.ON_ACCENT, T.ACCENT)
        ActionStyle.Danger -> Triple(T.RED, Color.White, T.RED)
        ActionStyle.DangerOutline -> Triple(T.CARD, T.RED, T.RED)
        ActionStyle.Ghost -> Triple(T.CARD, T.TEXT, T.BORDER)
    }
    Column(
        modifier
            .defaultMinSize(minHeight = height)
            .alpha(if (enabled) 1f else 0.4f)
            .clip(RoundedCornerShape(T.R_CTRL))
            .background(fill)
            .border(1.dp, border, RoundedCornerShape(T.R_CTRL))
            .clickable(enabled = enabled, role = Role.Button) {
                haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                onClick()
            }
            .padding(horizontal = 12.dp, vertical = 8.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(label, color = fg, fontSize = 16.sp, fontWeight = FontWeight.Bold, maxLines = 1)
        if (sub != null) {
            Text(sub, color = fg.copy(alpha = .75f), fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}

enum class ActionStyle { Primary, Danger, DangerOutline, Ghost }

/** The bar along the bottom that holds a screen's main actions, within a thumb's reach. */
@Composable
fun StickyActionBar(modifier: Modifier = Modifier, bottomInset: Boolean = false, content: @Composable RowScope.() -> Unit) {
    Column(modifier.fillMaxWidth().background(T.SCREEN)) {
        Box(Modifier.fillMaxWidth().height(1.dp).background(T.HAIRLINE))
        Row(
            Modifier
                .fillMaxWidth()
                .then(if (bottomInset) Modifier.navigationBarsPadding() else Modifier)
                .padding(horizontal = T.PAGE_PAD, vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            content = content,
        )
    }
}

/** A labelled slider with its value on the right: "Intensity   60% · 34 kPa". */
@Composable
fun ValueSlider(
    label: String,
    value: String,
    position: Float,
    modifier: Modifier = Modifier,
    range: ClosedFloatingPointRange<Float> = 0f..1f,
    trailing: @Composable (() -> Unit)? = null,
    onChange: (Float) -> Unit,
) {
    Column(modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(label, color = T.TEXT_2, fontSize = P.VALUE.sp, modifier = Modifier.weight(1f))
            if (trailing != null) {
                trailing()
                Spacer(Modifier.width(10.dp))
            }
            Text(value, color = T.TEXT, fontSize = P.VALUE.sp, fontWeight = FontWeight.SemiBold, fontFamily = Mono)
        }
        val colors = SliderDefaults.colors(
            thumbColor = T.ACCENT,
            activeTrackColor = T.ACCENT,
            inactiveTrackColor = T.CARD,
        )
        // No stop dot at the end of the track: the value on the right already says where it is.
        @OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
        Slider(
            value = position,
            onValueChange = onChange,
            valueRange = range,
            modifier = Modifier.heightIn(min = P.TOUCH),
            colors = colors,
            track = { SliderDefaults.Track(sliderState = it, colors = colors, drawStopIndicator = null) },
        )
    }
}

/** Signal strength as four bars. */
@Composable
fun SignalBars(bars: Int, modifier: Modifier = Modifier) {
    Canvas(modifier.size(20.dp, 14.dp)) {
        val w = size.width / 4
        for (i in 0 until 4) {
            val h = size.height * (i + 1) / 4
            drawRect(
                if (i < bars) T.GREEN else T.BORDER_STRONG,
                topLeft = Offset(i * w + 1, size.height - h),
                size = androidx.compose.ui.geometry.Size(w - 2, h),
            )
        }
    }
}

/** A dot and a word: the state of a view, a glove, a link. */
@Composable
fun StateChip(text: String, dot: Color?, modifier: Modifier = Modifier) {
    Row(
        modifier
            .clip(RoundedCornerShape(T.R_PILL))
            .background(T.CARD)
            .border(1.dp, T.BORDER_SOFT, RoundedCornerShape(T.R_PILL))
            .padding(horizontal = 10.dp, vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Box(Modifier.size(8.dp).clip(CircleShape).background(dot ?: T.TEXT_5))
        Text(text, color = T.TEXT_2, fontSize = P.SMALL.sp, fontWeight = FontWeight.SemiBold, maxLines = 1)
    }
}

/** A word that does something: All · None, Try again. */
@Composable
fun TextLink(text: String, modifier: Modifier = Modifier, color: Color = T.TEXT_2, onClick: () -> Unit) {
    Box(
        modifier
            .heightIn(min = P.TOUCH)
            .clip(RoundedCornerShape(T.R_CHIP))
            .clickable(role = Role.Button, onClick = onClick)
            .padding(horizontal = 10.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(text, color = color, fontSize = P.VALUE.sp, fontWeight = FontWeight.SemiBold)
    }
}

/**
 * The header's one glove status, on every screen: the Bluetooth rune, a dot for each hand
 * (green connected, orange connecting) and the lower battery, amber when it is low.
 */
@Composable
fun GlovesButton(
    left: Color,
    right: Color,
    battery: String?,
    low: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    Row(
        modifier
            .heightIn(min = 40.dp)
            .clip(RoundedCornerShape(T.R_CTRL))
            .background(T.CARD)
            .border(1.dp, T.BORDER_SOFT, RoundedCornerShape(T.R_CTRL))
            .clickable(role = Role.Button, onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Canvas(Modifier.size(12.dp, 18.dp)) { drawBluetoothRune(T.TEXT) }
        HandDot("L", left)
        HandDot("R", right)
        if (battery != null) {
            Text(battery, color = if (low) T.AMBER else T.TEXT_2, fontSize = P.VALUE.sp, fontFamily = Mono)
        }
    }
}

@Composable
private fun HandDot(letter: String, colour: Color) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(letter, color = T.TEXT, fontSize = P.VALUE.sp, fontWeight = FontWeight.Bold)
        Box(Modifier.size(8.dp).clip(CircleShape).background(colour))
    }
}

/** A tick box for a list row. */
@Composable
fun TickBox(on: Boolean, modifier: Modifier = Modifier) {
    Canvas(modifier.size(22.dp)) {
        val r = androidx.compose.ui.geometry.CornerRadius(5.dp.toPx())
        if (on) {
            drawRoundRect(T.ACCENT, cornerRadius = r)
            val s = size.width
            drawLine(T.ON_ACCENT, Offset(s * .25f, s * .52f), Offset(s * .43f, s * .7f), 2.4.dp.toPx(), StrokeCap.Round)
            drawLine(T.ON_ACCENT, Offset(s * .43f, s * .7f), Offset(s * .77f, s * .31f), 2.4.dp.toPx(), StrokeCap.Round)
        } else {
            drawRoundRect(T.TEXT_4, cornerRadius = r, style = androidx.compose.ui.graphics.drawscope.Stroke(1.6.dp.toPx()))
        }
    }
}
