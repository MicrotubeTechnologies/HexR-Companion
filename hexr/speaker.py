"""The headset's sound, played on this computer while its view is watched.

An AudioReceiver tap: each decoded piece of the app's sound is turned into 16-bit samples and
queued, and the sound card takes them from the queue at its own pace. The queue is kept short, so
what is heard stays close to the picture: a little is held back to ride out the network's
unevenness, and if it ever grows long (the sound card stalled, or a burst arrived) the oldest is
dropped rather than let the sound fall behind. While nothing arrives it plays silence.

sounddevice, which carries PortAudio for Windows and macOS in its wheel, does the playing. Without
it the app still runs and records the sound; it just stays quiet here. No Tk.
"""

from __future__ import annotations

import threading

PRIME_S = 0.12        # held back before the sound starts, and after it runs dry
MAX_S = 0.5           # more queued than this, and the oldest is dropped


def available() -> str | None:
    """None if sound can be played here, otherwise why not."""
    try:
        import sounddevice  # noqa: F401
    except Exception as e:  # missing, or PortAudio would not load
        return str(e) or type(e).__name__
    return None


class Speaker:
    """Plays what an AudioReceiver decodes. Add `speaker.tap` to its `taps`; `close()` stops."""

    def __init__(self):
        self._lock = threading.Lock()
        self._buf = bytearray()
        self._stream = None
        self._resampler = None
        self._rate = self._channels = 0
        self._primed = False
        self.error = ""

    def tap(self, frame, _pts_us: int):
        """From the receiver's thread: one decoded av.AudioFrame."""
        if self.error:
            return
        try:
            if self._stream is None or frame.sample_rate != self._rate:
                self._open(frame)
            for out in self._resampler.resample(frame):
                data = bytes(out.planes[0])[: out.samples * self._channels * 2]
                self._push(data)
        except Exception as e:
            self.error = str(e) or type(e).__name__
            self.close()

    def _open(self, frame):
        import av
        import sounddevice as sd

        self.close()
        self._rate = frame.sample_rate
        self._channels = min(2, len(frame.layout.channels)) or 2
        self._resampler = av.AudioResampler(format="s16", layout="stereo" if self._channels == 2
                                            else "mono", rate=self._rate)
        self._stream = sd.RawOutputStream(samplerate=self._rate, channels=self._channels,
                                          dtype="int16", callback=self._play, latency="low")
        self._stream.start()

    def _push(self, data: bytes):
        frame_bytes = self._channels * 2
        with self._lock:
            self._buf += data
            too_much = len(self._buf) - int(MAX_S * self._rate) * frame_bytes
            if too_much > 0:
                too_much -= too_much % frame_bytes
                del self._buf[:too_much]

    def _play(self, out, frames, _time, _status):
        """The sound card's thread: `frames` samples per channel, from the queue or silence."""
        want = frames * self._channels * 2
        with self._lock:
            if not self._primed and len(self._buf) >= int(PRIME_S * self._rate) * self._channels * 2:
                self._primed = True
            if not self._primed:
                out[:] = b"\0" * want
                return
            take = bytes(self._buf[:want])
            del self._buf[:want]
            if len(take) < want:
                # Ran dry: wait for a little to build up again before playing on.
                self._primed = False
                take += b"\0" * (want - len(take))
        out[:] = take

    def close(self):
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        with self._lock:
            self._buf.clear()
            self._primed = False
