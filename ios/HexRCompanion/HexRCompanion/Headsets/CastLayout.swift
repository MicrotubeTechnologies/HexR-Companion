// Where a headset's view and its two glove panels go (Android remote/CastLayout.kt, the
// desktop's viewer.py). Landscape: the view takes three quarters of the width, the gloves the rest.
// Portrait: the view across the top, as tall as leaves the gloves their room under it.

import CoreGraphics

enum CastLayout {
    static let viewShare: CGFloat = 0.75
    static let cutLow: CGFloat = 0.35
    static let glovesShare: CGFloat = 0.42

    struct Boxes { var view, left, right: CGRect }

    static func landscape(_ w: CGFloat, _ h: CGFloat, gap: CGFloat, head: CGFloat, pad: CGFloat) -> Boxes {
        let vw = w * viewShare - gap / 2
        let room = CGRect(x: vw + gap, y: 0, width: w - vw - gap, height: h)
        let (l, r) = twoPanels(room, gap: gap, head: head, pad: pad)
        return Boxes(view: CGRect(x: 0, y: 0, width: vw, height: h), left: l, right: r)
    }

    static func portrait(_ w: CGFloat, _ h: CGFloat, aspect: CGFloat, gap: CGFloat, minPanels: CGFloat,
                         head: CGFloat, pad: CGFloat) -> Boxes {
        let vh = max(0, min(w / aspect, h - max(h * glovesShare, minPanels) - gap))
        let room = CGRect(x: 0, y: vh + gap, width: w, height: h - vh - gap)
        let (l, r) = twoPanels(room, gap: gap, head: head, pad: pad)
        return Boxes(view: CGRect(x: 0, y: 0, width: w, height: vh), left: l, right: r)
    }

    /// The gloves' room in two: side by side or stacked, whichever draws the glove taller.
    static func twoPanels(_ room: CGRect, gap: CGFloat, head: CGFloat, pad: CGFloat) -> (CGRect, CGRect) {
        let halfW = (room.width - gap) / 2, halfH = (room.height - gap) / 2
        let beside = (CGRect(x: room.minX, y: room.minY, width: halfW, height: room.height),
                      CGRect(x: room.minX + halfW + gap, y: room.minY, width: halfW, height: room.height))
        let stacked = (CGRect(x: room.minX, y: room.minY, width: room.width, height: halfH),
                       CGRect(x: room.minX, y: room.minY + halfH + gap, width: room.width, height: halfH))
        return gloveHeight(stacked.0, head: head, pad: pad) >= gloveHeight(beside.0, head: head, pad: pad) ? stacked : beside
    }

    static func gloveHeight(_ cell: CGRect, head: CGFloat, pad: CGFloat) -> CGFloat {
        fitGh(CGSize(width: cell.width - pad * 2, height: cell.height - head - pad * 2), .cast)
    }

    /// Where the whole video frame goes so it shows in a box this size: filling it and cut low when
    /// the video is taller than the box; otherwise whole and centred.
    static func videoRect(_ box: CGSize, _ videoW: Int, _ videoH: Int) -> CGRect {
        guard videoW > 0, videoH > 0, box.width > 0, box.height > 0 else { return CGRect(origin: .zero, size: box) }
        let va = CGFloat(videoW) / CGFloat(videoH), ba = box.width / box.height
        if va < ba - 0.01 {
            let h = box.width / va
            let top = (h - box.height) / 2 * (1 + cutLow)
            return CGRect(x: 0, y: -top, width: box.width, height: h)
        }
        let s = min(box.width / CGFloat(videoW), box.height / CGFloat(videoH))
        let w = CGFloat(videoW) * s, h = CGFloat(videoH) * s
        return CGRect(x: (box.width - w) / 2, y: (box.height - h) / 2, width: w, height: h)
    }
}
