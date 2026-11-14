#!/bin/bash
# Build app/mac/build/Dialectic.app (SPEC §3.9). Run from anywhere: ./app/mac/build.sh
set -euo pipefail
cd "$(dirname "$0")"

swift build -c release
BIN="$(swift build -c release --show-bin-path)/Dialectic"

APP=build/Dialectic.app
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp "$BIN" "$APP/Contents/MacOS/Dialectic"

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
    <key>LSMinimumSystemVersion</key><string>13.0</string>
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

# Ad-hoc signature: enough to run locally. Note: macOS ties the Accessibility grant to the
# signature, so after a rebuild you may need to toggle Dialectic off and on again in System Settings.
codesign --force --sign - "$APP"
# Tell Launch Services about the dialectic:// scheme now, not on first launch.
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP"

echo "Built $(pwd)/$APP  (open it with: open $(pwd)/$APP)"
