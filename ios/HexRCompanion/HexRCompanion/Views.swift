// The app's frame and its glove screens, ported from the Android app (MainActivity.kt,
// ui/ConnectScreen.kt, ui/TestScreen.kt, ui/QuickTestScreen.kt, ui/PressureList.kt, ui/Controls.kt)
// and laid out for an iPad: every screen fills the room it has, in both orientations.

import SwiftUI

enum Tab: String, CaseIterable { case test = "Test", headsets = "Headsets" }
enum Panel: String, Identifiable { case gloves = "Gloves", quickTest = "Quick test"; var id: String { rawValue } }

let guideURL = URL(string: "https://github.com/MicrotubeTechnologies/HexR-Companion/blob/android-headsets/android/USER-GUIDE.md")!
let privacyURL = URL(string: "https://microtubetechnologies.github.io/HexR-Companion/privacy.html")!

struct RootView: View {
    @EnvironmentObject var vm: GloveManager
    @EnvironmentObject var i18n: I18n
    @State private var tab = Tab.test
    @State private var panel: Panel?
    @State private var immersive = false
    @State private var splash = true
    @State private var splashFading = false

    var body: some View {
        ZStack {
            T.screen.ignoresSafeArea()
            if vm.bluetoothDenied {
                PermissionGate()
            } else {
                VStack(spacing: 0) {
                    if !immersive {
                        Header(onGloves: { if vm.anyConnected || tab != .test { panel = .gloves } })
                    }
                    ZStack {
                        switch tab {
                        case .test:
                            if vm.anyConnected { TestScreen(onQuickTest: { panel = .quickTest }) }
                            else { ConnectScreen(panel: false) }
                        case .headsets:
                            HeadsetsTab(phoneGloves: Set(Hand.allCases.filter { vm.handConnected($0) }),
                                        immersive: $immersive)
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    if !immersive { BottomBar(tab: tab) { picked in
                        // Leaving the Test tab leaves the only Release all: the drive ends with it.
                        if picked != .test && vm.driving { vm.release() }
                        tab = picked
                    } }
                }
            }
            if splash {
                Splash().opacity(splashFading ? 0 : 1).animation(.easeOut(duration: 0.4), value: splashFading)
            }
        }
        .id(i18n.language)   // a language change redraws every screen at once
        .fullScreenCover(item: $panel, onDismiss: {
            if vm.quickTestRunning { vm.toggleQuickTest() }
        }) { p in
            PanelSheet(title: tr(p.rawValue), onClose: {
                if p == .quickTest && vm.quickTestRunning { vm.toggleQuickTest() }
                panel = nil
            }) {
                switch p {
                case .gloves: ConnectScreen(panel: true)
                case .quickTest: QuickTestScreen()
                }
            }
            .environmentObject(vm)
            .environmentObject(i18n)
        }
        .preferredColorScheme(.dark)
        .tint(T.accent)
        .task {
            try? await Task.sleep(nanoseconds: 1_600_000_000)
            splashFading = true
            try? await Task.sleep(nanoseconds: 400_000_000)
            splash = false
        }
    }
}

// MARK: - Frame

struct HexMark: View {
    var stroke: CGFloat = 2
    var body: some View {
        Canvas { ctx, size in
            let c = CGPoint(x: size.width / 2, y: size.height / 2)
            ctx.stroke(hexagon(c, size.width * 0.4583), with: .color(T.accent),
                       style: StrokeStyle(lineWidth: stroke, lineJoin: .round))
            ctx.fill(hexagon(c, size.width * 0.1833), with: .color(T.accent))
        }
    }
}

func hexagon(_ c: CGPoint, _ r: CGFloat) -> Path {
    var p = Path()
    for i in 0..<6 {
        let a = (60.0 * Double(i) - 90) * .pi / 180
        let pt = CGPoint(x: c.x + r * cos(a), y: c.y + r * sin(a))
        if i == 0 { p.move(to: pt) } else { p.addLine(to: pt) }
    }
    p.closeSubpath()
    return p
}

struct Header: View {
    @EnvironmentObject var vm: GloveManager
    @EnvironmentObject var i18n: I18n
    @Environment(\.openURL) private var openURL
    let onGloves: () -> Void

    func dot(_ h: Hand) -> Color {
        guard let g = vm.glove(h) else { return T.textFaint }
        return g.connected ? T.green : g.connecting ? T.accent : T.textFaint
    }

    var body: some View {
        let lowest = Hand.allCases.compactMap { vm.glove($0).flatMap { $0.connected ? $0.battery : nil } }.min()
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                HexMark(stroke: 1.8).frame(width: 26, height: 26)
                (Text("HEXR").font(.system(size: 20, weight: .heavy)).foregroundColor(T.accent).tracking(0.5)
                 + Text(" Companion").font(.system(size: 20)).foregroundColor(T.text))
                Spacer()
                Button(action: onGloves) {
                    HStack(spacing: 10) {
                        Image(systemName: "dot.radiowaves.left.and.right").font(.system(size: 14)).foregroundStyle(T.text)
                        handDot("L", dot(.left))
                        handDot("R", dot(.right))
                        if let b = lowest {
                            Text("\(Int((b * 100).rounded()))%").font(T.mono(FS.body2))
                                .foregroundStyle(b < 0.2 ? T.amber : T.text2)
                        }
                    }
                    .padding(.horizontal, 14).frame(minHeight: 44)
                    .background(T.card, in: RoundedRectangle(cornerRadius: T.rCtrl))
                    .overlay(RoundedRectangle(cornerRadius: T.rCtrl).stroke(T.borderSoft))
                }
                .buttonStyle(.plain)
                .accessibilityLabel(tr("Gloves"))
                Menu {
                    Picker("", selection: $i18n.language) {
                        Text("English").tag(I18n.en)
                        Text("中文").tag(I18n.zh)
                    }
                    Divider()
                    Button(tr("Help")) { openURL(guideURL) }
                    Button(tr("Privacy policy")) { openURL(privacyURL) }
                } label: {
                    Image(systemName: "ellipsis").rotationEffect(.degrees(90)).font(.system(size: 18, weight: .semibold))
                        .foregroundStyle(T.text2).frame(width: 48, height: 48)
                }
                .accessibilityLabel(tr("More"))
            }
            .padding(.leading, 20).padding(.trailing, 8).padding(.vertical, 6)
            Rectangle().fill(T.borderSoft).frame(height: 1)
        }
        .background(T.screen)
    }

    func handDot(_ l: String, _ c: Color) -> some View {
        HStack(spacing: 4) {
            Text(l).font(.system(size: FS.body2, weight: .bold)).foregroundStyle(T.text)
            Circle().fill(c).frame(width: 8, height: 8)
        }
    }
}

struct BottomBar: View {
    let tab: Tab
    let onPick: (Tab) -> Void
    var body: some View {
        VStack(spacing: 0) {
            Rectangle().fill(T.borderSoft).frame(height: 1)
            HStack {
                ForEach(Tab.allCases, id: \.self) { t in
                    let tint = t == tab ? T.accent : T.text4
                    Button { onPick(t) } label: {
                        HStack(spacing: 8) {
                            TabGlyph(tab: t, tint: tint).frame(width: 22, height: 22)
                            Text(tr(t.rawValue)).font(.system(size: FS.body2, weight: .semibold)).foregroundStyle(tint)
                        }
                        .frame(maxWidth: .infinity, minHeight: 52)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 16).padding(.vertical, 4)
        }
        .background(T.screen)
    }
}

struct TabGlyph: View {
    let tab: Tab
    let tint: Color
    var body: some View {
        Canvas { ctx, size in
            let u = size.width / 20
            switch tab {
            case .test:
                var p = Path()
                p.move(to: CGPoint(x: 3 * u, y: 13 * u)); p.addLine(to: CGPoint(x: 10 * u, y: 6 * u))
                p.addLine(to: CGPoint(x: 17 * u, y: 13 * u))
                ctx.stroke(p, with: .color(tint), style: StrokeStyle(lineWidth: 1.8 * u, lineCap: .round, lineJoin: .round))
            case .headsets:
                ctx.stroke(Path(roundedRect: CGRect(x: 2.5 * u, y: 6 * u, width: 15 * u, height: 8.5 * u), cornerRadius: 3 * u),
                           with: .color(tint), style: StrokeStyle(lineWidth: 1.6 * u, lineCap: .round, lineJoin: .round))
                for x in [7.0, 13.0] {
                    let c = CGPoint(x: x * u, y: 10.2 * u), r = 1.6 * u
                    ctx.fill(Path(ellipseIn: CGRect(x: c.x - r, y: c.y - r, width: 2 * r, height: 2 * r)), with: .color(tint))
                }
            }
        }
    }
}

struct PanelSheet<Content: View>: View {
    let title: String
    let onClose: () -> Void
    @ViewBuilder let content: Content
    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(title).font(.system(size: FS.title, weight: .bold)).foregroundStyle(T.text)
                Spacer()
                Button(action: onClose) {
                    Image(systemName: "xmark").font(.system(size: 15, weight: .semibold)).foregroundStyle(T.text)
                        .frame(width: 40, height: 40)
                        .background(T.card, in: RoundedRectangle(cornerRadius: T.rCard))
                        .overlay(RoundedRectangle(cornerRadius: T.rCard).stroke(T.border))
                }
                .buttonStyle(.plain)
                .accessibilityLabel(tr("Close"))
            }
            .padding(.horizontal, 20).padding(.top, 8).padding(.bottom, 10)
            Rectangle().fill(T.borderSoft).frame(height: 1)
            content.frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .background(T.screen.ignoresSafeArea())
        .preferredColorScheme(.dark)
    }
}

struct Splash: View {
    @State private var spin = false
    @State private var pulse = false
    var body: some View {
        VStack(spacing: 0) {
            ZStack {
                Canvas { ctx, size in
                    ctx.stroke(hexagon(CGPoint(x: size.width / 2, y: size.height / 2), size.width * 0.455),
                               with: .color(T.accent), style: StrokeStyle(lineWidth: 2, lineJoin: .round, dash: [20, 67]))
                }
                .frame(width: 96, height: 96)
                .rotationEffect(.degrees(spin ? 360 : 0))
                .animation(.linear(duration: 2.6).repeatForever(autoreverses: false), value: spin)
                HexMark(stroke: 3).frame(width: 64, height: 64)
                    .scaleEffect(pulse ? 1.06 : 0.94)
                    .animation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true), value: pulse)
            }
            Spacer().frame(height: 24)
            (Text("HEXR").font(.system(size: 30, weight: .heavy)).foregroundColor(T.accent).tracking(1.6)
             + Text(" Companion").font(.system(size: 30)).foregroundColor(T.text))
            Spacer().frame(height: 8)
            Text("BY MICROTUBE TECHNOLOGIES").font(.system(size: 12, weight: .semibold)).tracking(1.5).foregroundStyle(T.text3)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(T.screen.ignoresSafeArea())
        .onAppear { spin = true; pulse = true }
    }
}

/// The whole app, behind the Bluetooth grant: every screen here needs it.
struct PermissionGate: View {
    var body: some View {
        VStack(spacing: 0) {
            HexMark(stroke: 2.8).frame(width: 56, height: 56)
            Spacer().frame(height: 24)
            Text(tr("Bluetooth access needed")).font(.system(size: FS.title, weight: .bold)).foregroundStyle(T.text)
            Spacer().frame(height: 10)
            Text(tr("HEXR Companion talks to the glove over Bluetooth, so it needs permission to find and connect to nearby devices."))
                .font(.system(size: FS.body)).foregroundStyle(T.text2).multilineTextAlignment(.center)
            Spacer().frame(height: 28)
            ActionButton(label: tr("Open app settings")) {
                if let u = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(u) }
            }
            .frame(maxWidth: 420)
        }
        .padding(32)
        .frame(maxWidth: 560)
    }
}

// MARK: - Controls (ui/Controls.kt)

enum ActionStyle { case primary, danger, dangerOutline, ghost }

struct ActionButton: View {
    let label: String
    var sub: String? = nil
    var style = ActionStyle.primary
    var enabled = true
    var height: CGFloat = 64
    let action: () -> Void

    var body: some View {
        let (fill, fg, border): (Color, Color, Color) = {
            switch style {
            case .primary: return (T.accent, T.onAccent, T.accent)
            case .danger: return (T.red, .white, T.red)
            case .dangerOutline: return (T.card, T.red, T.red)
            case .ghost: return (T.card, T.text, T.border)
            }
        }()
        Button {
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
            action()
        } label: {
            VStack(spacing: 2) {
                Text(label).font(.system(size: 17, weight: .bold)).lineLimit(1)
                if let sub { Text(sub).font(.system(size: 13)).opacity(0.75).lineLimit(1) }
            }
            .foregroundStyle(fg)
            .padding(.horizontal, 14)
            .frame(maxWidth: .infinity, minHeight: height)
            .background(fill, in: RoundedRectangle(cornerRadius: T.rCtrl))
            .overlay(RoundedRectangle(cornerRadius: T.rCtrl).stroke(border))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .opacity(enabled ? 1 : 0.4)
    }
}

struct Segmented<K: Hashable>: View {
    let options: [(K, String)]
    let selected: K
    let onPick: (K) -> Void
    var body: some View {
        HStack(spacing: 0) {
            ForEach(options, id: \.0) { key, label in
                let on = key == selected
                Button {
                    UISelectionFeedbackGenerator().selectionChanged()
                    onPick(key)
                } label: {
                    Text(label).font(.system(size: 16, weight: .semibold)).lineLimit(1)
                        .foregroundStyle(on ? T.accent : T.text2)
                        .frame(maxWidth: .infinity, minHeight: 44)
                        .background(on ? T.elevated2 : .clear, in: RoundedRectangle(cornerRadius: T.rChip))
                        .overlay(RoundedRectangle(cornerRadius: T.rChip).stroke(on ? T.accent : .clear))
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .disabled(on)
            }
        }
        .padding(3)
        .background(T.card, in: RoundedRectangle(cornerRadius: T.rCtrl))
    }
}

struct ValueSlider<Trailing: View>: View {
    let label: String
    let value: String
    let position: Double
    let onChange: (Double) -> Void
    @ViewBuilder var trailing: Trailing

    var body: some View {
        VStack(spacing: 4) {
            HStack(spacing: 10) {
                Text(label).font(.system(size: 15)).foregroundStyle(T.text2)
                Spacer()
                trailing
                Text(value).font(T.mono(15, .semibold)).foregroundStyle(T.text)
            }
            Slider(value: Binding(get: { position }, set: onChange), in: 0...1)
                .tint(T.accent)
                .frame(minHeight: 44)
        }
    }
}

extension ValueSlider where Trailing == EmptyView {
    init(label: String, value: String, position: Double, onChange: @escaping (Double) -> Void) {
        self.init(label: label, value: value, position: position, onChange: onChange) { EmptyView() }
    }
}

struct TextLink: View {
    let text: String
    var colour: Color = T.text2
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            Text(text).font(.system(size: 15, weight: .semibold)).foregroundStyle(colour)
                .padding(.horizontal, 10).frame(minHeight: 44).contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

struct Disclosure<Content: View>: View {
    let title: String
    @Binding var expanded: Bool
    @ViewBuilder var content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Button { expanded.toggle() } label: {
                HStack(spacing: 8) {
                    Text(expanded ? "−" : "+").font(.system(size: 15, weight: .bold)).foregroundStyle(T.text3).frame(width: 12)
                    SectionLabel(title)
                    Spacer()
                }
                .padding(.vertical, 12).contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            if expanded { content }
        }
    }
}

struct CardBox<Content: View>: View {
    var fill: Color = T.card
    @ViewBuilder var content: Content
    var body: some View {
        content
            .background(fill, in: RoundedRectangle(cornerRadius: T.rCtrl))
            .overlay(RoundedRectangle(cornerRadius: T.rCtrl).stroke(T.border))
    }
}

struct StickyActionBar<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        VStack(spacing: 0) {
            Rectangle().fill(T.hairline).frame(height: 1)
            HStack(spacing: 12) { content }.padding(.horizontal, 20).padding(.vertical, 10)
        }
        .background(T.screen)
    }
}

struct TickBox: View {
    let on: Bool
    var body: some View {
        ZStack {
            if on {
                RoundedRectangle(cornerRadius: 5).fill(T.accent)
                Image(systemName: "checkmark").font(.system(size: 13, weight: .heavy)).foregroundStyle(T.onAccent)
            } else {
                RoundedRectangle(cornerRadius: 5).stroke(T.text4, lineWidth: 1.6)
            }
        }
        .frame(width: 24, height: 24)
    }
}

struct ProgressBar: View {
    let fraction: Double
    var colour: Color = T.accent
    var body: some View {
        GeometryReader { g in
            ZStack(alignment: .leading) {
                Capsule().fill(T.card)
                Capsule().fill(colour).frame(width: g.size.width * min(1, max(0, fraction)))
            }
        }
        .frame(height: 6)
        .animation(.linear(duration: 0.1), value: fraction)
    }
}

struct MonoText: View {
    let text: String
    var colour: Color = T.text4
    var size: CGFloat = 13
    init(_ text: String, colour: Color = T.text4, size: CGFloat = 13) { self.text = text; self.colour = colour; self.size = size }
    var body: some View { Text(text).font(T.mono(size)).foregroundStyle(colour).textSelection(.enabled) }
}

/// "Searching", with dots that count up, at a fixed width.
struct SearchingWord: View {
    var word = tr("Searching")
    var body: some View {
        TimelineView(.periodic(from: .now, by: 0.45)) { tl in
            let dots = Int(tl.date.timeIntervalSinceReferenceDate / 0.45) % 4
            Text(word + String(repeating: ".", count: dots) + String(repeating: " ", count: 3 - dots))
        }
    }
}

extension Verdict {
    var colour: Color { self == .good ? T.green : self == .poor ? T.amber : T.red }
}

// MARK: - Connect (ui/ConnectScreen.kt)

/// The Test tab until a glove connects, and the Gloves panel after. It searches by itself while
/// on screen: no Scan button. Under each glove, one word for where it is and one button.
struct ConnectScreen: View {
    @EnvironmentObject var vm: GloveManager
    let panel: Bool
    @State private var details = false

    var body: some View {
        GeometryReader { geo in
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    if !panel {
                        Text(tr("Connect a glove")).font(.system(size: FS.title, weight: .bold)).foregroundStyle(T.text)
                        Spacer().frame(height: 4)
                        Text(tr("Switch on the arm module.")).font(.system(size: 16)).foregroundStyle(T.text2)
                        Spacer().frame(height: 16)
                    }
                    if !vm.bluetoothOn && vm.bluetoothState != .unknown {
                        CardBox {
                            Text(tr("Bluetooth is off.")).font(.system(size: 16, weight: .semibold)).foregroundStyle(T.text)
                                .padding(16).frame(maxWidth: .infinity, alignment: .leading)
                        }
                        Spacer().frame(height: 16)
                    }
                    // The two gloves take most of the screen; the list below gets what is left.
                    let gloveH = max(260, geo.size.height * (panel ? 0.58 : 0.55))
                    HStack(alignment: .top, spacing: 16) {
                        ForEach(Hand.allCases) { h in Slot(hand: h, panel: panel, height: gloveH) }
                    }
                    FoundList()
                    Spacer().frame(height: 20)
                    Disclosure(title: tr("Details"), expanded: $details) {
                        VStack(alignment: .leading, spacing: 6) {
                            ForEach(Hand.allCases) { h in
                                if let g = vm.glove(h) {
                                    MonoText("\(tr(h.rawValue))  \(g.address)  \(g.status)")
                                    if g.connected {
                                        MonoText("   " + tr("battery {level}", ("level", g.batteryLabel)) + "   "
                                                 + tr("source {kpa} kPa", ("kpa", String(format: "%.1f", g.sourceKPa)))
                                                 + "   MTU \(g.mtu.map(String.init) ?? "?")")
                                    }
                                }
                                ForEach(vm.candidates(h)) { f in
                                    MonoText("\(tr(h.rawValue))  \(f.address)  \(f.rssi.map(String.init) ?? "?") dBm")
                                }
                            }
                            MonoText("v\(Bundle.main.version)   bluetooth \(vm.bluetoothOn ? "yes" : "no")   searching \(vm.scanning ? "yes" : "no")",
                                     colour: T.textFaint, size: 12)
                        }
                    }
                }
                .padding(.horizontal, 24).padding(.vertical, 20)
                .frame(minHeight: geo.size.height, alignment: .top)
            }
        }
        .onAppear { vm.setConnectVisible(true) }
        .onDisappear { vm.setConnectVisible(false) }
    }
}

private struct Slot: View {
    @EnvironmentObject var vm: GloveManager
    let hand: Hand
    let panel: Bool
    let height: CGFloat

    var body: some View {
        let g = vm.glove(hand)
        let heard = vm.candidates(hand)
        let connected = g?.connected == true, connecting = g?.connecting == true
        let dim = connected ? 1 : connecting ? 0.7 : !heard.isEmpty ? 0.6 : 0.3
        VStack(spacing: 8) {
            GloveArtView(hand: hand, look: .connect,
                         state: connectState(connected: connected, kpa: g?.isLive == true ? g?.channelKPa : nil), dim: dim)
                .frame(height: height)
                .animation(.easeInOut(duration: 0.3), value: dim)
                .accessibilityLabel(tr(hand.rawValue))
            Text(tr(hand.rawValue)).font(.system(size: 19, weight: .semibold)).foregroundStyle(T.text)
            HStack(spacing: 6) {
                let (word, dot) = statusWord(g, heard, connected, connecting)
                Circle().fill(dot).frame(width: 8, height: 8)
                word.font(.system(size: 15)).foregroundStyle(T.text2).lineLimit(1).truncationMode(.tail)
                if !connected && !connecting, let f = heard.first {
                    SignalBars(bars: GloveSearch.signalBars(f.rssi))
                }
            }
            .frame(minHeight: 24)
            Group {
                if connected && panel {
                    ActionButton(label: tr("Disconnect"), style: .ghost, height: 48) { vm.disconnect(hand) }
                } else if connected {
                    Color.clear.frame(height: 48)
                } else if connecting {
                    ActionButton(label: tr("Connecting…"), enabled: false, height: 48) {}
                } else if vm.scanError != nil && heard.isEmpty {
                    ActionButton(label: tr("Try again"), style: .ghost, height: 48) { vm.retryScan() }
                } else if !heard.isEmpty {
                    ConnectButton(heard: heard)
                } else {
                    Color.clear.frame(height: 48)
                }
            }
            .frame(maxWidth: 220)
        }
        .frame(maxWidth: .infinity)
    }

    func statusWord(_ g: Glove?, _ heard: [Found], _ connected: Bool, _ connecting: Bool) -> (AnyView, Color) {
        let name = { (a: String) in " · " + GloveNames.name(for: a) }
        if connected, let g {
            let batt = g.batteryLabel != "—" ? " · \(g.batteryLabel)" : ""
            return (AnyView(Text(tr("Connected") + name(g.address) + batt)), (g.battery ?? 1) < 0.2 ? T.amber : T.green)
        }
        if connecting, let g { return (AnyView(Text(tr("Connecting…") + name(g.address))), T.accent) }
        if !vm.bluetoothOn || vm.scanError != nil { return (AnyView(Text(tr("Bluetooth unavailable"))), T.red) }
        if g?.failed == true && heard.isEmpty { return (AnyView(Text(tr("Could not connect"))), T.red) }
        if !heard.isEmpty { return (AnyView(Text(tr("Found") + (heard.count == 1 ? name(heard[0].address) : ""))), T.green) }
        return (AnyView(SearchingWord().fixedSize()), T.text5)
    }
}

/// Connect, or with two kits of one hand about, a choice between them, strongest first.
private struct ConnectButton: View {
    @EnvironmentObject var vm: GloveManager
    let heard: [Found]
    var body: some View {
        if heard.count == 1 {
            ActionButton(label: tr("Connect"), height: 48) { vm.connect(heard[0]) }
        } else {
            Menu {
                ForEach(heard) { f in
                    Button("\(GloveNames.name(for: f.address))   \(String(repeating: "▮", count: GloveSearch.signalBars(f.rssi)))") {
                        vm.connect(f)
                    }
                }
            } label: {
                Text(tr("Connect")).font(.system(size: 17, weight: .bold)).foregroundStyle(T.onAccent)
                    .frame(maxWidth: .infinity, minHeight: 48)
                    .background(T.accent, in: RoundedRectangle(cornerRadius: T.rCtrl))
            }
        }
    }
}

/// Every glove found, for testing one after another: the ones connected here first, then the
/// rest nearest first. Test swaps that hand over to the glove.
private struct FoundList: View {
    @EnvironmentObject var vm: GloveManager
    var body: some View {
        let here = Hand.allCases.compactMap { h in vm.glove(h).flatMap { $0.connected || $0.connecting ? (h, $0) : nil } }
        let hereIDs = Set(here.map { $0.1.peripheral.identifier })
        let others = vm.allFound().filter { !hereIDs.contains($0.id) }
        if !here.isEmpty || !others.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                Spacer().frame(height: 12)
                SectionLabel(tr("Gloves found"))
                VStack(spacing: 0) {
                    ForEach(here, id: \.0) { h, g in
                        row(GloveNames.name(for: g.address), h, nil) {
                            Text(g.connected ? "✓ " + tr("Connected") : tr("Connecting…"))
                                .font(.system(size: 15, weight: .semibold)).foregroundStyle(g.connected ? T.green : T.text2)
                        }
                    }
                    ForEach(others) { f in
                        row(GloveNames.name(for: f.address), f.hand, f.rssi) {
                            if vm.swapping == nil { TextLink(text: tr("Test"), colour: T.accent) { vm.test(f) } }
                            else if vm.swapping == f.id { Text(tr("Connecting…")).font(.system(size: 15)).foregroundStyle(T.text2) }
                        }
                    }
                }
                .padding(.horizontal, 16).padding(.vertical, 4)
                .background(T.card, in: RoundedRectangle(cornerRadius: T.rCtrl))
                .overlay(RoundedRectangle(cornerRadius: T.rCtrl).stroke(T.border))
            }
        }
    }

    func row<Trailing: View>(_ name: String, _ hand: Hand, _ rssi: Int?, @ViewBuilder _ trailing: () -> Trailing) -> some View {
        HStack(spacing: 12) {
            SignalBars(bars: GloveSearch.signalBars(rssi))
            Text(name).font(.system(size: 16, weight: .semibold)).foregroundStyle(T.text).lineLimit(1)
            Text(tr(hand.rawValue)).font(.system(size: 15)).foregroundStyle(T.text2)
            Spacer()
            trailing()
        }
        .frame(minHeight: 52)
    }
}

extension Bundle {
    var version: String {
        let v = infoDictionary?["CFBundleShortVersionString"] as? String ?? "?"
        let b = infoDictionary?["CFBundleVersion"] as? String ?? "?"
        return "\(v) (\(b))"
    }
}

// MARK: - Test (ui/TestScreen.kt)

/// Pick fingers, Trigger them, Release all. The glove is the screen: tap a fingertip to pick it,
/// or tick it in the list, where each finger shows its pressure against where it is set to go.
struct TestScreen: View {
    @EnvironmentObject var vm: GloveManager
    let onQuickTest: () -> Void

    var body: some View {
        GeometryReader { geo in
            if geo.size.width > geo.size.height {
                // Landscape: the glove fills the left; the controls take a column of their own.
                HStack(spacing: 0) {
                    VStack(spacing: 8) {
                        TestGlove().frame(maxHeight: .infinity)
                        SelectRow()
                    }
                    .padding(20)
                    .frame(maxWidth: .infinity)
                    Rectangle().fill(T.hairline).frame(width: 1)
                    VStack(spacing: 0) {
                        ScrollView {
                            VStack(spacing: 16) {
                                TopRow(onQuickTest: onQuickTest)
                                SettingsCard()
                                FingersList()
                                TestDetails()
                            }
                            .padding(20)
                        }
                        StickyActionBar { TestButtons() }
                    }
                    .frame(width: min(440, geo.size.width * 0.42))
                }
            } else {
                // Portrait: the glove across the top, settings and the pressure list side by side.
                VStack(spacing: 0) {
                    ScrollView {
                        VStack(spacing: 16) {
                            TopRow(onQuickTest: onQuickTest)
                            TestGlove().frame(height: geo.size.height * 0.46)
                            SelectRow()
                            HStack(alignment: .top, spacing: 20) {
                                SettingsCard().frame(maxWidth: .infinity)
                                VStack(spacing: 8) { FingersList(); TestDetails() }.frame(maxWidth: .infinity)
                            }
                        }
                        .padding(20)
                    }
                    StickyActionBar { TestButtons() }
                }
            }
        }
    }
}

private struct TopRow: View {
    @EnvironmentObject var vm: GloveManager
    let onQuickTest: () -> Void
    var body: some View {
        HStack(spacing: 10) {
            if vm.handConnected(.left) && vm.handConnected(.right) {
                Segmented(options: Hand.allCases.map { ($0, "\(tr($0.rawValue)) · \(vm.glove($0)?.batteryLabel ?? "—")") },
                          selected: vm.hand, onPick: vm.pickHand)
            } else {
                let g = vm.glove(vm.hand)
                let b = g.map { $0.batteryLabel != "—" ? " · \($0.batteryLabel)" : "" } ?? ""
                Text(tr("{hand} glove", ("hand", tr(vm.hand.rawValue))) + b)
                    .font(.system(size: 16, weight: .semibold)).foregroundStyle(T.text2)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            ActionButton(label: tr("Quick test"), style: .ghost, height: 48, action: onQuickTest).fixedSize()
        }
    }
}

private struct TestGlove: View {
    @EnvironmentObject var vm: GloveManager
    var body: some View {
        let g = vm.glove(vm.hand), s = vm.settings, now = Date()
        let st = padState(kpa: g?.isLive == true ? g?.channelKPa : nil, on: vm.driving,
                          sincePress: Float(now.timeIntervalSince(vm.pressedAt)),
                          sinceRelease: vm.releasedAt.map { Float(now.timeIntervalSince($0)) },
                          vibration: s.mode == .vibration, intensity: Float(s.intensity), hz: Float(s.frequency),
                          channels: vm.channels)
        GloveArtView(hand: vm.hand, look: .test, state: st, selected: vm.channels, onTap: vm.toggleChannel)
            .frame(maxWidth: .infinity)
            .accessibilityLabel(tr("{hand} glove", ("hand", tr(vm.hand.rawValue))))
    }
}

private struct SelectRow: View {
    @EnvironmentObject var vm: GloveManager
    var body: some View {
        HStack(spacing: 0) {
            Text(vm.channels.isEmpty ? tr("Pick a finger") : "").font(.system(size: 15)).foregroundStyle(T.text4)
            Spacer()
            TextLink(text: tr("All"), action: vm.selectAll)
            Text("·").foregroundStyle(T.text5)
            TextLink(text: tr("None"), action: vm.selectNone)
        }
    }
}

private struct SettingsCard: View {
    @EnvironmentObject var vm: GloveManager
    @State private var fine = false
    var body: some View {
        let s = vm.settings
        CardBox(fill: T.elevated) {
            VStack(spacing: 8) {
                Segmented(options: [(Mode.pressure, tr("Pressure")), (Mode.vibration, tr("Vibration"))],
                          selected: s.mode, onPick: vm.pickMode)
                Spacer().frame(height: 4)
                ValueSlider(label: tr("Intensity"), value: s.intensityLabel, position: (s.intensity - 0.1) / 0.9) {
                    vm.setIntensity(0.1 + $0 * 0.9)
                }
                if s.mode == .vibration {
                    ValueSlider(label: tr("Frequency"), value: s.frequencyLabel, position: TestSettings.hzToSlider(s.frequency),
                                onChange: { vm.setFrequency(TestSettings.sliderToHz($0)) }) {
                        Text(s.pulse ? tr("Pulse") : tr("Buzz")).font(.system(size: 15, weight: .semibold)).foregroundStyle(T.accent)
                    }
                }
                Disclosure(title: tr("Fine-tune"), expanded: $fine) {
                    if s.mode == .pressure {
                        ValueSlider(label: tr("Ramp speed"), value: TestSettings.percent(s.speed), position: (s.speed - 0.1) / 0.9) {
                            vm.setSpeed(0.1 + $0 * 0.9)
                        }
                    } else {
                        ValueSlider(label: tr("Peak ratio"), value: TestSettings.percent(s.peakRatio), position: (s.peakRatio - 0.2) / 0.6) {
                            vm.setPeakRatio(0.2 + $0 * 0.6)
                        }
                    }
                }
            }
            .padding(16)
        }
    }
}

private struct FingersList: View {
    @EnvironmentObject var vm: GloveManager
    var body: some View {
        let g = vm.glove(vm.hand), live = g?.isLive == true
        PressureList(kpa: live ? g?.channelKPa : nil, source: live ? g?.sourceKPa : nil, picked: vm.channels,
                     targetKPa: vm.settings.targetKPa, title: tr("Air pressure"), note: live ? nil : tr("No readings"),
                     onToggle: vm.toggleChannel)
    }
}

private struct TestDetails: View {
    @EnvironmentObject var vm: GloveManager
    @State private var open = false
    var body: some View {
        if let g = vm.glove(vm.hand) {
            Disclosure(title: tr("Details"), expanded: $open) {
                VStack(alignment: .leading, spacing: 6) {
                    MonoText("\(GloveNames.name(for: g.address))  \(g.address)", colour: T.text3)
                    MonoText(tr("battery {level}", ("level", g.batteryLabel)) + "   MTU \(g.mtu.map(String.init) ?? "?")"
                             + (g.isLive ? "   " + tr("source {kpa} kPa", ("kpa", String(format: "%.1f", g.sourceKPa))) : ""),
                             colour: T.text3)
                    if g.absolutePa == true {
                        caption(tr("This glove reports absolute pressure; readings are converted to gauge kPa."))
                    }
                    if vm.settings.mode == .vibration {
                        let hz = String(Int(GP.pwmVibrationHz))
                        caption(vm.settings.pulse
                                ? tr("Under {hz} Hz the glove vibrates pneumatically: the pressure target is pulsed.", ("hz", hz))
                                : tr("At {hz} Hz and above the pressure loop is off and the channel's motor is driven directly.", ("hz", hz)))
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }
    func caption(_ s: String) -> some View { Text(s).font(.system(size: FS.caption)).foregroundStyle(T.text4) }
}

private struct TestButtons: View {
    @EnvironmentObject var vm: GloveManager
    var body: some View {
        let s = vm.settings, n = vm.channels.count
        ActionButton(label: tr("Trigger"),
                     sub: n == 0 ? tr("Pick a finger")
                        : tr("{n} fingers", ("n", n)) + " · " + (s.mode == .pressure ? TestSettings.percent(s.intensity) : s.frequencyLabel),
                     enabled: vm.canDrive, action: vm.trigger)
        ActionButton(label: tr("Release all"), style: vm.driving ? .danger : .ghost, action: vm.release)
    }
}

// MARK: - Pressure list (ui/PressureList.kt)

private let scaleKPa = 55.0

struct PressureList: View {
    let kpa: [Double]?
    let source: Double?
    let picked: Set<Int>
    let targetKPa: Double?
    var title: String? = nil
    var note: String? = nil
    let onToggle: (Int) -> Void

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(title ?? "").font(.system(size: 15, weight: .semibold)).foregroundStyle(T.text2)
                Spacer()
                if let note { Text(note).font(.system(size: 14)).foregroundStyle(T.text5) } else { legend }
            }
            .padding(.bottom, 4)
            ForEach(Finger.allCases) { f in
                let ch = f.rawValue, on = picked.contains(ch)
                Button { onToggle(ch) } label: {
                    HStack(spacing: 12) {
                        TickBox(on: on)
                        Text(tr(f.label)).font(.system(size: 16, weight: on ? .semibold : .regular))
                            .foregroundStyle(on ? T.text : T.text2).frame(width: 80, alignment: .leading).lineLimit(1)
                        bar(kpa.flatMap { ch < $0.count ? $0[ch] : nil }, on ? T.accent : T.text4, on ? targetKPa : nil)
                        value(kpa.flatMap { ch < $0.count ? $0[ch] : nil }, bright: on)
                    }
                    .frame(minHeight: 48).contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(on ? .isSelected : [])
            }
            Rectangle().fill(T.borderSoft).frame(height: 1).padding(.vertical, 4)
            HStack(spacing: 12) {
                Color.clear.frame(width: 24)
                Text(tr("Air supply")).font(.system(size: 16)).foregroundStyle(T.text3).frame(width: 80, alignment: .leading).lineLimit(1)
                bar(source, T.text2, nil)
                value(source, bright: false)
            }
            .frame(minHeight: 40)
        }
    }

    func bar(_ k: Double?, _ colour: Color, _ target: Double?) -> some View {
        GeometryReader { g in
            let w = g.size.width
            ZStack(alignment: .leading) {
                Capsule().fill(T.borderStrong).frame(height: 8)
                if let k, k > 0.5 { Capsule().fill(colour).frame(width: max(8, w * min(1, k / scaleKPa)), height: 8) }
                if let t = target { Rectangle().fill(.white).frame(width: 2, height: 18).offset(x: w * min(1, t / scaleKPa) - 1) }
            }
            .frame(height: g.size.height)
        }
        .frame(height: 18)
        .padding(.horizontal, 4)
    }

    func value(_ k: Double?, bright: Bool) -> some View {
        Text(k.map { "\(Int($0.rounded())) kPa" } ?? "—").font(T.mono(15)).foregroundStyle(bright ? T.text : T.text3)
            .frame(minWidth: 70, alignment: .trailing)
    }

    var legend: some View {
        HStack(spacing: 6) {
            Capsule().fill(T.accent).frame(width: 14, height: 8)
            Text(tr("Now")).font(.system(size: 14)).foregroundStyle(T.text5)
            Spacer().frame(width: 6)
            Rectangle().fill(.white).frame(width: 2, height: 14)
            Text(tr("Set to")).font(.system(size: 14)).foregroundStyle(T.text5)
        }
    }
}

// MARK: - Quick test (ui/QuickTestScreen.kt)

/// Is this glove healthy? One button, one answer, shown on the glove.
struct QuickTestScreen: View {
    @EnvironmentObject var vm: GloveManager
    @State private var details = false

    var body: some View {
        let running = vm.quickTestRunning
        let hand = vm.qtHand
        let g = hand.flatMap { vm.glove($0) }
        let result = vm.qtPhase == .done ? vm.qtResult : nil
        GeometryReader { geo in
            let side = geo.size.width > geo.size.height
            VStack(spacing: 0) {
                if side {
                    HStack(spacing: 0) {
                        VStack(spacing: 12) { picker(hand); glove(hand, g, result, running).frame(maxHeight: .infinity) }
                            .padding(20).frame(maxWidth: .infinity)
                        ScrollView { VStack(alignment: .leading, spacing: 14) { hint; answer(result, running) }.padding(20) }
                            .frame(maxWidth: .infinity)
                    }
                } else {
                    ScrollView {
                        VStack(spacing: 14) {
                            hint
                            picker(hand)
                            glove(hand, g, result, running).frame(height: geo.size.height * 0.5)
                            answer(result, running)
                        }
                        .padding(20)
                    }
                }
                StickyActionBar {
                    ActionButton(label: running ? "■  " + tr("Stop") : result != nil ? "▶  " + tr("Run again") : "▶  " + tr("Run"),
                                 style: running ? .dangerOutline : .primary, enabled: g?.connected == true,
                                 action: vm.toggleQuickTest)
                }
            }
        }
    }

    var hint: some View {
        Text(tr("Take the glove off first.")).font(.system(size: 16)).foregroundStyle(T.text2)
            .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder func picker(_ hand: Hand?) -> some View {
        if vm.handConnected(.left) && vm.handConnected(.right), let hand {
            Segmented(options: Hand.allCases.map { ($0, tr($0.rawValue)) }, selected: hand, onPick: vm.pickQuickTestHand)
                .frame(maxWidth: 480)
        }
    }

    @ViewBuilder func glove(_ hand: Hand?, _ g: Glove?, _ result: Judgement?, _ running: Bool) -> some View {
        if let hand {
            let st: HandState = {
                if let r = result { return verdictState(r.verdicts, pumpFailed: r.outcome == .pumpFailed) }
                if running, let g, g.isLive { return HandState(levels: g.channelKPa.map(levelFromKPa)) }
                return HandState()
            }()
            GloveArtView(hand: hand, look: .quick, state: st)
                .accessibilityLabel(tr("{hand} glove", ("hand", tr(hand.rawValue))))
        }
    }

    @ViewBuilder func answer(_ result: Judgement?, _ running: Bool) -> some View {
        if let r = result {
            Text(r.headline).font(.system(size: 34, weight: .heavy)).foregroundStyle(r.verdict.colour)
                .frame(maxWidth: .infinity, alignment: .leading)
            if !r.weak.isEmpty {
                Text(r.weak.compactMap { Finger(rawValue: $0).map { tr($0.label) } }.joined(separator: ", "))
                    .font(.system(size: 18)).foregroundStyle(T.text2).frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        if running || vm.qtProgress > 0 { ProgressBar(fraction: vm.qtProgress, colour: result?.verdict.colour ?? T.accent) }
        if !vm.qtStatus.isEmpty {
            Text(vm.qtStatus).font(.system(size: 15)).foregroundStyle(T.text3).frame(maxWidth: .infinity, alignment: .leading)
        }
        if let r = result {
            Disclosure(title: tr("Details"), expanded: $details) { evidence(r) }
        }
    }

    func evidence(_ r: Judgement) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            CardBox {
                VStack(spacing: 0) {
                    HStack {
                        SectionLabel(tr("Channel")).frame(maxWidth: .infinity, alignment: .leading)
                        SectionLabel(tr("Peak")).frame(width: 90, alignment: .leading)
                        SectionLabel(tr("Time")).frame(width: 80, alignment: .leading)
                        SectionLabel(tr("Verdict")).frame(width: 80, alignment: .leading)
                    }
                    .frame(minHeight: 36)
                    ForEach(Finger.allCases) { f in
                        let ch = f.rawValue, v = r.verdicts[ch]
                        HStack {
                            Text(tr(f.label)).font(.system(size: 15)).foregroundStyle(T.text).frame(maxWidth: .infinity, alignment: .leading)
                            Text(String(format: "%.1f", vm.qtPeaks[ch])).font(T.mono(15)).foregroundStyle(T.text).frame(width: 90, alignment: .leading)
                            Text(vm.qtPeaks[ch] > 0 ? String(format: "%.2f s", vm.qtTimes[ch]) : "—").font(T.mono(15))
                                .foregroundStyle(T.text2).frame(width: 80, alignment: .leading)
                            Text(tr(v.rawValue)).font(.system(size: 15, weight: .semibold)).foregroundStyle(v.colour)
                                .frame(width: 80, alignment: .leading)
                        }
                        .frame(minHeight: 44)
                    }
                }
                .padding(.horizontal, 14).padding(.vertical, 8)
            }
            Text(QuickTest.summary(r, vm.qtSource)).font(.system(size: 14)).foregroundStyle(T.text3)
            Text(tr("Good above {good} kPa, poor from {fail} kPa, failed under {fail} kPa.",
                    ("good", Int(QuickTest.goodKPa)), ("fail", Int(QuickTest.failKPa))))
                .font(.system(size: 14)).foregroundStyle(T.text5)
        }
    }
}
