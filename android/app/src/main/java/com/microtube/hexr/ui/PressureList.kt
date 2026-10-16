package com.microtube.hexr.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.microtube.hexr.Protocol
import com.microtube.hexr.tr
import kotlin.math.roundToInt

/** kPa at a bar's end: the glove is driven 15-50. */
private const val SCALE_KPA = 55.0

/**
 * Each finger's air pressure, a row each, the desktop's pressure list for a phone: a box to tick
 * it, its name, a bar for what the glove measures now and a white mark where the finger is set
 * to go, and the number in kPa. Picked fingers are bright and the rest faint. The last row is
 * the air supply feeding them all. A row is a 48 dp target, so picking from here is easy where
 * a fingertip on the glove picture is small.
 */
@Composable
fun PressureList(
    kpa: List<Double>?,
    source: Double?,
    picked: Set<Int>,
    targetKpa: Double?,
    modifier: Modifier = Modifier,
    title: String? = null,
    note: String? = null,
    onToggle: (Int) -> Unit,
) {
    Column(modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth().padding(bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(title ?: "", color = T.TEXT_2, fontSize = P.VALUE.sp, fontWeight = FontWeight.SemiBold,
                modifier = Modifier.weight(1f))
            if (note != null) {
                Text(note, color = T.TEXT_5, fontSize = P.SMALL.sp)
            } else {
                Legend()
            }
        }
        for (f in Protocol.ALL_FINGERS) {
            val ch = f.channel
            val on = ch in picked
            Row(
                Modifier
                    .fillMaxWidth()
                    .heightIn(min = P.TOUCH)
                    .toggleable(value = on, role = Role.Checkbox, onValueChange = { onToggle(ch) }),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                TickBox(on)
                Spacer(Modifier.width(12.dp))
                Text(
                    tr(f.label), color = if (on) T.TEXT else T.TEXT_2, fontSize = P.BODY.sp,
                    fontWeight = if (on) FontWeight.SemiBold else FontWeight.Normal,
                    modifier = Modifier.width(72.dp), maxLines = 1,
                )
                Bar(kpa?.getOrNull(ch), if (on) T.ACCENT else T.TEXT_4, if (on) targetKpa else null, Modifier.weight(1f))
                Value(kpa?.getOrNull(ch), bright = on)
            }
        }
        Box(Modifier.fillMaxWidth().padding(vertical = 4.dp).height(1.dp).background(T.BORDER_SOFT))
        Row(Modifier.fillMaxWidth().heightIn(min = 40.dp), verticalAlignment = Alignment.CenterVertically) {
            Spacer(Modifier.width(34.dp))
            Text(tr("Air supply"), color = T.TEXT_3, fontSize = P.BODY.sp, modifier = Modifier.width(72.dp), maxLines = 1)
            Bar(source, T.TEXT_2, null, Modifier.weight(1f))
            Value(source, bright = false)
        }
    }
}

@Composable
private fun Bar(kpa: Double?, colour: Color, target: Double?, modifier: Modifier) {
    Canvas(modifier.height(18.dp).padding(horizontal = 8.dp)) {
        val y = size.height / 2
        val w = 8.dp.toPx()
        val r = w / 2
        drawLine(T.BORDER_STRONG, Offset(r, y), Offset(size.width - r, y), w, StrokeCap.Round)
        if (kpa != null && kpa > .5) {
            val frac = (kpa / SCALE_KPA).coerceIn(0.0, 1.0).toFloat()
            drawLine(colour, Offset(r, y), Offset(r + frac * (size.width - w), y), w, StrokeCap.Round)
        }
        if (target != null) {
            val x = r + (target / SCALE_KPA).coerceIn(0.0, 1.0).toFloat() * (size.width - w)
            drawLine(Color.White, Offset(x, y - 8.dp.toPx()), Offset(x, y + 8.dp.toPx()), 2.dp.toPx())
        }
    }
}

@Composable
private fun Value(kpa: Double?, bright: Boolean) {
    Text(
        if (kpa == null) "—" else "${kpa.roundToInt()} kPa",
        color = if (bright) T.TEXT else T.TEXT_3,
        fontSize = P.VALUE.sp, fontFamily = Mono, textAlign = TextAlign.End,
        modifier = Modifier.widthIn(min = 64.dp),
    )
}

/** What the bar and the mark mean. */
@Composable
private fun Legend() {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Canvas(Modifier.size(16.dp, 8.dp)) {
            drawLine(T.ACCENT, Offset(4f, size.height / 2), Offset(size.width - 4f, size.height / 2), size.height, StrokeCap.Round)
        }
        Text(tr("Now"), color = T.TEXT_5, fontSize = P.SMALL.sp)
        Spacer(Modifier.width(6.dp))
        Canvas(Modifier.size(2.dp, 14.dp)) { drawRect(Color.White) }
        Text(tr("Set to"), color = T.TEXT_5, fontSize = P.SMALL.sp)
    }
}

