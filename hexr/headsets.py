"""Every HEXR headset on this network, as the Headsets screen sees them.

Kept apart from the glove engine on purpose: that drives gloves over this computer's own
Bluetooth, and this never touches Bluetooth. It talks to headsets that hold their gloves
themselves. A glove connects to one thing at a time, so the two meet only in the hint the screen
gives when this computer is holding a glove a headset wants.

Network threads write into the entries under a lock; the screen reads `rows()`, a snapshot, on
its own tick. Nothing here runs until `start()`, which the screen calls the first time it is
shown, so the firewall question Windows asks appears when someone has just asked for headsets.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from . import remote as R
from . import settings
from .i18n import tr

# A headset that stopped announcing and cannot be reached has gone: switched off, or its app
# closed. One added by address stays until forgotten, since nothing else would bring it back.
FORGET_AFTER_S = 15.0
ERROR_SHOWN_S = 8.0


@dataclass
class HeadsetRow:
    key: str
    host: str
    title: str
    nickname: str
    announce: R.Announce | None
    status: R.Status | None
    link: str            # connecting | connected | lost
    error: str | None
    manual: bool


class _Entry:
    def __init__(self, key: str, host: str, link: R.HeadsetLink, manual: bool):
        self.key = key
        self.host = host
        self.link = link
        self.manual = manual
        self.announce: R.Announce | None = None
        self.status: R.Status | None = None
        self.state = "connecting"
        self.error: str | None = None
        self.error_at = 0.0
        self.last_heard = time.monotonic()


class Headsets:
    def __init__(self):
        self._lock = threading.Lock()
        self._entries: dict[str, _Entry] = {}
        self._discovery = R.Discovery(self._on_announce, self._on_discovery_error)
        self._nicknames = _load_nicknames()
        self.started = False
        self.discovery_error: str | None = None

    # -- lifecycle -----------------------------------------------------------

    def start(self):
        if self.started:
            return
        self.started = True
        self._discovery.start()

    def stop(self):
        self._discovery.stop()
        with self._lock:
            entries = list(self._entries.values())
        for e in entries:
            e.link.stop()

    # -- what the screen asks for ----------------------------------------------

    def add_by_address(self, address: str):
        """For networks that keep devices from seeing each other's broadcasts."""
        host = address.strip()
        if not host:
            return
        if ":" in host and host.count(":") == 1:
            host, port_text = host.split(":")
            port = int(port_text) if port_text.isdigit() else R.CONTROL_PORT
        else:
            port = R.CONTROL_PORT
        key = f"ip:{host}"
        with self._lock:
            if key in self._entries:
                return
            entry = _Entry(key, host, R.HeadsetLink(key, host, port, self), manual=True)
            self._entries[key] = entry
        entry.link.start()

    def forget(self, key: str):
        with self._lock:
            entry = self._entries.pop(key, None)
        if entry:
            entry.link.stop()

    def rename(self, key: str, nickname: str):
        nickname = nickname.strip()
        if nickname:
            self._nicknames[key] = nickname
        else:
            self._nicknames.pop(key, None)
        _save_nicknames(self._nicknames)

    def connect_glove(self, key: str, hand: str):
        self._send(key, R.glove("connect", hand))

    def disconnect_glove(self, key: str, hand: str):
        self._send(key, R.glove("disconnect", hand))

    def release(self, key: str):
        self._send(key, R.release())

    def load_scene(self, key: str, index: int):
        self._send(key, R.scene(index))

    def run_command(self, key: str, command_id: str):
        self._send(key, R.command(command_id))

    def recenter(self, key: str):
        self._send(key, R.recenter())

    def start_view(self, key: str):
        self._send(key, R.stream("start"))

    def stop_view(self, key: str):
        self._send(key, R.stream("stop"))

    def _send(self, key: str, line: str):
        with self._lock:
            entry = self._entries.get(key)
            if entry:
                entry.error = None
        if entry and not entry.link.send(line):
            self.on_error(key, "", tr("Not connected to this headset right now."))

    # -- the snapshot ------------------------------------------------------------

    def rows(self) -> list[HeadsetRow]:
        now = time.monotonic()
        with self._lock:
            gone = [e for e in self._entries.values()
                    if not e.manual and e.state != "connected"
                    and now - e.last_heard > FORGET_AFTER_S]
            for e in gone:
                del self._entries[e.key]
            entries = list(self._entries.values())
            rows = []
            for e in entries:
                nickname = self._nicknames.get(e.key, "")
                name = (e.status.name if e.status else None) or \
                       (e.announce.name if e.announce else None) or e.host
                rows.append(HeadsetRow(
                    key=e.key,
                    host=e.host,
                    title=nickname or f"{name} · {_short_id(e.key)}",
                    nickname=nickname,
                    announce=e.announce,
                    status=e.status,
                    link=e.state,
                    error=e.error if e.error and now - e.error_at < ERROR_SHOWN_S else None,
                    manual=e.manual,
                ))
        for e in gone:
            e.link.stop()
        return sorted(rows, key=lambda r: r.title.lower())

    # -- from the network threads ------------------------------------------------

    def _on_announce(self, a: R.Announce, host: str):
        with self._lock:
            entry = self._entries.get(a.id)
            if entry is None:
                entry = _Entry(a.id, host, R.HeadsetLink(a.id, host, a.control, self), manual=False)
                entry.announce = a
                self._entries[a.id] = entry
                start = True
            else:
                start = False
                entry.last_heard = time.monotonic()
                # The same headset with its app restarted, or another HexR app on it: follow
                # the newest session. Two apps signed with the same key share an id, and both
                # announce, so only the newest one may move the link; following every
                # announcement flipped it between the two and it never stayed connected.
                newest = entry.announce is None or a.started_at >= entry.announce.started_at
                if newest:
                    entry.announce = a
                    entry.host = host
        if start:
            entry.link.start()
        elif newest:
            entry.link.retarget(host, a.control)

    def _on_discovery_error(self, message: str):
        self.discovery_error = message

    def on_link(self, key: str, state: str):
        with self._lock:
            if key in self._entries:
                self._entries[key].state = state

    def on_status(self, key: str, status: R.Status):
        with self._lock:
            e = self._entries.get(key)
            if e:
                e.status = status
                e.last_heard = time.monotonic()

    def on_error(self, key: str, request: str, message: str):
        with self._lock:
            e = self._entries.get(key)
            if e:
                e.error = message
                e.error_at = time.monotonic()


def _short_id(key: str) -> str:
    """Headsets of one model share a name ("Quest 3"), so an unnamed one needs something to
    tell it apart: the end of its id, or its address."""
    return key[3:] if key.startswith("ip:") else key[-4:].upper()


# -- nicknames, kept between runs ----------------------------------------------------

def _load_nicknames() -> dict[str, str]:
    try:
        return {str(k): str(v) for k, v in settings.load("headsets.json")
                .get("nicknames", {}).items()}
    except AttributeError:
        return {}


def _save_nicknames(nicknames: dict[str, str]):
    settings.save("headsets.json", {"nicknames": nicknames})
