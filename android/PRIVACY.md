# Privacy policy — HEXR Companion for Android

Google Play requires a privacy policy at a public URL before an app can be
published, even one that collects nothing. This is the source text; the
published copy is `docs/privacy.html`, served by GitHub Pages at

    https://microtubetechnologies.github.io/HexR-Companion/privacy.html

The two are maintained by hand and must be edited together. Have whoever signs
off on company copy read this before the first submission — in particular the
contact address, which is currently the repository's issue tracker rather than a
company mailbox.

Package: `com.microtube.hexr.tester`
Last updated: 14 October 2026

---

HEXR Companion is a diagnostic tool for HEXR pneumatic gloves, used by technicians
to drive a glove's channels and read back its sensors over Bluetooth, and to
look after HEXR headsets on the same Wi-Fi at an event.

## What it collects

Nothing.

The app has no user accounts, no analytics, no crash reporting and no
advertising. It does not read contacts, photos, files, or the device's location.

## What it sends

Nothing beyond your own local network.

Gloves are reached over Bluetooth LE, on the bench in front of you.

The Headsets tab talks to HEXR headsets on the same Wi-Fi network as the phone,
and to nothing else. It listens for headsets announcing themselves, sends them
the commands you give (connect or disconnect a glove, change scene), and reads
back their status. When the person wearing a headset agrees to it in the
headset, the tab also receives that headset's view as video and shows it on
screen; the video is not recorded or stored. None of this goes to Microtube or
to anyone else: the app contacts no server on the internet.

Android calls the permission to open any network connection, including one that
never leaves the room, the internet permission, so the app declares it. See
*Network permissions* below.

## What it stores

Test results exist only while the app is open, in memory. Closing it discards
them. The one thing written to storage is the name you may give a headset on the
Headsets tab (such as "Station 1"), kept in the app's private storage on the
phone so the name is still there next time. Nothing is backed up — the app sets
`allowBackup="false"` — and uninstalling the app removes it.

## Bluetooth and location permissions

On Android 12 and newer the app asks for *Nearby devices*, to find and connect
to gloves. The Bluetooth scan is declared `neverForLocation`, meaning the app
tells Android it will not use scan results to work out where you are — so
Android does not ask you for location access, and the app never receives it.

On Android 11 and older the app requests location permission instead. That is
not a change in what it does: before Android 12 there were no dedicated
Bluetooth permissions, and location was the only way the platform allowed a
Bluetooth scan at all. The app still only reads the advertised name of nearby
gloves.

## Network permissions

`INTERNET` lets the Headsets tab open connections to headsets on the local
Wi-Fi. `ACCESS_NETWORK_STATE` lets it keep those connections on the Wi-Fi, so a
router with no internet behind it does not push them out over mobile data.
`CHANGE_WIFI_MULTICAST_STATE` lets the phone receive the broadcast each headset
announces itself with; the app holds it only while the Headsets tab is open.
Android grants all three when the app is installed, without asking.

## Children

The app is a workshop tool and is not directed at children.

## Changes

Any change to this policy will be published at this URL, with the date above
updated.

## Contact

Questions about this policy: open an issue at
<https://github.com/MicrotubeTechnologies/HexR-Companion/issues>.

A monitored company address would be better here, and should replace this before
the listing goes to production. The issue tracker is public, is read, and is a
real channel — which is what Play requires — but it is not what a customer
expects to find on a privacy policy.
