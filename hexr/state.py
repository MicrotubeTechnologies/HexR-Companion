"""The model: what gloves exist, what the tester is set to send.

A plain object polled by the UI on its own timer — there is no observer graph.
The BLE thread mutates these fields and the Tk tick reads them, which is safe
because every field here is a single assignment of an immutable value.

Gloves are keyed by hand, not by address, because a HEXR kit has exactly one
left and one right and the two are not interchangeable. Two gloves of the same
hand cannot be driven at once, and keying by hand makes that structural rather
than something the UI has to police.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import protocol as P

LEFT, RIGHT = "Left", "Right"
HANDS = (LEFT, RIGHT)

# A glove that has not sent a notification in this long is treated as stale.
# Telemetry arrives at 50 Hz, so this is three orders of magnitude of slack.
STALE_AFTER_S = 3.0


@dataclass
class Glove:
    hand: str
    address: str
    name: str = ""
    rssi: int | None = None
    connected: bool = False
    connecting: bool = False
    status: str = "Not connected"
    telemetry: P.Telemetry = field(default_factory=P.Telemetry)
    last_rx: float = 0.0
    # Settled by observation on first connect — see protocol.raw_to_kpa.
    absolute_pa: bool | None = None

    @property
    def battery(self) -> float | None:
        """0.0-1.0, or None if the glove has not reported yet."""
        return self.telemetry.battery

    def battery_label(self) -> str:
        b = self.telemetry.battery
        return "—" if b is None else f"{round(b * 100)}%"

    def kpa(self, channel: int) -> float:
        """Gauge kPa for one channel. Channel 6 is the source/tank."""
        try:
            return P.raw_to_kpa(self.telemetry.pressure_raw[channel])
        except IndexError:
            return 0.0

    def channel_kpa(self) -> list[float]:
        return [self.kpa(i) for i in range(6)]

    def source_kpa(self) -> float:
        return self.kpa(6)

    def is_live(self, now: float | None = None) -> bool:
        """Connected *and* sending telemetry.

        Not a health check: a glove that has never sent a byte still actuates
        normally. This gates the things that genuinely need data — the
        pressure readout and the QA sweep — and nothing else."""
        if not self.connected:
            return False
        return (now or time.monotonic()) - self.last_rx < STALE_AFTER_S


@dataclass
class TestSettings:
    """What the Test screen will send. Defaults are deliberately mild."""
    channels: set[int] = field(default_factory=lambda: {int(P.Finger.Index)})
    mode: str = "pressure"          # "pressure" | "vibration"
    intensity: float = 0.6
    speed: float = 1.0
    frequency: float = 10.0
    peak_ratio: float = 0.5
    hands: set[str] = field(default_factory=lambda: {LEFT, RIGHT})

    def active_fingers(self) -> list[P.Finger]:
        return [P.Finger(c) for c in sorted(self.channels)]


class AppState:
    def __init__(self):
        self.gloves: dict[str, Glove] = {}
        self.discovered: dict[str, dict] = {}    # address -> scan result
        self.test = TestSettings()

    # -- gloves --------------------------------------------------------------

    def add_glove(self, hand: str, address: str, name: str = "",
                  rssi: int | None = None) -> Glove:
        g = Glove(hand=hand, address=address, name=name, rssi=rssi)
        self.gloves[hand] = g
        return g

    def get(self, hand: str) -> Glove | None:
        return self.gloves.get(hand)

    def connected_gloves(self) -> list[Glove]:
        return [g for g in self.gloves.values() if g.connected]

    def any_connected(self) -> bool:
        return any(g.connected for g in self.gloves.values())

    def drop_disconnected(self):
        """Forget gloves that are neither connected nor mid-connect.

        The `connecting` guard is load-bearing: without it an in-flight connect
        deletes its own glove before the session coroutine has come up.
        """
        for hand in list(self.gloves):
            g = self.gloves[hand]
            if not g.connected and not g.connecting:
                del self.gloves[hand]
