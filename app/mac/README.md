# Dialectic for Mac (hotkey app)

Menu-bar app from SPEC §3.9. Select text in any app (Preview, Notability, a browser), press **⌥⇧D**, type a question, press Enter. It sends `POST /api/ask` to the same server as the web app and shows: From your class → Sources → AI explanation (collapsed). **Open in reader** jumps to the question in the web reader.

All code is in `Sources/Dialectic/DialecticApp.swift`. Tunables (`SERVER_URL`, hotkey, timeouts, messages) are constants at the top.

## Build and run

```bash
./app/mac/build.sh                     # swift build + assembles app/mac/build/Dialectic.app, ad-hoc signed
open app/mac/build/Dialectic.app
```

Needs Xcode or the Command Line Tools (Swift 5.9+), macOS 13+. `SERVER_URL` defaults to `http://localhost:8000`; point it at the deployed site for the demo and rebuild. To see `print` logs, run the binary directly: `app/mac/build/Dialectic.app/Contents/MacOS/Dialectic`.

## First run

1. **Pick who you are** in the menu-bar menu (the quote icon): users come from `GET /api/users`. Or click **Use on Mac** on the web log-in page (`dialectic://login?user=<id>`).
2. **Grant Accessibility** (needed to copy your selection): the first ⌥⇧D shows macOS's prompt. Turn on Dialectic in System Settings → Privacy & Security → Accessibility, then press ⌥⇧D again.
   - After a rebuild, the ad-hoc signature changes and macOS may silently stop trusting the app: remove Dialectic from the Accessibility list and add it again (or toggle it off/on).

## Not built yet

- Screenshot + Vision capture when nothing is selected (SPEC §3.9 steps 1–2): today it says "Select some text first".
