// Plays one headset's view (Android remote/VideoPlayer.kt): reads its video stream and shows it
// with AVSampleBufferDisplayLayer, which decodes H.264 itself. The stream is the encoder's
// Annex-B output; this turns it into length-prefixed NAL units and a format description from the
// SPS/PPS. Every frame is shown the moment it arrives: a live view of someone's hands that is
// current beats a smooth one half a second late.

import Foundation
import Network
import AVFoundation
import CoreMedia
import UIKit
import SwiftUI

final class VideoPlayer {
    enum VideoState: Equatable {
        case connecting
        case playing(width: Int, height: Int)
        case failed(String)
    }

    /// A frame sent to the screen: its presentation time, and when it arrived (nowS()).
    struct Shown { let ptsUs: Int64; let arrivedS: Double }

    private let host: String, port: Int
    private let layer: AVSampleBufferDisplayLayer
    private let onState: (VideoState) -> Void
    private let queue = DispatchQueue(label: "HexRVideo")
    private var conn: NWConnection?
    private var running = false
    private var format: CMVideoFormatDescription?
    private var sps: Data?, pps: Data?
    private var playing = false
    private var header: VideoHeader?

    private let shownLock = NSLock()
    private var _shown: Shown?
    var shown: Shown? { shownLock.lock(); defer { shownLock.unlock() }; return _shown }

    init(host: String, port: Int, layer: AVSampleBufferDisplayLayer, onState: @escaping (VideoState) -> Void) {
        self.host = host; self.port = port; self.layer = layer; self.onState = onState
    }

    func start() {
        guard !running, let p = NWEndpoint.Port(rawValue: UInt16(clamping: port)) else { return }
        running = true
        state(.connecting)
        let tcp = NWProtocolTCP.Options()
        tcp.noDelay = true
        tcp.connectionTimeout = 3
        let params = NWParameters(tls: nil, tcp: tcp)
        params.requiredInterfaceType = .wifi
        let c = NWConnection(host: NWEndpoint.Host(host), port: p, using: params)
        conn = c
        c.stateUpdateHandler = { [weak self] st in
            guard let self, self.running else { return }
            switch st {
            case .ready: self.readHeader()
            case .failed(let e): self.fail(e.localizedDescription)
            case .waiting(let e): self.fail(e.localizedDescription)
            default: break
            }
        }
        c.start(queue: queue)
    }

    func stop() {
        running = false
        conn?.stateUpdateHandler = nil
        conn?.cancel()
        conn = nil
    }

    private func state(_ s: VideoState) { DispatchQueue.main.async { self.onState(s) } }

    private func fail(_ message: String) {
        guard running else { return }
        stop()
        state(.failed(message.isEmpty ? tr("The video connection closed.") : message))
    }

    private func read(_ n: Int, _ then: @escaping ([UInt8]) -> Void) {
        conn?.receive(minimumIncompleteLength: n, maximumLength: n) { [weak self] data, _, done, error in
            guard let self, self.running else { return }
            if let data, data.count == n { then([UInt8](data)); return }
            if error != nil || done { self.fail(error?.localizedDescription ?? tr("The video connection closed.")) }
        }
    }

    private func readHeader() {
        read(RemoteProtocol.videoHeaderBytes) { [weak self] b in
            guard let self else { return }
            guard let h = RemoteProtocol.parseVideoHeader(b) else { self.fail(tr("That is not a HexR video stream.")); return }
            guard h.codec == RemoteProtocol.codecH264 else {
                self.fail(tr("The headset sent a video format this iPad does not know.")); return
            }
            self.header = h
            self.readPacket()
        }
    }

    private func readPacket() {
        read(RemoteProtocol.packetHeaderBytes) { [weak self] b in
            guard let self else { return }
            let ph = RemoteProtocol.parsePacketHeader(b)
            guard ph.length > 0, ph.length <= RemoteProtocol.maxPacketBytes else {
                self.fail(tr("The video stream is damaged.")); return
            }
            self.read(ph.length) { payload in
                self.handle(ph, payload)
                self.readPacket()
            }
        }
    }

    // MARK: - H.264

    /// Annex-B to NAL units: split on 00 00 01 / 00 00 00 01 start codes.
    static func nalUnits(_ b: [UInt8]) -> [ArraySlice<UInt8>] {
        var units: [ArraySlice<UInt8>] = []
        var i = 0, start = -1
        let n = b.count
        while i + 2 < n {
            if b[i] == 0, b[i + 1] == 0, b[i + 2] == 1 {
                if start >= 0 {
                    var end = i
                    if end > start, b[end - 1] == 0 { end -= 1 }
                    if end > start { units.append(b[start..<end]) }
                }
                i += 3; start = i
            } else { i += 1 }
        }
        if start >= 0, start < n { units.append(b[start..<n]) }
        if start < 0, n > 0 { units.append(b[0..<n]) }   // no start code: one NAL unit
        return units
    }

    private func handle(_ ph: PacketHeader, _ payload: [UInt8]) {
        let arrived = nowS()
        var frame = Data()
        var hasPicture = false
        var isKey = ph.key
        for nal in Self.nalUnits(payload) {
            guard let first = nal.first else { continue }
            let type = first & 0x1F
            switch type {
            case 7: if sps != Data(nal) { sps = Data(nal); format = nil }
            case 8: if pps != Data(nal) { pps = Data(nal); format = nil }
            case 9, 6: break          // access unit delimiter, SEI
            default:
                if type == 5 { isKey = true }
                var len = UInt32(nal.count).bigEndian
                frame.append(Data(bytes: &len, count: 4))
                frame.append(contentsOf: nal)
                hasPicture = true
            }
        }
        if format == nil, let s = sps, let p = pps { format = makeFormat(s, p) }
        guard hasPicture, let fmt = format else { return }
        guard let sample = makeSample(frame, fmt, ph.ptsUs, key: isKey) else { return }

        DispatchQueue.main.async { [weak self] in
            guard let self, self.running else { return }
            if self.layer.status == .failed { self.layer.flush() }
            self.layer.enqueue(sample)
            self.shownLock.lock(); self._shown = Shown(ptsUs: ph.ptsUs, arrivedS: arrived); self.shownLock.unlock()
            if !self.playing {
                self.playing = true
                let dims = CMVideoFormatDescriptionGetDimensions(fmt)
                self.onState(.playing(width: Int(dims.width), height: Int(dims.height)))
            }
        }
    }

    private func makeFormat(_ sps: Data, _ pps: Data) -> CMVideoFormatDescription? {
        var fmt: CMVideoFormatDescription?
        let status = sps.withUnsafeBytes { s in
            pps.withUnsafeBytes { p in
                let ptrs = [s.bindMemory(to: UInt8.self).baseAddress!, p.bindMemory(to: UInt8.self).baseAddress!]
                let sizes = [sps.count, pps.count]
                return CMVideoFormatDescriptionCreateFromH264ParameterSets(
                    allocator: kCFAllocatorDefault, parameterSetCount: 2, parameterSetPointers: ptrs,
                    parameterSetSizes: sizes, nalUnitHeaderLength: 4, formatDescriptionOut: &fmt)
            }
        }
        return status == noErr ? fmt : nil
    }

    private func makeSample(_ frame: Data, _ fmt: CMVideoFormatDescription, _ ptsUs: Int64, key: Bool) -> CMSampleBuffer? {
        var block: CMBlockBuffer?
        let count = frame.count
        guard CMBlockBufferCreateWithMemoryBlock(allocator: kCFAllocatorDefault, memoryBlock: nil, blockLength: count,
                                                 blockAllocator: kCFAllocatorDefault, customBlockSource: nil,
                                                 offsetToData: 0, dataLength: count, flags: 0,
                                                 blockBufferOut: &block) == noErr, let block else { return nil }
        let copied = frame.withUnsafeBytes { CMBlockBufferReplaceDataBytes(with: $0.baseAddress!, blockBuffer: block,
                                                                           offsetIntoDestination: 0, dataLength: count) }
        guard copied == noErr else { return nil }
        var timing = CMSampleTimingInfo(duration: .invalid, presentationTimeStamp: CMTime(value: ptsUs, timescale: 1_000_000),
                                        decodeTimeStamp: .invalid)
        var size = count
        var sample: CMSampleBuffer?
        guard CMSampleBufferCreateReady(allocator: kCFAllocatorDefault, dataBuffer: block, formatDescription: fmt,
                                        sampleCount: 1, sampleTimingEntryCount: 1, sampleTimingArray: &timing,
                                        sampleSizeEntryCount: 1, sampleSizeArray: &size,
                                        sampleBufferOut: &sample) == noErr, let sample else { return nil }
        if let atts = CMSampleBufferGetSampleAttachmentsArray(sample, createIfNecessary: true),
           CFArrayGetCount(atts) > 0 {
            let dict = unsafeBitCast(CFArrayGetValueAtIndex(atts, 0), to: CFMutableDictionary.self)
            CFDictionarySetValue(dict, Unmanaged.passUnretained(kCMSampleAttachmentKey_DisplayImmediately).toOpaque(),
                                 Unmanaged.passUnretained(kCFBooleanTrue).toOpaque())
            if !key {
                CFDictionarySetValue(dict, Unmanaged.passUnretained(kCMSampleAttachmentKey_NotSync).toOpaque(),
                                     Unmanaged.passUnretained(kCFBooleanTrue).toOpaque())
            }
        }
        return sample
    }
}

// MARK: - The view and its player, held by the live screen so the glove panels can ask which frame shows

final class CastVideo: ObservableObject {
    @Published private(set) var state: VideoPlayer.VideoState?
    let layer: AVSampleBufferDisplayLayer = {
        let l = AVSampleBufferDisplayLayer()
        l.videoGravity = .resize      // the view's frame is placed by CastLayout.videoRect
        l.backgroundColor = UIColor.clear.cgColor
        return l
    }()
    private var player: VideoPlayer?
    private var host = "", port = 0
    private var generation = 0

    /// Whether this iPad is one of the viewers the headset counts.
    var joined: Bool {
        guard player != nil else { return false }
        if case .failed = state { return false }
        return true
    }

    var playing: Bool { if case .playing = state { return true }; return false }

    /// The frame on screen, while the view plays.
    func shown() -> VideoPlayer.Shown? { playing ? player?.shown : nil }

    func start(host: String, port: Int) {
        if player != nil, host == self.host, port == self.port { return }
        stopPlayer()
        self.host = host; self.port = port
        play()
    }

    /// The view dropped while the headset still shares it: join again.
    func rejoin() {
        guard !host.isEmpty else { return }
        stopPlayer()
        play()
    }

    private func play() {
        generation += 1
        let mine = generation
        state = .connecting
        layer.flushAndRemoveImage()
        let p = VideoPlayer(host: host, port: port, layer: layer) { [weak self] st in
            guard let self, self.generation == mine else { return }
            self.state = st
        }
        player = p
        p.start()
    }

    private func stopPlayer() {
        generation += 1
        player?.stop()
        player = nil
    }

    func release() {
        stopPlayer()
        layer.flushAndRemoveImage()
        state = nil
        host = ""; port = 0
    }
}

/// The headset's view, placed so the whole frame lands where CastLayout.videoRect puts it.
struct HeadsetVideoView: UIViewRepresentable {
    let video: CastVideo
    let videoW: Int, videoH: Int

    final class Host: UIView {
        var videoLayer: AVSampleBufferDisplayLayer?
        var vw = 0, vh = 0
        override func layoutSubviews() {
            super.layoutSubviews()
            guard let l = videoLayer else { return }
            CATransaction.begin(); CATransaction.setDisableActions(true)
            l.frame = CastLayout.videoRect(bounds.size, vw, vh)
            CATransaction.commit()
        }
    }

    func makeUIView(context: Context) -> Host {
        let v = Host()
        v.clipsToBounds = true
        v.backgroundColor = .clear
        v.layer.addSublayer(video.layer)
        v.videoLayer = video.layer
        return v
    }

    func updateUIView(_ v: Host, context: Context) {
        if v.videoLayer !== video.layer {
            v.videoLayer?.removeFromSuperlayer()
            v.layer.addSublayer(video.layer)
            v.videoLayer = video.layer
        }
        v.vw = videoW; v.vh = videoH
        v.setNeedsLayout()
    }
}
