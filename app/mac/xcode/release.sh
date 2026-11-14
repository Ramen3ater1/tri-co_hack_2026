#!/bin/bash
# Notarized Mac download: archive with Xcode, Developer ID-sign and notarize through the Apple account signed in
# to Xcode, staple, zip. Defaults to the dev server, like CI. Usage: ./app/mac/xcode/release.sh [server-url]
set -euo pipefail
cd "$(dirname "$0")"
SERVER="${1:-https://dialectic-dev.yaggy.dev}"
SRC=../Sources/Dialectic/DialecticApp.swift
cp "$SRC" build-DialecticApp.swift.bak 2>/dev/null || { mkdir -p build; cp "$SRC" build-DialecticApp.swift.bak; }
trap 'mv build-DialecticApp.swift.bak "$SRC"' EXIT
sed -i '' "s|^let DEFAULT_SERVER_URL = \".*\"|let DEFAULT_SERVER_URL = \"$SERVER\"|" "$SRC"
mkdir -p build && xcodegen -q
xcodebuild -project DialecticMac.xcodeproj -scheme Dialectic -configuration Release -archivePath build/Dialectic.xcarchive \
  -derivedDataPath build/dd -allowProvisioningUpdates archive -quiet
cat > build/ExportOptions.plist <<'P'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>method</key><string>developer-id</string>
  <key>destination</key><string>upload</string>
  <key>signingStyle</key><string>automatic</string>
  <key>teamID</key><string>SGL8MGZNZV</string>
</dict></plist>
P
xcodebuild -exportArchive -archivePath build/Dialectic.xcarchive -exportOptionsPlist build/ExportOptions.plist \
  -exportPath build/notarize -allowProvisioningUpdates
# Wait for Apple's notary service, then export the stapled app.
until xcodebuild -exportNotarizedApp -archivePath build/Dialectic.xcarchive -exportPath build/export 2>/dev/null; do
  echo "Waiting for notarization…"; sleep 30
done
spctl -a -vv build/export/Dialectic.app
ditto -c -k --keepParent build/export/Dialectic.app build/Dialectic-mac.zip
echo "Built $(pwd)/build/Dialectic-mac.zip"
