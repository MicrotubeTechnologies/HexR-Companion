# HEXR Window Tester

A Windows app for testing HEXR haptic gloves. Scan, connect a left and/or right
glove, drive any channel, watch what the hardware reports back, and run a
pass/fail sweep on all six channels.

**This is a test and diagnostic tool, not a runtime.** To *build* with HEXR you
integrate the [`com.microtube.hexr`](https://github.com/MicrotubeTechnologies/com.microtube.hexr)
Unity package or the Python control library — the glove has no companion app
and does not pair through Windows Bluetooth settings. This app opens its own
connection, the same way your application will.

It replaces the Unity version (`PneuClutch v1.0`) that lives on the
`New-Version` branch. Same job, no game engine.

---

## Install

Download `HexR-Window-Tester-Setup.exe` from the
[latest release](https://github.com/MicrotubeTechnologies/HexR-Companion/releases/latest).

- Windows 10 or 11, 64-bit
- Bluetooth Low Energy — built in, or any USB BLE dongle
- Installs for your user only. No admin rights, no UAC prompt.

The build is not code signed, so SmartScreen will warn the first time: choose
**More info → Run anyway**. Every release publishes SHA-256 sums and GitHub
build provenance so the download can be verified.

## Run from source

```
pip install -r requirements.txt
python hexr_tester.py
```

Python 3.10 or newer. The only runtime dependency is `bleak`.

---

## Using it

**01 Connect** — power on the arm module, press scan. Gloves advertise as
`HaptGloveAR Left` / `HaptGloveAR Right`; hand is read from that name. Both
connect independently and can be driven at once.

**02 Test** — pick channels, pick pressure or vibration, set the levels, and
trigger. Release vents them. The right-hand panel shows live per-channel
pressure and battery straight from the glove, so a weak channel is visible
rather than something you have to feel for.

**03 Quick test** — drives all six channels to full for two seconds, records
peak pressure and time-to-peak, and judges each channel. Take the glove off
first.

**Escape is the panic key**, and the header's **All off** button works from
every screen. All channels are also vented on disconnect and on exit.

---

## How it talks to the glove

| | |
|---|---|
| Service | `000000ff-0000-1000-8000-00805f9b34fb` |
| Characteristic | `0000ff01-0000-1000-8000-00805f9b34fb` (write + notify) |
| Names | `HaptGloveAR Left`, `HaptGloveAR Right` |

Outbound frames are `[len][opcode][TLV…]` with no checksum; inbound frames add
a trailing XOR byte. `hexr/protocol.py` has the full layout, and
`tests/test_protocol.py` pins it to reference frames taken from the firmware
and the shipped Unity plugin.

```
python tests/test_protocol.py
```

Two things worth knowing before changing anything here:

- **State byte 1 ("stay") is a no-op.** Only 0 (apply) and 2 (release) do
  anything.
- **Telemetry is not required for actuation.** Reading the firmware suggests
  otherwise — the 50 Hz notify timer also feeds the pressure loop — but gloves
  in hand actuate perfectly well having sent nothing back (confirmed on
  hardware). Subscribe anyway, because the pressure readout and the QA sweep
  need it, but do not treat silence as a fault.

### Pressure units are still unsettled

The firmware comments its pressure values as gauge kPa; the Unity editor
tooling converts them as though they were absolute pascals; the old Unity test
app printed the raw number as kPa with no conversion. Those cannot all be
right. `protocol.raw_to_kpa()` detects which convention a glove is using — a
glove at rest reads near 0 for gauge kPa and near 100000 for absolute pascals —
so the readout is correct either way, and the Test screen says so when it sees
absolute values. **Confirm against real hardware before trusting the Quick Test
thresholds**, which came from the Unity app and assume the reading is kPa.

---

## Building the installer

```
BUILD-INSTALLER.bat
```

Finds Python and Inno Setup (offering to install either), regenerates the icon,
runs PyInstaller, compiles the installer to `Installer\HexR-Window-Tester-Setup.exe`,
and zips a portable build.

Or let CI do it: push a `v*` tag and
`.github/workflows/build-windows.yml` builds, checksums, attests and publishes
the release. `VERSION` is the single source of truth — CI overwrites it from
the tag, and the app footer, exe properties and installer all read it.

The installer filename deliberately carries no version: GitHub resolves
`/releases/latest/download/<name>` by exact asset name, so a version in the
name would break that permalink on every release.

---

## Layout

```
hexr_tester.py        entry point; owns the 20 Hz UI tick
hexr/
  protocol.py         frame building and decoding — no I/O, fully testable
  engine.py           BLE: one asyncio loop, one client per hand
  state.py            the model the UI polls
  theme.py            design tokens
  widgets.py          the Canvas widget library
  shell.py            frameless window, title bar, nav rail
  screens/            connect · test · quicktest
tests/                protocol tests, no hardware needed
packaging/            Inno Setup script and wizard art
tools/make_icon.py    generates the app icon
```

`theme.py`, `widgets.py`, `shell.py` and `screens/base.py` are shared in spirit
with [FLEXR Controller](https://github.com/MicrotubeTechnologies/FlexR_Keyboard)
— the same design system, copied rather than packaged. A fix worth having in
both has to be applied in both.
