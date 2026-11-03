// One headset, live (Android ui/HeadsetLive.kt): what the wearer sees, and their two gloves beside
// it, lighting up as they are touched. Upright, the view runs across the top with the gloves under
// it and the controls in a bar along the bottom. Sideways, the view takes three quarters of the
// width, the gloves the last quarter, and the controls float over the view, fading once it
// plays; a tap brings them back. Tap a glove's panel to connect it; a connected one asks first.

import SwiftUI

private let gap: CGFloat = 10
private let head: CGFloat = 30
private let pad: CGFloat = 12
private let recenteredS = 3.0

/// A word for the state beside the title, and the sentence in the view while there is no view.
private struct LiveLook { let word: String; let dot: Color?; let say: String }

private func liveLook(_ row: HeadsetRow, _ video: VideoPlayer.VideoState?) -> LiveLook {
    guard let s = row.status else { return LiveLook(word: tr("Connecting…"), dot: T.accent, say: tr("Connecting to the headset…")) }
    let st = s.stream
    if row.link != .connected { return LiveLook(word: tr("Offline"), dot: T.red, say: tr("Reconnecting…")) }
    if s.paused && !st.live { return LiveLook(word: tr("Asleep"), dot: T.accent, say: tr("Asleep. Put the headset on.")) }
    if !s.allowVideo { return LiveLook(word: tr("No view"), dot: nil, say: tr("This app does not share its view.")) }
    switch video {
    case .failed(let m)?: return LiveLook(word: tr("Failed"), dot: T.red, say: m)
    case .playing?: return LiveLook(word: tr("Live"), dot: T.green, say: "")
    case .connecting?: return LiveLook(word: tr("Live"), dot: T.green, say: tr("Connecting to the view…"))
    case nil: break
    }
    switch st.state {
    case "requesting": return LiveLook(word: tr("Waiting"), dot: T.accent, say: tr("Waiting for the wearer…"))
    case "denied": return LiveLook(word: tr("Declined"), dot: T.red, say: tr("The wearer said no."))
    case "unsupported": return LiveLook(word: tr("No view"), dot: nil, say: tr("This headset cannot share its view."))
    case "error": return LiveLook(word: tr("Failed"), dot: T.red, say: tr("Sharing failed."))
    default:
        if st.live { return LiveLook(word: tr("Shared"), dot: T.green, say: tr("Watch to see what they see.")) }
        return LiveLook(word: tr("Off"), dot: nil, say: tr("Watch asks the wearer to share."))
    }
}

struct HeadsetLiveView: View {
    @EnvironmentObject var headsets: HeadsetsModel
    let row: HeadsetRow
    let phoneGloves: Set<Hand>
    let onLeave: () -> Void

    @StateObject private var video = CastVideo()
    @State private var note: String?
    @State private var showGloves = false
    @State private var controls = true
    @State private var renaming = false
    @State private var nickname = ""
    @State private var details = false
    @State private var hideTask: Task<Void, Never>?

    private var s: HeadsetStatus? { row.status }
    private var stream: StreamState { s?.stream ?? StreamState() }
    private var connected: Bool { row.link == .connected && s != nil }
    private var playView: Bool { row.watching && stream.live && headsets.online }
    private var canWatch: Bool { connected && s!.allowVideo && stream.state != "unsupported" && !(s!.paused && !stream.live) }
    private var canControl: Bool { connected && s!.allowGloveControl && !s!.paused }
    private var anyGlove: Bool { s?.gloves.contains { $0.connected } ?? false }
    private var recenterWhyNot: String? {
        if !connected { return tr("Reconnecting…") }
        if !s!.allowRecenter { return tr("Needs HexR 0.10.6 with Allow Recenter.") }
        if s!.paused { return tr("Asleep. Put the headset on.") }
        return nil
    }
    private var timeline: HapticsTimeline { headsets.timeline(row.key) ?? HapticsTimeline() }

    var body: some View {
        GeometryReader { geo in
            let landscape = geo.size.width > geo.size.height
            let look = liveLook(row, playView ? video.state : nil)
            VStack(spacing: 0) {
                if !landscape { topBar(look) }
                GeometryReader { stage in
                    let boxes = castBoxes(stage.size, landscape)
                    ZStack(alignment: .topLeading) {
                        viewBox(look).frame(width: boxes.view.width, height: boxes.view.height)
                            .offset(x: boxes.view.minX, y: boxes.view.minY)
                        GlovePanel(hand: .left, row: row, timeline: timeline, video: video, canControl: canControl)
                            .frame(width: boxes.left.width, height: boxes.left.height)
                            .offset(x: boxes.left.minX, y: boxes.left.minY)
                        GlovePanel(hand: .right, row: row, timeline: timeline, video: video, canControl: canControl)
                            .frame(width: boxes.right.width, height: boxes.right.height)
                            .offset(x: boxes.right.minX, y: boxes.right.minY)
                        if landscape {
                            overlay(look)
                                .frame(width: boxes.view.width, height: boxes.view.height)
                                .offset(x: boxes.view.minX, y: boxes.view.minY)
                                .opacity(controls || !video.playing ? 1 : 0)
                                .allowsHitTesting(controls || !video.playing)
                                .animation(.easeInOut(duration: 0.25), value: controls)
                        }
                    }
                    .frame(width: stage.size.width, height: stage.size.height, alignment: .topLeading)
                }
                if !landscape {
                    if let (text, tone) = footnote() {
                        Text(text).font(.system(size: FS.caption)).foregroundStyle(tone)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, 20).padding(.vertical, 8)
                    }
                    actionBar
                }
            }
            .onChange(of: video.playing) { _, _ in scheduleHide(landscape) }
            .onChange(of: landscape) { _, l in controls = true; scheduleHide(l) }
        }
        .background(T.screen.ignoresSafeArea())
        .onAppear { syncVideo() }
        .onChange(of: playView) { _, _ in syncVideo() }
        .onChange(of: stream.port) { _, _ in syncVideo() }
        .onChange(of: row.host) { _, _ in syncVideo() }
        .onChange(of: video.state) { _, st in
            // Dropped while the share goes on: join again after a moment.
            if case .failed = st {
                Task { try? await Task.sleep(for: .seconds(3)); if playView { video.rejoin() } }
            }
        }
        .onChange(of: note) { _, n in
            guard n != nil else { return }
            Task { try? await Task.sleep(for: .seconds(4)); note = nil }
        }
        .onDisappear { video.release() }
        .sheet(isPresented: $showGloves) { GlovesSheet(rowKey: row.key) }
        .alert(tr("Rename"), isPresented: $renaming) {
            TextField(tr("Station 1"), text: $nickname)
            Button(tr("Cancel"), role: .cancel) {}
            Button(tr("Done")) { headsets.rename(row.key, nickname) }
        }
        .sheet(isPresented: $details) { DetailsSheet(row: row) }
    }

    private func syncVideo() {
        if playView { video.start(host: row.host, port: stream.port) } else { video.release() }
    }

    private func leave() {
        headsets.stopWatching(row.key, joined: video.joined)
        onLeave()
    }

    private func scheduleHide(_ landscape: Bool) {
        hideTask?.cancel()
        guard landscape, controls, video.playing else { return }
        hideTask = Task { @MainActor in
            try? await Task.sleep(for: .seconds(4))
            if !Task.isCancelled { controls = false }
        }
    }

    private func footnote() -> (String, Color)? {
        if let e = row.error { return (e, T.red) }
        if let n = note { return (n, T.text2) }
        if let s, s.allowGloveControl,
           Hand.allCases.contains(where: { phoneGloves.contains($0) && s.glove($0)?.connected != true }) {
            return (tr("This iPad has a glove for this hand; disconnect it on the Test tab first."), T.amber)
        }
        if let s, !s.allowGloveControl { return (tr("This app does not let a phone connect its gloves."), T.text5) }
        if video.playing && !timeline.exact {
            return (tr("The glove shows the pressure the gloves measure. Update this app to HexR 0.10.2 or newer to show every touch and vibration as it is sent."), T.text5)
        }
        return nil
    }

    private func castBoxes(_ size: CGSize, _ landscape: Bool) -> CastLayout.Boxes {
        if landscape {
            let b = CastLayout.landscape(size.width - gap * 2, size.height - gap * 2, gap: gap, head: head, pad: pad)
            return CastLayout.Boxes(view: b.view.offsetBy(dx: gap, dy: gap), left: b.left.offsetBy(dx: gap, dy: gap),
                                    right: b.right.offsetBy(dx: gap, dy: gap))
        }
        let aspect: CGFloat = stream.width > 0 && stream.height > 0 ? CGFloat(stream.width) / CGFloat(stream.height) : 1
        let minPanels = head + pad * 2 + 160 * panelSize(1, .cast).height
        let b = CastLayout.portrait(size.width - gap * 2, size.height - gap, aspect: aspect, gap: gap,
                                    minPanels: minPanels, head: head, pad: pad)
        return CastLayout.Boxes(view: b.view.offsetBy(dx: gap, dy: 0), left: b.left.offsetBy(dx: gap, dy: 0),
                                right: b.right.offsetBy(dx: gap, dy: 0))
    }

    // MARK: - the view

    private func viewBox(_ look: LiveLook) -> some View {
        ZStack {
            RoundedRectangle(cornerRadius: T.rCard).fill(T.card)
            if playView {
                HeadsetVideoView(video: video, videoW: playingSize.0, videoH: playingSize.1)
                    .clipShape(RoundedRectangle(cornerRadius: T.rCard))
            }
            if !(playView && video.playing) && !look.say.isEmpty {
                Text(look.say).font(.system(size: FS.body)).foregroundStyle(T.text2)
                    .multilineTextAlignment(.center).padding(24)
            }
        }
        .contentShape(Rectangle())
        .onTapGesture {
            if video.playing { controls.toggle(); if controls { scheduleHide(true) } }
            else if !row.watching && canWatch { headsets.watch(row.key) }
            else { controls = true }
        }
    }

    private var playingSize: (Int, Int) {
        if case .playing(let w, let h)? = video.state { return (w, h) }
        return (stream.width, stream.height)
    }

    // MARK: - header and controls

    private func topBar(_ look: LiveLook) -> some View {
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                Button(action: leave) {
                    Image(systemName: "chevron.left").font(.system(size: 18, weight: .semibold)).foregroundStyle(T.text)
                        .frame(width: 44, height: 44)
                }
                .accessibilityLabel(tr("Back"))
                VStack(alignment: .leading, spacing: 2) {
                    Text(row.title).font(.system(size: 17, weight: .semibold)).foregroundStyle(T.text).lineLimit(1)
                    Text(appLine(row)).font(.system(size: FS.caption)).foregroundStyle(T.text4).lineLimit(1)
                }
                Spacer()
                StateChip(word: look.word, dot: look.dot)
                moreMenu
            }
            .padding(.horizontal, 8).frame(minHeight: 60)
            Rectangle().fill(T.hairline).frame(height: 1)
        }
    }

    private var moreMenu: some View {
        Menu {
            Button(tr("Rename")) { nickname = row.nickname; renaming = true }
            Button(tr("Details")) { details = true }
            if row.manual { Button(tr("Forget"), role: .destructive) { headsets.forget(row.key) } }
        } label: {
            Image(systemName: "ellipsis").font(.system(size: 18, weight: .semibold)).foregroundStyle(T.text2)
                .frame(width: 44, height: 44).rotationEffect(.degrees(90))
        }
        .accessibilityLabel(tr("More"))
    }

    private var actionBar: some View {
        VStack(spacing: 0) {
            Rectangle().fill(T.hairline).frame(height: 1)
            HStack(spacing: 10) {
                watchButton.frame(maxWidth: .infinity).layoutPriority(1.3)
                glovesButton
                releaseButton
                triggerButton
                recenterButton
            }
            .padding(.horizontal, 16).padding(.vertical, 12)
        }
        .background(T.screen)
    }

    private func overlay(_ look: LiveLook) -> some View {
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                Button(action: leave) {
                    Image(systemName: "chevron.left").font(.system(size: 18, weight: .semibold)).foregroundStyle(T.text)
                        .frame(width: 44, height: 44)
                }
                Text(row.title).font(.system(size: 16, weight: .semibold)).foregroundStyle(T.text).lineLimit(1)
                Spacer()
                StateChip(word: look.word, dot: look.dot)
                moreMenu
            }
            .padding(6)
            .background(LinearGradient(colors: [.black.opacity(0.7), .clear], startPoint: .top, endPoint: .bottom))
            Spacer(minLength: 0).allowsHitTesting(false)
            VStack(alignment: .leading, spacing: 8) {
                if let (text, tone) = footnote() {
                    Text(text).font(.system(size: FS.caption)).foregroundStyle(tone)
                }
                HStack(spacing: 8) {
                    watchButton.layoutPriority(1.3)
                    glovesButton
                    releaseButton
                    triggerButton
                    recenterButton
                }
            }
            .padding(.horizontal, 12).padding(.vertical, 10)
            .background(LinearGradient(colors: [.clear, .black.opacity(0.75)], startPoint: .top, endPoint: .bottom))
        }
        .clipShape(RoundedRectangle(cornerRadius: T.rCard))
    }

    private var watchButton: some View {
        Button {
            if row.watching { headsets.stopWatching(row.key, joined: video.joined) } else { headsets.watch(row.key) }
        } label: {
            Label(row.watching ? tr("Stop watching") : tr("Watch"), systemImage: row.watching ? "stop.fill" : "play.fill")
        }
        .buttonStyle(HSButton(style: row.watching ? .dangerOutline : .primary))
        .disabled(!(row.watching || canWatch))
    }

    private var glovesButton: some View {
        Button(tr("Gloves")) { showGloves = true }
            .buttonStyle(HSButton(style: .ghost)).disabled(!connected)
    }

    private var releaseButton: some View {
        Button(tr("Release all")) { headsets.release(row.key) }
            .buttonStyle(HSButton(style: .ghost)).disabled(!(canControl && anyGlove))
    }

    /// Every channel of the connected gloves pressed for a second: does the glove work?
    private var triggerButton: some View {
        Button(tr("Trigger all")) { headsets.trigger(row.key) }
            .buttonStyle(HSButton(style: .ghost)).disabled(!(canControl && s?.gloveSearch != nil && anyGlove))
    }

    private var recenterButton: some View {
        let recentered = row.recenteredAt > 0 && nowS() - row.recenteredAt < recenteredS && row.error == nil
        // Disabled-looking but still tappable, so a tap can say why not.
        return Button {
            if let why = recenterWhyNot { note = why } else { headsets.recenter(row.key) }
        } label: {
            Text(recentered ? "✓  " + tr("Recenter") : tr("Recenter"))
                .foregroundStyle(recenterWhyNot == nil ? T.text : T.text5)
        }
        .buttonStyle(HSButton(style: .ghost))
    }
}

// MARK: - one glove's panel

/// One glove: its hand, whether the headset has it and its battery, and the glove itself, lit with
/// what the frame on screen shows the wearer feeling.
private struct GlovePanel: View {
    @EnvironmentObject var headsets: HeadsetsModel
    let hand: Hand
    let row: HeadsetRow
    let timeline: HapticsTimeline
    @ObservedObject var video: CastVideo
    let canControl: Bool
    @State private var confirm = false

    var body: some View {
        let glove = row.status?.glove(hand)
        let connected = glove?.connected == true
        let tappable = canControl && glove != nil && !(glove!.missing) && !(glove!.connecting)
        let (word, colour) = badgeWord(glove)
        let battery = (connected && (glove?.batteryPct ?? -1) >= 0) ? glove!.batteryPct : nil
        let key = hand.rawValue.lowercased()

        GeometryReader { geo in
            let stacked = geo.size.width < 190
            VStack(alignment: .leading, spacing: 6) {
                if stacked {
                    heading
                    badge(word, colour, battery)
                } else {
                    HStack { heading; Spacer(); badge(word, colour, battery) }.frame(height: 20)
                }
                GeometryReader { inner in
                    let fit = fitGh(inner.size, .cast)
                    if fit >= 40 {
                        GloveArtView(hand: hand, look: fit >= 200 ? .cast : .castQuiet,
                                     stateAt: { _ in
                                         if let sh = video.shown() { return timeline.state(key, ptsUs: sh.ptsUs, arrived: sh.arrivedS) }
                                         return timeline.stateNow(key, now: nowS())
                                     },
                                     dim: connected ? 1 : 0.3)
                            .frame(width: inner.size.width, height: inner.size.height)
                    }
                }
            }
            .padding(pad)
        }
        .background(T.elevated, in: RoundedRectangle(cornerRadius: T.rCard))
        .overlay(RoundedRectangle(cornerRadius: T.rCard).stroke(T.borderSoft))
        .contentShape(Rectangle())
        .onTapGesture {
            guard tappable else { return }
            if connected { confirm = true } else { headsets.connectGlove(row.key, hand) }
        }
        .confirmationDialog(tr("{hand} glove", ("hand", tr(hand.rawValue))), isPresented: $confirm) {
            Button(tr("Disconnect"), role: .destructive) { headsets.disconnectGlove(row.key, hand) }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(tr("{hand} glove", ("hand", tr(hand.rawValue))) + ", " + word.lowercased()
                            + (battery.map { ", " + tr("battery {level}", ("level", "\($0)%")) } ?? ""))
    }

    /// The words drawn with the glove stay English, as on the desktop and the website.
    private var heading: some View {
        Text(hand == .left ? "LEFT HAND" : "RIGHT HAND")
            .font(.system(size: 11.5, weight: .bold)).tracking(1).foregroundStyle(T.text3).lineLimit(1)
    }

    private func badge(_ word: String, _ colour: Color, _ battery: Int?) -> some View {
        HStack(spacing: 5) {
            Circle().fill(colour).frame(width: 7, height: 7)
            Text(word).font(.system(size: 11, weight: .bold)).foregroundStyle(colour).lineLimit(1)
            if let b = battery {
                Text("  ·  \(b)%").font(.system(size: 11, weight: .bold)).foregroundStyle(b < 20 ? T.amber : T.text2).lineLimit(1)
            }
        }
        .frame(height: 20)
    }

    private func badgeWord(_ g: GloveState?) -> (String, Color) {
        guard let g, !g.missing else { return ("NO GLOVE", T.text5) }
        if g.connected { return ("CONNECTED", T.green) }
        if g.connecting { return ("CONNECTING", T.accent) }
        return ("NOT CONNECTED", T.text5)
    }
}

// MARK: - details

/// The numbers, for a bug report: versions, the share, the gloves.
private struct DetailsSheet: View {
    let row: HeadsetRow
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 8) {
                    line(row.host, T.text2)
                    if let s = row.status {
                        line("hexr \(s.hexrVersion)   app \(s.appVersion)   phones \(s.controllers)"
                             + (s.headsetBatteryPct >= 0 ? "   headset \(s.headsetBatteryPct)%" : ""), T.text2)
                        if s.stream.live {
                            line(tr("Shared · {w}×{h}", ("w", s.stream.width), ("h", s.stream.height))
                                 + (s.stream.viewers > 0 ? tr(" · {n} watching", ("n", s.stream.viewers)) : ""), T.text2)
                        }
                        if !s.stream.message.isEmpty { line(s.stream.message, T.text3) }
                        ForEach(Array(s.gloves.enumerated()), id: \.offset) { _, g in
                            line("\(g.hand)  \(g.state)" + (g.batteryPct >= 0 ? "  \(g.batteryPct)%" : "")
                                 + (g.message.isEmpty ? "" : "  \(g.message)"), T.text3)
                        }
                    }
                }
                .padding(20).frame(maxWidth: .infinity, alignment: .leading)
            }
            .background(T.card)
            .navigationTitle(tr("Details"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button(tr("Close")) { dismiss() } } }
        }
        .presentationDetents([.medium])
        .preferredColorScheme(.dark)
    }
    private func line(_ s: String, _ c: Color) -> some View {
        Text(s).font(T.mono(13)).foregroundStyle(c).textSelection(.enabled)
    }
}
