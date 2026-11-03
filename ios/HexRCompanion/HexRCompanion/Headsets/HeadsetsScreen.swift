// The Headsets tab: the HexR headsets on this Wi-Fi, and one of them live (Android ui/HeadsetsScreen.kt).
// For running a demo: the facilitator stands beside someone in a headset, connects their gloves
// from here, and watches what they see. The gloves are the headset's, so no Bluetooth is used.

import SwiftUI

struct HeadsetsScreen: View {
    @EnvironmentObject var headsets: HeadsetsModel
    @EnvironmentObject var i18n: I18n
    /// Hands this iPad itself holds on the Test tab: a headset cannot reach those gloves.
    var phoneGloves: Set<Hand> = []
    /// Told when a headset opens and closes, so the shell can give it the whole screen.
    var onImmersive: (Bool) -> Void = { _ in }

    var body: some View {
        Group {
            if let key = headsets.selected, let row = headsets.rows.first(where: { $0.key == key }) {
                HeadsetLiveView(row: row, phoneGloves: phoneGloves) { headsets.select(nil) }
                    .id(row.key)
            } else {
                HeadsetList()
            }
        }
        .background(T.screen.ignoresSafeArea())
        .onAppear { headsets.setVisible(true) }
        .onDisappear { headsets.setVisible(false); onImmersive(false) }
        .onChange(of: headsets.selected) { _, s in onImmersive(s != nil) }
    }
}

// MARK: - The list

private struct HeadsetList: View {
    @EnvironmentObject var headsets: HeadsetsModel

    var body: some View {
        GeometryReader { geo in
            let cols = geo.size.width > 900 ? 3 : geo.size.width > 560 ? 2 : 1
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    HStack(alignment: .firstTextBaseline) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(tr("Headsets")).font(.system(size: FS.title, weight: .bold)).foregroundStyle(T.text)
                            Text(tr("Same Wi-Fi as this iPad."))
                                .font(.system(size: FS.body)).foregroundStyle(T.text2)
                        }
                        Spacer()
                        Button { headsets.searchAgain() } label: {
                            Label(tr("Search again"), systemImage: "arrow.clockwise")
                                .font(.system(size: FS.control, weight: .semibold))
                        }
                        .buttonStyle(HSButton(style: .ghost, height: 40))
                        .disabled(headsets.searching)
                    }
                    .padding(.bottom, 6)

                    if headsets.rows.isEmpty {
                        HSCard {
                            VStack(alignment: .leading, spacing: 6) {
                                SearchingText(word: tr("Searching for headsets"))
                                    .font(.system(size: FS.body, weight: .semibold)).foregroundStyle(T.text)
                                Text(tr("Start a HexR app on a headset on this Wi-Fi."))
                                    .font(.system(size: FS.caption)).foregroundStyle(T.text2)
                                Text(tr("If it does not show up, add it by its address below."))
                                    .font(.system(size: FS.caption)).foregroundStyle(T.text4)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(18)
                        }
                    } else {
                        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 12), count: cols), spacing: 12) {
                            ForEach(headsets.rows) { row in
                                HeadsetCard(row: row) { headsets.select(row.key) }
                            }
                        }
                    }

                    AddByAddress()
                        .frame(maxWidth: 560, alignment: .leading)
                        .padding(.top, 6)
                }
                .padding(.horizontal, 24).padding(.vertical, 20)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .scrollDismissesKeyboard(.interactively)
        }
    }
}

/// One headset: its name and app, a word for its state, and its two gloves.
private struct HeadsetCard: View {
    let row: HeadsetRow
    let onOpen: () -> Void

    var body: some View {
        let (word, dot) = listWord(row)
        Button(action: onOpen) {
            HStack(spacing: 10) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(row.title).font(.system(size: 17, weight: .semibold)).foregroundStyle(T.text).lineLimit(1)
                    Text(appLine(row)).font(.system(size: FS.caption)).foregroundStyle(T.text4).lineLimit(1)
                    if let s = row.status {
                        HStack(spacing: 8) {
                            GloveChip(letter: "L", glove: s.glove(.left))
                            GloveChip(letter: "R", glove: s.glove(.right))
                        }
                        .padding(.top, 4)
                    }
                }
                Spacer(minLength: 8)
                StateChip(word: word, dot: dot)
                Image(systemName: "chevron.right").font(.system(size: 14, weight: .semibold)).foregroundStyle(T.text4)
            }
            .padding(.leading, 16).padding(.trailing, 12).padding(.vertical, 14)
            .frame(maxWidth: .infinity, minHeight: 84, alignment: .leading)
            .background(T.card, in: RoundedRectangle(cornerRadius: T.rCtrl))
            .overlay(RoundedRectangle(cornerRadius: T.rCtrl).stroke(T.border))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

/// "L ●  85%": a hand, a dot for its state, and its battery once connected.
private struct GloveChip: View {
    let letter: String
    let glove: GloveState?
    var body: some View {
        let colour: Color = {
            guard let g = glove, !g.missing else { return T.textFaint }
            if g.connected { return T.green }
            if g.connecting { return T.accent }
            return T.text5
        }()
        HStack(spacing: 5) {
            Text(letter).font(.system(size: 12, weight: .bold)).foregroundStyle(T.text2)
            Circle().fill(colour).frame(width: 7, height: 7)
            if let g = glove, g.connected, g.batteryPct >= 0 {
                Text("\(g.batteryPct)%").font(T.mono(12)).foregroundStyle(g.batteryPct < 20 ? T.amber : T.text2)
            }
        }
        .padding(.horizontal, 8).padding(.vertical, 4)
        .background(T.elevated, in: RoundedRectangle(cornerRadius: T.rChip))
    }
}

/// For venue Wi-Fi that hides devices from each other: the headset's address, typed in.
private struct AddByAddress: View {
    @EnvironmentObject var headsets: HeadsetsModel
    @State private var open = false
    @State private var address = ""
    @State private var wrong = false
    @FocusState private var focused: Bool

    var body: some View {
        if !open {
            Button { open = true; focused = true } label: {
                Text("+  " + tr("Add by address")).font(.system(size: FS.body, weight: .semibold)).foregroundStyle(T.text3)
            }
            .buttonStyle(.plain)
        } else {
            HSCard {
                VStack(alignment: .leading, spacing: 10) {
                    Text(tr("Add by address")).font(.system(size: FS.body, weight: .semibold)).foregroundStyle(T.text)
                    Text(tr("On the headset: Settings › Wi-Fi › the network shows its IP address."))
                        .font(.system(size: FS.caption)).foregroundStyle(T.text2)
                    TextField("", text: $address, prompt: Text("192.168.1.20").foregroundColor(T.text5))
                        .keyboardType(.numbersAndPunctuation)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .focused($focused)
                        .submitLabel(.done)
                        .onSubmit(add)
                        .onChange(of: address) { _, _ in wrong = false }
                        .font(T.mono(16))
                        .foregroundStyle(T.text)
                        .padding(.horizontal, 12).frame(height: 46)
                        .background(T.elevated, in: RoundedRectangle(cornerRadius: T.rCtrl))
                        .overlay(RoundedRectangle(cornerRadius: T.rCtrl).stroke(wrong ? T.red : (focused ? T.accent : T.border)))
                    if wrong {
                        Text(tr("That is not an address.")).font(.system(size: FS.caption)).foregroundStyle(T.red)
                    }
                    HStack(spacing: 10) {
                        Button(tr("Cancel")) { open = false; wrong = false }
                            .buttonStyle(HSButton(style: .ghost))
                        Button(tr("Add"), action: add)
                            .buttonStyle(HSButton(style: .primary))
                            .disabled(address.trimmingCharacters(in: .whitespaces).isEmpty)
                    }
                }
                .padding(16)
            }
        }
    }

    private func add() {
        if let key = headsets.addByAddress(address) {
            address = ""; open = false; wrong = false
            headsets.select(key)
        } else {
            wrong = true
        }
    }
}

/// The list's word for a headset: connecting, offline, asleep, live, ready.
func listWord(_ row: HeadsetRow) -> (String, Color?) {
    if row.link == .connecting && row.status == nil { return (tr("Connecting…"), T.accent) }
    if row.link != .connected { return (tr("Offline"), T.red) }
    if row.status?.paused == true { return (tr("Asleep"), nil) }
    if row.status?.stream.live == true { return (tr("Live"), T.green) }
    return (tr("Ready"), T.green)
}

/// The app on the headset, and its scene: "HexR Demo · Lab".
func appLine(_ row: HeadsetRow) -> String {
    let app = row.status?.app ?? row.announce?.app ?? tr("HexR headset")
    if let scene = row.status?.scene.name, !scene.isEmpty { return "\(app) · \(scene)" }
    return app
}

// MARK: - Small shared pieces for the Headsets screens

struct HSCard<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        content
            .background(T.card, in: RoundedRectangle(cornerRadius: T.rCtrl))
            .overlay(RoundedRectangle(cornerRadius: T.rCtrl).stroke(T.border))
    }
}

/// A word and a dot for a state.
struct StateChip: View {
    let word: String
    let dot: Color?
    var body: some View {
        HStack(spacing: 6) {
            if let dot { Circle().fill(dot).frame(width: 7, height: 7) }
            Text(word).font(.system(size: FS.micro, weight: .semibold)).foregroundStyle(dot ?? T.text2).lineLimit(1)
        }
        .padding(.horizontal, 10).padding(.vertical, 5)
        .background(T.elevated, in: Capsule())
        .overlay(Capsule().stroke(T.borderSoft))
    }
}

/// "Searching" with dots that come and go.
struct SearchingText: View {
    let word: String
    var body: some View {
        TimelineView(.periodic(from: .now, by: 0.45)) { tl in
            let dots = Int(tl.date.timeIntervalSinceReferenceDate / 0.45) % 4
            Text(word + String(repeating: ".", count: dots) + String(repeating: " ", count: 3 - dots))
        }
    }
}

struct HSButton: ButtonStyle {
    enum Style { case primary, ghost, dangerOutline }
    var style: Style
    var height: CGFloat = 48
    @Environment(\.isEnabled) private var enabled

    func makeBody(configuration: Configuration) -> some View {
        let fg: Color, bg: Color, stroke: Color
        switch style {
        case .primary: fg = T.onAccent; bg = T.accent; stroke = .clear
        case .ghost: fg = T.text; bg = T.card; stroke = T.border
        case .dangerOutline: fg = T.red; bg = T.card; stroke = T.red.opacity(0.6)
        }
        return configuration.label
            .font(.system(size: FS.action, weight: .semibold))
            .lineLimit(1).minimumScaleFactor(0.7)
            .foregroundStyle(enabled ? fg : T.text5)
            .padding(.horizontal, 14)
            .frame(maxWidth: .infinity, minHeight: height, maxHeight: height)
            .background(enabled ? bg : T.card.opacity(0.6), in: RoundedRectangle(cornerRadius: T.rCtrl))
            .overlay(RoundedRectangle(cornerRadius: T.rCtrl).stroke(enabled ? stroke : T.borderSoft))
            .opacity(configuration.isPressed ? 0.75 : 1)
            .contentShape(Rectangle())
    }
}
