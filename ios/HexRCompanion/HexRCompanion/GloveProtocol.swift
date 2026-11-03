// HEXR glove wire protocol — a Swift port of hexr/protocol.py. No I/O.
//
// Outbound  [len][opcode][TLV...]        — no checksum, no terminator
// Inbound   [len][opcode][TLV...][xor]   — trailing XOR of bytes 0..len-2
// `len` is the whole frame including itself. A TLV is a one-byte tag then a
// little-endian value. State 1 ("stay") is a no-op: send 0 (enter) or 2 (exit).

import Foundation
import CoreBluetooth

enum GP {
    static let serviceUUID = CBUUID(string: "000000ff-0000-1000-8000-00805f9b34fb")
    static let charUUID = CBUUID(string: "0000ff01-0000-1000-8000-00805f9b34fb")
    static let namePrefix = "HaptGloveAR"

    static let minKPa: Double = 15
    static let maxKPa: Double = 50
    static let pwmVibrationHz: Double = 5

    static func hand(fromName name: String?) -> Hand? {
        guard let n = name?.trimmingCharacters(in: .whitespaces), n.hasPrefix(namePrefix) else { return nil }
        let tail = n.dropFirst(namePrefix.count).trimmingCharacters(in: .whitespaces).lowercased()
        if tail.hasPrefix("left") { return .left }
        if tail.hasPrefix("right") { return .right }
        return nil
    }

    enum Op: UInt8 { case setPressure = 0x04, setVibration = 0x07 }
    enum InOp: UInt8 { case pressure = 0x01, microtube = 0x04, clutch = 0x05, battery = 0x06 }

    static let stateEnter: UInt8 = 0
    static let stateExit: UInt8 = 2

    // -- encoding

    private static func u8(_ v: UInt8) -> [UInt8] { [0x01, v] }
    private static func f32(_ v: Double) -> [UInt8] {
        var f = Float(v).bitPattern.littleEndian
        return [0x09] + withUnsafeBytes(of: &f) { Array($0) }
    }
    private static func frame(_ op: Op, _ payload: [UInt8]) -> [UInt8] {
        [UInt8(payload.count + 2), op.rawValue] + payload
    }

    static func clamp(_ lo: Double, _ hi: Double, _ v: Double) -> Double { min(max(v, lo), hi) }

    /// 0.1–1.0 → 15–50 kPa. Exactly 0 means off.
    static func intensityToKPa(_ i: Double) -> Double {
        if i == 0 { return 0 }
        return (maxKPa - minKPa) * (clamp(0.1, 1, i) - 0.1) / 0.9 + minKPa
    }
    static func speedByte(_ s: Double) -> UInt8 { UInt8(clamp(0.1, 1, s) * 100) }
    static func peakByte(_ p: Double) -> UInt8 { UInt8(clamp(0.2, 0.8, p) * 100) }

    static func pressure(_ f: Finger, on: Bool, intensity: Double, speed: Double) -> [UInt8] {
        frame(.setPressure,
              f32(0) + u8(UInt8(f.rawValue)) + u8(on ? stateEnter : stateExit)
              + f32(intensityToKPa(on ? intensity : 0)) + u8(speedByte(speed)))
    }

    static func vibration(_ f: Finger, on: Bool, frequency: Double, intensity: Double,
                          peakRatio: Double = 0.5) -> [UInt8] {
        frame(.setVibration,
              f32(clamp(0.1, 40, frequency)) + u8(UInt8(f.rawValue)) + u8(on ? stateEnter : stateExit)
              + f32(intensityToKPa(on ? intensity : 0)) + u8(peakByte(peakRatio)))
    }

    /// Both opcodes, vibration exits first, so the last word on every channel is
    /// a zero pressure target with the loop released.
    static func allOff() -> [UInt8] {
        Finger.allCases.flatMap { vibration($0, on: false, frequency: 0, intensity: 0) }
        + Finger.allCases.flatMap { pressure($0, on: false, intensity: 0, speed: 1) }
    }

    /// Gauge kPa, whether the firmware reports gauge kPa or absolute pascals.
    static func rawToKPa(_ raw: Double) -> Double { raw > 10000 ? (raw - 100000) / 1000 : raw }
}

enum Hand: String, CaseIterable, Identifiable {
    case left = "Left", right = "Right"
    var id: String { rawValue }
}

enum Finger: Int, CaseIterable, Identifiable {
    case thumb = 0, index, middle, ring, pinky, palm
    var id: Int { rawValue }
    var label: String { ["Thumb", "Index", "Middle", "Ring", "Pinky", "Palm"][rawValue] }
}

struct Telemetry {
    var pressureRaw = [Double](repeating: 0, count: 7)   // Thumb..Palm, then source/tank
    var fingerPosition = [Int32](repeating: 0, count: 5)
    var battery: Double?                                  // 0–1
    var seen = false
}

/// Resynchronising stream parser for the notify characteristic. A frame that
/// fails validation costs one byte, not the whole buffer.
struct FrameDecoder {
    private var buf: [UInt8] = []
    var badFrames = 0
    private static let maxBuffer = 74 * 16

    mutating func feed(_ data: Data, into t: inout Telemetry) {
        buf.append(contentsOf: data)
        if buf.count > Self.maxBuffer { buf.removeFirst(buf.count - Self.maxBuffer) }
        while buf.count >= 3 {
            let len = Int(buf[0]), op = buf[1]
            if len < 3 || GP.InOp(rawValue: op) == nil { buf.removeFirst(); continue }
            if buf.count < len { break }
            let fr = Array(buf[0..<len])
            let x = fr[0..<(len - 1)].reduce(0, ^)
            if x != fr[len - 1] { badFrames += 1; buf.removeFirst(); continue }
            buf.removeFirst(len)
            apply(fr, &t)
        }
    }

    private func f32(_ fr: [UInt8], _ off: Int) -> Double? {
        guard off + 4 <= fr.count else { return nil }
        let bits = UInt32(fr[off]) | UInt32(fr[off+1]) << 8 | UInt32(fr[off+2]) << 16 | UInt32(fr[off+3]) << 24
        return Double(Float(bitPattern: bits))
    }

    private mutating func apply(_ fr: [UInt8], _ t: inout Telemetry) {
        switch GP.InOp(rawValue: fr[1]) {
        case .pressure:
            var vals: [Double] = []
            for i in 0..<7 { guard let v = f32(fr, 3 + i * 5) else { badFrames += 1; return }; vals.append(v) }
            t.pressureRaw = vals; t.seen = true
        case .microtube, .clutch:
            for i in 0..<5 {
                guard let v = f32(fr, 3 + i * 5) else { badFrames += 1; return }
                t.fingerPosition[i] = Int32(bitPattern: Float(v).bitPattern)
            }
            t.seen = true
        case .battery:
            guard let v = f32(fr, 3) else { badFrames += 1; return }
            t.battery = v; t.seen = true
        case .none: break
        }
    }
}
