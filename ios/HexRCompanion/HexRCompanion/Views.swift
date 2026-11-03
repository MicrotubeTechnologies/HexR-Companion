import SwiftUI

enum Theme {
    static let surface = Color(hex: 0x111214)
    static let raised = Color(hex: 0x17191C)
    static let inset = Color(hex: 0x1C1F23)
    static let border = Color(hex: 0x2A2E34)
    static let text = Color(hex: 0xE9EAEC)
    static let muted = Color(hex: 0x868C94)
    static let faint = Color(hex: 0x6E747C)
    static let accent = Color(hex: 0xF26B21)
    static let success = Color(hex: 0x3ECF8E)
    static let danger = Color(hex: 0xE5484D)
    static let warn = Color(hex: 0xE8B04B)
}

extension Color {
    init(hex: UInt32) {
        self.init(red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255)
    }
}

enum Screen: String, CaseIterable, Identifiable {
    case connect = "Connect", test = "Test", quick = "Quick test"
    var id: String { rawValue }
    var icon: String {
        switch self {
        case .connect: return "antenna.radiowaves.left.and.right"
        case .test: return "hand.raised.fingers.spread"
        case .quick: return "checkmark.seal"
        }
    }
}

struct RootView: View {
    @EnvironmentObject var mgr: GloveManager
    @State private var screen: Screen? = .connect

    var body: some View {
        NavigationSplitView {
            List(Screen.allCases, selection: $screen) { s in
                Label(s.rawValue, systemImage: s.icon).tag(s)
            }
            .navigationTitle("HEXR Companion")
            .safeAreaInset(edge: .bottom) { GloveChips().padding() }
        } detail: {
            ZStack {
                Theme.surface.ignoresSafeArea()
                switch screen ?? .connect {
                case .connect: ConnectView()
                case .test: TestView()
                case .quick: QuickTestView()
                }
            }
        }
        .tint(Theme.accent)
        .preferredColorScheme(.dark)
    }
}

struct GloveChips: View {
    @EnvironmentObject var mgr: GloveManager
    var body: some View {
        HStack(spacing: 8) {
            ForEach(Hand.allCases) { h in
                let g = mgr.gloves[h]
                HStack(spacing: 6) {
                    Circle().fill(g?.connected == true ? Theme.success : Theme.faint).frame(width: 8, height: 8)
                    Text(h.rawValue).font(.footnote.weight(.semibold))
                    if let g, g.connected { Text(g.batteryLabel).font(.footnote).foregroundStyle(Theme.muted) }
                }
                .padding(.horizontal, 10).padding(.vertical, 6)
                .background(Theme.inset, in: Capsule())
            }
            Spacer(minLength: 0)
        }
    }
}

// MARK: - Connect

struct ConnectView: View {
    @EnvironmentObject var mgr: GloveManager

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                header("Connect", "Switch the gloves on, then find them. They do not pair in Settings — this app connects to them itself.")
                HStack {
                    Button {
                        mgr.scanning ? mgr.stopScan() : mgr.scan()
                    } label: {
                        Label(mgr.scanning ? "Stop" : "Find gloves",
                              systemImage: mgr.scanning ? "stop.fill" : "magnifyingglass")
                            .font(.headline).padding(.horizontal, 20).padding(.vertical, 12)
                    }
                    .buttonStyle(.borderedProminent)
                    if mgr.scanning { ProgressView().padding(.leading, 8) }
                    Spacer()
                    if !mgr.connectedGloves.isEmpty {
                        Button("Release all", role: .destructive) { mgr.allOff() }.buttonStyle(.bordered)
                    }
                }
                if let e = mgr.bluetoothError {
                    Text(e).foregroundStyle(Theme.danger)
                }

                HStack(alignment: .top, spacing: 20) {
                    ForEach(Hand.allCases) { h in HandCard(hand: h) }
                }

                if !mgr.found.isEmpty {
                    sectionLabel("Found")
                    VStack(spacing: 0) {
                        ForEach(mgr.found) { f in
                            HStack {
                                Image(systemName: "hand.raised").foregroundStyle(Theme.accent)
                                VStack(alignment: .leading) {
                                    Text(f.name).font(.body.weight(.semibold))
                                    Text("\(f.hand.rawValue) · \(f.rssi) dBm").font(.footnote).foregroundStyle(Theme.muted)
                                }
                                Spacer()
                                let g = mgr.gloves[f.hand]
                                if g?.peripheral.identifier == f.id, g?.connected == true {
                                    Text("Connected").foregroundStyle(Theme.success)
                                } else {
                                    Button("Connect") { mgr.connect(f) }.buttonStyle(.bordered)
                                }
                            }
                            .padding(14)
                            Divider().overlay(Theme.border)
                        }
                    }
                    .background(Theme.raised, in: RoundedRectangle(cornerRadius: 12))
                } else if !mgr.scanning {
                    Text("No gloves found yet.").foregroundStyle(Theme.muted)
                }
            }
            .padding(32)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

struct HandCard: View {
    @EnvironmentObject var mgr: GloveManager
    let hand: Hand
    var body: some View {
        let g = mgr.gloves[hand]
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(hand.rawValue).font(.title2.weight(.bold))
                Spacer()
                Circle().fill(g?.connected == true ? Theme.success : Theme.faint).frame(width: 10, height: 10)
            }
            Text(g?.status ?? "Not connected").foregroundStyle(Theme.muted)
            if let g, g.connected {
                HStack(spacing: 24) {
                    stat("Battery", g.batteryLabel)
                    stat("Source", String(format: "%.1f kPa", g.sourceKPa))
                    stat("Data", g.isLive ? "Live" : "None")
                }
                Button("Disconnect") { mgr.disconnect(hand) }.buttonStyle(.bordered)
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity, minHeight: 170, alignment: .topLeading)
        .background(Theme.raised, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border))
    }

    func stat(_ k: String, _ v: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(k.uppercased()).font(.caption2.weight(.semibold)).foregroundStyle(Theme.faint)
            Text(v).font(.body.monospacedDigit())
        }
    }
}

// MARK: - Test

final class TestSettings: ObservableObject {
    @Published var channels: Set<Finger> = [.index]
    @Published var vibration = false
    @Published var intensity = 0.6
    @Published var speed = 1.0
    @Published var frequency = 10.0
    @Published var peakRatio = 0.5
    @Published var hands: Set<Hand> = [.left, .right]
}

struct TestView: View {
    @EnvironmentObject var mgr: GloveManager
    @StateObject private var s = TestSettings()
    @State private var on = false

    var body: some View {
        GeometryReader { geo in
            let wide = geo.size.width > geo.size.height
            let layout = wide ? AnyLayout(HStackLayout(alignment: .top, spacing: 28))
                              : AnyLayout(VStackLayout(spacing: 24))
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    header("Test", "Tap fingers to pick them, then Trigger. They stay on until Release all.")
                    layout {
                        fingers.frame(maxWidth: .infinity)
                        controls.frame(width: wide ? min(380, geo.size.width * 0.38) : nil)
                    }
                }
                .padding(32)
                .frame(minHeight: geo.size.height, alignment: .top)
            }
        }
        .onDisappear { if on { release() } }
    }

    // One tile per channel: pick it, and see what the glove measures against the target.
    var fingers: some View {
        let target = (!s.vibration || s.frequency < GP.pwmVibrationHz) ? GP.intensityToKPa(s.intensity) : nil
        return VStack(spacing: 14) {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 150), spacing: 14)], spacing: 14) {
                ForEach(Finger.allCases) { f in
                    let picked = s.channels.contains(f)
                    Button {
                        if picked { s.channels.remove(f) } else { s.channels.insert(f) }
                    } label: {
                        VStack(alignment: .leading, spacing: 10) {
                            HStack {
                                Text(f.label).font(.headline)
                                Spacer()
                                Image(systemName: picked ? "checkmark.circle.fill" : "circle")
                                    .foregroundStyle(picked ? Theme.accent : Theme.faint)
                            }
                            ForEach(Hand.allCases) { h in
                                if let g = mgr.gloves[h], g.connected {
                                    PressureBar(label: String(h.rawValue.prefix(1)), kpa: g.kpa(f.rawValue),
                                                target: picked ? target : nil, live: g.isLive)
                                }
                            }
                        }
                        .padding(16)
                        .frame(maxWidth: .infinity, minHeight: 120, alignment: .topLeading)
                        .background(picked ? Theme.accent.opacity(0.12) : Theme.raised,
                                    in: RoundedRectangle(cornerRadius: 14))
                        .overlay(RoundedRectangle(cornerRadius: 14).stroke(picked ? Theme.accent : Theme.border))
                    }
                    .buttonStyle(.plain)
                }
            }
            HStack {
                Button("All") { s.channels = Set(Finger.allCases) }
                Text("·").foregroundStyle(Theme.faint)
                Button("None") { s.channels = [] }
                Spacer()
                ForEach(Hand.allCases) { h in
                    Toggle(h.rawValue, isOn: Binding(get: { s.hands.contains(h) },
                                                     set: { if $0 { s.hands.insert(h) } else { s.hands.remove(h) } }))
                        .toggleStyle(.button)
                }
            }
            if mgr.connectedGloves.isEmpty {
                Text("No glove connected. Go to Connect first.").foregroundStyle(Theme.warn)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    var controls: some View {
        VStack(alignment: .leading, spacing: 22) {
            Picker("Mode", selection: Binding(get: { s.vibration }, set: { v in
                if on && v != s.vibration { release() }
                s.vibration = v
            })) {
                Text("Pressure").tag(false)
                Text("Vibration").tag(true)
            }
            .pickerStyle(.segmented)

            slider("Intensity", $s.intensity, 0.1...1,
                   "\(Int((s.intensity * 100).rounded()))% · \(Int(GP.intensityToKPa(s.intensity).rounded())) kPa")
            if s.vibration {
                slider("Frequency", $s.frequency, 0.1...40,
                       String(format: "%.1f Hz · %@", s.frequency, s.frequency < GP.pwmVibrationHz ? "Pulse" : "Buzz"))
                slider("Peak ratio", $s.peakRatio, 0.2...0.8, "\(Int((s.peakRatio * 100).rounded()))%")
            } else {
                slider("Ramp speed", $s.speed, 0.1...1, "\(Int((s.speed * 100).rounded()))%")
            }

            VStack(spacing: 12) {
                Button { trigger() } label: {
                    Label(on ? "Trigger again" : "Trigger", systemImage: "bolt.fill")
                        .font(.title3.weight(.semibold)).frame(maxWidth: .infinity).padding(.vertical, 14)
                }
                .buttonStyle(.borderedProminent)
                .disabled(s.channels.isEmpty || mgr.connectedGloves.isEmpty)

                Button(role: .destructive) { release() } label: {
                    Label("Release all", systemImage: "stop.fill")
                        .font(.title3.weight(.semibold)).frame(maxWidth: .infinity).padding(.vertical, 14)
                }
                .buttonStyle(.bordered)
            }
            if on { Text("On — fingers stay inflated until released.").font(.footnote).foregroundStyle(Theme.accent) }
        }
        .padding(20)
        .background(Theme.raised, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border))
    }

    func slider(_ name: String, _ v: Binding<Double>, _ r: ClosedRange<Double>, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(name).font(.subheadline.weight(.semibold))
                Spacer()
                Text(value).font(.subheadline.monospacedDigit()).foregroundStyle(Theme.muted)
            }
            Slider(value: v, in: r)
        }
    }

    func trigger() {
        let fingers = Finger.allCases.filter { s.channels.contains($0) }
        let bytes: [UInt8] = fingers.flatMap { f in
            s.vibration ? GP.vibration(f, on: true, frequency: s.frequency, intensity: s.intensity, peakRatio: s.peakRatio)
                        : GP.pressure(f, on: true, intensity: s.intensity, speed: s.speed)
        }
        mgr.send(Array(s.hands), bytes)
        on = true
    }

    func release() {
        mgr.allOff()
        on = false
    }
}

struct PressureBar: View {
    let label: String
    let kpa: Double
    let target: Double?
    let live: Bool
    var body: some View {
        HStack(spacing: 8) {
            Text(label).font(.caption.weight(.bold)).foregroundStyle(Theme.faint).frame(width: 12)
            GeometryReader { g in
                let w = g.size.width
                ZStack(alignment: .leading) {
                    Capsule().fill(Theme.inset)
                    Capsule().fill(Theme.accent).frame(width: w * min(1, max(0, kpa / GP.maxKPa)))
                    if let t = target {
                        Rectangle().fill(.white).frame(width: 2).offset(x: w * min(1, t / GP.maxKPa) - 1)
                    }
                }
            }
            .frame(height: 8)
            Text(live ? String(format: "%.1f", kpa) : "—")
                .font(.caption.monospacedDigit()).foregroundStyle(Theme.muted).frame(width: 40, alignment: .trailing)
        }
    }
}

// MARK: - Quick test

struct QuickTestView: View {
    @EnvironmentObject var mgr: GloveManager
    enum Phase { case idle, settle, drive, done }
    @State private var hand: Hand = .left
    @State private var phase = Phase.idle
    @State private var t0 = Date()
    @State private var peak = [Double](repeating: 0, count: 6)
    @State private var tPeak = [Double](repeating: 0, count: 6)
    @State private var sourcePeak = 0.0
    @State private var status = ""
    @State private var progress = 0.0
    private let timer = Timer.publish(every: 0.05, on: .main, in: .common).autoconnect()

    static let settleS = 0.6, driveS = 2.0, goodKPa = 40.0, failKPa = 2.0, sourceMin = 10.0

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                header("Quick test", "Take the glove off first. Every channel is driven to full pressure for 2 seconds and judged on what it reaches.")
                HStack {
                    Picker("Glove", selection: $hand) {
                        ForEach(Hand.allCases) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented).frame(maxWidth: 260)
                    .disabled(running)
                    Spacer()
                    Button { running ? abort("Stopped") : start() } label: {
                        Label(running ? "Stop" : (phase == .done ? "Run again" : "Run"),
                              systemImage: running ? "stop.fill" : "play.fill")
                            .font(.headline).padding(.horizontal, 24).padding(.vertical, 12)
                    }
                    .buttonStyle(.borderedProminent)
                }
                ProgressView(value: progress).tint(phase == .done ? headlineColour : Theme.accent)
                if !status.isEmpty { Text(status).foregroundStyle(Theme.muted) }

                if phase == .done {
                    Text(headline).font(.system(size: 44, weight: .heavy)).foregroundStyle(headlineColour)
                    Text(summary).foregroundStyle(Theme.muted)
                }

                VStack(spacing: 0) {
                    row("Channel", "Peak", "Time to peak", "Verdict", head: true)
                    ForEach(Finger.allCases) { f in
                        let i = f.rawValue
                        let v = phase == .done ? verdict(peak[i]) : nil
                        row(f.label,
                            phase == .done ? String(format: "%.1f kPa", peak[i]) : "—",
                            phase == .done && peak[i] > 0 ? String(format: "%.2f s", tPeak[i]) : "—",
                            v ?? "—", colour: v.map(colour) ?? Theme.muted)
                    }
                    row("Source", phase == .done ? String(format: "%.1f kPa", sourcePeak) : "—", "", "")
                }
                .background(Theme.raised, in: RoundedRectangle(cornerRadius: 12))
            }
            .padding(32)
        }
        .onReceive(timer) { _ in tick() }
        .onDisappear { if running { abort("Stopped") } }
    }

    var running: Bool { phase == .settle || phase == .drive }

    func row(_ a: String, _ b: String, _ c: String, _ d: String, head: Bool = false,
             colour: Color = Theme.muted) -> some View {
        HStack {
            Text(a).frame(maxWidth: .infinity, alignment: .leading)
            Text(b).frame(maxWidth: .infinity, alignment: .leading)
            Text(c).frame(maxWidth: .infinity, alignment: .leading)
            Text(d).foregroundStyle(head ? Theme.faint : colour).frame(maxWidth: .infinity, alignment: .leading)
        }
        .font(head ? .caption.weight(.semibold) : .body.monospacedDigit())
        .foregroundStyle(head ? Theme.faint : Theme.text)
        .padding(.horizontal, 18).padding(.vertical, head ? 10 : 14)
    }

    func verdict(_ p: Double) -> String { p > Self.goodKPa ? "Good" : p >= Self.failKPa ? "Poor" : "Fail" }
    func colour(_ v: String) -> Color { v == "Good" ? Theme.success : v == "Poor" ? Theme.warn : Theme.danger }

    var counts: (good: Int, poor: Int, fail: Int) {
        let vs = peak.map(verdict)
        return (vs.filter { $0 == "Good" }.count, vs.filter { $0 == "Poor" }.count, vs.filter { $0 == "Fail" }.count)
    }
    var headline: String {
        if sourcePeak < Self.sourceMin { return "Pump failed" }
        let c = counts
        if c.fail > 0 { return "\(c.fail) failed" }
        if c.poor > 0 { return "\(c.poor) poor" }
        return "All good"
    }
    var headlineColour: Color {
        if sourcePeak < Self.sourceMin || counts.fail > 0 { return Theme.danger }
        return counts.poor > 0 ? Theme.warn : Theme.success
    }
    var summary: String {
        let c = counts, kpa = String(format: "%.1f", sourcePeak)
        let breakdown = "\(c.good) good, \(c.poor) poor, \(c.fail) failed"
        let weak = Finger.allCases.filter { verdict(peak[$0.rawValue]) != "Good" }.map(\.label).joined(separator: ", ")
        if sourcePeak < Self.sourceMin {
            return "The source never rose above \(kpa) kPa, so no channel could have reached pressure. This is one fault in the pump or its supply, not six failed channels."
        }
        if c.fail > 0 {
            return "Source reached \(kpa) kPa, so supply is fine — a channel reading nothing with a healthy source is a blocked line, a valve that never opened, or a dead indenter. \(breakdown). Check: \(weak)."
        }
        if c.poor > 0 {
            return "Source reached \(kpa) kPa. Every channel moved, but not all reached full pressure — check the tubing on: \(weak). \(breakdown)."
        }
        return "Source reached \(kpa) kPa."
    }

    func start() {
        guard let g = mgr.gloves[hand], g.connected else { status = "Connect the \(hand.rawValue.lowercased()) glove first"; return }
        guard g.isLive else { status = "No readings from this glove"; return }
        peak = Array(repeating: 0, count: 6); tPeak = peak; sourcePeak = 0
        mgr.send([hand], GP.allOff())
        phase = .settle; t0 = Date(); progress = 0; status = "Venting…"
    }

    func abort(_ why: String) {
        phase = .idle
        mgr.send([hand], GP.allOff())
        progress = 0; status = why
    }

    func tick() {
        guard running else { return }
        guard let g = mgr.gloves[hand], g.connected else { abort("Glove disconnected"); return }
        let el = Date().timeIntervalSince(t0)
        if phase == .settle {
            progress = min(1, el / Self.settleS) * 0.2
            if el >= Self.settleS {
                mgr.send([hand], Finger.allCases.flatMap { GP.pressure($0, on: true, intensity: 1, speed: 1) })
                phase = .drive; t0 = Date(); status = "Driving all channels…"
            }
            return
        }
        progress = 0.2 + min(1, el / Self.driveS) * 0.8
        sourcePeak = max(sourcePeak, g.sourceKPa)
        for f in Finger.allCases {
            let k = g.kpa(f.rawValue)
            if k > peak[f.rawValue] { peak[f.rawValue] = k; tPeak[f.rawValue] = el }
        }
        if el >= Self.driveS {
            mgr.send([hand], GP.allOff())
            phase = .done; status = ""; progress = 1
        }
    }
}

// MARK: - shared

func header(_ title: String, _ sub: String) -> some View {
    VStack(alignment: .leading, spacing: 6) {
        Text(title).font(.largeTitle.weight(.bold))
        Text(sub).foregroundStyle(Theme.muted)
    }
}

func sectionLabel(_ s: String) -> some View {
    Text(s.uppercased()).font(.caption.weight(.semibold)).foregroundStyle(Theme.faint)
}
