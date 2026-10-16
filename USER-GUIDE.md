# HEXR Companion — how to use it

A Windows and macOS app for checking a HEXR glove and feeling what it can do. Connect a
glove, drive any finger, and see what the hardware reports back. No code, no
Unity, no SDK.

Use it to answer three kinds of question:

- **Does this glove work?** Run the Quick test: the glove turns green where it is good.
- **What does this setting feel like?** Tap a finger, hold the button, feel it.
- **Why is this one weak?** Turn on **Details** and watch the pressure while it fires.

The screens show as little as they can. The numbers behind them (kPa, addresses,
versions) are one click away under **ⓘ Details** at the top right of each screen,
which the app remembers per screen. **Help**, at the bottom of the left rail, opens
this guide.

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
- The first time the app looks for gloves, macOS asks whether it may
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

Open **Test**. Until a glove is connected it shows two dimmed gloves, left and
right, and searches by itself; there is nothing to press. When a glove is found,
**Found** appears under it with its signal strength, and a **Connect** button.
Press it. The glove lights up, and a moment later Test turns into the controls
below.

If two gloves of the same hand are switched on (two kits in one room),
**Connect** asks which one, by the last four characters of its address,
strongest signal first.

You can connect **both gloves at once**. They are separate devices and
everything after this treats them separately.

**The gloves button**, at the top right of every screen, shows which gloves are
connected (a green dot for **L** and **R**) and the battery, which turns amber
below 20%. Press it to connect the second glove, check one or disconnect it. It
opens over the screen you are on; **Close** goes back.

**Nothing found?** The arm module is probably not switched on — press and hold
the power button; the app is still searching. If it says *Bluetooth
unavailable*, that is your PC's adapter, not the glove: press **Try again** once
it is on.

---

## Test · driving channels

This is where you feel things.

**Tap the fingers you want.** The glove on the screen is the picker: tap a
fingertip or the palm to pick it, tap again to drop it. Thumb, Index, Middle,
Ring, Pinky and Palm are the six things a HEXR glove can drive. **All** and
**None** under the glove pick all six or clear them.

**Pick a hand**, when both gloves are connected: the **Left** and **Right** chips
under the gloves. A hand that is not picked shows dimmed.

**Pick a mode:**

| Mode | What it feels like |
|---|---|
| **Pressure** | A steady squeeze, for as long as you hold |
| **Vibration** | An oscillation — buzzing, tapping or pulsing depending on frequency |

**Set the levels**, then **press and hold Hold to feel**. The glove presses for
as long as you hold it and lets go when you do, the way a hand meets an object.
The space bar does the same.

For a longer run, turn on **Keep on**: then one press starts it and the next
stops it. **Release all** vents everything.

The glove on the screen shows what is happening: a point glows orange where the
glove is pressing (from what the glove measures, when it reports it), a
vibration sends out rings, and the caption under it reads *Press. Hold.
Release.*, or *Pulse. Buzz.* in vibration mode.

### The settings, and what they actually change

**Intensity** (10% – 100%) is how hard it squeezes. With **Details** on, the
real target shows next to it in kPa. Below 15 kPa the glove treats a channel as
off, and it will not go above 50 kPa — so the useful range really is that
slider, end to end.

**Ramp speed** and **Peak ratio** are under **Fine-tune**, below the sliders.

**Ramp speed** (pressure mode) is how fast it gets there, not how hard. At 100%
it snaps; at 10% it swells slowly. Two very different sensations at the same
intensity — worth trying before you decide a preset feels wrong.

**Frequency** (vibration mode) is the one that changes the *character* of the
sensation, and there is a hard boundary in the hardware at **5 Hz**:

| Frequency | What the glove does | What it feels like |
|---|---|---|
| Under 5 Hz | Pulses the air pressure itself | Slow, deep, physical — a heartbeat or a knock |
| 5 Hz and above | Drives the channel's motor directly | Fast buzz — texture, alerts, engine hum |

These are two different mechanisms, not one scale. The word beside the
frequency tells you which one is running: **Pulse** under 5 Hz, **Buzz** above
(Details explains it in a sentence). If a vibration setting feels nothing like
you expected, check which side of 5 Hz you are on.

**Peak ratio** (vibration mode, 20% – 80%) is how much of each cycle is "on".
Low is a short sharp tick; high is a longer swell. This is what separates a tap
from a throb at the same frequency.

### Feeling effects quickly

Some starting points worth trying with the glove on:

| To feel | Mode | Settings |
|---|---|---|
| Gripping a solid object | Pressure | All channels, intensity 100%, speed 100% |
| Something soft giving way | Pressure | All channels, intensity 40%, speed 15% |
| A heartbeat | Vibration | Palm, ~1 Hz, intensity 70%, peak ratio 35% |
| A light tap on one finger | Vibration | Index, ~3 Hz, intensity 50%, peak ratio 20% |
| Texture / roughness | Vibration | Fingertips, 20–30 Hz, intensity 50% |
| A buzzing alert | Vibration | All, 35 Hz, intensity 100%, peak ratio 60% |

> **Named effect presets — heartbeat, fountain, raindrops — are not in this
> version.** They exist in the Unity package as authored effects. This app
> gives you the raw controls those effects are built from, so you can dial in
> something close by hand.

### What the glove reports

The glove on the screen glows with the pressure the glove measures. **Details**
adds the numbers: kPa beside each point, the source pressure feeding all of
them, and the battery.

**If a glove reports nothing, that is not a fault.** Some gloves stream
telemetry and some do not, and haptics work either way; the picture then follows
the button instead. It only matters for the Quick test, which needs the readings
to measure anything.

---

## Quick test

The pass/fail check. Use it on a glove coming off the bench, or one back from a
customer. Press **Quick test** at the top right of Test; **Close** goes back to
Test, and closing it in the middle of a run stops the run and vents the glove.

**Take the glove off first.** It drives all six channels to full at once.

Press **Run** (**Stop** while it runs). It vents everything, drives all six
channels hard for two seconds, and then answers in one line: **All good**,
**2 poor**, **1 failed** or **Pump failed**, with the weak fingers named under
it. The glove shows the same answer, each point coloured by its verdict:

| Colour | Verdict | Peak reached | Meaning |
|---|---|---|---|
| Green | **Good** | Above 40 kPa | Full pressure |
| Amber | **Poor** | 2 – 40 kPa | Moved, but never got to full — check the tubing |
| Red | **Fail** | Under 2 kPa | Not working |

**Details** shows the table behind it: each channel's peak, how long it took,
and its verdict.

The failure line sits at 2 kPa rather than at zero because the sensor on a dead
channel floats on noise instead of reading a clean 0.0.

**If the source never develops pressure**, every channel reads Fail for one
reason — a dead pump. The answer says **Pump failed** rather than blaming six
channels, so don't go replacing indenters.

With both gloves connected, **Left** and **Right** under the glove pick which
one to test.

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
app is open. The list searches by itself. A headset shows *Asleep* while nobody
is wearing it, and refuses commands until someone puts it on.

Click a headset (or its **Open**) to open it below the list: its view first,
then its gloves, its scene and its commands.

- **Watch** — the wearer is asked in the headset to allow sharing their view;
  once they do, it appears in the picture. Clicking the picture does the same.
  Until then the picture says what is happening (waiting for the wearer, they
  said no, asleep). **Stop watching** leaves the view running for anyone else
  still watching it. The chip beside the buttons is the view's state in a word.
- **Gloves** — a chip per glove, green when the headset has it. Click a grey one
  to connect it; a green one offers **Disconnect**. The headset does the connecting,
  over its own Bluetooth. A glove talks to one thing at a time, so if this
  computer (or a phone) has it, disconnect it there first. **Release all**
  beside them vents both.
- **Scene** — pick one and the headset switches to it.
- **Recenter** — puts the wearer back on the scene's starting spot, facing its
  front, for someone who has wandered off or was handed the headset facing the
  wrong way. Works on Quest and PICO alike. A tick shows it worked. The app
  needs **HexR 0.11.0 or newer**; on an older one the button is greyed out.
- **The app's own commands** sit beside Recenter, as buttons.
- **The glove on the view** — a HEXR glove in the corner of the picture lights
  up where the wearer is being touched: pressure glows and holds, a vibration
  sends out rings, and a caption reads *Press. Hold. Release.* or *Pulse. Buzz.
  Click.*, so an audience can see what the haptics are doing. Turn it off, or
  change its size, from the **⋯** menu beside the buttons. Apps built with
  **HexR 0.10.2 or newer**
  send every touch and vibration as it happens, lined up with the picture; with
  an older app the glove follows the pressure the gloves measure, which shows a
  press or a hold but not a vibration.
- **Frame** — in the **⋯** menu. The headset sends a square view. **16:9** cuts
  a widescreen band from it for a TV or a video; drag the picture up or down to
  choose which band (hands are usually low in the view). **Square** shows all of
  it.
- **Record** — saves the view as you see it, glove included, as an MP4 in
  *Videos\HEXR Companion*. While it records the button shows the time; when it
  stops, **Show in folder** opens the file. With a HexR 0.10.2 app a
  *.haptics.json* is saved beside it, which HexR Overlay Studio opens to restyle
  the glove afterwards.
- **Full screen** — the **⛶** button. The view alone, on a second display if one
  is connected (a projector or TV), or on this one. **Esc** leaves, **R**
  records, **G** turns the glove on or off, and dragging or the arrow keys move
  a 16:9 frame.
- **Rename** — in the **⋯** beside the headset's name: call it *Station 1* or
  similar. Headsets of one model all report the same name, so this is how you
  tell them apart. The name is kept on this computer. **Forget** is there too.
- **Details** — the headset's versions, address and battery, each glove's
  pressure, and how many are watching.

**No headsets appear?** The first time you open Headsets, Windows asks whether
to allow the app on networks: allow it on **private** networks, and make sure
the Wi-Fi is set to *Private* in Windows settings. Event Wi-Fi often stops
devices seeing each other; press **+ Add by address** under the list, type the
headset's IP address and press **Add** instead, or bring your own router.

On a Mac the Headsets screen controls headsets but cannot show their view yet.

---

## Safety

A haptic glove can hold a finger squeezed. Three ways to stop everything:

- **Escape** — works anywhere in the app
- **Release all** — under **Hold to feel** on the Test screen
- **Close the app** — every channel is vented on the way out

**Hold to feel** lets go on its own when you release it, when you leave the
Test screen, and when the window loses focus, even with **Keep on**. Channels
are also vented automatically when you disconnect a glove.

If the app is closed or crashes while something is inflated, powering the arm
module off releases it.

---

## When something is wrong

| What you see | What it means |
|---|---|
| Stays on *Searching* | The arm module is off, or out of range. Press and hold the power button. |
| *Bluetooth unavailable* | Your PC's Bluetooth is off or has no adapter — not a glove problem. |
| Connects, then drops | Usually a low battery. Check the light on the module; red means swap the pack. |
| Connects but no pressure readings | Normal on some gloves. Haptics still work; only Quick test is affected. |
| Hold to feel is greyed out | No finger is picked: tap one on the glove. With two gloves, check a hand is picked. |
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
