// The orange HEXR glove and its six touch points, lit by what the glove does.
// Ported from the Android app's glove/HandState.kt, glove/GloveGeometry.kt and ui/GloveArt.kt,
// which follow the desktop's overlay.py: the same numbers, so a point lands on the same fingertip.

import SwiftUI
import UIKit

let FINGERS = 6

// MARK: - HandState

struct HandState: Equatable {
    var levels = [Float](repeating: 0, count: FINGERS)
    var vibrating = [Float](repeating: 0, count: FINGERS)  // Hz while vibrating
    var since = [Float](repeating: 0, count: FINGERS)
    var words = 0          // 0 press/hold/release, 1 pulse/buzz/click
    var word = -1          // the word lit, -1 none
    var hz: Float = 0
    var tints: [UInt32?]? = nil   // ARGB
}

enum HandLook {
    static let quietKPa = 2.0
    static let fullKPa = 45.0
    static let pressS: Float = 0.3
    static let releaseWordS: Float = 0.7
    static let attackS: Float = 0.09
    static let releaseS: Float = 0.25
    static let green: UInt32 = 0xFF3ECF8E
    static let amber: UInt32 = 0xFFE8B04B
    static let red: UInt32 = 0xFFE5484D
}

func levelFromKPa(_ kpa: Double) -> Float {
    kpa < HandLook.quietKPa ? 0 : Float(min(1, kpa / HandLook.fullKPa))
}

/// The Test screen's glove: what it measures when it streams, else what it was told while on.
func padState(kpa: [Double]?, on: Bool, sincePress: Float, sinceRelease: Float?,
              vibration: Bool, intensity: Float, hz: Float, channels: Set<Int>) -> HandState {
    let levels: [Float]
    if let kpa { levels = kpa.prefix(FINGERS).map(levelFromKPa) }
    else if on { levels = (0..<FINGERS).map { channels.contains($0) ? intensity : 0 } }
    else { levels = [Float](repeating: 0, count: FINGERS) }

    if on && vibration {
        return HandState(levels: levels,
                         vibrating: (0..<FINGERS).map { channels.contains($0) ? hz : 0 },
                         since: [Float](repeating: sincePress, count: FINGERS),
                         words: 1, word: hz <= 3 ? 0 : 1, hz: hz)
    }
    if on { return HandState(levels: levels, word: sincePress < HandLook.pressS ? 0 : 1) }
    if !vibration, let r = sinceRelease, r < HandLook.releaseWordS { return HandState(levels: levels, word: 2) }
    return HandState(levels: levels)
}

/// The Connect screen's glove: lit green to say it is here; a pressing fingertip glows white.
func connectState(connected: Bool, kpa: [Double]?) -> HandState {
    guard connected else { return HandState() }
    let k = kpa?.prefix(FINGERS).map(levelFromKPa) ?? [Float](repeating: 0, count: FINGERS)
    return HandState(levels: k.map { max(0.32, $0) }, tints: k.map { $0 > 0.32 ? nil : HandLook.green })
}

enum Verdict: String { case good = "Good", poor = "Poor", fail = "Fail" }

func verdictState(_ verdicts: [Verdict], pumpFailed: Bool) -> HandState {
    let looks: [(UInt32, Float)] = (pumpFailed ? [Verdict](repeating: .fail, count: FINGERS) : verdicts).map {
        switch $0 {
        case .good: return (HandLook.green, 1)
        case .poor: return (HandLook.amber, 0.75)
        case .fail: return (HandLook.red, 0.6)
        }
    }
    return HandState(levels: looks.map(\.1), tints: looks.map { $0.0 })
}

// MARK: - Geometry

enum GloveGeometry {
    static let aspect: CGFloat = 768.0 / 1295.0
    static let hit: CGFloat = 0.09
    /// Thumb, index, middle, ring, pinky, palm, on the right-hand art (x, y, label to the left).
    static let dots: [(CGFloat, CGFloat, Bool)] = [
        (0.8802, 0.3475, false), (0.5951, 0.1158, false), (0.4232, 0.0772, true),
        (0.2591, 0.1251, true), (0.1042, 0.2069, true), (0.5469, 0.6178, false),
    ]
    static let names = ["THUMB", "INDEX", "MIDDLE", "RING", "PINKY", "PALM"]
    static let words = [["PRESS.", "HOLD.", "RELEASE."], ["PULSE.", "BUZZ.", "CLICK."]]
}

enum Labels { case off, active, always }

struct GloveLook: Equatable {
    var margin: CGFloat
    var caption: Bool
    var labels: Labels = .off
    static let test = GloveLook(margin: 0.12, caption: true)
    static let connect = GloveLook(margin: 0.12, caption: false)
    static let quick = GloveLook(margin: 0.12, caption: false)
    static let cast = GloveLook(margin: 0.25, caption: true, labels: .active)
    static let castQuiet = GloveLook(margin: 0.25, caption: true)
}

func panelSize(_ gh: CGFloat, _ look: GloveLook) -> CGSize {
    let gw = gh * GloveGeometry.aspect
    let cap = gh * (look.caption ? 0.24 : 0.06)
    return CGSize(width: gw + gw * look.margin * 2, height: gh * 0.12 + gh + cap)
}

func touchPoints(_ hand: Hand, _ gh: CGFloat, _ look: GloveLook) -> [CGPoint] {
    let gw = gh * GloveGeometry.aspect, gx = gw * look.margin, gy = gh * 0.1
    return GloveGeometry.dots.map { d in
        CGPoint(x: gx + (hand == .left ? 1 - d.0 : d.0) * gw, y: gy + d.1 * gh)
    }
}

func nearestPoint(_ pts: [CGPoint], _ p: CGPoint, _ radius: CGFloat) -> Int? {
    var best: Int?, bestD = radius * radius
    for (i, q) in pts.enumerated() {
        let d = (q.x - p.x) * (q.x - p.x) + (q.y - p.y) * (q.y - p.y)
        if d <= bestD { best = i; bestD = d }
    }
    return best
}

func tagOnLeft(_ ch: Int, _ hand: Hand) -> Bool { GloveGeometry.dots[ch].2 != (hand == .left) }

/// The tallest glove whose panel fits inside the room.
func fitGh(_ size: CGSize, _ look: GloveLook) -> CGFloat {
    let u = panelSize(1, look)
    return max(0, min(size.width / u.width, size.height / u.height))
}

// MARK: - Drawing

private let fire = Color(hex: 0xFFF6E2)
private let dotColour = Color(hex: 0x18191C)
private let tagColour = Color(hex: 0x111214)
private let litWord = Color(hex: 0xF2661A)

enum GloveAssets {
    static let art: Image = {
        if let ui = UIImage(named: "glove") { return Image(uiImage: ui) }
        return Image(systemName: "hand.raised.fill")
    }()
}

/// Eases shown levels toward their targets frame by frame: fast as air fills, slower as it empties.
final class GloveEaser {
    var shown = [Float](repeating: 0, count: FINGERS)
    var last: Date?
    func step(_ target: [Float], now: Date) -> [Float] {
        let dt = Float(last.map { now.timeIntervalSince($0) } ?? 1)
        last = now
        for i in 0..<FINGERS {
            let t = i < target.count ? target[i] : 0
            let tau = t > shown[i] ? HandLook.attackS : HandLook.releaseS
            let k = 1 - exp(-max(dt, 0) / tau)
            var n = shown[i] + (t - shown[i]) * k
            if abs(n - t) < 0.002 { n = t }
            shown[i] = n
        }
        return shown
    }
}

/// One hand's glove, lit as `state` says. Sized to fill the room it is given.
/// `stateAt` draws a fresh state every frame (the headset cast). `onTap` makes points pickable.
struct GloveArtView: View {
    let hand: Hand
    var look: GloveLook = .test
    var state = HandState()
    var stateAt: ((Date) -> HandState)? = nil
    var selected: Set<Int>? = nil
    var dim: Double = 1
    var onTap: ((Int) -> Void)? = nil

    @State private var easer = GloveEaser()
    @State private var start = Date()

    var body: some View {
        GeometryReader { geo in
            let gh = fitGh(geo.size, look)
            let panel = panelSize(gh, look)
            TimelineView(.animation) { tl in
                Canvas { ctx, size in
                    var st = stateAt?(tl.date) ?? state
                    if stateAt == nil { st.levels = easer.step(state.levels, now: tl.date) }
                    let clock = Float(tl.date.timeIntervalSince(start))
                    drawGlove(&ctx, size: size, gh: gh, st: st, clock: clock)
                }
            }
            .frame(width: panel.width, height: panel.height)
            .opacity(dim)
            .contentShape(Rectangle())
            .gesture(onTap == nil ? nil : SpatialTapGesture().onEnded { e in
                let pts = touchPoints(hand, gh, look)
                if let hit = nearestPoint(pts, e.location, max(GloveGeometry.hit * gh, 24)) {
                    UISelectionFeedbackGenerator().selectionChanged()
                    onTap?(hit)
                }
            })
            .frame(width: geo.size.width, height: geo.size.height)
        }
        .aspectRatio(panelSize(1, look), contentMode: .fit)
    }

    private func drawGlove(_ ctx: inout GraphicsContext, size: CGSize, gh: CGFloat, st: HandState, clock: Float) {
        let gw = gh * GloveGeometry.aspect, gx = gw * look.margin, gy = gh * 0.1
        let rect = CGRect(x: gx, y: gy, width: gw, height: gh)

        // The glove, mirrored for the left hand.
        var art = ctx
        if hand == .left {
            art.translateBy(x: rect.midX, y: 0)
            art.scaleBy(x: -1, y: 1)
            art.translateBy(x: -rect.midX, y: 0)
        }
        art.draw(GloveAssets.art.resizable(), in: rect)

        let pts = touchPoints(hand, gh, look)
        func lvl(_ i: Int) -> CGFloat { CGFloat(i < st.levels.count ? st.levels[i] : 0) }
        func tint(_ i: Int, _ fallback: Color) -> Color {
            if let t = st.tints, i < t.count, let c = t[i] { return Color(argb: c) }
            return fallback
        }

        // What fires glows white-hot, or in its verdict's colour.
        for (ch, p) in pts.enumerated() {
            let level = lvl(ch)
            guard level > 0.003 else { continue }
            let c = tint(ch, fire)
            let r = gh * 0.085 * (0.55 + 0.9 * level)
            ctx.fill(Path(ellipseIn: CGRect(x: p.x - r, y: p.y - r, width: r * 2, height: r * 2)),
                     with: .radialGradient(Gradient(colors: [c.opacity(0.15 + 0.85 * level), c.opacity(0)]),
                                           center: p, startRadius: 0, endRadius: r))
        }
        // A vibration sends rings out from its point.
        for (ch, p) in pts.enumerated() {
            let hz = ch < st.vibrating.count ? st.vibrating[ch] : 0
            guard hz > 0 else { continue }
            let rate = min(hz, 2.5)
            for k in 0..<2 {
                let phase = CGFloat((clock * rate + Float(k) / 2).truncatingRemainder(dividingBy: 1))
                let r = gh * 0.03 * (1 + 2.4 * phase)
                ctx.stroke(Path(ellipseIn: CGRect(x: p.x - r, y: p.y - r, width: r * 2, height: r * 2)),
                           with: .color(fire.opacity((1 - phase) * 0.9)), lineWidth: max(1, gh * 0.007))
            }
        }
        // Each touch point: a dark edge, its colour, a white centre.
        for (ch, p) in pts.enumerated() {
            let a = 0.55 + 0.45 * lvl(ch)
            for (r, c) in [(gh * 0.029, dotColour.opacity(0.9 * a)), (gh * 0.024, tint(ch, dotColour).opacity(0.9 * a)),
                           (gh * 0.016, Color.white.opacity(a))] {
                ctx.fill(Path(ellipseIn: CGRect(x: p.x - r, y: p.y - r, width: r * 2, height: r * 2)), with: .color(c))
            }
        }
        // Picked fingers, ringed in white.
        if let sel = selected {
            let r = max(gh * 0.05, 10)
            for (ch, p) in pts.enumerated() where sel.contains(ch) {
                ctx.stroke(Path(ellipseIn: CGRect(x: p.x - r, y: p.y - r, width: r * 2, height: r * 2)),
                           with: .color(.white), lineWidth: 2)
            }
        }
        // A finger's name beside it while one or two fire.
        let firing = st.levels.filter { $0 > 0.08 }.count
        if look.labels == .always || (look.labels == .active && firing <= 2) {
            let fs = max(10, gh * 0.04)
            for (ch, p) in pts.enumerated() {
                let level = lvl(ch)
                let show = look.labels == .always ? 0.55 + 0.45 * min(1, level * 2) : min(1, max(0, (level - 0.08) * 4))
                guard show > 0 else { continue }
                let text = ctx.resolve(Text(GloveGeometry.names[ch]).font(.system(size: fs, weight: .bold))
                    .foregroundColor(.white.opacity(show)))
                let ts = text.measure(in: size)
                let ph = fs * 0.55, w = ts.width + ph * 2, h = fs * 1.7, off = gh * 0.045
                var cx = tagOnLeft(ch, hand) ? p.x - off - w / 2 : p.x + off + w / 2
                cx = min(max(cx, w / 2), size.width - w / 2)
                let top = p.y - h * 0.3 - h / 2
                ctx.fill(Path(roundedRect: CGRect(x: cx - w / 2, y: top, width: w, height: h), cornerRadius: h / 2),
                         with: .color(tagColour.opacity(0.92 * show)))
                ctx.draw(text, at: CGPoint(x: cx, y: top + h / 2))
            }
        }
        if look.caption { drawCaption(&ctx, size: size, st: st, gh: gh, gy: gy) }
    }

    private func drawCaption(_ ctx: inout GraphicsContext, size: CGSize, st: HandState, gh: CGFloat, gy: CGFloat) {
        let words = GloveGeometry.words[min(max(st.words, 0), 1)]
        let top = gy + gh + gh * 0.02
        func resolve(_ fs: CGFloat) -> [GraphicsContext.ResolvedText] {
            words.enumerated().map { i, w in
                ctx.resolve(Text(w).font(.custom(Fonts.captionName, fixedSize: fs))
                    .foregroundColor(i == st.word ? litWord : .white.opacity(60.0 / 255)))
            }
        }
        var fs = gh * 0.085
        var laid = resolve(fs)
        var widths = laid.map { $0.measure(in: size).width }
        var space = fs * 0.3
        var total = widths.reduce(0, +) + space * 2
        let room = size.width - gh * 0.12
        if total > room, total > 0 {
            fs *= room / total
            laid = resolve(fs); widths = laid.map { $0.measure(in: size).width }
            space = fs * 0.3; total = widths.reduce(0, +) + space * 2
        }
        if st.words == 1, st.word >= 0, st.hz > 0 {
            var s = String(format: "%.1f", st.hz)
            if s.hasSuffix(".0") { s.removeLast(2) }
            let hz = ctx.resolve(Text("\(s) Hz").font(.system(size: gh * 0.045, weight: .semibold))
                .foregroundColor(Color(hex: 0xEBEBED)))
            ctx.draw(hz, at: CGPoint(x: size.width / 2, y: top + gh * 0.075), anchor: .bottom)
        }
        var x = (size.width - total) / 2
        let baseline = top + gh * 0.19
        for (t, w) in zip(laid, widths) {
            ctx.draw(t, at: CGPoint(x: x, y: baseline), anchor: .bottomLeading)
            x += w + space
        }
    }
}
