// Finds HexR headsets on this iPad's Wi-Fi (Android remote/HeadsetDiscovery.kt).
//
// Headsets broadcast an announcement on UDP 47800 every two seconds. iOS hands broadcast and
// multicast packets only to apps that hold Apple's com.apple.developer.networking.multicast
// entitlement, so the listener here may hear nothing. That is why this also sweeps the Wi-Fi
// subnet: a plain TCP connect to each address on the control port (47801), which needs only the
// Local Network permission. A headset that answers says its id in its welcome or status.
// Typing an address in (Add by address) still works where both are blocked.

import Foundation
import Network
import Darwin

final class HeadsetDiscovery {
    /// (announce or nil, id, host, port, name) — called on the main queue.
    typealias Found = (_ announce: Announce?, _ id: String, _ host: String, _ port: Int, _ name: String) -> Void

    private let onFound: Found
    private var running = false
    private var udpThread: Thread?
    private var udpSocket: Int32 = -1
    private var sweepTimer: Timer?
    private(set) var sweeping = false
    var knownHosts: () -> Set<String> = { [] }

    init(onFound: @escaping Found) { self.onFound = onFound }

    func start() {
        guard !running else { return }
        running = true
        startUDP()
        sweep()
        sweepTimer = Timer.scheduledTimer(withTimeInterval: 20, repeats: true) { [weak self] _ in self?.sweep() }
    }

    func stop() {
        running = false
        sweepTimer?.invalidate(); sweepTimer = nil
        if udpSocket >= 0 { Darwin.close(udpSocket); udpSocket = -1 }
    }

    // MARK: - UDP announcements (works once the multicast entitlement is granted)

    private func startUDP() {
        let s = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
        guard s >= 0 else { return }
        var yes: Int32 = 1
        setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &yes, socklen_t(MemoryLayout<Int32>.size))
        setsockopt(s, SOL_SOCKET, SO_REUSEPORT, &yes, socklen_t(MemoryLayout<Int32>.size))
        setsockopt(s, SOL_SOCKET, SO_BROADCAST, &yes, socklen_t(MemoryLayout<Int32>.size))
        var tv = timeval(tv_sec: 1, tv_usec: 0)
        setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, &tv, socklen_t(MemoryLayout<timeval>.size))
        var addr = sockaddr_in()
        addr.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = RemoteProtocol.discoveryPort.bigEndian
        addr.sin_addr = in_addr(s_addr: INADDR_ANY)
        let ok = withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(s, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) }
        }
        guard ok == 0 else { Darwin.close(s); return }
        udpSocket = s
        let t = Thread { [weak self] in self?.listen(s) }
        t.name = "HexRHeadsetDiscovery"
        udpThread = t
        t.start()
    }

    private func listen(_ s: Int32) {
        var buf = [UInt8](repeating: 0, count: 4096)
        while running && udpSocket == s {
            var from = sockaddr_in()
            var len = socklen_t(MemoryLayout<sockaddr_in>.size)
            let n = withUnsafeMutablePointer(to: &from) {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { recvfrom(s, &buf, buf.count, 0, $0, &len) }
            }
            guard n > 0 else { continue }
            var ip = [CChar](repeating: 0, count: Int(INET_ADDRSTRLEN))
            var a = from.sin_addr
            inet_ntop(AF_INET, &a, &ip, socklen_t(INET_ADDRSTRLEN))
            let host = String(cString: ip)
            guard let text = String(bytes: buf[0..<n], encoding: .utf8),
                  let ann = RemoteProtocol.parseAnnounce(text) else { continue }
            DispatchQueue.main.async { [weak self] in
                self?.onFound(ann, ann.id, host, ann.control, ann.name)
            }
        }
    }

    // MARK: - Subnet sweep

    /// This iPad's Wi-Fi IPv4 address and netmask (en0), as host-order integers.
    static func wifiAddress() -> (UInt32, UInt32)? {
        var ifap: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&ifap) == 0, let first = ifap else { return nil }
        defer { freeifaddrs(ifap) }
        var p: UnsafeMutablePointer<ifaddrs>? = first
        while let i = p {
            defer { p = i.pointee.ifa_next }
            guard String(cString: i.pointee.ifa_name) == "en0", let a = i.pointee.ifa_addr,
                  a.pointee.sa_family == sa_family_t(AF_INET), let m = i.pointee.ifa_netmask else { continue }
            let ip = a.withMemoryRebound(to: sockaddr_in.self, capacity: 1) { UInt32(bigEndian: $0.pointee.sin_addr.s_addr) }
            let mask = m.withMemoryRebound(to: sockaddr_in.self, capacity: 1) { UInt32(bigEndian: $0.pointee.sin_addr.s_addr) }
            return (ip, mask)
        }
        return nil
    }

    private static func dotted(_ v: UInt32) -> String {
        "\(v >> 24 & 0xFF).\(v >> 16 & 0xFF).\(v >> 8 & 0xFF).\(v & 0xFF)"
    }

    func sweep() {
        guard running, !sweeping, let (ip, rawMask) = Self.wifiAddress() else { return }
        // Large networks: just this address's /22, at most 1022 hosts.
        let mask = max(rawMask, 0xFFFF_FC00)
        let net = ip & mask, bcast = net | ~mask
        let known = knownHosts()
        var hosts: [String] = []
        var h = net + 1
        while h < bcast { if h != ip { let d = Self.dotted(h); if !known.contains(d) { hosts.append(d) } }; h += 1 }
        guard !hosts.isEmpty else { return }
        sweeping = true
        var next = 0, inFlight = 0
        let width = 48
        func launch() {
            while running && inFlight < width && next < hosts.count {
                let host = hosts[next]; next += 1; inFlight += 1
                Probe(host: host, port: RemoteProtocol.controlPort) { [weak self] id, name in
                    inFlight -= 1
                    if let id, let self, self.running { self.onFound(nil, id, host, RemoteProtocol.controlPort, name) }
                    if next < hosts.count { launch() } else if inFlight == 0 { self?.sweeping = false }
                }.start()
            }
            if !running { sweeping = false }
        }
        launch()
    }
}

/// One address tried on the control port: connect, say hello, read until an id turns up.
private final class Probe {
    private let host: String, port: Int
    private var conn: NWConnection?
    private var done: ((String?, String) -> Void)?
    private var buffer = Data()
    private var name = ""
    private var retain: Probe?

    init(host: String, port: Int, done: @escaping (String?, String) -> Void) {
        self.host = host; self.port = port; self.done = done
    }

    func start() {
        retain = self
        let tcp = NWProtocolTCP.Options()
        tcp.connectionTimeout = 2
        let params = NWParameters(tls: nil, tcp: tcp)
        params.requiredInterfaceType = .wifi
        let c = NWConnection(host: NWEndpoint.Host(host), port: NWEndpoint.Port(rawValue: UInt16(port))!, using: params)
        conn = c
        c.stateUpdateHandler = { [weak self] st in
            guard let self else { return }
            switch st {
            case .ready:
                c.send(content: Data((RemoteProtocol.hello(HeadsetLink.client) + "\n").utf8), completion: .contentProcessed { _ in })
                self.read()
            case .failed, .cancelled, .waiting: self.finish(nil)
            default: break
            }
        }
        c.start(queue: .main)
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) { [weak self] in self?.finish(nil) }
    }

    private func read() {
        conn?.receive(minimumIncompleteLength: 1, maximumLength: 16 * 1024) { [weak self] data, _, fin, err in
            guard let self else { return }
            if let data { self.buffer.append(data) }
            while let nl = self.buffer.firstIndex(of: 0x0A) {
                let line = String(data: self.buffer[self.buffer.startIndex..<nl], encoding: .utf8) ?? ""
                self.buffer.removeSubrange(self.buffer.startIndex...nl)
                switch RemoteProtocol.parseLine(line) {
                case .welcome(let id, _, _) where !id.isEmpty: self.finish(id); return
                case .status(let s) where !s.id.isEmpty: self.name = s.name; self.finish(s.id); return
                default: break
                }
            }
            if fin || err != nil || self.buffer.count > 64 * 1024 { self.finish(nil); return }
            self.read()
        }
    }

    private func finish(_ id: String?) {
        guard let d = done else { return }
        done = nil
        conn?.stateUpdateHandler = nil
        conn?.cancel()
        conn = nil
        d(id, name)
        retain = nil
    }
}
