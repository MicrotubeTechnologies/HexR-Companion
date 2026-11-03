// BLE runtime — CoreBluetooth port of hexr/engine.py.
// Left and right are two independent sessions. Writes are with-response (the
// characteristic does not allow write-without-response) and spaced ≥100 ms per
// glove, as the Unity plugin and the desktop app do.

import Foundation
import CoreBluetooth
import Combine

struct FoundGlove: Identifiable, Equatable {
    let id: UUID
    let name: String
    let hand: Hand
    var rssi: Int
}

final class Glove: ObservableObject, Identifiable {
    let hand: Hand
    let peripheral: CBPeripheral
    var id: Hand { hand }
    @Published var status = "Connecting…"
    @Published var connected = false
    @Published var telemetry = Telemetry()
    var decoder = FrameDecoder()
    var characteristic: CBCharacteristic?
    var lastRx: Date = .distantPast
    var queue: [Data] = []
    var writing = false
    var lastSend: Date = .distantPast

    init(hand: Hand, peripheral: CBPeripheral) { self.hand = hand; self.peripheral = peripheral }

    func kpa(_ ch: Int) -> Double { GP.rawToKPa(telemetry.pressureRaw[ch]) }
    var sourceKPa: Double { kpa(6) }
    var isLive: Bool { connected && Date().timeIntervalSince(lastRx) < 3 }
    var batteryLabel: String { telemetry.battery.map { "\(Int(($0 * 100).rounded()))%" } ?? "—" }
}

final class GloveManager: NSObject, ObservableObject {
    @Published var found: [FoundGlove] = []
    @Published var gloves: [Hand: Glove] = [:]
    @Published var scanning = false
    @Published var bluetoothError: String?

    private var central: CBCentralManager!
    private var peripherals: [UUID: CBPeripheral] = [:]
    private var scanTimer: Timer?
    private var pendingScan = false
    private var tick: AnyCancellable?

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: .main)
        // Re-publish telemetry for the UI at ~15 Hz rather than on every notification.
        tick = Timer.publish(every: 1.0 / 15, on: .main, in: .common).autoconnect()
            .sink { [weak self] _ in self?.objectWillChange.send() }
    }

    var connectedGloves: [Glove] { Hand.allCases.compactMap { gloves[$0] }.filter { $0.connected } }

    // -- scanning

    func scan() {
        guard !scanning else { return }
        guard central.state == .poweredOn else {
            pendingScan = true
            bluetoothError = describe(central.state)
            return
        }
        bluetoothError = nil
        found.removeAll()
        scanning = true
        central.scanForPeripherals(withServices: nil,
                                   options: [CBCentralManagerScanOptionAllowDuplicatesKey: false])
        scanTimer?.invalidate()
        scanTimer = Timer.scheduledTimer(withTimeInterval: 8, repeats: false) { [weak self] _ in self?.stopScan() }
    }

    func stopScan() {
        scanTimer?.invalidate()
        if central.isScanning { central.stopScan() }
        scanning = false
    }

    // -- connections

    func connect(_ f: FoundGlove) {
        if let g = gloves[f.hand], g.connected || g.status == "Connecting…" { return }
        guard let p = peripherals[f.id] else { return }
        let g = Glove(hand: f.hand, peripheral: p)
        gloves[f.hand] = g
        p.delegate = self
        central.connect(p)
    }

    func disconnect(_ hand: Hand) {
        guard let g = gloves[hand] else { return }
        // Vent first, then drop the link once the queue has gone out.
        send([hand], GP.allOff())
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { [weak self] in
            self?.central.cancelPeripheralConnection(g.peripheral)
        }
    }

    // -- sending

    func send(_ hands: [Hand], _ bytes: [UInt8]) {
        for h in hands {
            guard let g = gloves[h], g.connected, g.characteristic != nil else { continue }
            g.queue.append(Data(bytes))
            pump(g)
        }
    }

    func allOff() { send(Hand.allCases, GP.allOff()) }

    private func pump(_ g: Glove) {
        guard !g.writing, !g.queue.isEmpty, let c = g.characteristic else { return }
        let gap = Date().timeIntervalSince(g.lastSend)
        if gap < 0.1 {
            DispatchQueue.main.asyncAfter(deadline: .now() + (0.1 - gap)) { [weak self] in self?.pump(g) }
            return
        }
        g.writing = true
        let data = g.queue.removeFirst()
        g.peripheral.writeValue(data, for: c, type: .withResponse)
    }

    private func describe(_ s: CBManagerState) -> String? {
        switch s {
        case .poweredOff: return "Bluetooth is off. Turn it on in Control Centre."
        case .unauthorized: return "Bluetooth access is off for HEXR Companion. Allow it in Settings → Privacy & Security → Bluetooth."
        case .unsupported: return "This iPad has no Bluetooth LE."
        case .poweredOn: return nil
        default: return "Bluetooth is starting…"
        }
    }

    private func glove(for p: CBPeripheral) -> Glove? { gloves.values.first { $0.peripheral === p } }
}

extension GloveManager: CBCentralManagerDelegate {
    func centralManagerDidUpdateState(_ c: CBCentralManager) {
        bluetoothError = describe(c.state)
        if c.state == .poweredOn, pendingScan { pendingScan = false; scan() }
        if c.state != .poweredOn {
            for g in gloves.values { g.connected = false; g.status = "Not connected" }
            scanning = false
        }
    }

    func centralManager(_ c: CBCentralManager, didDiscover p: CBPeripheral,
                        advertisementData ad: [String: Any], rssi: NSNumber) {
        let name = (ad[CBAdvertisementDataLocalNameKey] as? String) ?? p.name
        guard let hand = GP.hand(fromName: name) else { return }
        peripherals[p.identifier] = p
        if let i = found.firstIndex(where: { $0.id == p.identifier }) {
            found[i].rssi = rssi.intValue
        } else {
            found.append(FoundGlove(id: p.identifier, name: name ?? "", hand: hand, rssi: rssi.intValue))
        }
    }

    func centralManager(_ c: CBCentralManager, didConnect p: CBPeripheral) {
        glove(for: p)?.status = "Finding the glove's service…"
        p.discoverServices([GP.serviceUUID])
    }

    func centralManager(_ c: CBCentralManager, didFailToConnect p: CBPeripheral, error: Error?) {
        guard let g = glove(for: p) else { return }
        g.connected = false
        g.status = "Error: \(error?.localizedDescription ?? "could not connect")"
    }

    func centralManager(_ c: CBCentralManager, didDisconnectPeripheral p: CBPeripheral, error: Error?) {
        guard let g = glove(for: p) else { return }
        g.connected = false
        g.characteristic = nil
        g.queue.removeAll()
        g.writing = false
        g.status = error.map { "Lost: \($0.localizedDescription)" } ?? "Not connected"
        objectWillChange.send()
    }
}

extension GloveManager: CBPeripheralDelegate {
    func peripheral(_ p: CBPeripheral, didDiscoverServices error: Error?) {
        guard let s = p.services?.first(where: { $0.uuid == GP.serviceUUID }) else {
            glove(for: p)?.status = "Error: this is not a HEXR glove service"
            return
        }
        p.discoverCharacteristics([GP.charUUID], for: s)
    }

    func peripheral(_ p: CBPeripheral, didDiscoverCharacteristicsFor s: CBService, error: Error?) {
        guard let g = glove(for: p), let ch = s.characteristics?.first(where: { $0.uuid == GP.charUUID }) else { return }
        g.characteristic = ch
        // Subscribe before reporting connected; actuation does not depend on it,
        // but the pressure readout and the quick test do.
        p.setNotifyValue(true, for: ch)
        g.connected = true
        g.status = "Connected"
        objectWillChange.send()
    }

    func peripheral(_ p: CBPeripheral, didUpdateValueFor ch: CBCharacteristic, error: Error?) {
        guard let g = glove(for: p), let data = ch.value else { return }
        var t = g.telemetry
        g.decoder.feed(data, into: &t)
        g.telemetry = t
        g.lastRx = Date()
    }

    func peripheral(_ p: CBPeripheral, didWriteValueFor ch: CBCharacteristic, error: Error?) {
        guard let g = glove(for: p) else { return }
        g.writing = false
        g.lastSend = Date()
        pump(g)
    }
}
