# HEXR Companion for Android

The desktop HEXR Companion as a phone app: the same glove on screen, the same words, the
same wire protocol and the same quick-test verdicts, so a glove that passes on a bench
laptop passes here, and a result recorded on either means the same thing. Two tabs: Test,
for this phone's own gloves over Bluetooth, and Headsets, to watch a HEXR headset's view
live with its gloves lighting up beside it. English and Chinese.

How to use it: **[USER-GUIDE.md](USER-GUIDE.md)**, which the app's Help opens.

Built with Kotlin and Jetpack Compose, talking to the glove over Android's own
Bluetooth LE stack.

---

## Getting the APK

**You do not need Android Studio.** GitHub builds it.

- **Any build:** push to this branch, open the repository's **Actions** tab,
  pick the newest *Build Android APK* run and download the `HexR-Companion-APK`
  artifact.
- **A release:** tag it.

  ```
  git tag android-v0.2.0 && git push origin android-v0.2.0
  ```

  That publishes a GitHub Release with the APK, its SHA-256, and notes.

The tag stream is deliberately separate from the desktop app's. A `v*` tag
builds the Windows installer; an `android-v*` tag builds the APK. One shared tag
would have both workflows racing to create the same release.

### Installing it

Open the `.apk` on the phone. Android asks you to allow installs from your
browser or file manager the first time — expected for anything not from the Play
Store.

The APK is a **debug** build, signed with the standard Android debug key. That
is on purpose: it sideloads with no keystore, no secret in this repository and
no Play Store account.

It installs as `com.microtube.hexr.tester.debug`, one letter different from the
Play build's `com.microtube.hexr.tester`. That is deliberate — the two are
signed with different keys and Android will not install one over the other, so
they are kept as separate apps rather than as an upgrade that always fails. Both
appear in the launcher under the same name and icon; the build line under
Details on the Connect screen (or the Gloves panel) is what tells them apart.

### Getting it from the Play Store instead

The same code also builds as a signed Android App Bundle for Google Play, under
the package name `com.microtube.hexr.tester`. That route, the upload key and the
Console paperwork are all in **[PLAY-RELEASE.md](PLAY-RELEASE.md)**.

The two routes cannot share a phone: same package name, different signing key,
so Android refuses to install one over the other. Uninstall first.

### Building locally

Android Studio (Ladybug or newer) opens the `android/` directory directly and
supplies its own Gradle. From a terminal you need JDK 17, an Android SDK, and
Gradle 8.11+:

```
cd android
gradle assembleDebug          # app/build/outputs/apk/debug/app-debug.apk
gradle testDebugUnitTest      # the protocol suite
gradle bundleRelease          # the Play bundle; needs an upload key
```

There is no Gradle wrapper committed. The wrapper exists to pin a Gradle
version, and the workflow pins it in one visible line instead — without a binary
jar in the tree that nobody reviews.

---

## What is different from the desktop app

Everything you can *do* is the same. What changed is underneath.

### The protocol is implemented twice

`Protocol.kt` is a port of `hexr/protocol.py`. Two copies of one wire format can
drift, so `ProtocolTest.kt` is a port of `tests/test_protocol.py` carrying the
same reference frames — including the byte-for-byte
`12 04 09 00 00 00 00 01 01 01 00 09 00 00 48 42 01 64`. CI runs it before it
builds the APK. If the two languages ever disagree about what a frame looks
like, a suite goes red rather than a glove quietly ignoring the phone.

**If you change the wire format, change it in both places.**

### The MTU has to be negotiated

This is the one thing the desktop app never had to think about, and the reason a
naive port does not work.

A BLE connection carries `MTU - 3` bytes per write, and the MTU is 23 until you
ask for more — 20 usable bytes. `Protocol.allOff()` is **108 bytes**: six
18-byte frames. So is the quick test's six-channel drive burst. Neither fits.

Bleak papers over this on the desktop. Android does not, so `BleEngine`:

1. requests MTU 247 on connect, before discovering services;
2. if the glove grants less, splits the batch back into whole frames and packs
   as many as fit into each write.

Frames are self-delimiting by their length byte, so the glove cannot tell the
difference — the same bytes arrive, just over several writes. A frame is never
split across writes, which would desynchronise the firmware's parser instead of
merely being slow.

The Gloves panel shows the negotiated MTU, and says so when a glove kept a
small one. It matters for the quick test specifically: split writes mean the six
channels no longer start at exactly the same instant, which is part of what that
test measures.

### GATT operations are serialised

Android silently drops a write issued while another is outstanding. Every write
goes through a per-glove queue that waits for `onCharacteristicWrite` before
sending the next, still honouring the desktop's 100 ms inter-write gap.

The queue has a 2-second watchdog on each write. A write that never calls back
would otherwise stall the queue forever — including, quite possibly, an all-off
sitting behind it.

### It vents when it leaves the screen

`onStop` sends all-off to every connected glove.

A phone gets pocketed mid-test in a way a laptop window does not, and a channel
left inflated presses on someone's hand until the battery dies. Costing a
technician one re-trigger is much the cheaper mistake.

Release all also happens on Back while anything is on, and on leaving the Test tab:
Release all is on that tab only, so a drive must not outlive it.

### Permissions

Android 12+ asks for *Nearby devices* (`BLUETOOTH_SCAN` + `BLUETOOTH_CONNECT`).
Android 11 and below ask for location instead, because that is how the platform
gated BLE scanning before the dedicated permissions existed.

The scan is declared `neverForLocation`, so on modern Android the app never asks
for location at all. It only ever reads the glove's advertised name.

---

## Layout

```
android/
  app/src/main/java/com/microtube/hexr/
    Protocol.kt          port of hexr/protocol.py — pure, no I/O
    Model.kt             port of hexr/state.py
    BleEngine.kt         GATT: queue, MTU, two concurrent gloves
    HexrViewModel.kt     UI state, and the quick-test state machine
    MainActivity.kt      Test and Headsets tabs, header, panels, language,
                         permission flow, vent-on-stop
    HeadsetsViewModel.kt the Headsets tab's state: links, watching, recenter
    QuickTest.kt         the quick test's verdicts and words (screens/quicktest.py)
    TestSettings.kt      pressure or vibration, intensity, frequency
    GloveSearch.kt       which gloves were heard, strongest first
    I18n.kt, I18nZh.kt   tr() and its Chinese (hexr/i18n.py)
    DemoSeed.kt          canned state for the store screenshots, debug only
    glove/               the glove picture's geometry and states (hexr/overlay.py)
    remote/              HexR Remote: protocol, link, video, haptics timeline
                         (hexr/haptics.py), cast layout (hexr/viewer.py)
    ui/Theme.kt          tokens transcribed from hexr/theme.py
    ui/Controls.kt       buttons, sticky bar, segmented, sliders, chips
    ui/GloveArt.kt       the orange glove, drawn and tapped
    ui/PressureList.kt   each finger's pressure against where it is set to go
    ui/ConnectScreen.kt  Test with no glove yet, and the Gloves panel
    ui/TestScreen.kt     the Test tab once a glove is connected
    ui/QuickTestScreen.kt the Quick test panel
    ui/HeadsetsScreen.kt the Headsets tab's list
    ui/HeadsetLive.kt    one headset live: the view, its gloves, the controls
  app/src/test/java/com/microtube/hexr/
    ProtocolTest.kt      port of tests/test_protocol.py, and the other ports' tests
    I18nTest.kt          every tr() sentence has its Chinese
  keystore.properties.example   shape of the gitignored signing config
  PLAY-RELEASE.md               shipping it to Google Play
  PRIVACY.md                    source text for the published privacy policy
  play/
    listing.md                  every Play Console field, written out
    icon-512.png                Play's hi-res icon
    feature-graphic-1024x500.png
    screenshots/phone/          1080x1920, in upload order
```

The store graphics are generated by `tools/make_play_assets.py` from the same
path data as the launcher icon, and the screenshots are captured from a debug
build seeded by `DemoSeed.kt` — see `play/listing.md` for how.

The version comes from the repository's top-level `VERSION` file, the same one
the desktop installer reads, so the two apps can never claim different versions
of one release.

---

## Not carried over

- **Ramped vibration** (`vibrationRamped`) is implemented in `Protocol.kt` and
  tested, but no screen exposes it. Neither does the desktop app.
- **Bundled fonts.** The desktop ships IBM Plex; this uses the system font, with
  monospace for anything the glove reported. The one font it carries is Archivo Black,
  for the caption under the glove (PRESS. HOLD. RELEASE.), as the desktop draws it.
- **Recording and export.** The desktop records a headset's cast to a video; the phone
  only watches it live.
- **Window chrome.** The custom title bar and left rail are a desktop idea; the
  phone gets a header and a bottom tab bar.
