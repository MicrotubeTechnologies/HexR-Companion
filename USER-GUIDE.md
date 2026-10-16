# HEXR Companion — how to use it

A Windows and macOS app for checking a HEXR glove and feeling what it can do. Connect a
glove, drive any finger, and see what the hardware reports back. No code, no
Unity, no SDK.

Use it to answer three kinds of question:

- **Does this glove work?** Run the Quick test and read the verdicts.
- **What does this setting feel like?** Drive a channel and put your hand in it.
- **Why is this one weak?** Watch the live pressure while it fires.

> **This is a test tool, not a runtime.** It is for checking hardware and
> feeling effects by hand. To *build* something with HEXR you integrate the
> `com.microtube.hexr` Unity package or the Python library — the glove does not
> need this app to work with your application.

---

## Install

Download **`HexR-Companion-Setup.exe`** from the
[latest release](https://github.com/MicrotubeTechnologies/HexR-Companion/releases/latest)
and run it.

- Windows 10 or 11, 64-bit
- Bluetooth Low Energy — built into most laptops, or any USB BLE dongle
- Installs for you only. It never asks for an administrator password.

**Windows will warn you the first time.** The build is not code signed, so
SmartScreen shows *"Windows protected your PC"*. Choose **More info → Run
anyway**. Nothing is wrong; an unsigned installer simply has no certificate for
Windows to check.

You get a **HEXR Companion** icon on your desktop and in the Start menu.

Until version 0.4.0 the app was called **HEXR Window Tester**. If you have it,
installing HEXR Companion replaces it: the old icons go and the new ones take
their place.

---

### On a Mac

Download **`HexR-Companion-Mac.pkg`**, double-click it, and click through
the installer (**Continue → Install**). It installs **HEXR Companion**
into Applications; open it from there or from Launchpad.

- macOS 10.13 or newer, on Apple silicon or Intel
- The first time you press **Scan for gloves**, macOS asks whether the app may
  use Bluetooth. Choose **Allow** — without it the app cannot see the glove. If
  you clicked *Don't Allow*, turn it back on in System Settings → Privacy &
  Security → Bluetooth.

As on Windows, do not pair the glove in the Mac's Bluetooth settings. A
**HEXR Window Tester** left in Applications from before is the same app under
its old name; move it to the Bin.

---

## Before you start

You need the glove and its arm module, charged.

1. Attach the glove to the arm module — the connector is magnetic and guides
   itself in. **Left glove to left module, right to right.** If the connector
   pushes back at you, you have mismatched sides; the magnets are reversed
   between hands on purpose so you cannot connect the wrong pair.
2. Strap the arm module to your wrist.
3. **Press and hold** the power button on the arm module until the light comes
   on. Green is fully charged, blue is between 30% and 90%, red means swap or
   charge the pack.

You do **not** pair the glove in Windows Bluetooth settings. Leave those alone
— the app makes its own connection.

---

## Two places: Test and Headsets

The rail on the left has two entries. **Test** is this computer's own gloves,
over its Bluetooth. **Headsets** is the HEXR headsets on the network, at an
event. Everything below up to Safety is Test.

## Test · connecting a glove

Open **Test**. Until a glove is connected it is the scan: press
**Scan for HEXR**. Gloves appear as `HaptGloveAR Left` or `HaptGloveAR Right`,
and the app reads which hand it is from that name.

Press **Connect** on the row you want. The moment a glove connects, Test turns
into the controls below.

You can connect **both gloves at once**. They are separate devices and
everything after this treats them separately. To connect the second one, check
a glove's battery or disconnect it, press **Gloves** at the top right while
testing. It opens over Test; **Close** goes back.

**Nothing found?** The arm module is probably not switched on — press and hold
the power button and scan again. If the status says *Bluetooth unavailable*,
that is your PC's adapter, not the glove.

---

## Test · driving channels

This is where you feel things.

**Pick a hand.** Left, right, or both. A glove that is not connected cannot be
selected.

**Pick channels.** Thumb, Index, Middle, Ring, Pinky and Palm are the six
things a HEXR glove can drive. Use **Select all** for all six or **None** to
clear them.

**Pick a mode:**

| Mode | What it feels like |
|---|---|
| **Pressure** | A steady squeeze that holds until you release it |
| **Vibration** | An oscillation — buzzing, tapping or pulsing depending on frequency |

**Set the levels**, then press **Trigger**. Press **Release** to vent.

Nothing switches itself off. A channel you triggered stays inflated until you
release it, close the app, or hit the panic control below.

### The settings, and what they actually change

**Intensity** (0.1 – 1.0) is how hard it squeezes. The app shows you the real
target next to the slider, in kPa. Below 15 kPa the glove treats a channel as
off, and it will not go above 50 kPa — so the useful range really is that
slider, end to end.

**Ramp speed** (pressure mode) is how fast it gets there, not how hard. At 1.0
it snaps; at 0.1 it swells slowly. Two very different sensations at the same
intensity — worth trying before you decide a preset feels wrong.

**Frequency** (vibration mode) is the one that changes the *character* of the
sensation, and there is a hard boundary in the hardware at **5 Hz**:

| Frequency | What the glove does | What it feels like |
|---|---|---|
| Under 5 Hz | Pulses the air pressure itself | Slow, deep, physical — a heartbeat or a knock |
| 5 Hz and above | Drives the channel's motor directly | Fast buzz — texture, alerts, engine hum |

These are two different mechanisms, not one scale. The app tells you which one
is running underneath the frequency slider. If a vibration setting feels
nothing like you expected, check which side of 5 Hz you are on.

**Peak ratio** (vibration mode, 0.2 – 0.8) is how much of each cycle is "on".
Low is a short sharp tick; high is a longer swell. This is what separates a tap
from a throb at the same frequency.

### Feeling effects quickly

Some starting points worth trying with the glove on:

| To feel | Mode | Settings |
|---|---|---|
| Gripping a solid object | Pressure | All channels, intensity 1.0, speed 1.0 |
| Something soft giving way | Pressure | All channels, intensity 0.4, speed 0.15 |
| A heartbeat | Vibration | Palm, ~1 Hz, intensity 0.7, peak ratio 0.35 |
| A light tap on one finger | Vibration | Index, ~3 Hz, intensity 0.5, peak ratio 0.2 |
| Texture / roughness | Vibration | Fingertips, 20–30 Hz, intensity 0.5 |
| A buzzing alert | Vibration | All, 35 Hz, intensity 1.0, peak ratio 0.6 |

> **Named effect presets — heartbeat, fountain, raindrops — are not in this
> version.** They exist in the Unity package as authored effects. This app
> gives you the raw controls those effects are built from, so you can dial in
> something close by hand.

### The live monitor

The right-hand panel shows what the glove is reporting: pressure per channel,
battery, and the source pressure feeding all of it.

**If those readings stay empty, that is not a fault.** Some gloves stream
telemetry and some do not, and haptics work either way. It only matters for the
Quick test, which needs the readings to measure anything.

---

## Quick test

The pass/fail check. Use it on a glove coming off the bench, or one back from a
customer. Press **Quick test** at the top right while testing; **Close** goes
back to Test, and closing it in the middle of a run stops the run and vents the
glove.

**Take the glove off first.** It drives all six channels to full at once.

Press **Run quick test**. It vents everything, drives all six channels hard for
two seconds, and reports what each one reached:

| Verdict | Peak reached | Meaning |
|---|---|---|
| **Good** | Above 40 kPa | Full pressure |
| **Poor** | 2 – 40 kPa | Moved, but never got to full — check the tubing |
| **Fail** | Under 2 kPa | Not working |

The failure line sits at 2 kPa rather than at zero because the sensor on a dead
channel floats on noise instead of reading a clean 0.0.

**If the source never develops pressure**, every channel reads Fail for one
reason — a dead pump. The summary says so once rather than blaming six
channels, so don't go replacing indenters.

Quick test needs telemetry. If the glove is not reporting, the app will say so
rather than invent numbers.

---

## The window

The title bar carries the usual three controls at the top right: **minimise**,
**maximise** and **close**. Maximise fills the monitor the window is on, up to
the taskbar, and the same button restores it to exactly where it was. A
double-click anywhere on the title bar does the same thing, and dragging a
maximised window pulls it loose under the cursor.

Drag the bar to move the window. There is no OS frame — the app draws its own.

**English | 中文**, at the bottom of the left rail just above the version,
switches the whole app between English and Simplified Chinese. The app
remembers the choice the next time it opens.

---

## Headsets

At an event, the headsets running a HEXR app can be looked after from here
without taking one off anyone: connect and disconnect their gloves, recenter
the wearer, change the scene, run the app's own commands, and watch what the
wearer sees.

A headset shows up when its app was built with **HexR 0.10.0 or newer with
HexR Remote added**, it is on the **same network** as this computer, and the
app is open. It reports *asleep* while nobody is wearing it, and then refuses
commands until someone puts it on.

Press **Open** on a headset to see its gloves, its scene and its view.

- **Gloves** — Connect or Disconnect each one. The headset does the connecting,
  over its own Bluetooth. A glove talks to one thing at a time, so if this
  computer (or a phone) has it, disconnect it there first.
- **Scene** — pick one and the headset switches to it.
- **Recenter** — puts the wearer back on the scene's starting spot, facing its
  front, for someone who has wandered off or was handed the headset facing the
  wrong way. Works on Quest and PICO alike. The app needs **HexR 0.11.0 or
  newer**; on an older one the button is greyed out.
- **Watch** — the wearer is asked in the headset to allow sharing their view;
  once they do, it appears here. **Stop watching** leaves the view running for
  anyone else still watching it.
- **Name** — call a headset *Station 1* or similar. Headsets of one model all
  report the same name, so this is how you tell them apart. The name is kept on
  this computer.

**No headsets appear?** The first time you open Headsets, Windows asks whether
to allow the app on networks: allow it on **private** networks, and make sure
the Wi-Fi is set to *Private* in Windows settings. Event Wi-Fi often stops
devices seeing each other; type the headset's IP address into
**Headset address** and press **Add** instead, or bring your own router.

On a Mac the Headsets screen controls headsets but cannot show their view yet.

---

## Safety

A haptic glove can hold a finger squeezed. Three ways to stop everything:

- **Escape** — works anywhere in the app
- **All off** — the red button beside Trigger and Release on the Test screen
- **Close the app** — every channel is vented on the way out

Channels are also vented automatically when you disconnect a glove.

If the app is closed or crashes while something is inflated, powering the arm
module off releases it.

---

## When something is wrong

| What you see | What it means |
|---|---|
| Scan finds nothing | The arm module is off, or out of range. Press and hold the power button. |
| *Bluetooth unavailable* | Your PC's Bluetooth is off or has no adapter — not a glove problem. |
| Connects, then drops | Usually a low battery. Check the light on the module; red means swap the pack. |
| Connects but no pressure readings | Normal on some gloves. Haptics still work; only Quick test is affected. |
| Trigger does nothing | Check a channel is selected, and that the hand you are driving is the one connected. |
| Wrong finger responds | Tell us — that is a channel mapping problem worth knowing about. |
| The connector pushes back | Mismatched sides. Left glove needs the left module. |
| SmartScreen warning on install | Expected — the build is not signed. **More info → Run anyway**. |

Anything the app cannot explain, `tools/probe_glove.py` in the source will dump
exactly what the glove exposes and sends. Run it with the app closed.

---

## What it does not do

- It does not track your hand. HEXR provides touch; hand tracking comes from a
  headset or an external tracker.
- It does not record or export sessions.
- It does not carry the authored effect presets from the Unity package.
- It is not needed to use HEXR in an application.
