// One headset's control connection: requests out, status and errors in (Android remote/HeadsetLink.kt).
// A headset sends its status five times a second, and at least once a second even asleep, so four
// seconds of silence means it has gone and the link reconnects with a growing pause. The headset
// drops a phone it has not heard from in fifteen seconds, which the ping every five prevents.
// Everything here runs on the main queue: a few short lines a second is nothing to it.

import Foundation
import Network

protocol HeadsetLinkListener: AnyObject {
    func onLinkState(_ key: String, _ state: HeadsetLink.State)
    func onStatus(_ key: String, _ status: HeadsetStatus)
    func onError(_ key: String, request: String, message: String)
    func onHaptics(_ key: String, _ update: HapticsUpdate)
}

final class HeadsetLink {
    enum State { case connecting, connected, lost }

    static let client = "HexR Companion (iPad)"
    private static let connectTimeout: TimeInterval = 3
    private static let silenceTimeout: TimeInterval = 4
    private static let pingEvery: TimeInterval = 5
    private static let initialBackoff: TimeInterval = 0.5
    private static let maxBackoff: TimeInterval = 5

    let key: String
    private(set) var host: String
    private(set) var port: Int
    weak var listener: HeadsetLinkListener?

    private var running = false
    private var generation = 0
    private var conn: NWConnection?
    private var buffer = Data()
    private var lastRx = Date.distantPast
    private var lastPing = Date.distantPast
    private var backoff = initialBackoff
    private var watchdog: Timer?
    private var ready = false

    init(key: String, host: String, port: Int, listener: HeadsetLinkListener) {
        self.key = key; self.host = host; self.port = port; self.listener = listener
    }

    func start() {
        guard !running else { return }
        running = true
        generation += 1
        backoff = Self.initialBackoff
        open(generation)
    }

    func stop() {
        running = false
        generation += 1
        close()
    }

    /// Points the link at a new address, after the headset's app restarted somewhere else.
    func retarget(_ newHost: String, _ newPort: Int) {
        guard newHost != host || newPort != port else { return }
        host = newHost; port = newPort
        if running { reconnectSoon(generation, after: 0) }
    }

    func send(_ line: String) {
        guard ready, let c = conn else { return }
        c.send(content: Data((line + "\n").utf8), completion: .contentProcessed { _ in })
    }

    private func close() {
        watchdog?.invalidate(); watchdog = nil
        conn?.stateUpdateHandler = nil
        conn?.cancel()
        conn = nil
        ready = false
        buffer.removeAll()
    }

    private func open(_ mine: Int) {
        guard running, mine == generation, let p = NWEndpoint.Port(rawValue: UInt16(clamping: port)) else { return }
        listener?.onLinkState(key, .connecting)
        let tcp = NWProtocolTCP.Options()
        tcp.noDelay = true
        tcp.connectionTimeout = Int(Self.connectTimeout)
        let params = NWParameters(tls: nil, tcp: tcp)
        params.requiredInterfaceType = .wifi
        let c = NWConnection(host: NWEndpoint.Host(host), port: p, using: params)
        conn = c
        let opened = Date()
        c.stateUpdateHandler = { [weak self] st in
            guard let self, mine == self.generation else { return }
            switch st {
            case .ready:
                self.ready = true
                self.lastRx = Date(); self.lastPing = Date()
                self.backoff = Self.initialBackoff
                self.send(RemoteProtocol.hello(Self.client))
                self.listener?.onLinkState(self.key, .connected)
                self.receive(mine)
            case .failed, .cancelled:
                self.lost(mine)
            case .waiting:
                // No route yet (Wi-Fi off, host down): give up after the connect timeout and retry.
                if Date().timeIntervalSince(opened) > Self.connectTimeout { self.lost(mine) }
            default: break
            }
        }
        c.start(queue: .main)
        watchdog = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            guard let self, mine == self.generation else { return }
            let now = Date()
            if !self.ready {
                if now.timeIntervalSince(opened) > Self.connectTimeout + 1 { self.lost(mine) }
                return
            }
            if now.timeIntervalSince(self.lastRx) > Self.silenceTimeout { self.lost(mine); return }
            if now.timeIntervalSince(self.lastPing) > Self.pingEvery {
                self.send(RemoteProtocol.ping()); self.lastPing = now
            }
        }
    }

    private func receive(_ mine: Int) {
        conn?.receive(minimumIncompleteLength: 1, maximumLength: 64 * 1024) { [weak self] data, _, done, error in
            guard let self, mine == self.generation else { return }
            if let data, !data.isEmpty {
                self.lastRx = Date()
                self.buffer.append(data)
                self.drainLines()
            }
            if done || error != nil { self.lost(mine); return }
            self.receive(mine)
        }
    }

    private func drainLines() {
        while let nl = buffer.firstIndex(of: 0x0A) {
            var lineData = buffer[buffer.startIndex..<nl]
            if lineData.last == 0x0D { lineData = lineData.dropLast() }
            buffer.removeSubrange(buffer.startIndex...nl)
            guard let line = String(data: lineData, encoding: .utf8) else { continue }
            switch RemoteProtocol.parseLine(line) {
            case .status(let s): listener?.onStatus(key, s)
            case .error(let r, let m): listener?.onError(key, request: r, message: m)
            case .haptics(let u): listener?.onHaptics(key, u)
            default: break
            }
        }
        if buffer.count > 64 * 1024 { buffer.removeAll() }   // a line that long is not one
    }

    private func lost(_ mine: Int) {
        guard running, mine == generation else { return }
        generation += 1
        close()
        listener?.onLinkState(key, .lost)
        reconnectSoon(generation, after: backoff)
        backoff = min(backoff * 2, Self.maxBackoff)
    }

    private func reconnectSoon(_ mine: Int, after: TimeInterval) {
        if after == 0 {
            generation += 1
            close()
        }
        let gen = generation
        DispatchQueue.main.asyncAfter(deadline: .now() + after) { [weak self] in
            guard let self, self.running, gen == self.generation else { return }
            self.open(gen)
        }
    }
}
