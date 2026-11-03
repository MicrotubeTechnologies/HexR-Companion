// Which physical glove each hand of the headset connects to, and finding the right one when
// several are switched on (Android ui/GlovesDialog.kt). Find gloves has the headset list every
// glove in range, nearest first; Connect picks one, and the headset keeps to it from then on.
// Each glove goes by its own name from its address, or by one given here with a tap.

import SwiftUI

struct GlovesSheet: View {
    @EnvironmentObject var headsets: HeadsetsModel
    let rowKey: String
    @Environment(\.dismiss) private var dismiss
    @State private var renaming: String?
    @State private var newName = ""

    var body: some View {
        let row = headsets.rows.first { $0.key == rowKey }
        let s = row?.status
        let search = s?.gloveSearch
        let usable = s != nil && search != nil && s!.allowGloveControl && !s!.paused
        let searching = search?.state == "searching"

        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    if let s, let search {
                        let savedBy: [String: Hand] = Dictionary(
                            Hand.allCases.compactMap { h in
                                let a = s.glove(h)?.savedAddress ?? ""
                                return a.isEmpty ? nil : (a.uppercased(), h)
                            }, uniquingKeysWith: { a, _ in a })

                        // Each hand, and the glove it keeps to.
                        ForEach(Hand.allCases) { hand in
                            let saved = s.glove(hand)?.savedAddress ?? ""
                            HStack {
                                Text(tr(hand.rawValue)).foregroundStyle(T.text2).frame(width: 72, alignment: .leading)
                                Text(saved.isEmpty ? tr("Any glove") : headsets.gloveName(saved))
                                    .fontWeight(saved.isEmpty ? .regular : .semibold)
                                    .foregroundStyle(saved.isEmpty ? T.text2 : T.text)
                                Spacer()
                                if !saved.isEmpty && usable {
                                    Button(tr("Forget")) { headsets.forgetGlove(rowKey, hand) }.foregroundStyle(T.accent)
                                }
                            }
                            .font(.system(size: FS.body))
                            .frame(minHeight: 36)
                        }

                        Button(searching ? tr("Searching…") : tr("Find gloves")) { headsets.searchGloves(rowKey) }
                            .buttonStyle(HSButton(style: .ghost))
                            .disabled(!usable || searching)
                            .padding(.top, 4)

                        Group {
                            if searching { Text(tr("Looking for gloves…")).foregroundStyle(T.text2) }
                            else if search.state == "failed" { Text(search.message).foregroundStyle(T.red) }
                            else if search.state == "done" && search.found.isEmpty {
                                Text(tr("No gloves found. Switch them on, and disconnect them from other headsets.")).foregroundStyle(T.text2)
                            } else if !search.found.isEmpty { Text(tr("Tap a name to rename it.")).foregroundStyle(T.text2) }
                        }
                        .font(.system(size: FS.caption))

                        ForEach(search.found) { g in
                            let savedFor = savedBy[g.address.uppercased()]
                            foundRow(g, savedFor: savedFor,
                                     savedState: savedFor.flatMap { s.glove($0)?.state } ?? "", usable: usable)
                            Rectangle().fill(T.hairline).frame(height: 1)
                        }
                    } else {
                        Text(tr("Update this app to HexR 0.10.6 or later to pick gloves."))
                            .font(.system(size: FS.caption)).foregroundStyle(T.text2)
                    }
                }
                .padding(20)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .background(T.card)
            .navigationTitle(tr("Gloves"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button(tr("Close")) { dismiss() } } }
        }
        .preferredColorScheme(.dark)
        .tint(T.accent)
        .alert(tr("Rename"), isPresented: Binding(get: { renaming != nil }, set: { if !$0 { renaming = nil } })) {
            TextField("", text: $newName)
            Button(tr("Cancel"), role: .cancel) { renaming = nil }
            Button(tr("Done")) { if let a = renaming { headsets.renameGlove(a, newName) }; renaming = nil }
        }
    }

    @ViewBuilder
    private func foundRow(_ g: NearbyGlove, savedFor: Hand?, savedState: String, usable: Bool) -> some View {
        HStack(spacing: 12) {
            SignalBars(bars: GloveSearch.signalBars(g.rssi == 0 ? nil : g.rssi))
            Button {
                newName = headsets.gloveName(g.address); renaming = g.address
            } label: {
                VStack(alignment: .leading, spacing: 2) {
                    Text(headsets.gloveName(g.address)).font(.system(size: FS.body, weight: .semibold)).foregroundStyle(T.text)
                    if !g.hand.isEmpty {
                        Text(tr(g.hand.capitalized)).font(.system(size: FS.caption)).foregroundStyle(T.text2)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .buttonStyle(.plain)
            // The glove chosen and connected, or what connects it.
            if let h = savedFor, savedState == "connected" {
                Text("✓ " + tr(h.rawValue)).fontWeight(.semibold).foregroundStyle(T.green)
            } else if savedFor != nil, savedState == "connecting" {
                Text(tr("Connecting…")).foregroundStyle(T.text2)
            } else if let h = savedFor ?? Hand(rawValue: g.hand.capitalized) {
                Button(tr("Connect")) { headsets.connectGloveAt(rowKey, h, g.address) }
                    .foregroundStyle(usable ? T.accent : T.text5).disabled(!usable)
            } else {
                ForEach(Hand.allCases) { h in
                    Button(tr(h.rawValue)) { headsets.connectGloveAt(rowKey, h, g.address) }
                        .foregroundStyle(usable ? T.accent : T.text5).disabled(!usable)
                }
            }
        }
        .font(.system(size: FS.body))
        .frame(minHeight: 48)
    }
}
