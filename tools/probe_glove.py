"""Diagnostic: what does the glove actually expose, and what does it send?

Run this when the app says "Connected · no telemetry" — it answers the three
questions that state can mean, in order:

  1. Is the characteristic we subscribe to the one that actually notifies?
  2. Does subscribing alone start the stream, or does the glove need a poke?
  3. Are frames arriving but failing to decode?

    python tools/probe_glove.py                 # scan, pick the first glove
    python tools/probe_glove.py --hand Left
    python tools/probe_glove.py --address AA:BB:CC:DD:EE:FF
    python tools/probe_glove.py --seconds 20

Close HEXR Companion first. A BLE peripheral generally accepts one connection,
so the app holding the glove is itself a reason a second connect sees nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hexr import protocol as P  # noqa: E402

NOTIFY_WINDOW_S = 4.0     # how long to wait for unprompted data


def _props(char) -> str:
    return ",".join(char.properties)


async def probe(address: str | None, hand: str | None, seconds: float):
    from bleak import BleakClient, BleakScanner

    if not address:
        print(f"Scanning {P.NAME_PREFIX}… ", end="", flush=True)
        found = []
        devices = await BleakScanner.discover(timeout=8.0, return_adv=True)
        for dev, adv in devices.values():
            name = dev.name or adv.local_name or ""
            h = P.hand_from_name(name)
            if h and (hand is None or h == hand):
                found.append((dev.address, name, h, adv.rssi))
        if not found:
            print("nothing found.")
            print("\nThe glove is not advertising. Check the arm module is "
                  "powered on, and that HEXR Companion is not already connected "
                  "to it.")
            return 1
        print(f"found {len(found)}")
        for a, n, h, r in found:
            print(f"   {n:22s} {a}  {r} dBm")
        address, name, hand, _ = found[0]
        print(f"\nUsing {name} at {address}")

    print("\nConnecting…")
    async with BleakClient(address) as client:
        print(f"connected: {client.is_connected}")

        # 1. The GATT table, as the device actually presents it.
        print("\n--- services and characteristics " + "-" * 40)
        target = None
        notifiable = []
        for service in client.services:
            print(f"service {service.uuid}")
            for ch in service.characteristics:
                mark = ""
                if ch.uuid.lower() == P.CHAR_UUID.lower():
                    mark = "   <-- the one the app uses"
                    target = ch
                print(f"    char {ch.uuid}  [{_props(ch)}]{mark}")
                if "notify" in ch.properties or "indicate" in ch.properties:
                    notifiable.append(ch)
                for d in ch.descriptors:
                    print(f"        descriptor {d.uuid}")

        if target is None:
            print(f"\n!! {P.CHAR_UUID} is NOT present on this device.")
            print("   That alone explains 'no telemetry' — the app is "
                  "subscribing to something that does not exist here.")
        elif "notify" not in target.properties:
            print(f"\n!! {P.CHAR_UUID} exists but does not advertise notify.")
            print(f"   Its properties are: {_props(target)}")

        # 2. Subscribe to everything that can notify, and see what arrives.
        counts: dict[str, int] = {}
        first_bytes: dict[str, bytes] = {}
        decoder = P.FrameDecoder()

        def make_cb(uuid: str):
            def cb(_h, data: bytearray):
                counts[uuid] = counts.get(uuid, 0) + 1
                first_bytes.setdefault(uuid, bytes(data))
                if uuid.lower() == P.CHAR_UUID.lower():
                    decoder.feed(bytes(data))
            return cb

        print(f"\n--- subscribing to {len(notifiable)} characteristic(s) "
              + "-" * 26)
        for ch in notifiable:
            try:
                await client.start_notify(ch, make_cb(ch.uuid))
                print(f"    subscribed {ch.uuid}")
            except Exception as e:
                print(f"    FAILED     {ch.uuid}: {e}")

        print(f"\nListening {NOTIFY_WINDOW_S:.0f}s with no commands sent…")
        await asyncio.sleep(NOTIFY_WINDOW_S)
        unprompted = dict(counts)
        print(f"    notifications so far: {sum(unprompted.values())}")

        # 3. If nothing came, poke it. A release-all is the safest command
        #    there is: it vents every channel and inflates nothing.
        if not unprompted:
            print("\nNothing yet — sending an all-off to see if the glove "
                  "only streams once addressed.")
            for response in (True, False):
                try:
                    await client.write_gatt_char(P.CHAR_UUID, P.all_off(),
                                                 response=response)
                    print(f"    write (response={response}) accepted")
                except Exception as e:
                    print(f"    write (response={response}) FAILED: {e}")
                await asyncio.sleep(1.5)
                if counts:
                    print(f"    -> data started after the write "
                          f"(response={response})")
                    break

        remaining = max(0.0, seconds - NOTIFY_WINDOW_S)
        if remaining:
            print(f"\nListening a further {remaining:.0f}s…")
            await asyncio.sleep(remaining)

        # -- verdict ---------------------------------------------------------
        print("\n--- what arrived " + "-" * 55)
        if not counts:
            print("NOTHING. Not one notification on any characteristic.")
            print("\nThat rules out a decoding bug — no bytes reached us at "
                  "all. The cause is on the link or the device: wrong "
                  "characteristic, a firmware build that does not stream, or "
                  "the glove needing something else before it starts.")
        else:
            for uuid, n in sorted(counts.items()):
                head = first_bytes[uuid][:24].hex(" ")
                mine = "  <-- app's characteristic" if uuid.lower() == P.CHAR_UUID.lower() else ""
                print(f"{uuid}  {n:5d} notifications{mine}")
                print(f"    first bytes: {head}")

            t = decoder.telemetry
            print("\n--- decoded " + "-" * 61)
            print(f"bad frames        : {decoder.bad_frames}")
            print(f"battery           : {t.battery}")
            print(f"pressure (raw)    : "
                  f"{[round(v, 2) for v in t.pressure_raw]}")
            print(f"finger position   : {t.finger_position}")
            if t.seen:
                absolute = P.looks_like_absolute_pa(t.pressure_raw)
                print(f"\nUNITS: this glove reports "
                      f"{'ABSOLUTE PASCALS' if absolute else 'GAUGE kPa'}.")
                print("       as gauge kPa: "
                      f"{[round(P.raw_to_kpa(v), 1) for v in t.pressure_raw]}")
            else:
                print("\nBytes arrived but nothing decoded — the frame layout "
                      "does not match. The raw bytes above are what to compare "
                      "against hexr/protocol.py.")

        for ch in notifiable:
            try:
                await client.stop_notify(ch)
            except Exception:
                pass
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--address", help="connect straight to this BLE address")
    ap.add_argument("--hand", choices=("Left", "Right"))
    ap.add_argument("--seconds", type=float, default=10.0,
                    help="total listen time (default 10)")
    a = ap.parse_args()
    try:
        return asyncio.run(probe(a.address, a.hand, a.seconds))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
