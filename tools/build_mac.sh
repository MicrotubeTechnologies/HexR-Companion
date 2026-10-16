#!/bin/bash
# Build the macOS installer: dist/HexR-Companion-Mac.pkg
#
#     tools/build_mac.sh                # build, sign, notarize the installer
#     tools/build_mac.sh --no-notarize  # skip Apple notarization (local testing only)
#
# The installer puts a universal app (Apple silicon + Intel, macOS 10.13+) into
# /Applications through the standard Continue / Install steps.
#
# Needs, once per Mac (see README "Building for macOS"):
#   - Python 3.10+ from python.org (the "universal2" installer). Homebrew Python
#     builds an arm64-only app that refuses to start on any macOS older than
#     the build machine's.
#   - "Developer ID Application" and "Developer ID Installer" certificates in
#     the login keychain (the first signs the app, the second the installer).
#   - Notarization credentials saved with:
#       xcrun notarytool store-credentials hexr-notary \
#         --apple-id <email> --team-id <TEAMID> --password <app-specific-password>
#
# Environment overrides: PYTHON, SIGN_IDENTITY, INSTALLER_IDENTITY,
# NOTARY_PROFILE (default hexr-notary).
set -euo pipefail

cd "$(dirname "$0")/.."
APP_NAME="HEXR Companion"
APP="dist/$APP_NAME.app"
PKG="dist/HexR-Companion-Mac.pkg"
ENTITLEMENTS="packaging/macos/entitlements.plist"
NOTARY_PROFILE="${NOTARY_PROFILE:-hexr-notary}"
VENV=".venv-mac"

NOTARIZE=1
for arg in "$@"; do
  case "$arg" in
    --no-notarize) NOTARIZE=0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n==> %s\n' "$*"; }
die() { echo "error: $*" >&2; exit 1; }

# -------------------------------------------------------------- python
if [[ -z "${PYTHON:-}" ]]; then
  for v in 3.13 3.12 3.11 3.10; do
    p="/Library/Frameworks/Python.framework/Versions/$v/bin/python3"
    [[ -x "$p" ]] && { PYTHON="$p"; break; }
  done
fi
[[ -x "${PYTHON:-}" ]] || die "python.org Python 3.10+ not found; install the universal2 build from python.org or set PYTHON"
"$PYTHON" -c 'import sysconfig, sys; sys.exit(0 if "universal2" in sysconfig.get_platform() else 1)' \
  || die "$PYTHON is not a universal2 build; the app would not run on Intel Macs or older macOS"

step "Preparing build environment ($("$PYTHON" -V))"
if [[ ! -x "$VENV/bin/python" ]]; then
  "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r requirements.txt pyinstaller delocate certifi

# Pillow and PyAV ship an arm64 wheel and an Intel wheel but no universal2
# one, and PyInstaller refuses single-arch binaries in a universal app. Fuse
# each pair into one, at the version requirements.txt installed.
PY_TAG="$("$VENV/bin/python" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
fuse() {  # fuse <package> <import name>
  local version wheels plat
  version="$("$VENV/bin/python" -c "import $2; print($2.__version__)")"
  wheels="$(mktemp -d)"
  for plat in macosx_11_0_arm64 macosx_10_13_x86_64; do
    "$VENV/bin/pip" download -q --only-binary=:all: --no-deps --platform "$plat" \
      --python-version "$PY_TAG" "$1==$version" -d "$wheels"
  done
  "$VENV/bin/delocate-merge" -w "$wheels/fused" "$wheels"/*arm64.whl "$wheels"/*x86_64.whl >/dev/null
  "$VENV/bin/pip" install -q --force-reinstall --no-deps "$wheels"/fused/*.whl
  rm -rf "$wheels"
}
fuse pillow PIL
fuse av av

step "Running protocol tests"
"$VENV/bin/python" tests/test_protocol.py
"$VENV/bin/python" tests/test_remote.py
"$VENV/bin/python" tests/test_sideload.py

# -------------------------------------------------------------- adb
# Google's adb for the APK Sideload screen: the app carries it, so it needs no internet.
step "Fetching adb"
# python.org's Python has no root certificates until its "Install Certificates"
# script is run; certifi's do instead, so no build Mac needs that step.
SSL_CERT_FILE="$("$VENV/bin/python" -c 'import certifi; print(certifi.where())')" \
  "$VENV/bin/python" tools/fetch_adb.py --platform mac

# -------------------------------------------------------------- icon
step "Generating icon.icns"
ICONSET="$(mktemp -d)/icon.iconset"
mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s assets/icon.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  d=$((s * 2)); [[ $d -gt 512 ]] && d=512
  sips -z $d $d assets/icon.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o assets/icon.icns

# -------------------------------------------------------------- build
step "Building $APP"
rm -rf build "dist/$APP_NAME" "$APP"
"$VENV/bin/pyinstaller" --noconfirm --log-level WARN HexR-Companion.spec
[[ -d "$APP" ]] || die "PyInstaller did not produce $APP"
lipo -archs "$APP/Contents/MacOS/HexR-Companion"
ADB_BIN="$(find "$APP" -type f -name adb | head -1)"
[[ -n "$ADB_BIN" ]] || die "adb is missing from $APP"
ADB_ARCHS="$(lipo -archs "$ADB_BIN")"
[[ "$ADB_ARCHS" == *x86_64* && "$ADB_ARCHS" == *arm64* ]] \
  || die "$ADB_BIN is $ADB_ARCHS, not universal"

# -------------------------------------------------------------- sign
if [[ -z "${SIGN_IDENTITY:-}" ]]; then
  SIGN_IDENTITY="$(security find-identity -v -p codesigning \
    | sed -n 's/.*"\(Developer ID Application: [^"]*\)".*/\1/p' | head -1)"
fi
if [[ -z "$SIGN_IDENTITY" ]]; then
  [[ $NOTARIZE -eq 1 ]] && die "no 'Developer ID Application' certificate in the keychain (create one in Xcode > Settings > Accounts > Manage Certificates), or pass --no-notarize for a local-only build"
  echo "No Developer ID certificate: ad-hoc signing. This build only runs on THIS Mac."
  SIGN_IDENTITY="-"
fi

step "Signing with: $SIGN_IDENTITY"
xattr -cr "$APP"
# adb is copied in as data, where --deep may not look for code, and notarization rejects any
# binary in the bundle that is not signed with our Developer ID and the hardened runtime. So it
# is signed on its own first, with no entitlements: it needs none of the app's.
if [[ "$SIGN_IDENTITY" == "-" ]]; then
  codesign --force --sign - "$ADB_BIN"
else
  codesign --force --timestamp --options runtime --sign "$SIGN_IDENTITY" "$ADB_BIN"
fi
if [[ "$SIGN_IDENTITY" == "-" ]]; then
  codesign --force --deep --sign - "$APP"
else
  # PyInstaller's layout signs cleanly with --deep; every nested binary gets the
  # hardened runtime and a secure timestamp, which notarization requires.
  codesign --force --deep --timestamp --options runtime \
    --entitlements "$ENTITLEMENTS" --sign "$SIGN_IDENTITY" "$APP"
fi
codesign --verify --deep --strict "$APP"

# -------------------------------------------------------------- installer
if [[ -z "${INSTALLER_IDENTITY:-}" && "$SIGN_IDENTITY" != "-" ]]; then
  INSTALLER_IDENTITY="$(security find-identity -v \
    | sed -n 's/.*"\(Developer ID Installer: [^"]*\)".*/\1/p' | head -1)"
fi
if [[ -z "${INSTALLER_IDENTITY:-}" && $NOTARIZE -eq 1 ]]; then
  die "no 'Developer ID Installer' certificate in the keychain (create one in Xcode > Settings > Accounts > Manage Certificates), or pass --no-notarize"
fi

VERSION="$(cat VERSION)"
step "Creating $PKG (version $VERSION)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/root" "$WORK/resources"
cp -R "$APP" "$WORK/root/"
cp packaging/macos/welcome.html packaging/macos/conclusion.html "$WORK/resources/"
sed "s/@VERSION@/$VERSION/" packaging/macos/distribution.xml > "$WORK/distribution.xml"

# Not relocatable: otherwise Installer "updates" whatever copy of the app it
# finds elsewhere on disk (a Downloads folder, a mounted DMG) instead of
# installing into /Applications.
pkgbuild --analyze --root "$WORK/root" "$WORK/component.plist" >/dev/null
/usr/libexec/PlistBuddy -c "Set :0:BundleIsRelocatable false" "$WORK/component.plist"
# The id is the one from when the app was HEXR Window Tester, as in the spec: a
# new one would make macOS treat it as another app and ask for Bluetooth again.
pkgbuild --quiet --root "$WORK/root" --component-plist "$WORK/component.plist" \
  --identifier tech.microtube.hexr-window-tester --version "$VERSION" \
  --install-location /Applications "$WORK/app.pkg"

rm -f "$PKG"
SIGN_ARGS=()
[[ -n "${INSTALLER_IDENTITY:-}" ]] && SIGN_ARGS=(--sign "$INSTALLER_IDENTITY" --timestamp)
productbuild --quiet --distribution "$WORK/distribution.xml" \
  --resources "$WORK/resources" --package-path "$WORK" ${SIGN_ARGS[@]+"${SIGN_ARGS[@]}"} "$PKG"

# -------------------------------------------------------------- notarize
if [[ $NOTARIZE -eq 1 ]]; then
  step "Notarizing with Apple (usually a few minutes)"
  xcrun notarytool submit "$PKG" --keychain-profile "$NOTARY_PROFILE" --wait
  xcrun stapler staple "$PKG"
  step "Gatekeeper check"
  spctl -a -t install -v "$PKG"
fi

shasum -a 256 "$PKG" | tee "$PKG.sha256"
step "Done: $PKG"
[[ $NOTARIZE -eq 1 ]] || echo "Not notarized: other Macs will refuse to open this installer."
