// The glove side of the app: CoreBluetooth sessions (BleEngine.kt) and what the Test tab and the
// quick test do with them (HexrViewModel.kt), ported from the Android app on android-headsets.
//
// Left and right are two independent sessions, keyed by hand: a kit has one of each and two
// gloves of one hand cannot be driven at once. Writes are with-response (the characteristic has
// no write-without-response), one at a time per glove, at least 100 ms apart. A batch bigger than
// one write is split into whole frames: the firmware walks a write by each frame's length byte.

import Foundation
import CoreBluetooth
import Combine

struct Found: Identifiable, Equatable {
    let id: UUID
    let name: String
    let hand: Hand
    var rssi: Int?
    var address: String { id.uuidString }
}

struct Seen { var found: Found; var seenAt: Date }

final class Glove {
    let hand: Hand
    let peripheral: CBPeripheral
    var connected = false
    var connecting = true
    var status = "Connecting…"
    var telemetry = Telemetry()
    var decoder = FrameDecoder()
    var characteristic: CBCharacteristic?
    var lastRx: Date = .distantPast
    var absolutePa: Bool?
    var queue: [Data] = []
    var writing = false
    var writeStarted: Date?
    var lastSend: Date = .distantPast

    init(hand: Hand, peripheral: CBPeripheral) { self.hand = hand; self.peripheral = peripheral }

    var address: String { peripheral.identifier.uuidString }
    func kpa(_ ch: Int) -> Double { ch < telemetry.pressureRaw.count ? GP.rawToKPa(telemetry.pressureRaw[ch]) : 0 }
    var channelKPa: [Double] { (0..<6).map(kpa) }
    var sourceKPa: Double { kpa(6) }
    var isLive: Bool { connected && Date().timeIntervalSince(lastRx) < 3 }
    var battery: Double? { telemetry.battery }
    var batteryLabel: String { telemetry.battery.map { "\(Int(($0 * 100).rounded()))%" } ?? "—" }
    var failed: Bool { !connected && !connecting && status.hasPrefix("Error") }
    var mtu: Int? { connected ? peripheral.maximumWriteValueLength(for: .withResponse) + 3 : nil }
}

enum Mode { case pressure, vibration }

/// How the Test tab drives a glove (TestSettings.kt). Nothing here sends: Trigger does.
struct TestSettings: Equatable {
    var mode = Mode.pressure
    var intensity = 0.6     // 0.1–1.0
    var frequency = 10.0    // 0.1–40 Hz, vibration only
    var speed = 1.0         // 0.1–1.0, pressure only
    var peakRatio = 0.5     // 0.2–0.8, vibration only

    static let minHz = 0.1, maxHz = 40.0

    func frames(_ fingers: [Finger], on: Bool) -> [UInt8] {
        fingers.flatMap { f in
            mode == .vibration ? GP.vibration(f, on: on, frequency: frequency, intensity: intensity, peakRatio: peakRatio)
                               : GP.pressure(f, on: on, intensity: intensity, speed: speed)
        }
    }
    var pulse: Bool { frequency < GP.pwmVibrationHz }
    var targetKPa: Double? { mode == .pressure || pulse ? GP.intensityToKPa(intensity) : nil }
    var intensityLabel: String { "\(Int((intensity * 100).rounded()))% · \(Int(GP.intensityToKPa(intensity).rounded())) kPa" }
    var frequencyLabel: String { String(format: "%.1f Hz", frequency) }
    static func percent(_ v: Double) -> String { "\(Int((v * 100).rounded()))%" }

    /// A log-scale frequency slider: the 0.1–5 Hz pulses get most of the travel.
    static func hzToSlider(_ hz: Double) -> Double { log(min(max(hz, minHz), maxHz) / minHz) / log(maxHz / minHz) }
    static func sliderToHz(_ t: Double) -> Double {
        let hz = minHz * pow(maxHz / minHz, min(max(t, 0), 1))
        return min(max((hz * 10).rounded() / 10, minHz), maxHz)
    }
}

// MARK: - Quick test (QuickTest.kt)

enum QuickTest {
    static let settleS = 0.6, driveS = 2.0
    static let goodKPa = 40.0, failKPa = 2.0, sourceMinKPa = 10.0

    static func grade(_ peak: Double) -> Verdict { peak > goodKPa ? .good : peak >= failKPa ? .poor : .fail }

    static func judge(_ peaks: [Double], _ sourcePeak: Double) -> Judgement {
        let v = peaks.map(grade)
        let failed = v.indices.filter { v[$0] == .fail }, poor = v.indices.filter { v[$0] == .poor }
        if sourcePeak < sourceMinKPa { return Judgement(verdicts: v, outcome: .pumpFailed, count: 0, weak: []) }
        if !failed.isEmpty { return Judgement(verdicts: v, outcome: .failed, count: failed.count, weak: (failed + poor).sorted()) }
        if !poor.isEmpty { return Judgement(verdicts: v, outcome: .poor, count: poor.count, weak: poor) }
        return Judgement(verdicts: v, outcome: .allGood, count: 0, weak: [])
    }

    static func summary(_ j: Judgement, _ sourcePeak: Double) -> String {
        let good = j.verdicts.filter { $0 == .good }.count, poor = j.verdicts.filter { $0 == .poor }.count
        let failed = j.verdicts.filter { $0 == .fail }.count
        let kpa = String(format: "%.1f", sourcePeak)
        let breakdown = tr("{good} good, {poor} poor, {failed} failed", ("good", good), ("poor", poor), ("failed", failed))
        switch j.outcome {
        case .pumpFailed:
            return tr("The source never rose above {kpa} kPa, so no channel could have reached pressure. This is one fault in the pump or its supply, not six failed channels.", ("kpa", kpa))
        case .failed:
            return tr("The source reached {kpa} kPa, so supply is fine: a channel reading nothing with a healthy source is a blocked line, a valve that never opened, or a dead indenter.", ("kpa", kpa)) + " " + breakdown + "."
        case .poor:
            return tr("The source reached {kpa} kPa. Every channel moved, but not all of them reached full pressure: check the tubing on the weak ones.", ("kpa", kpa)) + " " + breakdown + "."
        case .allGood:
            return tr("The source reached {kpa} kPa.", ("kpa", kpa))
        }
    }
}

enum Outcome { case allGood, poor, failed, pumpFailed }

struct Judgement {
    let verdicts: [Verdict]
    let outcome: Outcome
    let count: Int
    let weak: [Int]
    var headline: String {
        switch outcome {
        case .allGood: return tr("All good")
        case .poor: return tr("{n} poor", ("n", count))
        case .failed: return tr("{n} failed", ("n", count))
        case .pumpFailed: return tr("Pump failed")
        }
    }
    var verdict: Verdict { outcome == .allGood ? .good : outcome == .poor ? .poor : .fail }
}

enum QTPhase { case idle, settle, drive, done }

// MARK: - The model

final class GloveManager: NSObject, ObservableObject {
    // Gloves and the search
    private(set) var gloves: [Hand: Glove] = [:]
    @Published private(set) var seen: [UUID: Seen] = [:]
    @Published private(set) var scanning = false
    @Published private(set) var bluetoothState: CBManagerState = .unknown
    @Published private(set) var scanError: String?
    @Published private(set) var swapping: UUID?

    // The Test tab
    @Published var channels: Set<Int> = [Finger.index.rawValue]
    @Published private(set) var settings = TestSettings()
    @Published var hand: Hand = .left
    @Published private(set) var driving = false
    @Published private(set) var pressedAt = Date.distantPast
    @Published private(set) var releasedAt: Date?
    private var onChannels: Set<Int> = []

    // The quick test
    @Published var qtHand: Hand?
    @Published private(set) var qtPhase = QTPhase.idle
    @Published private(set) var qtProgress = 0.0
    @Published private(set) var qtStatus = ""
    @Published private(set) var qtResult: Judgement?
    @Published private(set) var qtPeaks = [Double](repeating: 0, count: 6)
    @Published private(set) var qtTimes = [Double](repeating: 0, count: 6)
    @Published private(set) var qtSource = 0.0
    private var qtT0 = Date()
    private var peak = [Double](repeating: 0, count: 6)
    private var timeToPeak = [Double](repeating: 0, count: 6)
    private var sourcePeak = 0.0

    private var central: CBCentralManager!
    private var peripherals: [UUID: CBPeripheral] = [:]
    private var connectVisible = 0
    private var foreground = true
    private var nextScanAt = Date.distantPast
    private var scanEndsAt: Date?
    private var ticker: AnyCancellable?

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: .main)
        ticker = Timer.publish(every: 0.1, on: .main, in: .common).autoconnect().sink { [weak self] _ in self?.tick() }
    }

    var bluetoothOn: Bool { bluetoothState == .poweredOn }
    var bluetoothDenied: Bool { bluetoothState == .unauthorized }
    var quickTestRunning: Bool { qtPhase == .settle || qtPhase == .drive }

    func glove(_ h: Hand) -> Glove? { gloves[h] }
    func handConnected(_ h: Hand? = nil) -> Bool { gloves[h ?? hand]?.connected == true }
    var anyConnected: Bool { gloves.values.contains { $0.connected } }

    // MARK: tick

    private func tick() {
        let now = Date()
        // Writes that never call back must not stall the queue with something inflated.
        for g in gloves.values where g.writing {
            if let s = g.writeStarted, now.timeIntervalSince(s) > 1.5 { g.writing = false; pump(g) }
        }
        if driving && !handConnected() { driving = false }
        if !handConnected(), handConnected(hand.other) { hand = hand.other }
        if let q = qtHand, gloves[q]?.connected != true { qtHand = nil }
        if qtHand == nil { qtHand = Hand.allCases.first { gloves[$0]?.connected == true } }

        search(now)
        tickQuickTest(now)
        objectWillChange.send()   // telemetry, batteries, "Live": the screens sample at 10 Hz
    }

    // MARK: search

    /// The Connect screen (as the Test tab or the Gloves panel) is on screen, or no longer.
    func setConnectVisible(_ on: Bool) {
        connectVisible = max(0, connectVisible + (on ? 1 : -1))
        if connectVisible == 0 { stopScan() }
    }

    func setForeground(_ on: Bool) {
        foreground = on
        if !on { onBackground() }
    }

    func retryScan() { scanError = nil; nextScanAt = .distantPast }

    private func search(_ now: Date) {
        seen = seen.filter { now.timeIntervalSince($0.value.seenAt) <= GloveSearch.expireS }
        let wanted = bluetoothOn && connectVisible > 0 && foreground && !gloves.values.contains { $0.connecting }
        if !wanted { stopScan(); return }
        if scanning {
            if let end = scanEndsAt, now >= end { finishScan() }
            return
        }
        guard now >= nextScanAt else { return }
        scanning = true
        scanEndsAt = now.addingTimeInterval(8)
        central.scanForPeripherals(withServices: nil, options: [CBCentralManagerScanOptionAllowDuplicatesKey: true])
    }

    private func finishScan() {
        if central.isScanning { central.stopScan() }
        scanning = false
        scanEndsAt = nil
        let both = Hand.allCases.allSatisfy { gloves[$0]?.connected == true }
        nextScanAt = Date().addingTimeInterval(scanError != nil ? GloveSearch.retryS : both ? GloveSearch.fullRescanS : GloveSearch.rescanS)
    }

    private func stopScan() {
        if central.isScanning { central.stopScan() }
        scanning = false
        scanEndsAt = nil
    }

    /// One hand's gloves heard lately, strongest first.
    func candidates(_ h: Hand) -> [Found] {
        seen.values.map(\.found).filter { $0.hand == h }.sorted { ($0.rssi ?? .min) > ($1.rssi ?? .min) }
    }

    /// Every glove heard lately, strongest first: the list to test from.
    func allFound() -> [Found] { seen.values.map(\.found).sorted { ($0.rssi ?? .min) > ($1.rssi ?? .min) } }

    // MARK: connections

    func connect(_ f: Found) {
        stopScan()
        if let g = gloves[f.hand], g.connected || g.connecting { return }
        guard let p = peripherals[f.id] else { return }
        let g = Glove(hand: f.hand, peripheral: p)
        gloves[f.hand] = g
        p.delegate = self
        central.connect(p)
        // A connect that never answers must not leave the hand stuck on Connecting….
        DispatchQueue.main.asyncAfter(deadline: .now() + 15) { [weak self, weak g] in
            guard let self, let g, g.connecting, self.gloves[g.hand] === g else { return }
            self.central.cancelPeripheralConnection(p)
            g.connecting = false
            g.status = "Error: the glove did not answer"
        }
    }

    func disconnect(_ h: Hand) {
        guard let g = gloves[h] else { return }
        sendAllOff(h)
        // Vent first, then drop the link once the vent has gone out (or after 1 s regardless).
        let deadline = Date().addingTimeInterval(1)
        func close() {
            if (g.writing || !g.queue.isEmpty) && Date() < deadline {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) { close() }
            } else {
                central.cancelPeripheralConnection(g.peripheral)
                if !g.connected { g.connecting = false; g.status = "Not connected" }
            }
        }
        close()
    }

    /// Test this glove: its hand lets go of the glove it has, then takes this one.
    func test(_ f: Found) {
        guard let g = gloves[f.hand], g.connected || g.connecting else { connect(f); return }
        disconnect(f.hand)
        swapping = f.id
        let until = Date().addingTimeInterval(6)
        func wait() {
            if Date() < until, let g = gloves[f.hand], g.connected || g.connecting {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { wait() }
            } else {
                swapping = nil
                connect(f)
            }
        }
        wait()
    }

    // MARK: sending

    func send(_ h: Hand, _ bytes: [UInt8]) {
        guard let g = gloves[h], g.connected, g.characteristic != nil, !bytes.isEmpty else { return }
        let room = max(20, g.peripheral.maximumWriteValueLength(for: .withResponse))
        g.queue.append(contentsOf: Self.split(bytes, room))
        pump(g)
    }

    /// Vent every channel. Anything still waiting is dropped first: a Release all must never sit
    /// in the queue behind a drive that has not gone out yet.
    func sendAllOff(_ h: Hand? = nil) {
        for hh in h.map({ [$0] }) ?? Hand.allCases {
            gloves[hh]?.queue.removeAll()
            send(hh, GP.allOff())
        }
    }

    /// Split a batch into writes of at most `room` bytes, never breaking a frame.
    static func split(_ bytes: [UInt8], _ room: Int) -> [Data] {
        var out: [Data] = [], cur: [UInt8] = [], i = 0
        while i < bytes.count {
            let len = max(1, Int(bytes[i]))
            let frame = Array(bytes[i..<min(bytes.count, i + len)])
            if !cur.isEmpty && cur.count + frame.count > room { out.append(Data(cur)); cur = [] }
            cur += frame
            i += len
        }
        if !cur.isEmpty { out.append(Data(cur)) }
        return out
    }

    private func pump(_ g: Glove) {
        guard !g.writing, !g.queue.isEmpty, let c = g.characteristic, g.connected else { return }
        let gap = Date().timeIntervalSince(g.lastSend)
        if gap < 0.1 {
            DispatchQueue.main.asyncAfter(deadline: .now() + (0.1 - gap)) { [weak self] in self?.pump(g) }
            return
        }
        g.writing = true
        g.writeStarted = Date()
        g.peripheral.writeValue(g.queue.removeFirst(), for: c, type: .withResponse)
    }

    // MARK: the Test tab

    var activeFingers: [Finger] { channels.sorted().compactMap(Finger.init(rawValue:)) }

    func toggleChannel(_ ch: Int) { if channels.contains(ch) { channels.remove(ch) } else { channels.insert(ch) } }
    func selectAll() { channels = Set(0..<6) }
    func selectNone() { channels = [] }

    func pickHand(_ h: Hand) {
        guard h != hand else { return }
        if driving { release() }   // never leave the hand you walk away from inflated
        hand = h
    }

    func pickMode(_ m: Mode) {
        guard m != settings.mode else { return }
        if driving { release() }
        settings.mode = m
    }

    // The sliders only change what Trigger will send.
    func setIntensity(_ v: Double) { settings.intensity = min(max(v, 0.1), 1) }
    func setFrequency(_ v: Double) { settings.frequency = min(max(v, TestSettings.minHz), TestSettings.maxHz) }
    func setSpeed(_ v: Double) { settings.speed = min(max(v, 0.1), 1) }
    func setPeakRatio(_ v: Double) { settings.peakRatio = min(max(v, 0.2), 0.8) }

    var canDrive: Bool { !channels.isEmpty && handConnected() }

    /// Fire the picked fingers as set and leave them on. A finger dropped since is let go.
    func trigger() {
        guard canDrive else { return }
        let dropped = onChannels.subtracting(channels).sorted().compactMap(Finger.init(rawValue:))
        send(hand, settings.frames(dropped, on: false) + settings.frames(activeFingers, on: true))
        driving = true
        pressedAt = Date()
        releasedAt = nil
        onChannels = channels
    }

    /// Stop output, whatever is picked: every channel, every glove.
    func release() {
        if driving { releasedAt = Date() }
        driving = false
        onChannels = []
        sendAllOff()
    }

    func allOff() {
        if quickTestRunning { abortQuickTest(tr("Stopped")) }
        release()
    }

    /// Vent on the way to the background: an iPad put down mid-test must not keep pressing.
    func onBackground() {
        if quickTestRunning { abortQuickTest(tr("Stopped")) }
        release()
        stopScan()
    }

    // MARK: the quick test

    func toggleQuickTest() { quickTestRunning ? abortQuickTest(tr("Stopped")) : startQuickTest() }

    private func startQuickTest() {
        guard let h = qtHand, let g = gloves[h], g.connected else { qtStatus = tr("Connect a glove first"); return }
        guard g.isLive else { qtStatus = tr("No readings from this glove"); return }
        if driving { release() }
        peak = .init(repeating: 0, count: 6); timeToPeak = peak; sourcePeak = 0
        qtResult = nil
        sendAllOff(h)
        qtPhase = .settle
        qtT0 = Date()
        qtProgress = 0
        qtStatus = tr("Venting…")
    }

    private func abortQuickTest(_ why: String) {
        qtPhase = .idle
        if let h = qtHand { sendAllOff(h) }
        qtProgress = 0
        qtStatus = why
    }

    func pickQuickTestHand(_ h: Hand) {
        guard !quickTestRunning, h != qtHand else { return }
        qtHand = h
        qtPhase = .idle
        qtResult = nil
        qtStatus = ""
        qtProgress = 0
    }

    private func tickQuickTest(_ now: Date) {
        guard quickTestRunning else { return }
        guard let h = qtHand, let g = gloves[h], g.connected else { abortQuickTest(tr("Glove disconnected")); return }
        let el = now.timeIntervalSince(qtT0)
        if qtPhase == .settle {
            qtProgress = min(1, el / QuickTest.settleS) * 0.2
            if el >= QuickTest.settleS {
                // Everything at once: it also exercises whether the pump can keep up with six.
                send(h, Finger.allCases.flatMap { GP.pressure($0, on: true, intensity: 1, speed: 1) })
                qtPhase = .drive
                qtT0 = now
                qtStatus = tr("Driving all channels…")
            }
            return
        }
        qtProgress = 0.2 + 0.8 * min(1, el / QuickTest.driveS)
        sourcePeak = max(sourcePeak, g.sourceKPa)
        for ch in 0..<6 {
            let k = g.kpa(ch)
            if k > peak[ch] { peak[ch] = k; timeToPeak[ch] = el }
        }
        if el >= QuickTest.driveS {
            sendAllOff(h)
            qtPhase = .done
            qtProgress = 1
            qtStatus = ""
            qtPeaks = peak
            qtTimes = timeToPeak
            qtSource = sourcePeak
            qtResult = QuickTest.judge(peak, sourcePeak)
        }
    }

    private func gloveFor(_ p: CBPeripheral) -> Glove? { gloves.values.first { $0.peripheral === p } }
}

extension Hand {
    var other: Hand { self == .left ? .right : .left }
}

// MARK: - CoreBluetooth

extension GloveManager: CBCentralManagerDelegate {
    func centralManagerDidUpdateState(_ c: CBCentralManager) {
        bluetoothState = c.state
        if c.state != .poweredOn {
            for g in gloves.values { g.connected = false; g.connecting = false; g.status = "Not connected" }
            scanning = false
            driving = false
        }
    }

    func centralManager(_ c: CBCentralManager, didDiscover p: CBPeripheral,
                        advertisementData ad: [String: Any], rssi: NSNumber) {
        let name = (ad[CBAdvertisementDataLocalNameKey] as? String) ?? p.name
        guard let hand = GP.hand(fromName: name) else { return }
        peripherals[p.identifier] = p
        let r = rssi.intValue == 127 ? nil : rssi.intValue   // 127: the radio could not say
        seen[p.identifier] = Seen(found: Found(id: p.identifier, name: name ?? "", hand: hand, rssi: r), seenAt: Date())
    }

    func centralManager(_ c: CBCentralManager, didConnect p: CBPeripheral) {
        gloveFor(p)?.status = "Connecting…"
        p.discoverServices([GP.serviceUUID])
    }

    func centralManager(_ c: CBCentralManager, didFailToConnect p: CBPeripheral, error: Error?) {
        guard let g = gloveFor(p) else { return }
        g.connected = false
        g.connecting = false
        g.status = "Error: \(error?.localizedDescription ?? "could not connect")"
    }

    func centralManager(_ c: CBCentralManager, didDisconnectPeripheral p: CBPeripheral, error: Error?) {
        guard let g = gloveFor(p) else { return }
        g.connected = false
        g.connecting = false
        g.characteristic = nil
        g.queue.removeAll()
        g.writing = false
        g.status = error.map { "Error: \($0.localizedDescription)" } ?? "Not connected"
    }
}

extension GloveManager: CBPeripheralDelegate {
    func peripheral(_ p: CBPeripheral, didDiscoverServices error: Error?) {
        guard let s = p.services?.first(where: { $0.uuid == GP.serviceUUID }) else {
            if let g = gloveFor(p) { g.connecting = false; g.status = "Error: no HEXR service on this device" }
            central.cancelPeripheralConnection(p)
            return
        }
        p.discoverCharacteristics([GP.charUUID], for: s)
    }

    func peripheral(_ p: CBPeripheral, didDiscoverCharacteristicsFor s: CBService, error: Error?) {
        guard let g = gloveFor(p), let ch = s.characteristics?.first(where: { $0.uuid == GP.charUUID }) else { return }
        g.characteristic = ch
        // Subscribe before reporting connected: actuation does not need it, the readouts do.
        p.setNotifyValue(true, for: ch)
        g.connected = true
        g.connecting = false
        g.status = "Connected"
    }

    func peripheral(_ p: CBPeripheral, didUpdateValueFor ch: CBCharacteristic, error: Error?) {
        guard let g = gloveFor(p), let data = ch.value else { return }
        g.decoder.feed(data, into: &g.telemetry)
        g.lastRx = Date()
        if g.absolutePa == nil, g.telemetry.seen {
            g.absolutePa = g.telemetry.pressureRaw.contains { $0 > 10000 }
        }
    }

    func peripheral(_ p: CBPeripheral, didWriteValueFor ch: CBCharacteristic, error: Error?) {
        guard let g = gloveFor(p) else { return }
        g.writing = false
        g.lastSend = Date()
        pump(g)
    }
}
