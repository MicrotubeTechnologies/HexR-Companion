# HEXR Companion for Android: how to use it

HEXR Companion tests a HEXR haptic glove from your phone, and lets you watch a HEXR
headset's view with its gloves lighting up beside it. It is the phone version of the
desktop HEXR Companion: the same glove, the same words, the same pass and fail.

Two tabs along the bottom: **Test**, for this phone's own gloves over Bluetooth, and
**Headsets**, for the HEXR headsets on your Wi-Fi.

The ⋯ in the top corner switches between **English** and **中文**, and opens this guide.

---

## Install

- **Microtube Apps:** download `HexR-Companion.apk` on the phone and open it. Android asks
  you to allow installs from your browser or file manager the first time.
- **Google Play:** search for HEXR Companion.

The two are separate apps (different signing keys), so keep one or the other.

## Before you start

- Allow **Nearby devices** when asked. Everything on the Test tab talks to the glove over
  Bluetooth, so the app waits for it.
- Switch on the glove's **arm module**.
- For the quick test, **take the glove off** first.

---

## Test · connecting a glove

With no glove connected, the Test tab shows two dimmed gloves, left and right. It searches
by itself while it is on screen; there is no Scan button.

Under each glove, one word says where it is:

| Word | What it means | What to do |
|---|---|---|
| Searching… | No glove of that hand heard yet | Switch the arm module on, bring it closer |
| Found + bars | Heard, with its signal strength | Tap **Connect** |
| Connecting… | Connecting | Wait a few seconds |
| Connected · 85% | Connected, with its battery (amber under 20%) | Nothing: the glove lights up |
| Could not connect | It was found but would not connect, and has not been heard since | Restart the arm module, then tap **Connect** once it is found again |
| Bluetooth unavailable | Bluetooth is off, or a search failed | **Open Bluetooth settings**, or **Try again** |

If two kits of the same hand are about, **Connect** asks which, strongest signal first,
by the last four characters of each one's address.

Once a glove connects, the Test tab becomes the glove. The **Gloves** button in the header
(the Bluetooth rune, a dot for each hand, the lower battery) opens the same two gloves
again, to connect the other hand or disconnect one.

## Test · driving it

1. **Pick fingers.** Tap a fingertip or the palm on the glove, or tick it in the list under
   it. **All** and **None** pick everything or nothing. With both gloves connected,
   **Left | Right** at the top picks which one you are driving.
2. **Set how it feels** in the card under the glove (below).
3. **Trigger** sends it to the picked fingers, and they stay on. Press it again after
   changing something and it sends the new setting; fingers you un-picked are released.
4. **Release all** lets every finger go. It turns red while anything is on.

Trigger and Release all sit in the bar along the bottom, within a thumb's reach. Back also
releases while anything is on, and so does leaving the Test tab.

Moving a slider changes nothing on the glove by itself: press **Trigger** to send it.

### The settings

- **Pressure | Vibration.** Pressure holds the finger at a pressure. Vibration pulses or
  buzzes it.
- **Intensity**, with the pressure it aims for: 60% · 34 kPa.
- **Frequency** (Vibration only), from 0.1 to 40 Hz. Under 5 Hz the glove **pulses**: the
  air pressure itself swings, which you feel as a slow beat. At 5 Hz and above it **buzzes**:
  the finger's motor is driven directly.
- **Fine-tune:** **Ramp speed** (Pressure: how fast it fills) and **Peak ratio**
  (Vibration: how much of each beat is on).

### What the glove shows

The glove glows white-hot where it measures pressure, and rings where it vibrates. The
caption under it says **PRESS. HOLD. RELEASE.**, or **PULSE. BUZZ. CLICK.** for a vibration.

The **Air pressure** list gives each finger's pressure now (the bar), where it is set to go
(the white mark), and the **air supply**. **Details** at the bottom has the glove's address,
battery, MTU and source pressure.

---

## Quick test

**Quick test** at the top of the Test tab answers one question: is this glove healthy?

1. **Take the glove off.** The test inflates every finger to full.
2. Tap **Run**. It drives all six to full for two seconds and measures what each reached.
3. The answer is one line, and the glove shows it: each finger green, amber or red.

| Answer | Colour | Means |
|---|---|---|
| All good | Green | Every finger rose above 40 kPa |
| 2 poor | Amber | Those moved, but not to full pressure: check their tubing |
| 1 failed | Red | Under 2 kPa with the supply healthy: a blocked line, a valve that never opened, or a dead indenter |
| Pump failed | Red | The supply itself never rose, so no finger could: one fault in the pump, not six |

The weak fingers are named under the answer. **Details** has the table (peak, time to
peak, verdict) and the sentence explaining it.

---

## Headsets

The Headsets tab lists every HEXR headset running a HexR app on the same Wi-Fi as the
phone. Each shows its app, a word for its state (**Ready**, **Live**, **Asleep**,
**Offline**), and its two gloves with their batteries.

If a headset never appears, the network may hide devices from each other: tap
**+ Add by address** and type its IP address (on the headset: Settings › Wi-Fi). Add
`:port` after it for a headset on another port.

Tap a headset to open it.

### Watching

- **Watch** asks the wearer to share their view. They allow it in the headset each time.
  If someone else is already watching, the phone just joins.
- The view runs across the top, and the wearer's two gloves sit under it, lighting up as
  they are touched, in step with the picture.
- **Stop watching** ends the share, unless another phone or computer is still watching,
  in which case this phone just leaves.
- **Full screen** (the four corners) turns the view sideways and gives it the whole screen.
  Turning the phone sideways does the same. Tap the view to bring the controls back; Back
  leaves full screen.

The word beside the headset's name says what is happening: **Live**, **Waiting** (for the
wearer to allow it), **Declined**, **Asleep** (nobody is wearing it), **Offline**.

### The gloves, and the wearer

- **Tap a glove's panel** to connect it. Tap a connected one for **Disconnect**: it asks
  first, so one slip does not end someone's demo.
- **Release all** lets every finger of both gloves go.
- **Recenter** puts the wearer back on the scene's starting spot, facing its front. It
  shows ✓ for a moment once sent. It needs HexR 0.11.0 with Allow Recenter on the headset;
  tap it to see why when it is greyed.

A glove connects to one thing at a time. If this phone holds a glove on the Test tab, the
headset cannot reach that hand, and the screen says so: disconnect it on the Test tab first.

⋯ on a headset: **Rename** it (for example "Station 1"), **Details** (versions, the share,
the gloves), and **Forget** for one added by address.

---

## Safety

- The phone **releases every finger** when the app leaves the screen, when you leave the
  Test tab, and on Back while anything is on.
- Run the quick test with the glove **off the hand**. It drives every finger to full.
- If a finger stays pressed, tap **Release all**; if it still does, switch off the arm
  module.

## When something is wrong

| What you see | Try |
|---|---|
| Searching… forever | Arm module on and close by; Bluetooth on; Nearby devices allowed in the app's settings |
| Connects, then drops | Charge the arm module; move closer; restart it |
| No readings | The glove is connected but not reporting: disconnect and connect again |
| A headset never appears | Same Wi-Fi? Add it by address |
| Watch does nothing | The wearer has to allow sharing in the headset; is it asleep? |
| The gloves under the view do not light up | The headset's glove is not connected (tap its panel), or the app on it is older than HexR 0.10.2, in which case only measured pressure shows |
