# Shipping HEXR Companion to the Play Store

Everything needed to put version **1.0.0** of the Android app on Google Play,
in the order you need it.

The sideload route in [README.md](README.md) does not change. A technician still
opens an APK from the Actions tab. This is the second, parallel route, for the
same code signed a different way.

---

## The package name

```
com.microtube.hexr.tester
```

That is the `applicationId` in `app/build.gradle.kts`, and it is the identity of
the app on Google Play.

**It is permanent.** Once a bundle with that id is uploaded to a Play Console
app, it can never be changed, reused for a different app, or recovered if the
listing is deleted — the id is burned. If a different name is wanted (a bare
`com.microtube.hexr`, or a `com.hexr.*` if the company domain is different),
change it *before* the first upload and never after.

The Kotlin `namespace` is `com.microtube.hexr` and is unrelated to any of this;
it only decides where `R` and `BuildConfig` are generated. Leave it alone.

---

## What version 1.0.0 produces

| | |
|---|---|
| Package name | `com.microtube.hexr.tester` |
| Version name | `1.0.0` (from the repository's `VERSION` file) |
| Version code | `10000` |
| Format | Android App Bundle (`.aab`) |
| Min / target SDK | 26 (Android 8.0) / 36 (Android 16) |
| Signing | upload key, then Play App Signing |

The version code comes from the `major * 10000 + minor * 100 + patch` rule in
`app/build.gradle.kts`, so 1.0.0 is 10000 and 1.0.1 will be 10001. Play only
requires that it *increases*; starting at 10000 costs nothing and keeps the two
numbers readable off each other for the life of the app.

`targetSdk = 36` is the floor for a new Play submission as of **31 August
2026**. Google raises it roughly every August, and a release that suddenly stops
being accepted is almost always this. Moving to 36 also pulled AGP to 8.13.0 and
the CI Gradle pin to 8.14.3, because 8.7.3 could not compile against API 36.

The Android 16 behaviour change that usually breaks an app at this bump —
enforced edge-to-edge — was already handled: `MainActivity` calls
`enableEdgeToEdge()` and the header, permission gate and tab bar each apply
their own `windowInsetsPadding`. There is no orientation lock or
`resizeableActivity` to be ignored either.

---

## 1. Create the upload key

Once, ever. Then back it up.

One line, deliberately. PowerShell does not join backslash line continuations,
and a wrapped version of this command pasted into it runs as `keytool
-genkeypair -v` on its own — which silently produces a **90-day** certificate:

```
cd android
keytool -genkeypair -v -keystore hexr-upload.jks -alias hexr-upload -keyalg RSA -keysize 4096 -validity 10000 -dname "CN=Microtube, O=Microtube, C=GB"
```

`keytool` ships with the JDK. It asks for a keystore password and a key
password; they may be the same.

**`-validity 10000` is not decoration.** Play refuses any bundle whose
certificate expires before **22 October 2033** — *"You uploaded an APK or
Android App Bundle signed with a certificate that expires too soon"* — and
keytool's default without that flag is 90 days. 10000 days is about 27 years,
so a key made today is good until 2053. `bundleRelease` now checks this at
configuration time and refuses to sign with a short-lived key, but check the
certificate yourself once you have made it:

```
keytool -list -v -keystore hexr-upload.jks -alias hexr-upload
```

The `Valid from ... until ...` line must end well past 2033. The same check
works on a finished bundle, which is the last chance before an upload:

```
keytool -printcert -jarfile app/build/outputs/bundle/release/app-release.aab
```

A rejected upload registers nothing — no certificate is bound to the app, and
the version code is not consumed — so a bundle refused for this reason costs
only the round trip: make a proper key, rebuild, upload again.

`hexr-upload.jks` is gitignored, along with `*.jks`, `*.keystore` and
`keystore.properties`. Do not defeat that. Put the file and its passwords in
whatever the company uses for secrets, on something that is not this laptop.

Losing it is survivable — Play App Signing holds the real distribution key, and
Google will reset a lost *upload* key on request — but the reset is a support
round-trip measured in days, and you will want it on the one day you cannot
afford one.

Then point the build at it:

```
cp keystore.properties.example keystore.properties
# fill in storePassword and keyPassword
```

---

## 2. Build the bundle

Locally:

```
cd android
gradle testDebugUnitTest      # the protocol suite, same as CI
gradle bundleRelease          # app/build/outputs/bundle/release/app-release.aab
```

Without a key the release build stops at configuration time with the fix in the
message, rather than handing you an unsigned bundle the Play Console will reject
half an hour later.

Or from CI, which is the route to prefer — it builds from a tag, on a clean
checkout, with the tests in front of it. Add four repository secrets
(*Settings → Secrets and variables → Actions*):

| Secret | Value |
|---|---|
| `HEXR_KEYSTORE_BASE64` | `base64 -w0 hexr-upload.jks` |
| `HEXR_KEYSTORE_PASSWORD` | keystore password |
| `HEXR_KEY_ALIAS` | `hexr-upload` |
| `HEXR_KEY_PASSWORD` | key password |

then tag:

```
git tag android-v1.0.0 && git push origin android-v1.0.0
```

The run publishes the usual GitHub Release with the sideload APK, and attaches
`HexR-Companion-1.0.0.aab` as a **workflow artifact** — deliberately not a release
asset. An `.aab` cannot be installed on a phone, and a download button offering
one next to the APK is a support ticket waiting to happen.

---

## 3. Play Console

Create the app, then work through the tasks it lists. The ones this app makes
non-obvious:

**App access.** The app needs a HEXR glove to do anything at all. Say so, in the
*Instructions* box, and offer a video — a reviewer with no glove sees the
scan screen scanning and nothing else, and "we could not test the app" is a
rejection.

**Data safety.** No data collected, no data shared. Since 1.1.0 the app does
make network connections, for the Headsets tab, but only to HEXR headsets on the
same local network: nothing goes to Microtube or any third party, which is what
the form means by collected and shared. The one thing stored is a headset
nickname, on the phone. Answer the form that way; it is checked against the
actual bundle, which now declares INTERNET.

**Permissions.** `BLUETOOTH_SCAN` is declared `neverForLocation`, so no location
declaration is required and the app never asks for location on Android 12+. The
`ACCESS_FINE_LOCATION` line in the manifest is capped at `maxSdkVersion="30"`
and exists only because that is how the platform gated BLE scanning before the
dedicated permissions arrived. If the Console asks about location anyway, that
cap is the answer.

**Privacy policy.** Required, with a public URL, even for an app that collects
nothing. The published copy is `docs/privacy.html`, served by GitHub Pages:

```
https://microtubetechnologies.github.io/HexR-Companion/privacy.html
```

That URL is dead until two things happen: this work reaches `main`, and Pages is
switched on at *Settings → Pages → Deploy from a branch → `main` → `/docs`*.
Check it loads before pasting it into the Console. [PRIVACY.md](PRIVACY.md) is
the source text; the contact line currently points at the repository's issue
tracker, which is a real channel but not the company mailbox a customer expects.

**Store listing text and graphics.** All of it is written out in
[play/listing.md](play/listing.md) — name, short and full descriptions with
their character counts, release notes, the screenshot order, and the answers to
every content declaration. The graphics live in `play/` and are regenerated by
`tools/make_play_assets.py`.

**Content rating, target audience, ads.** Utility, not directed at children, no
ads.

**Distribution.** Consider *Internal testing* first — it takes minutes rather
than the days a first production review takes, and it is the honest shape for a
tool aimed at technicians. Closed or internal testing also keeps the app out of
public search, which may well be the right answer permanently.

---

## The one thing that will bite

A phone with the sideloaded APK **cannot install the Play version over it**, and
vice versa. Same package name, different signing key; Android refuses the
upgrade with `INSTALL_FAILED_UPDATE_INCOMPATIBLE`.

**This is now fixed.** Debug builds carry `applicationIdSuffix = ".debug"`, so
the sideload installs as `com.microtube.hexr.tester.debug` and the two sit side
by side on one phone. It was done before the first upload on purpose: renaming
the sideload package is cheap now and awkward once the Play build exists.

The cost, once: a technician who already has the old sideload gets the next one
as a *second* app rather than an upgrade, and should uninstall the old one. Both
apps look identical in the launcher, which is the one thing to watch for when
someone reports a bug against "the app" — the build line at the bottom of the
scan screen (or the Gloves panel) is what tells them apart.

---

## Not done, on purpose

- **R8 / minification stays off.** Size is irrelevant for an app this small, and
  a readable stack trace off a technician's phone is worth more than the saving.
  Enabling it means writing keep rules and then actually exercising a minified
  build on hardware before it ships.
- **No Gradle wrapper.** The version is pinned in the workflow instead, in one
  visible line, without a binary jar in the tree.
- **No Play Publisher plugin.** The upload is a manual Console step. One release
  a quarter does not justify a service account with release permissions.
- **No tablet screenshots.** The app is drawn against a 390x844 dp phone and
  `TestScreen` is a fixed-height layout with no scroll. It would need a
  large-screen pass before a tablet screenshot was worth showing anyone.
