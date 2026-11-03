// Things every screen uses: design tokens, the language, glove names.
// Ported from the Android app (branch android-headsets): ui/Theme.kt, I18n.kt, GloveNames.kt.

import SwiftUI
import CoreText

// MARK: - Theme (ui/Theme.kt). Dark only, deliberately.

enum T {
    static let screen = Color(hex: 0x0C0C0E)
    static let card = Color(hex: 0x1B1B1F)
    static let elevated = Color(hex: 0x141417)
    static let elevated2 = Color(hex: 0x141416)
    static let chip = Color(hex: 0x26262B)

    static let border = Color.white.opacity(0.09)
    static let borderSoft = Color.white.opacity(0.07)
    static let borderStrong = Color.white.opacity(0.10)
    static let hairline = Color.white.opacity(0.05)

    static let text = Color(hex: 0xECECEC)
    static let text2 = Color(hex: 0x9A9AA0)
    static let text3 = Color(hex: 0x7C7C84)
    static let text4 = Color(hex: 0x6C6C74)
    static let text5 = Color(hex: 0x57575E)
    static let textFaint = Color(hex: 0x3A3A40)

    static let accent = Color(hex: 0xF4762A)
    static let onAccent = Color(hex: 0x140B04)

    static let green = Color(hex: 0x3ECF8E)
    static let red = Color(hex: 0xE5484D)
    static let amber = Color(hex: 0xE8B04B)

    static let rChip: CGFloat = 8
    static let rCard: CGFloat = 10
    static let rCtrl: CGFloat = 12
    static let rSheet: CGFloat = 14
    static let rPill: CGFloat = 14
    static let pagePad: CGFloat = 16

    /// Monospace for every numeric readout.
    static func mono(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .monospaced)
    }
}

/// The type scale (Theme.kt `Size`). iPad gets the same scale, a touch larger.
enum FS {
    static let verdict: CGFloat = 26
    static let title: CGFloat = 24
    static let wordmark: CGFloat = 17
    static let action: CGFloat = 16
    static let control: CGFloat = 15
    static let body: CGFloat = 14.5
    static let body2: CGFloat = 14
    static let caption: CGFloat = 13
    static let micro: CGFloat = 12
    static let label: CGFloat = 11
    static let tag: CGFloat = 10
}

extension Color {
    init(hex: UInt32, alpha: Double = 1) {
        self.init(.sRGB, red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255, opacity: alpha)
    }
    init(argb: UInt32) {
        self.init(hex: argb & 0xFFFFFF, alpha: Double((argb >> 24) & 0xFF) / 255)
    }
}

/// Archivo Black, the caption font under the glove. Registered once at launch.
enum Fonts {
    static let captionName = "ArchivoBlack-Regular"
    static func register() {
        guard let url = Bundle.main.url(forResource: "ArchivoBlack", withExtension: "ttf") else { return }
        CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil)
    }
}

// MARK: - Language (I18n.kt): the English sentence is the key; ZH holds its Chinese.

final class I18n: ObservableObject {
    static let shared = I18n()
    static let en = "en", zh = "zh"

    @Published var language: String {
        didSet { UserDefaults.standard.set(language, forKey: "language") }
    }

    private init() {
        if let saved = UserDefaults.standard.string(forKey: "language") {
            language = saved
        } else {
            // The first run follows the iPad's own language.
            language = (Locale.preferredLanguages.first ?? "en").hasPrefix("zh") ? I18n.zh : I18n.en
        }
    }

    var chinese: Bool { language == I18n.zh }
}

func tr(_ text: String, _ args: (String, Any)...) -> String {
    var out = I18n.shared.chinese ? (ZH[text] ?? ZH_HEADSETS[text] ?? text) : text
    for (name, value) in args { out = out.replacingOccurrences(of: "{\(name)}", with: "\(value)") }
    return out
}

// MARK: - Glove names (GloveNames.kt)
//
// A name for every glove, from its Bluetooth address alone: FNV-1a 32-bit over the address's
// upper-case hex digits; adjective = A[h % 64], animal = B[(h >> 6) % 64], number (h >> 12) % 10 + 1.
// Never reorder the lists, or every glove gets a new name.
//
// iOS caveat: CoreBluetooth never shows an app a glove's Bluetooth address, only a UUID this iPad
// made up for it. So for gloves this iPad connects itself the name comes from that UUID: steady on
// this iPad, but not the name a phone or computer gives the same glove. Gloves reported by a
// headset (Headsets tab) carry their real address and get the same name as everywhere else.

enum GloveNames {
    static let adjectives: [(String, String)] = [
        ("Amber", "琥珀"), ("Azure", "蔚蓝"), ("Bold", "大胆"), ("Brave", "勇敢"),
        ("Bright", "明亮"), ("Brisk", "轻快"), ("Calm", "沉静"), ("Clever", "聪明"),
        ("Coral", "珊瑚"), ("Cosmic", "星际"), ("Crimson", "深红"), ("Daring", "无畏"),
        ("Dusky", "暮色"), ("Eager", "热切"), ("Fiery", "火焰"), ("Frosty", "霜白"),
        ("Gentle", "温和"), ("Golden", "金色"), ("Happy", "快乐"), ("Hazel", "榛色"),
        ("Honest", "诚实"), ("Indigo", "靛蓝"), ("Ivory", "象牙"), ("Jade", "翡翠"),
        ("Jolly", "欢乐"), ("Keen", "敏锐"), ("Kind", "善良"), ("Lively", "活泼"),
        ("Lucky", "幸运"), ("Lunar", "月光"), ("Merry", "愉快"), ("Mighty", "强大"),
        ("Misty", "薄雾"), ("Noble", "高贵"), ("Olive", "橄榄"), ("Plucky", "机灵"),
        ("Polar", "极地"), ("Proud", "骄傲"), ("Quick", "敏捷"), ("Quiet", "安静"),
        ("Rapid", "迅疾"), ("Royal", "皇家"), ("Ruby", "红宝石"), ("Rusty", "锈色"),
        ("Sandy", "沙色"), ("Scarlet", "猩红"), ("Silver", "银色"), ("Snowy", "雪白"),
        ("Solar", "太阳"), ("Spry", "矫健"), ("Steady", "稳健"), ("Stormy", "风暴"),
        ("Sunny", "阳光"), ("Swift", "飞速"), ("Teal", "青色"), ("Tidy", "整洁"),
        ("Velvet", "丝绒"), ("Vivid", "鲜艳"), ("Witty", "风趣"), ("Wild", "狂野"),
        ("Windy", "疾风"), ("Zesty", "热情"), ("Cheery", "开朗"), ("Sleek", "流线"),
    ]
    static let animals: [(String, String)] = [
        ("Otter", "水獭"), ("Falcon", "猎鹰"), ("Panda", "熊猫"), ("Tiger", "老虎"),
        ("Koala", "考拉"), ("Lynx", "猞猁"), ("Heron", "苍鹭"), ("Bison", "野牛"),
        ("Badger", "獾"), ("Beaver", "河狸"), ("Camel", "骆驼"), ("Cobra", "眼镜蛇"),
        ("Crane", "仙鹤"), ("Dingo", "澳洲野犬"), ("Dolphin", "海豚"), ("Eagle", "雄鹰"),
        ("Ferret", "雪貂"), ("Finch", "雀鸟"), ("Fox", "狐狸"), ("Gecko", "壁虎"),
        ("Gibbon", "长臂猿"), ("Hare", "野兔"), ("Hawk", "鹰"), ("Hedgehog", "刺猬"),
        ("Ibis", "朱鹭"), ("Jaguar", "美洲豹"), ("Kestrel", "红隼"), ("Kiwi", "几维鸟"),
        ("Lemur", "狐猴"), ("Leopard", "花豹"), ("Lion", "狮子"), ("Llama", "羊驼"),
        ("Magpie", "喜鹊"), ("Marten", "貂"), ("Moose", "驼鹿"), ("Narwhal", "独角鲸"),
        ("Newt", "蝾螈"), ("Ocelot", "豹猫"), ("Orca", "虎鲸"), ("Osprey", "鱼鹰"),
        ("Owl", "猫头鹰"), ("Panther", "黑豹"), ("Parrot", "鹦鹉"), ("Pelican", "鹈鹕"),
        ("Penguin", "企鹅"), ("Puffin", "海鹦"), ("Puma", "美洲狮"), ("Quail", "鹌鹑"),
        ("Rabbit", "兔子"), ("Raven", "渡鸦"), ("Robin", "知更鸟"), ("Salmon", "鲑鱼"),
        ("Seal", "海豹"), ("Shark", "鲨鱼"), ("Sparrow", "麻雀"), ("Squirrel", "松鼠"),
        ("Swan", "天鹅"), ("Tapir", "貘"), ("Toucan", "巨嘴鸟"), ("Turtle", "海龟"),
        ("Walrus", "海象"), ("Whale", "鲸鱼"), ("Wolf", "狼"), ("Yak", "牦牛"),
    ]

    static func hash(_ address: String) -> UInt32 {
        var h: UInt32 = 2166136261
        for c in address.uppercased().unicodeScalars {
            guard ("0"..."9").contains(c) || ("A"..."F").contains(c) else { continue }
            h = (h ^ UInt32(c.value)) &* 16777619
        }
        return h
    }

    /// "Amber Otter 4", or "琥珀水獭4号" in Chinese.
    static func autoName(_ address: String, chinese: Bool = I18n.shared.chinese) -> String {
        let h = hash(address)
        let a = adjectives[Int(h % 64)], b = animals[Int((h >> 6) % 64)]
        let n = (h >> 12) % 10 + 1
        return chinese ? "\(a.1)\(b.1)\(n)号" : "\(a.0) \(b.0) \(n)"
    }

    /// What this iPad calls the glove: a name given to it here, or else its own.
    static func name(for address: String) -> String {
        UserDefaults.standard.string(forKey: "glove:\(address.uppercased())") ?? autoName(address)
    }

    static func rename(_ address: String, to name: String?) {
        let key = "glove:\(address.uppercased())"
        let n = name?.trimmingCharacters(in: .whitespaces) ?? ""
        if n.isEmpty || n == autoName(address) { UserDefaults.standard.removeObject(forKey: key) }
        else { UserDefaults.standard.set(n, forKey: key) }
    }
}

// MARK: - Glove search (GloveSearch.kt)

enum GloveSearch {
    static let expireS: TimeInterval = 20
    static let rescanS: TimeInterval = 1.5
    static let fullRescanS: TimeInterval = 6
    static let retryS: TimeInterval = 10

    static func signalBars(_ rssi: Int?) -> Int {
        guard let r = rssi else { return 0 }
        return r >= -60 ? 4 : r >= -70 ? 3 : r >= -80 ? 2 : 1
    }
}

/// Four signal bars.
struct SignalBars: View {
    let bars: Int
    var body: some View {
        HStack(alignment: .bottom, spacing: 2) {
            ForEach(0..<4) { i in
                Rectangle()
                    .fill(i < bars ? T.green : T.borderStrong)
                    .frame(width: 4, height: CGFloat(14 * (i + 1)) / 4)
            }
        }
        .frame(width: 22, height: 14, alignment: .bottom)
        .accessibilityLabel("\(bars) of 4")
    }
}

/// Tracked uppercase section label.
struct SectionLabel: View {
    let text: String
    init(_ text: String) { self.text = text }
    var body: some View {
        Text(text.uppercased()).font(.system(size: FS.label, weight: .semibold)).tracking(1.2)
            .foregroundStyle(T.text3)
    }
}
