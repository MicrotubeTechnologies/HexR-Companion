# HEXR Companion

A Windows and macOS app for testing HEXR haptic gloves. Connect a left and/or right
glove, pick fingers and trigger them, see each finger's air pressure against what
it is set to, and run a pass/fail sweep on all six channels.

**This is a test and diagnostic tool, not a runtime.** To *build* with HEXR you
integrate the [`com.microtube.hexr`](https://github.com/MicrotubeTechnologies/com.microtube.hexr)
Unity package or the Python control library — the glove needs no app of its
own and does not pair through Windows Bluetooth settings. This app opens its
own connection, the same way your application will.

Until 0.4.0 it was called HEXR Window Tester, and the repository still carries
that name. It replaces the Unity version (`PneuClutch v1.0`) that lives on the
`New-Version` branch. Same job, no game engine.

---

## Install

Download `HexR-Companion-Setup.exe` from the
[latest release](https://github.com/MicrotubeTechnologies/HexR-Companion/releases/latest).

- Windows 10 or 11, 64-bit
- Bluetooth Low Energy — built in, or any USB BLE dongle
- Installs for your user only. No admin rights, no UAC prompt.

The build is not code signed, so SmartScreen will warn the first time: choose
**More info → Run anyway**. Every release publishes SHA-256 sums and GitHub
build provenance so the download can be verified.

### macOS

Download `HexR-Companion-Mac.pkg`, double-click it, and follow the
installer. It puts **HEXR Companion** in Applications.

- macOS 10.13 or newer, Apple silicon or Intel (one universal app)
- The first time it looks for gloves macOS asks for Bluetooth access — choose **Allow**. If it was
  denied, re-enable it in System Settings → Privacy & Security → Bluetooth.

On macOS the app uses the native window frame (close and minimise are the
traffic lights), and Cmd-Q vents every channel before quitting, the same as
closing the window.

## Run from source

```
pip install -r requirements.txt
python hexr_tester.py
```

Python 3.10 or newer. The only runtime dependency is `bleak`.

---

## Using it

Three entries in the rail: **Test** for this computer's own gloves, **Headsets**
for HEXR headsets on the network, and **Recordings** for what was recorded from
them.

**Test** — until a glove connects it shows a left and a right glove, dimmed, and
searches on its own: power on the arm module and press **Connect** when it is
found. Gloves advertise as `HaptGloveAR Left` / `HaptGloveAR Right`; hand is
read from that name. Both connect independently and can be driven at once. Once
one connects, Test is the controls: pick the fingers to drive (tick them in the
list, or tap them on the glove picture), pick pressure or vibration and the
intensity, and press **Trigger**; **Release all** vents them. Each finger's row
shows the air pressure the glove measures against where it is set to go, and
grows when the window is maximised, so a weak channel is visible rather than
something you have to feel for. **Quick test**, in Test's title row, drives
all six channels to full for two seconds and colours the glove by verdict (take
the glove off first). The gloves button at the top right of every screen shows
which gloves are connected and the battery, and opens a panel to connect the
other glove or disconnect one.

Every screen keeps its numbers (kPa, addresses, dBm, versions) behind **ⓘ
Details** in its title row, off by default and remembered per screen.
**Help** in the rail opens [USER-GUIDE.md](USER-GUIDE.md).

**Headsets** — every headset running a HEXR app with HexR Remote (HexR 0.10.0
or newer) on the same network: watch its view once the wearer allows it, with a
panel per glove beside it that lights up as the glove fires and shows whether
it is connected (click a panel to connect or disconnect it), recenter the
wearer, and record. The protocol is `Documentation~/RemoteProtocol.md` in the
com.microtube.hexr package, the same one the Android app's Headsets tab speaks.
The view needs PyAV, which only the Windows build ships.

**Recordings** — a recording is the view as it came and what the gloves did,
frame by frame. Export makes it a video in landscape (1920×1080) or portrait
(1080×1920), the view with its gloves beside it, or the view alone. The Recordings
screen plays a recording in the shape picked before it is exported.

**Escape is the panic key**, and **Release all** sits beside Trigger on the Test
screen; a triggered finger stays on until one of them.
All channels are also vented on disconnect, on exit, and when the Quick test
panel is closed mid-run.

**English | 中文** at the bottom of the rail, above the version, switches the
whole app between English and Simplified Chinese, and the choice is remembered.

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
runs PyInstaller, compiles the installer to `Installer\HexR-Companion-Setup.exe`,
and zips a portable build.

Or let CI do it: push a `v*` tag and
`.github/workflows/build-windows.yml` builds, checksums, attests and publishes
the release. `VERSION` is the single source of truth — CI overwrites it from
the tag, and the app footer, exe properties and installer all read it.

The installer filename deliberately carries no version: GitHub resolves
`/releases/latest/download/<name>` by exact asset name, so a version in the
name would break that permalink on every release.

---

## Building for macOS

```
tools/build_mac.sh
```

Builds a universal app with PyInstaller (same spec as Windows), signs it with
the hardened runtime, wraps it in a signed installer at
`dist/HexR-Companion-Mac.pkg`, notarizes it with Apple and staples the
ticket. That `.pkg` is the file to upload to the website. Like the Windows installer, the filename carries no version, so the
download link can stay the same from release to release.

One-time setup on the build Mac:

1. **Python from python.org** (the universal2 installer). Homebrew's Python
   produces an arm64-only app that will not start on macOS older than the
   build machine.
2. **Developer ID Application and Developer ID Installer certificates.** The
   Apple Developer account holder creates both in Xcode → Settings → Accounts
   → *team* → Manage Certificates → `+`. The first signs the app, the second
   the installer. Check with `security find-identity -v`.
3. **Notarization credentials.** Make an app-specific password at
   account.apple.com (Sign-In and Security), then:

   ```
   xcrun notarytool store-credentials hexr-notary \
     --apple-id <email> --team-id <TEAM_ID> --password <app-specific-password>
   ```

`tools/build_mac.sh --no-notarize` makes a local test build without the
certificate; it runs only on the Mac that built it.

## Layout

```
hexr_tester.py        entry point; owns the 20 Hz UI tick
hexr/
  protocol.py         frame building and decoding — no I/O, fully testable
  engine.py           BLE: one asyncio loop, one client per hand
  state.py            the model the UI polls
  remote.py           HexR Remote: discovery, control links, video, no Tk
  headsets.py         the Headsets screen's model of every headset
  haptics.py          what each headset's gloves are doing, moment by moment
  overlay.py          the HEXR glove, lit as it fires, drawn with PIL
  gloveview.py        that glove as a Tk widget: tap a finger, see it light
  viewer.py           the view beside its gloves: landscape, portrait or square
  recorder.py         the view as it came, and what the gloves did, recorded
  exporter.py         a recording made into a video in the shape wanted
  player.py           a recording played back as it will be exported
  theme.py            design tokens
  widgets.py          the Canvas widget library
  shell.py            frameless window, title bar, nav rail, language switch
  i18n.py             English and Simplified Chinese: tr() and the Chinese table
  settings.py         what is kept between runs: headset names, the language, Details
  screens/            connect · test · quicktest · headsets · fullview · recordings
tests/                protocol, remote, overlay, glove and language tests, no hardware needed
packaging/            Inno Setup script and wizard art
tools/make_icon.py    generates the app icon
tools/fake_headset.py a pretend headset, for trying the Headsets screen without
                      a Quest: video, glove status and haptics on this computer
tools/ui_snapshots.py screenshots of every screen in English or Chinese, with pretend
                      gloves and a pretend headset, and a check that each fits
```

`theme.py`, `widgets.py`, `shell.py` and `screens/base.py` are shared in spirit
with [FLEXR Controller](https://github.com/MicrotubeTechnologies/FlexR_Keyboard)
— the same design system, copied rather than packaged. A fix worth having in
both has to be applied in both.
