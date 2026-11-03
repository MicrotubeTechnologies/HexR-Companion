import SwiftUI

@main
struct HexRCompanionApp: App {
    @StateObject private var mgr = GloveManager()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootView().environmentObject(mgr)
        }
        // Never leave a channel inflated against someone's finger when the app
        // goes to the background.
        .onChange(of: scenePhase) { _, phase in
            if phase != .active { mgr.allOff() }
        }
    }
}
