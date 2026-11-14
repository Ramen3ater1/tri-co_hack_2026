#!/bin/bash
# Build app/mac/build/Dialectic.app (SPEC §3.9). Run from anywhere: ./app/mac/build.sh
set -euo pipefail
cd "$(dirname "$0")"

# Universal binary (Apple Silicon + Intel), so one download runs on every Mac, including
# the Intel ones; a plain `swift build` only targets the chip it runs on.
ARCHS=(--arch arm64 --arch x86_64)
swift build -c release "${ARCHS[@]}"
BIN="$(swift build -c release "${ARCHS[@]}" --show-bin-path)/Dialectic"

APP=build/Dialectic.app
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/Dialectic"
# STUB: POST /api/locate pending Owen's OK. Regenerate with make-stub.swift.
cp stub-locate-response.json "$APP/Contents/Resources/"
# CI sets DIALECTIC_VERSION to the commit. Written before signing: changing the app afterwards
# breaks the signature (and notarization rejects it).
if [ -n "${DIALECTIC_VERSION:-}" ]; then
    echo "$DIALECTIC_VERSION" > "$APP/Contents/Resources/version.txt"
fi

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key><string>space.dialectic.mac</string>
    <key>CFBundleName</key><string>Dialectic</string>
    <key>CFBundleDisplayName</key><string>Dialectic</string>
    <key>CFBundleExecutable</key><string>Dialectic</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleShortVersionString</key><string>0.1</string>
    <key>CFBundleVersion</key><string>1</string>
    <key>LSMinimumSystemVersion</key><string>14.0</string>
    <key>LSUIElement</key><true/>
    <key>NSHighResolutionCapable</key><true/>
    <key>NSAppTransportSecurity</key>
    <dict><key>NSAllowsArbitraryLoads</key><true/></dict>
    <key>CFBundleURLTypes</key>
    <array>
        <dict>
            <key>CFBundleURLName</key><string>space.dialectic.mac.login</string>
            <key>CFBundleURLSchemes</key><array><string>dialectic</string></array>
        </dict>
    </array>
</dict>
</plist>
PLIST

# Sign with your Apple Development certificate if you have one: then macOS keeps the Accessibility
# and Screen Recording grants across rebuilds. Without one, ad-hoc ("-"), and grants break on rebuild.
# `|| true`: no such certificate (e.g. a CI runner) is fine, but under pipefail grep's "no match"
# would otherwise end the script right here, silently.
SIGN_ID="${DIALECTIC_SIGN_ID:-$( (security find-identity -p codesigning -v | grep -m1 "Apple Development" | sed -E 's/.*"(.*)".*/\1/') || true)}"
SIGN_ID="${SIGN_ID:--}"
echo "Signing with: $SIGN_ID"
SIGN_OPTS=()
# Notarization (CI, see mac-app.yml) needs the hardened runtime and a secure timestamp.
if [[ "$SIGN_ID" == "Developer ID Application"* ]]; then
    SIGN_OPTS=(--options runtime --timestamp)
fi
# The ${…+…} form: macOS's bash 3.2 calls an empty array "unbound" under set -u.
codesign --force --sign "$SIGN_ID" ${SIGN_OPTS[@]+"${SIGN_OPTS[@]}"} "$APP"
# Tell Launch Services about the dialectic:// scheme now, not on first launch.
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP"

lipo -info "$APP/Contents/MacOS/Dialectic"
# Fail here, not on a teammate's Mac, if the signature is broken.
codesign --verify --deep --strict --verbose=2 "$APP"
echo "Built $(pwd)/$APP  (open it with: open $(pwd)/$APP)"
