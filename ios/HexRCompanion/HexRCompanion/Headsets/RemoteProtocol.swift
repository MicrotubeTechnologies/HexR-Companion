// HexR Remote, protocol version 1: how the Headsets tab talks to a HexR app on a headset.
// A port of the Android app's remote/RemoteProtocol.kt. The contract is
// Documentation~/RemoteProtocol.md in the com.microtube.hexr package. Requests are written by
// hand so they match the reference lines exactly; replies are parsed with JSONSerialization.

import Foundation

enum RemoteProtocol {
    static let version = 1
    static let discoveryPort: UInt16 = 47800
    static let controlPort = 47801

    // -- requests

    static func hello(_ client: String) -> String { #"{"type":"hello","protocol":\#(version),"client":\#(str(client))}"# }
    static func ping() -> String { #"{"type":"ping"}"# }
    static func glove(_ action: String, _ hand: Hand) -> String {
        #"{"type":"glove","action":\#(str(action)),"hand":\#(str(hand.rawValue.lowercased()))}"#
    }
    static func release() -> String { #"{"type":"release"}"# }
    /// Every channel of the connected gloves pressed for a second, then let go (HexR 0.10.6 on).
    static func trigger() -> String { #"{"type":"trigger"}"# }
    /// Every glove in range, listed in the status's gloveSearch about 8 s later (HexR 0.10.6 on).
    static func gloveSearch() -> String { #"{"type":"glove","action":"search"}"# }
    /// That exact glove for this hand, which the headset then keeps to (HexR 0.10.6 on).
    static func connectGloveAt(_ hand: Hand, _ address: String) -> String {
        #"{"type":"glove","action":"connect","hand":\#(str(hand.rawValue.lowercased())),"address":\#(str(address))}"#
    }
    static func scene(_ index: Int) -> String { #"{"type":"scene","index":\#(index)}"# }
    static func command(_ id: String) -> String { #"{"type":"command","id":\#(str(id))}"# }
    static func stream(_ action: String) -> String { #"{"type":"stream","action":\#(str(action))}"# }
    /// Put the wearer back on the scene's starting spot, facing its front (HexR 0.10.6 on).
    static func recenter() -> String { #"{"type":"recenter"}"# }

    /// "192.168.1.20", or "192.168.1.20:47811" for one on another port. Nil if it cannot be one.
    static func parseAddress(_ text: String) -> (String, Int)? {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.isEmpty { return nil }
        var host = t, port = controlPort
        if let colon = t.lastIndex(of: ":") {
            host = String(t[..<colon])
            guard let p = Int(t[t.index(after: colon)...]) else { return nil }
            port = p
        }
        guard (1...65535).contains(port),
              host.range(of: #"^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$"#, options: .regularExpression) != nil
        else { return nil }
        return (host, port)
    }

    /// A JSON string literal: quotes, backslashes and control characters escaped.
    static func str(_ s: String) -> String {
        var out = "\""
        for c in s.unicodeScalars {
            switch c {
            case "\"": out += "\\\""
            case "\\": out += "\\\\"
            case "\n": out += "\\n"
            case "\r": out += "\\r"
            case "\t": out += "\\t"
            default:
                if c.value < 0x20 { out += String(format: "\\u%04x", c.value) } else { out.unicodeScalars.append(c) }
            }
        }
        return out + "\""
    }

    // -- what the headset sends

    private static func object(_ text: String) -> [String: Any]? {
        guard let d = text.data(using: .utf8) else { return nil }
        return (try? JSONSerialization.jsonObject(with: d)) as? [String: Any]
    }

    static func parseAnnounce(_ text: String) -> Announce? {
        guard let o = object(text), o.string("type") == "announce", o.int("hexr", 0) >= 1 else { return nil }
        let a = Announce(id: o.string("id"), name: o.string("name"), model: o.string("model"),
                         platform: o.string("platform"), app: o.string("app"), appId: o.string("appId"),
                         hexrVersion: o.string("hexrVersion"), control: o.int("control", controlPort),
                         video: o.int("video", 0), startedAt: o.int64("startedAt", 0))
        return a.id.isEmpty ? nil : a
    }

    static func parseLine(_ line: String) -> Message {
        guard let o = object(line) else { return .other }
        switch o.string("type") {
        case "status": return .status(parseStatus(o))
        case "error": return .error(request: o.string("request"), message: o.string("message"))
        case "hello": return .welcome(id: o.string("id"), control: o.int("control", 0), video: o.int("video", 0))
        case "haptics": return parseHaptics(o).map { .haptics($0) } ?? .other
        default: return .other
        }
    }

    private static func sceneOf(_ o: [String: Any]) -> SceneInfo { SceneInfo(index: o.int("index", -1), name: o.string("name")) }

    static func parseStatus(_ o: [String: Any]) -> HeadsetStatus {
        HeadsetStatus(
            id: o.string("id"), name: o.string("name"), model: o.string("model"), platform: o.string("platform"),
            app: o.string("app"), appVersion: o.string("appVersion"), hexrVersion: o.string("hexrVersion"),
            paused: o.bool("paused"), headsetBatteryPct: o.int("headsetBatteryPct", -1),
            scene: o.obj("scene").map(sceneOf) ?? SceneInfo(index: -1, name: ""),
            scenes: o.objs("scenes").map(sceneOf),
            gloves: o.objs("gloves").map { g in
                GloveState(hand: g.string("hand"), state: g.string("state"), message: g.string("message"),
                           batteryPct: g.int("batteryPct", -1),
                           pressureDeciKPa: (g["pressureDeciKPa"] as? [Any])?.map { jsonInt($0) ?? 0 } ?? [],
                           savedAddress: g.string("savedAddress"))
            },
            stream: o.obj("stream").map { s in
                StreamState(state: s.string("state", "off"), port: s.int("port", 0), width: s.int("width", 0),
                            height: s.int("height", 0), viewers: s.int("viewers", 0), message: s.string("message"))
            } ?? StreamState(),
            commands: o.objs("commands").map { CommandInfo(id: $0.string("id"), label: $0.string("label")) },
            allowGloveControl: o.bool("allowGloveControl"), allowVideo: o.bool("allowVideo"),
            exposeScenes: o.bool("exposeScenes"), controllers: o.int("controllers", 0),
            allowRecenter: o.bool("allowRecenter"), haptics: o.bool("haptics"),
            clockUs: jsonInt64(o["clockUs"]) ?? 0,
            gloveSearch: o.obj("gloveSearch").map { gs in
                RemoteGloveSearch(
                    state: gs.string("state", "idle"), message: gs.string("message"),
                    found: gs.objs("found").filter { !$0.string("address").isEmpty }.map {
                        let h = $0.string("hand")
                        return NearbyGlove(address: $0.string("address"), name: $0.string("name"),
                                           hand: (h == "left" || h == "right") ? h : "",
                                           rssi: jsonInt($0["rssi"]) ?? 0)
                    })
            })
    }

    private static let hapticModes: Set<String> = ["off", "pressure", "vibration", "pulse"]

    /// A "haptics" line (HexR 0.10.2 on). Nil if not usable; a channel that is not one is skipped.
    static func parseHaptics(_ o: [String: Any]) -> HapticsUpdate? {
        guard let hand = o["hand"] as? String, hand == "left" || hand == "right" else { return nil }
        var channels: [HapticChannel] = []
        for item in (o["channels"] as? [Any]) ?? [] {
            guard let c = item as? [String: Any] else { continue }
            let finger = jsonInt(c["finger"]) ?? -1
            guard (0...5).contains(finger), let mode = c["mode"] as? String, hapticModes.contains(mode) else { continue }
            channels.append(HapticChannel(
                finger: finger, mode: mode,
                intensity: Double(min(max(jsonInt(c["intensityPct"]) ?? 0, 0), 100)) / 100,
                hz: Double(max(0, jsonInt(c["frequencyDeciHz"]) ?? 0)) / 10,
                tap: (c["tap"] as? NSNumber).map { CFGetTypeID($0) == CFBooleanGetTypeID() && $0.boolValue } ?? false))
        }
        return HapticsUpdate(hand: hand, tUs: jsonInt64(o["t"]) ?? 0, channels: channels)
    }

    // -- video: big-endian. Once "HXV1" u16 w u16 h u8 codec; per packet u32 len u8 flags u64 pts.

    static let videoHeaderBytes = 9
    static let packetHeaderBytes = 13
    static let flagConfig = 1
    static let flagKey = 2
    static let codecH264 = 1
    static let maxPacketBytes = 8 * 1024 * 1024

    static func parseVideoHeader(_ b: [UInt8]) -> VideoHeader? {
        guard b.count >= videoHeaderBytes, b[0] == 0x48, b[1] == 0x58, b[2] == 0x56, b[3] == 0x31 else { return nil }
        return VideoHeader(width: Int(b[4]) << 8 | Int(b[5]), height: Int(b[6]) << 8 | Int(b[7]), codec: Int(b[8]))
    }

    static func parsePacketHeader(_ b: [UInt8]) -> PacketHeader {
        let len = Int(b[0]) << 24 | Int(b[1]) << 16 | Int(b[2]) << 8 | Int(b[3])
        var pts: Int64 = 0
        for i in 5..<13 { pts = pts << 8 | Int64(b[i]) }
        return PacketHeader(length: len, flags: Int(b[4]), ptsUs: pts)
    }
}

// MARK: - JSON helpers: a number is a number, never a boolean (as the Android intOf/longOf)

private func isBool(_ v: Any?) -> Bool {
    guard let n = v as? NSNumber else { return false }
    return CFGetTypeID(n) == CFBooleanGetTypeID()
}
func jsonInt(_ v: Any?) -> Int? { isBool(v) ? nil : (v as? NSNumber)?.intValue }
func jsonInt64(_ v: Any?) -> Int64? { isBool(v) ? nil : (v as? NSNumber)?.int64Value }

private extension Dictionary where Key == String, Value == Any {
    func string(_ k: String, _ d: String = "") -> String { (self[k] as? String) ?? d }
    func int(_ k: String, _ d: Int) -> Int { jsonInt(self[k]) ?? d }
    func int64(_ k: String, _ d: Int64) -> Int64 { jsonInt64(self[k]) ?? d }
    func bool(_ k: String) -> Bool { isBool(self[k]) ? (self[k] as! NSNumber).boolValue : false }
    func obj(_ k: String) -> [String: Any]? { self[k] as? [String: Any] }
    func objs(_ k: String) -> [[String: Any]] { ((self[k] as? [Any]) ?? []).compactMap { $0 as? [String: Any] } }
}

// MARK: - Models

struct Announce: Equatable {
    var id, name, model, platform, app, appId, hexrVersion: String
    var control, video: Int
    var startedAt: Int64
}

enum Message {
    case status(HeadsetStatus)
    case error(request: String, message: String)
    case welcome(id: String, control: Int, video: Int)
    case haptics(HapticsUpdate)
    case other
}

struct SceneInfo: Equatable { var index: Int; var name: String }
struct CommandInfo: Equatable { var id: String; var label: String }

struct HapticChannel: Equatable {
    var finger: Int
    var mode: String          // off | pressure | vibration | pulse
    var intensity: Double = 0
    var hz: Double = 0
    var tap: Bool = false
}

struct HapticsUpdate: Equatable { var hand: String; var tUs: Int64; var channels: [HapticChannel] }

struct NearbyGlove: Equatable, Identifiable {
    var address: String
    var name: String
    var hand: String = ""     // left | right, or "" when the name does not say
    var rssi: Int = 0
    var id: String { address }
}

struct RemoteGloveSearch: Equatable {
    var state = "idle"        // idle | searching | done | failed
    var message = ""
    var found: [NearbyGlove] = []
}

struct GloveState: Equatable {
    var hand, state, message: String
    var batteryPct: Int
    /// Thumb … palm, then the source tank. Tenths of a kPa, gauge.
    var pressureDeciKPa: [Int]
    var savedAddress = ""
    var connected: Bool { state == "connected" }
    var connecting: Bool { state == "connecting" }
    var missing: Bool { state == "missing" }
    func kpa(_ ch: Int) -> Double? { ch < pressureDeciKPa.count ? Double(pressureDeciKPa[ch]) / 10 : nil }
}

struct StreamState: Equatable {
    var state = "off"
    var port = 0
    var width = 0
    var height = 0
    var viewers = 0
    var message = ""
    var live: Bool { state == "live" && port > 0 }
}

struct HeadsetStatus: Equatable {
    var id, name, model, platform, app, appVersion, hexrVersion: String
    var paused: Bool
    var headsetBatteryPct: Int
    var scene: SceneInfo
    var scenes: [SceneInfo]
    var gloves: [GloveState]
    var stream: StreamState
    var commands: [CommandInfo]
    var allowGloveControl, allowVideo, exposeScenes: Bool
    var controllers: Int
    var allowRecenter = false
    var haptics = false
    var clockUs: Int64 = 0
    var gloveSearch: RemoteGloveSearch? = nil

    func glove(_ hand: String) -> GloveState? { gloves.first { $0.hand.lowercased() == hand.lowercased() } }
    func glove(_ hand: Hand) -> GloveState? { glove(hand.rawValue) }
}

struct VideoHeader { var width, height, codec: Int }

struct PacketHeader {
    var length, flags: Int
    var ptsUs: Int64
    var config: Bool { flags & RemoteProtocol.flagConfig != 0 }
    var key: Bool { flags & RemoteProtocol.flagKey != 0 }
}
