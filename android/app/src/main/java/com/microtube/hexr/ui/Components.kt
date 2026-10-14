package com.microtube.hexr.ui

import androidx.compose.animation.animateColorAsState
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
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.microtube.hexr.Tone

/** Maps a status line's severity onto the palette. */
fun Tone.color(): Color = when (this) {
    Tone.Muted -> T.TEXT_2
    Tone.Accent -> T.ACCENT
    Tone.Success -> T.GREEN
    Tone.Danger -> T.RED
}

// -- text ---------------------------------------------------------------------

/** A screen heading. */
@Composable
fun Title(text: String, modifier: Modifier = Modifier) {
    Text(
        text,
        modifier = modifier,
        color = T.TEXT,
        fontSize = Size.TITLE.sp,
        fontWeight = FontWeight.Bold,
    )
}

/** Body and label text. */
@Composable
fun Label(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = T.TEXT,
    size: Float = Size.BODY,
    weight: FontWeight = FontWeight.Normal,
) {
    Text(text, modifier = modifier, color = color, fontSize = size.sp, fontWeight = weight)
}

/**
 * Every numeric readout. Monospace so a column of pressures does not jitter
 * sideways as the digits change — which they do fifty times a second.
 */
@Composable
fun MonoText(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = T.TEXT,
    size: Float = Size.BODY_2,
    weight: FontWeight = FontWeight.Normal,
) {
    Text(
        text,
        modifier = modifier,
        color = color,
        fontFamily = Mono,
        fontSize = size.sp,
        fontWeight = weight,
    )
}

/** The tracked uppercase micro-label above a group of controls. */
@Composable
fun SectionLabel(text: String, modifier: Modifier = Modifier, color: Color = T.TEXT_3) {
    Text(
        text.uppercase(),
        modifier = modifier,
        fontSize = Size.LABEL.sp,
        fontWeight = FontWeight.SemiBold,
        letterSpacing = 0.95.sp,      // .09em at 10.5sp
        color = color,
    )
}

/** Explanatory copy under a control. */
@Composable
fun Caption(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = T.TEXT_5,
    size: Float = Size.CAPTION,
    textAlign: TextAlign? = null,
) {
    if (text.isEmpty()) return
    Text(
        text,
        modifier = modifier,
        color = color,
        fontSize = size.sp,
        lineHeight = (size * 1.4).sp,
        textAlign = textAlign,
    )
}

@Composable
fun EmptyNote(text: String, modifier: Modifier = Modifier) {
    Text(
        text,
        modifier = modifier.fillMaxWidth().padding(20.dp),
        color = T.TEXT_5,
        fontSize = Size.BODY_2.sp,
        lineHeight = 18.sp,
        textAlign = TextAlign.Center,
    )
}

// -- containers -----------------------------------------------------------------

/** An elevated panel: connected-glove cards, results tables, verdict banners. */
@Composable
fun Card(
    modifier: Modifier = Modifier,
    fill: Color = T.ELEVATED,
    border: Color = T.BORDER_SOFT,
    radius: androidx.compose.ui.unit.Dp = T.R_CTRL,
    content: @Composable () -> Unit,
) {
    Box(
        modifier
            .clip(RoundedCornerShape(radius))
            .background(fill)
            .border(1.dp, border, RoundedCornerShape(radius)),
    ) { content() }
}

@Composable
fun Hairline(modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth().height(1.dp).background(T.HAIRLINE))
}

@Composable
fun TableRow(
    modifier: Modifier = Modifier,
    content: @Composable RowScope.() -> Unit,
) {
    Row(
        modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 13.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        content = content,
    )
}

/** A small status word — hand side, streaming, MTU. Tappable when given [onClick]. */
@Composable
fun Pill(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = T.TEXT_2,
    fill: Color = T.CARD,
    border: Color = T.BORDER_SOFT,
    onClick: (() -> Unit)? = null,
) {
    val haptics = LocalHapticFeedback.current
    Box(
        modifier
            .clip(RoundedCornerShape(T.R_CHIP))
            .background(fill)
            .border(1.dp, border, RoundedCornerShape(T.R_CHIP))
            .then(
                if (onClick == null) {
                    Modifier
                } else {
                    Modifier.clickable {
                        haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                        onClick()
                    }
                },
            )
            .padding(horizontal = 10.dp, vertical = 4.dp),
    ) {
        Text(text, color = color, fontSize = Size.MICRO.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
fun Dot(color: Color, modifier: Modifier = Modifier, size: Int = 6) {
    Box(modifier.size(size.dp).clip(CircleShape).background(color))
}

// -- controls -------------------------------------------------------------------

/** The solid accent action: Scan, Trigger, Run quick test. */
@Composable
fun PrimaryButton(
    label: String,
    modifier: Modifier = Modifier,
    sub: String? = null,
    enabled: Boolean = true,
    active: Boolean = false,
    height: Int = 50,
    onClick: () -> Unit,
) {
    val haptics = LocalHapticFeedback.current
    val fill by animateColorAsState(if (active) T.CARD else T.ACCENT, label = "primaryFill")
    val fg = if (active) T.ACCENT else T.ON_ACCENT
    Column(
        modifier
            .defaultMinSize(minHeight = height.dp)
            .clip(RoundedCornerShape(T.R_CTRL))
            .background(fill)
            .alpha(if (enabled) 1f else 0.4f)
            .clickable(enabled = enabled) {
                haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                onClick()
            }
            .padding(horizontal = 18.dp, vertical = 10.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(label, color = fg, fontSize = Size.ACTION.sp, fontWeight = FontWeight.Bold)
        if (sub != null) {
            Text(
                sub,
                color = fg.copy(alpha = 0.75f),
                fontSize = Size.LABEL.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }
    }
}

/** An outlined action: Release all, Disconnect. */
@Composable
fun GhostButton(
    label: String,
    modifier: Modifier = Modifier,
    tint: Color = T.TEXT_2,
    enabled: Boolean = true,
    height: Int = 42,
    onClick: () -> Unit,
) {
    val haptics = LocalHapticFeedback.current
    Box(
        modifier
            .defaultMinSize(minHeight = height.dp)
            .clip(RoundedCornerShape(T.R_CTRL))
            .background(T.CARD)
            .border(1.dp, T.BORDER, RoundedCornerShape(T.R_CTRL))
            .alpha(if (enabled) 1f else 0.4f)
            .clickable(enabled = enabled) {
                haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                onClick()
            }
            .padding(horizontal = 14.dp, vertical = 10.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, color = tint, fontSize = Size.BODY_2.sp, fontWeight = FontWeight.SemiBold)
    }
}

/** The rounded All / None chips beside a section label. */
@Composable
fun ChipButton(
    label: String,
    modifier: Modifier = Modifier,
    tint: Color = T.TEXT,
    onClick: () -> Unit,
) {
    val haptics = LocalHapticFeedback.current
    Box(
        modifier
            .clip(RoundedCornerShape(T.R_PILL))
            .background(T.CHIP)
            .clickable {
                haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                onClick()
            }
            .padding(horizontal = 12.dp, vertical = 5.dp),
    ) {
        Text(label, color = tint, fontSize = Size.MICRO.sp, fontWeight = FontWeight.SemiBold)
    }
}

/**
 * The hand picker on the Test tab: two segments in one track.
 *
 * A disconnected hand dims rather than disappearing — which glove is missing is
 * as much a part of the answer as which one is selected.
 */
@Composable
fun HandSegments(
    left: String,
    right: String,
    selected: String,
    leftEnabled: Boolean,
    rightEnabled: Boolean,
    modifier: Modifier = Modifier,
    onPick: (String) -> Unit,
) {
    val haptics = LocalHapticFeedback.current
    Row(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(T.R_CARD))
            .background(T.CARD)
            .padding(3.dp),
    ) {
        listOf("Left" to Triple(left, leftEnabled, "Left"), "Right" to Triple(right, rightEnabled, "Right"))
            .forEach { (key, spec) ->
                val (label, enabled, _) = spec
                val on = key == selected
                Box(
                    Modifier
                        .weight(1f)
                        .clip(RoundedCornerShape(T.R_CHIP))
                        .background(if (on) T.ELEVATED_2 else Color.Transparent)
                        .border(
                            1.dp,
                            if (on) T.ACCENT else Color.Transparent,
                            RoundedCornerShape(T.R_CHIP),
                        )
                        .clickable(enabled = enabled) {
                            haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                            onPick(key)
                        }
                        .padding(vertical = 10.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        label,
                        color = when {
                            !enabled -> T.TEXT_5
                            on -> T.ACCENT
                            else -> T.TEXT_2
                        },
                        fontSize = Size.BODY_2.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            }
    }
}

/** A taller stacked hand card, used where the quick test picks its glove. */
@Composable
fun HandCard(
    hand: String,
    sub: String,
    selected: Boolean,
    enabled: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    val haptics = LocalHapticFeedback.current
    Column(
        modifier
            .defaultMinSize(minHeight = 56.dp)
            .clip(RoundedCornerShape(T.R_CARD))
            .background(if (selected) T.ELEVATED_2 else T.CARD)
            .border(
                1.5.dp,
                if (selected) T.ACCENT else T.BORDER_SOFT,
                RoundedCornerShape(T.R_CARD),
            )
            .clickable(enabled = enabled) {
                haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                onClick()
            }
            .padding(horizontal = 14.dp, vertical = 9.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text(
            hand,
            color = when {
                !enabled -> T.TEXT_5
                selected -> T.ACCENT
                else -> T.TEXT
            },
            fontSize = Size.CONTROL.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Text(sub, color = if (enabled) T.TEXT_2 else T.TEXT_5, fontSize = Size.LABEL.sp)
    }
}

/** A labelled slider. [trailing] carries the value or a toggle. */
@Composable
fun ControlSlider(
    label: String,
    value: Float,
    range: ClosedFloatingPointRange<Float>,
    modifier: Modifier = Modifier,
    steps: Int = 0,
    enabled: Boolean = true,
    trailing: @Composable () -> Unit,
    onChange: (Float) -> Unit,
) {
    Column(modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            SectionLabel(label, Modifier.weight(1f))
            trailing()
        }
        Slider(
            value = value,
            onValueChange = onChange,
            valueRange = range,
            steps = steps,
            enabled = enabled,
            modifier = Modifier.alpha(if (enabled) 1f else 0.4f),
            colors = SliderDefaults.colors(
                thumbColor = T.ACCENT,
                activeTrackColor = T.ACCENT,
                inactiveTrackColor = T.CARD,
                disabledThumbColor = T.ACCENT,
                disabledActiveTrackColor = T.ACCENT,
                disabledInactiveTrackColor = T.CARD,
            ),
        )
    }
}

/** A labelled scalar — battery, source pressure. */
@Composable
fun StatTile(label: String, value: String, modifier: Modifier = Modifier) {
    Column(
        modifier
            .clip(RoundedCornerShape(T.R_CARD))
            .background(T.CARD)
            .padding(horizontal = 13.dp, vertical = 10.dp),
    ) {
        SectionLabel(label)
        Spacer(Modifier.height(5.dp))
        MonoText(value, size = 17f, weight = FontWeight.Medium)
    }
}

@Composable
fun ProgressBar(fraction: Float, color: Color = T.ACCENT, modifier: Modifier = Modifier) {
    Box(
        modifier
            .fillMaxWidth()
            .height(6.dp)
            .clip(RoundedCornerShape(3.dp))
            .background(T.CARD),
    ) {
        Box(
            Modifier
                .fillMaxSize(fraction = fraction.coerceIn(0f, 1f))
                .clip(RoundedCornerShape(3.dp))
                .background(color),
        )
    }
}

/**
 * The quick test's answer, stated once and large.
 *
 * Someone runs the sweep to learn one thing. Making them derive it from six
 * table rows is making them do the summarising themselves.
 */
@Composable
fun VerdictBanner(headline: String, detail: String, ok: Boolean, modifier: Modifier = Modifier) {
    val tone = if (ok) T.GREEN else T.RED
    Column(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(T.R_CTRL))
            .background(tone.copy(alpha = 0.07f))
            .border(1.dp, tone.copy(alpha = 0.5f), RoundedCornerShape(T.R_CTRL))
            .padding(16.dp),
    ) {
        Text(
            headline,
            color = tone,
            fontSize = Size.VERDICT.sp,
            fontWeight = FontWeight.ExtraBold,
            lineHeight = 26.sp,
        )
        if (detail.isNotEmpty()) {
            Spacer(Modifier.height(6.dp))
            Text(detail, color = T.TEXT_2, fontSize = Size.CAPTION.sp, lineHeight = 17.sp)
        }
    }
}

/** A collapsed section. Reference material should not cost a screen of scroll. */
@Composable
fun Disclosure(
    title: String,
    expanded: Boolean,
    modifier: Modifier = Modifier,
    onToggle: () -> Unit,
    content: @Composable () -> Unit,
) {
    Column(modifier.fillMaxWidth()) {
        Row(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(T.R_CARD))
                .clickable(onClick = onToggle)
                .padding(vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                if (expanded) "−" else "+",
                color = T.TEXT_3,
                fontSize = 14.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.width(12.dp),
            )
            SectionLabel(title, Modifier.weight(1f))
        }
        if (expanded) content()
    }
}

@Composable
fun HSpace(width: Int) = Spacer(Modifier.width(width.dp))

@Composable
fun VSpace(height: Int) = Spacer(Modifier.height(height.dp))
