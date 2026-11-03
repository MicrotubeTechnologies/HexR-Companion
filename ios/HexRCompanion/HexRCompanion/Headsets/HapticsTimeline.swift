// What a headset's gloves are doing to the wearer's hands, moment by moment, for the glove panels
// beside its view. A line-for-line port of the Android remote/HapticsTimeline.kt (itself the
// desktop's hexr/haptics.py). Exact from "haptics" lines when the headset sends them (HexR 0.10.2
// on), else from the measured pressure in each status. Times are seconds, passed in.

import Foundation
import QuartzCore

/// The monotonic clock frames and haptics are timed on, in seconds.
func nowS() -> Double { CACurrentMediaTime() }

final class HapticsTimeline {
    final class Segment {
        let t0: Double
        var t1: Double?
        let mode: String
        let intensity: Double
        let hz: Double
        init(_ t0: Double, _ t1: Double?, _ mode: String, _ intensity: Double, _ hz: Double) {
            self.t0 = t0; self.t1 = t1; self.mode = mode; self.intensity = intensity; self.hz = hz
        }
    }

    static let hands = ["left", "right"]
    static let attackS = 0.09, releaseS = 0.25, tapS = 0.12, pressS = 0.3, releaseWordS = 0.7
    static let keepS = 60.0, videoLagS = 0.15, sameClockS = 5.0, quietKPa = 2.0
    private static let maxSamples = 600, maxOffsets = 40

    private let lock = NSLock()
    private var segments: [String: [Segment]] = [:]          // "hand/finger"
    private var pressure: [String: [(Double, [Double])]] = [:]
    private var offsets: [Double] = []                        // headset clock - ours, seconds
    private var used = Set<String>()
    private(set) var exact = false

    private func key(_ hand: String, _ f: Int) -> String { "\(hand)/\(f)" }

    // -- feeding

    func onStatus(_ status: HeadsetStatus, arrived: Double) {
        lock.lock(); defer { lock.unlock() }
        if status.haptics { exact = true }
        if status.clockUs != 0 { push(&offsets, Double(status.clockUs) / 1e6 - arrived, Self.maxOffsets) }
        for hand in Self.hands {
            let g = status.glove(hand)
            var kpa = [Double](repeating: 0, count: FINGERS)
            if let g, g.connected, g.pressureDeciKPa.count >= FINGERS {
                kpa = (0..<FINGERS).map { Double(g.pressureDeciKPa[$0]) / 10 }
            }
            var q = pressure[hand] ?? []
            push(&q, (arrived, kpa), Self.maxSamples)
            pressure[hand] = q
            if (kpa.max() ?? 0) > Self.quietKPa * 3 { used.insert(hand) }
        }
    }

    func onHaptics(_ update: HapticsUpdate) {
        lock.lock(); defer { lock.unlock() }
        let t = Double(update.tUs) / 1e6
        exact = true
        for c in update.channels {
            let k = key(update.hand, c.finger)
            var segs = segments[k] ?? []
            if let last = segs.last, last.t1 == nil { last.t1 = max(last.t0, t) }
            if c.mode != "off" {
                segs.append(Segment(t, c.tap ? t + Self.tapS : nil, c.mode, max(0.1, c.intensity), c.hz))
                used.insert(update.hand)
            }
            while let first = segs.first, let e = first.t1, e < t - Self.keepS { segs.removeFirst() }
            segments[k] = segs
        }
    }

    /// Forget the clock's offset: the headset may have restarted, and its clock with it.
    func resetClock() { lock.lock(); offsets.removeAll(); lock.unlock() }

    // -- reading

    func handsUsed() -> [String] { lock.lock(); defer { lock.unlock() }; return Self.hands.filter { used.contains($0) } }

    /// Headset clock minus ours. The largest sample is the one that waited least on the way.
    func offset() -> Double? { lock.lock(); defer { lock.unlock() }; return offsets.max() }

    func frameTime(ptsUs: Int64, arrived: Double) -> Double {
        let pts = Double(ptsUs) / 1e6
        guard let off = offset() else { return pts }
        if abs(pts - (arrived + off)) < Self.sameClockS { return pts }
        return arrived + off - Self.videoLagS
    }

    /// The glove as the frame with this presentation time, which arrived then, shows it.
    func state(_ hand: String, ptsUs: Int64, arrived: Double) -> HandState {
        exact ? exactState(hand, frameTime(ptsUs: ptsUs, arrived: arrived)) : measuredState(hand, arrived - Self.videoLagS)
    }

    /// The glove as it is now, with no frame to go by.
    func stateNow(_ hand: String, now: Double) -> HandState {
        if exact, let off = offset() { return exactState(hand, now + off - Self.videoLagS) }
        return measuredState(hand, now - Self.videoLagS)
    }

    private func exactState(_ hand: String, _ t: Double) -> HandState {
        lock.lock(); defer { lock.unlock() }
        var levels = [Float](repeating: 0, count: FINGERS)
        var vibrating = [Float](repeating: 0, count: FINGERS)
        var since = [Float](repeating: 0, count: FINGERS)
        var active: Segment?, fading: Segment?
        for f in 0..<FINGERS {
            guard let segs = segments[key(hand, f)] else { continue }
            for s in segs.reversed() {
                let end = s.t1
                if let e = end, e < t - Self.releaseS * 8 { break }
                let level = Float(Self.segmentLevel(s, t))
                if level > levels[f] {
                    levels[f] = level
                    let on = s.mode != "pressure" && t >= s.t0 && (end == nil || t <= end!)
                    vibrating[f] = on ? Float(s.hz) : 0
                    since[f] = Float(t - s.t0)
                }
                if s.t0 <= t && (end == nil || t <= end!) {
                    if active == nil || s.t0 > active!.t0 { active = s }
                } else if let e = end, t - e >= 0, t - e < Self.releaseWordS {
                    if fading == nil || e > (fading!.t1 ?? 0) { fading = s }
                }
            }
        }
        var words = 0, word = -1
        var hz: Float = 0
        if let cur = active ?? fading {
            if cur.mode == "pressure" {
                word = cur !== active ? 2 : (t - cur.t0 < Self.pressS ? 0 : 1)
            } else {
                words = 1
                let short = cur.t1 != nil && cur.t1! - cur.t0 < 0.2
                word = short ? 2 : (cur.hz <= 3 ? 0 : 1)
                hz = Float(cur.hz)
            }
        }
        return HandState(levels: levels, vibrating: vibrating, since: since, words: words, word: word, hz: hz)
    }

    private func measuredState(_ hand: String, _ t: Double) -> HandState {
        lock.lock()
        let samples = pressure[hand] ?? []
        lock.unlock()
        guard !samples.isEmpty else { return HandState() }
        let now = Self.pressureAt(samples, t)
        let before = Self.pressureAt(samples, t - 0.25)
        let levels = now.map(levelFromKPa)
        let total = levels.reduce(0, +)
        let was = before.map(levelFromKPa).reduce(0, +)
        var word = -1
        if total > 0.15 || was > 0.15 {
            if total > was + 0.15 { word = 0 }
            else if total < was - 0.15 { word = 2 }
            else if total > 0.15 { word = 1 }
            else { word = 2 }
        }
        return HandState(levels: levels, words: 0, word: word)
    }

    /// How full one actuator is drawn at `t`: fills while on, empties after, as air does.
    static func segmentLevel(_ s: Segment, _ t: Double) -> Double {
        if t < s.t0 { return 0 }
        let end = s.t1 ?? t
        let filled = 1 - exp(-max(0, min(t, end) - s.t0) / attackS)
        var level = t <= end ? filled : filled * exp(-(t - end) / releaseS)
        level *= s.intensity
        if s.mode != "pressure" && t <= end {
            if s.hz <= 5 {
                let phase = ((t - s.t0) * s.hz).truncatingRemainder(dividingBy: 1)
                level *= 0.2 + 0.8 * (0.5 + 0.5 * tanh(5 * cos(2 * .pi * phase)))
            } else {
                level *= 0.86 + 0.14 * sin((t - s.t0) * 2 * .pi * 7)
            }
        }
        return level > 0.003 ? level : 0
    }

    /// The measured pressure at `t`, between the two readings around it.
    static func pressureAt(_ samples: [(Double, [Double])], _ t: Double) -> [Double] {
        if t <= samples[0].0 { return samples[0].1 }
        for i in 0..<(samples.count - 1) {
            let (ta, a) = samples[i], (tb, b) = samples[i + 1]
            if t >= ta && t <= tb {
                let k = tb > ta ? (t - ta) / (tb - ta) : 1
                return a.indices.map { a[$0] + (b[$0] - a[$0]) * k }
            }
        }
        return samples[samples.count - 1].1
    }

    private func push<E>(_ q: inout [E], _ e: E, _ maxLen: Int) {
        q.append(e)
        if q.count > maxLen { q.removeFirst(q.count - maxLen) }
    }
}
