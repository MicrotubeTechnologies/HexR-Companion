import SwiftUI

@main
struct HexRCompanionApp: App {
    @StateObject private var gloves = GloveManager()
    @StateObject private var headsets = HeadsetsModel()
    @StateObject private var i18n = I18n.shared
    @Environment(\.scenePhase) private var scenePhase

    init() { Fonts.register() }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(gloves)
                .environmentObject(headsets)
                .environmentObject(i18n)
        }
        // Vent everything the moment the app is not in front: a channel left inflated presses on
        // someone's hand until the battery dies. Headset sockets go with the screen too.
        .onChange(of: scenePhase) { _, phase in
            gloves.setForeground(phase == .active)
            headsets.setForeground(phase == .active)
        }
    }
}
