# Dialectic for iPad and iPhone

Same features as the Mac app (`app/mac/README.md`), shaped for touch. The reader is the web app in a `WKWebView` (every reader feature is built once, on the web); the Ask | Note panel and the answer card are native, from **DialecticKit** (`app/shared/`), the Swift package shared with the Mac.

- **In the app:** pick who you are (person button, top left; or pick a person on the web log-in page, the app follows). Select a passage in the reader, then **Ask or note** (top bar) or **Ask Dialectic** in the menu over the selection. The panel is the Mac's: Ask | Note, the three-layer answer (From your class → Sources → "Still stuck? Show the AI explanation"), **Open in reader**. Server picker under the person menu (Dev by default).
- **Over other apps (like the Mac's ⌃⌥D):** two Shortcuts actions, **Ask Dialectic Here** and **Note Dialectic Here**. Make a shortcut *Take Screenshot → Ask Dialectic Here* (Screenshot field = the screenshot) and put it on **Back Tap** (iPhone: Settings → Accessibility → Touch → Back Tap) or **AssistiveTouch** (iPad: Custom Actions). Reading anywhere, trigger it, type the question: Vision reads the screen on the device, the app tries the lines nearest the middle of the screen until the server finds one in a course reading (`candidateQuotes` / `firstInReading` in `app/shared/Sources/DialecticKit/ScreenText.swift`), and the answer shows as a card over the app (class answers, sources, how many class notes are on that page, **Open in Dialectic**). AI stays behind a click: the card only says it's there. Only recognised text is sent, never the screenshot. The app's hand button shows these steps.
- **Not on iPad/iPhone:** the Mac's highlight overlay drawn on another app's page and session highlights (iOS can't watch other apps' screens). In the app the web reader shows highlights itself.

## Build

```bash
cd app/ios && xcodegen          # brew install xcodegen; the .xcodeproj is generated from project.yml
open Dialectic.xcodeproj        # run on a simulator or device
```

TestFlight upload (Xcode signed in to the team account, SGL8MGZNZV; bump CURRENT_PROJECT_VERSION or let export manage it):

```bash
xcodebuild -project Dialectic.xcodeproj -scheme Dialectic -configuration Release -destination 'generic/platform=iOS' \
  -archivePath build/Dialectic.xcarchive -allowProvisioningUpdates archive
xcodebuild -exportArchive -archivePath build/Dialectic.xcarchive -exportOptionsPlist ExportOptions.plist \
  -exportPath build/export -allowProvisioningUpdates
```

Bundle id `space.dialectic.ios`, App Store Connect app "Dialectic". Icon: `swift make-icon.swift Dialectic/Assets.xcassets/AppIcon.appiconset/icon-1024.png` (from `app/frontend/public/icon.svg`).

## Checked

- Builds for simulator and device; runs on the iPad simulator against dev (log-in page, reader).
- Screen reading: page 3 of the seed PDF rendered as an image → Vision → first candidate found on dev (`/readings/2?page=3`), saved as a private test note by Ben.
- Not yet checked on a real device: the shortcut flow end to end (Back Tap / AssistiveTouch, the card), the edit-menu item.
