// The Headsets tab's model (Android HeadsetsViewModel.kt): every HexR headset on this Wi-Fi, each
// one's gloves through the headset, and its view. It never touches Bluetooth: the gloves belong to
// the headset. Links write into `entries`; the UI reads `rows`, a snapshot rebuilt four times a
// second, so a headset reporting five times a second does not redraw the screen each time.

import Foundation
import SwiftUI

struct HeadsetRow: Identifiable, Equatable {
    let key: String
    var host: String
    var title: String
    var nickname: String
    var announce: Announce?
    var status: HeadsetStatus?
    var link: HeadsetLink.State
    var error: String?
    var manual: Bool
    /// This iPad asked to watch: the view shows while the headset shares it.
    var watching = false
    /// When Recenter was last pressed (nowS()), 0 for never.
    var recenteredAt: Double = 0
    var id: String { key }
}

final class HeadsetsModel: ObservableObject, HeadsetLinkListener {
    private final class Entry {
        let key: String
        var host: String
        let link: HeadsetLink
        let manual: Bool
        var announce: Announce?
        var status: HeadsetStatus?
        var state: HeadsetLink.State = .connecting
        var error: String?
        var errorAt: Double = 0
        var lastHeard = nowS()
        var recenteredAt: Double = 0
        var askToShare = false
        let timeline = HapticsTimeline()
        init(key: String, host: String, link: HeadsetLink, manual: Bool) {
            self.key = key; self.host = host; self.link = link; self.manual = manual
        }
    }

    private static let tickS = 0.25, forgetAfterS = 15.0, errorShownS = 8.0

    @Published private(set) var rows: [HeadsetRow] = []
    /// The headset open in the live view, by key. Nil shows the list.
    @Published var selected: String?
    /// Names given to gloves on this iPad, by Bluetooth address (upper case).
    @Published private(set) var gloveNames: [String: String] = [:]
    /// Listening and connected: the tab is on screen and the app in front.
    @Published private(set) var online = false
    @Published private(set) var searching = false

    private var watching = Set<String>()
    private var entries: [String: Entry] = [:]
    private var discovery: HeadsetDiscovery!
    private var visible = false
    private var foreground = true
    private var timer: Timer?
    private let prefs = UserDefaults.standard

    init() {
        discovery = HeadsetDiscovery { [weak self] ann, id, host, port, _ in self?.onFound(ann, id, host, port) }
        discovery.knownHosts = { [weak self] in Set(self?.entries.values.map(\.host) ?? []) }
        gloveNames = loadGloveNames()
        // Headsets added by address before are kept, and come back next time.
        for addr in prefs.stringArray(forKey: "headsets.manual") ?? [] { _ = addByAddress(addr, save: false) }
        timer = Timer.scheduledTimer(withTimeInterval: Self.tickS, repeats: true) { [weak self] _ in self?.tick() }
    }

    // -- when to listen

    /// The tab is on screen. Nothing is opened until it is.
    func setVisible(_ on: Bool) { visible = on; update() }

    /// The app is in front. Sockets are given up the moment it is not.
    func setForeground(_ on: Bool) { foreground = on; update() }

    private func update() {
        let want = visible && foreground
        guard want != online else { return }
        online = want
        if want {
            discovery.start()
            entries.values.forEach { $0.link.start() }
        } else {
            discovery.stop()
            entries.values.forEach { $0.link.stop() }
        }
        UIApplication.shared.isIdleTimerDisabled = want && !watching.isEmpty
    }

    /// Look again now: a fresh sweep of the Wi-Fi.
    func searchAgain() { discovery.sweep() }

    // -- headsets

    private func onFound(_ a: Announce?, _ id: String, _ host: String, _ port: Int) {
        if let existing = entries[id] {
            existing.lastHeard = nowS()
            if let a {
                let previous = existing.announce
                // The same headset with its app restarted, or a different app on it: follow the newest.
                if previous == nil || a.startedAt >= previous!.startedAt {
                    existing.announce = a
                    existing.host = host
                    existing.link.retarget(host, a.control)
                }
            }
            return
        }
        // A headset typed in by address that the sweep also found: keep the typed one.
        if entries.values.contains(where: { $0.manual && $0.host == host && $0.link.port == port }) { return }
        let e = Entry(key: id, host: host, link: HeadsetLink(key: id, host: host, port: port, listener: self), manual: false)
        e.announce = a
        entries[id] = e
        if online { e.link.start() }
        tick()
    }

    /// For venue Wi-Fi that hides devices from each other: the headset's address, typed in. Its key, or nil.
    @discardableResult
    func addByAddress(_ address: String, save: Bool = true) -> String? {
        guard let (host, port) = RemoteProtocol.parseAddress(address) else { return nil }
        let key = port == RemoteProtocol.controlPort ? "ip:\(host)" : "ip:\(host):\(port)"
        if entries[key] == nil {
            let e = Entry(key: key, host: host, link: HeadsetLink(key: key, host: host, port: port, listener: self), manual: true)
            entries[key] = e
            if online { e.link.start() }
            if save { saveManual() }
            tick()
        }
        return key
    }

    private func saveManual() {
        let list = entries.values.filter(\.manual).map { e in
            e.link.port == RemoteProtocol.controlPort ? e.host : "\(e.host):\(e.link.port)"
        }
        prefs.set(list.sorted(), forKey: "headsets.manual")
    }

    func forget(_ key: String) {
        guard let e = entries.removeValue(forKey: key) else { return }
        e.link.stop()
        watching.remove(key)
        if selected == key { selected = nil }
        if e.manual { saveManual() }
        tick()
    }

    func select(_ key: String?) { selected = key }

    func rename(_ key: String, _ nickname: String) {
        let n = nickname.trimmingCharacters(in: .whitespaces)
        if n.isEmpty { prefs.removeObject(forKey: "nick:\(key)") } else { prefs.set(n, forKey: "nick:\(key)") }
        tick()
    }

    func timeline(_ key: String) -> HapticsTimeline? { entries[key]?.timeline }

    // -- requests

    func connectGlove(_ key: String, _ hand: Hand) { send(key, RemoteProtocol.glove("connect", hand)) }
    func disconnectGlove(_ key: String, _ hand: Hand) { send(key, RemoteProtocol.glove("disconnect", hand)) }
    func release(_ key: String) { send(key, RemoteProtocol.release()) }
    func trigger(_ key: String) { send(key, RemoteProtocol.trigger()) }
    func searchGloves(_ key: String) { send(key, RemoteProtocol.gloveSearch()) }
    func connectGloveAt(_ key: String, _ hand: Hand, _ address: String) { send(key, RemoteProtocol.connectGloveAt(hand, address)) }
    func forgetGlove(_ key: String, _ hand: Hand) {
        send(key, #"{"type":"glove","action":"forget","hand":"\#(hand.rawValue.lowercased())"}"#)
    }

    /// What this iPad calls the glove at this address: the name given here, or its own.
    func gloveName(_ address: String) -> String { gloveNames[address.uppercased()] ?? GloveNames.autoName(address) }

    /// Names a glove by its address on this iPad. Blank, or its own name, clears it.
    func renameGlove(_ address: String, _ name: String) {
        GloveNames.rename(address, to: name)
        gloveNames = loadGloveNames()
    }

    private func loadGloveNames() -> [String: String] {
        var out: [String: String] = [:]
        for (k, v) in prefs.dictionaryRepresentation() where k.hasPrefix("glove:") {
            if let s = v as? String { out[String(k.dropFirst("glove:".count))] = s }
        }
        return out
    }

    func recenter(_ key: String) {
        entries[key]?.recenteredAt = nowS()
        send(key, RemoteProtocol.recenter())
        tick()
    }

    /// Watch: ask the wearer to share, unless the headset already is, in which case just join.
    func watch(_ key: String) {
        watching.insert(key)
        UIApplication.shared.isIdleTimerDisabled = online
        guard let e = entries[key] else { return }
        if e.state != .connected || e.status == nil { e.askToShare = true }
        else if let st = e.status?.stream, !st.live, st.state != "requesting" { send(key, RemoteProtocol.stream("start")) }
        tick()
    }

    /// Stop watching. Ending the share closes every viewer, so it ends only if nobody else watches.
    func stopWatching(_ key: String, joined: Bool) {
        guard watching.contains(key) else { return }
        watching.remove(key)
        if watching.isEmpty { UIApplication.shared.isIdleTimerDisabled = false }
        entries[key]?.askToShare = false
        if let st = entries[key]?.status?.stream, st.live || st.state == "requesting" {
            if st.viewers - (joined ? 1 : 0) <= 0 { send(key, RemoteProtocol.stream("stop")) }
        }
        tick()
    }

    private func send(_ key: String, _ line: String) {
        guard let e = entries[key] else { return }
        e.error = nil
        e.link.send(line)
    }

    // -- from the links (main queue)

    func onLinkState(_ key: String, _ state: HeadsetLink.State) {
        guard let e = entries[key] else { return }
        if state == .connected && e.state != .connected { e.timeline.resetClock() }
        e.state = state
    }

    func onStatus(_ key: String, _ status: HeadsetStatus) {
        guard let e = entries[key] else { return }
        e.status = status
        e.lastHeard = nowS()
        e.timeline.onStatus(status, arrived: nowS())
        if e.askToShare {
            e.askToShare = false
            if !status.stream.live && status.stream.state != "requesting" { e.link.send(RemoteProtocol.stream("start")) }
        }
    }

    func onHaptics(_ key: String, _ update: HapticsUpdate) { entries[key]?.timeline.onHaptics(update) }

    func onError(_ key: String, request: String, message: String) {
        guard let e = entries[key] else { return }
        e.error = message
        e.errorAt = nowS()
    }

    // -- tick

    private func tick() {
        let now = nowS()
        searching = discovery?.sweeping ?? false
        // A headset that stopped announcing and cannot be reached has gone.
        for e in entries.values where !e.manual && e.state != .connected && now - e.lastHeard > Self.forgetAfterS {
            forget(e.key)
        }
        // The wearer said no: an answer, not something to keep waiting on.
        for k in watching where entries[k]?.status?.stream.state == "denied" { watching.remove(k) }

        let next = entries.values.map { e -> HeadsetRow in
            let nickname = prefs.string(forKey: "nick:\(e.key)") ?? ""
            let name = e.status?.name ?? e.announce?.name ?? e.host
            return HeadsetRow(
                key: e.key, host: e.host,
                title: nickname.isEmpty ? "\(name) · \(Self.shortId(e.key))" : nickname,
                nickname: nickname, announce: e.announce, status: e.status, link: e.state,
                error: (e.error != nil && now - e.errorAt < Self.errorShownS) ? e.error : nil,
                manual: e.manual, watching: watching.contains(e.key), recenteredAt: e.recenteredAt)
        }.sorted { $0.title.lowercased() < $1.title.lowercased() }
        if next != rows { rows = next }
        if let s = selected, entries[s] == nil { selected = nil }
    }

    /// Headsets of one model share a name ("Quest 3"): the end of the id, or the address, tells them apart.
    private static func shortId(_ key: String) -> String {
        key.hasPrefix("ip:") ? String(key.dropFirst(3)) : String(key.suffix(4)).uppercased()
    }
}
