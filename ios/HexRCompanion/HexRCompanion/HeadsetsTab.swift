import SwiftUI

/// The Headsets tab's slot in the frame: this iPad's own gloves (for the hint when it holds a glove
/// a headset is trying to reach), and full screen while a headset's view is watched.
struct HeadsetsTab: View {
    let phoneGloves: Set<Hand>
    @Binding var immersive: Bool
    var body: some View {
        HeadsetsScreen(phoneGloves: phoneGloves, onImmersive: { immersive = $0 })
    }
}
