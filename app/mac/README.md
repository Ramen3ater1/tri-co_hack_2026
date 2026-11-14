# Dialectic for Mac

Menu-bar app (SPEC §3.9, `design.md`). You read wherever you already read (Preview, Notability, a browser); Dialectic sits on top of the page. It also has a **reader window**: the web app itself, so every reader feature is built once, on the web. Same server and database as the web app; the Mac keeps nothing of its own.

**One hotkey, ⌃⌥D (Control-Option-D).** Select text anywhere and press it: one panel opens with the quote and two tabs, **Ask | Note** (Ask the first time; after that, whichever you used last).

- **Ask:** your question goes to `POST /api/ask`. The answer: From your class → Sources → "Still stuck? Show the AI explanation" (collapsed), then **Open in reader**.
- **Note:** `POST /api/note`, with **Share with future classes**. Near locked notes it says "N notes near here. Your note opens them."
- **Highlights switch** in the panel header (also **Show highlights** in the menu-bar menu; no hotkey of its own): classmates' highlights over the reading window, with boxes by role (professor green, classmates magenta, you blue), dashed outlines for locked notes, numbered pins, a status pill ("Classmates' highlights · section, p. N · **Hide**") and a margin strip with the threads. Click a card for the thread and reply.

If ⌃⌥D copies nothing (Notability with scanned or annotated PDFs, images), a crosshair appears: drag a box round the passage. Vision reads it on the Mac, the image is deleted at once, and only the text is sent as the quote. Esc cancels. No text in the box: "Couldn't read any text in that box." Not in a course reading: the server's "This passage isn't in a course reading."

Menu-bar menu: **Ask or note on selection (⌃⌥D)**, **Show highlights**, **Open Dialectic**, who you are, the server.

## Session highlights

**Start session** (link in the ⌃⌥D panel, or the menu-bar menu) while your PDF app is in front. Highlight in your own app as you read; a pill at the top says **"Dialectic session · N highlights · End"** (plus "N not in a course reading" when a mark isn't in one). **End** (pill, panel or menu) opens a review: each new highlight with its page and an optional note box; **Save notes** saves the ones that have a note, through `POST /api/note`, so they count for the lock like any note.

How it sees them (`Session.swift`, constants at the top): every 2 s it captures the reading window in memory (never written to disk), Vision reads the text with a box per word, and each word's background pixels are checked for a highlighter colour (saturated and bright, unlike white paper or dark text). Runs of marked words on a line become one quote. Marks already there when you pressed Start are ignored, the same text is counted once, and each quote is located like any other (only text leaves the Mac). Handwriting and pen marks aren't captured; a mark across two lines gives two quotes (`TODO(edge)`). The render check tests the colour detection on page 2 with a drawn yellow mark (finds exactly that quote) and without (finds nothing).



**Open Dialectic** (menu, ⌘O; also shown at launch) opens a 1280×860 window. While it's open Dialectic acts as a normal app (its own menu bar, a Dock icon, ⌘Tab); close it and it goes back to living in the menu bar only. The window holds the web app in a `WKWebView`, loading `READER_URL` (top of `ReaderWindow.swift`, default `SERVER_URL`: in production FastAPI serves the built frontend on the same port). **In development** point it at Vite instead: `npm run dev` in `app/frontend` serves on `http://localhost:5173` and forwards `/api` to `:8000`.

- **Same person in both:** before every page load the window sets the web app's `localStorage` user (`dialectic_user`, the whole user object, plus `dialectic_users`, as `app/frontend/src/api.js` and `colors.js` save them at log-in) to the user picked in the menu, and reloads when that changes (menu or `dialectic://login`).
- **Open in reader** (Ask and Note panels, thread view) opens `reader_url` in this window and brings it to the front. Links to other sites (sources) open in the default browser.
- **Server down:** the window says "Can't reach the Dialectic reader at <URL>. Is the server running?" with **Retry**.

Code: `Sources/Dialectic/` — `DialecticApp.swift` (constants, menu, the hotkey, copy selection), `Panels.swift` (the Ask | Note panel), `Overlay.swift` (capture, Vision, page fit, overlay windows, margin, thread), `ReaderWindow.swift` (the web reader window), `Style.swift` (canvas tokens and shared pieces), `API.swift` (shapes and HTTP), `RenderCheck.swift` (the check below). Tunables are constants at the top of each file; `SERVER_URL` is in `DialecticApp.swift`.

## Report a problem

Menu-bar menu → **Report a problem…** opens the same GitHub feedback form as the web app's button (`CLAUDE.md`, *Feedback issues*), prefilled with "Mac app", the server, the page open in the reader window, who you are, the app's build (`version.txt` in CI builds) and the macOS version.

## Download a build (no Xcode needed)

Every push to `main` that touches `app/mac/` is built on GitHub's macOS runners (`.github/workflows/mac-app.yml`, ~1 min). Open the latest **Mac app** run under the repo's **Actions** tab and download **Dialectic-dev-mac** (a zip of `Dialectic.app`). That build talks to the **dev copy**, `https://dialectic-dev.yaggy.dev`, not localhost; the commit it was built from is in `Dialectic.app/Contents/Resources/version.txt`. It's a universal app (Intel and Apple Silicon), ad-hoc signed: macOS calls a downloaded copy **"damaged"** until you run `xattr -dr com.apple.quarantine /Applications/Dialectic.app` (once per download; right-click → Open no longer gets round it). Then grant permissions as in *First run* below. The same run's **render-check** artifact has PNGs of every screen (stub data), for reviewing UI changes without a Mac.

## Build and run

```bash
./app/mac/build.sh                     # swift build + app/mac/build/Dialectic.app, signed (see First run)
open app/mac/build/Dialectic.app
```

Needs Xcode or the Command Line Tools (Swift 5.9+), **macOS 14+** (ScreenCaptureKit screenshots). **Pick the server in the menu-bar menu → Server** (Dev, Demo, Sandbox or This Mac); the pick is remembered and the user list, reader window and highlights follow it. A fresh install starts on `DEFAULT_SERVER_URL` (top of `DialecticApp.swift`): `localhost:8000` in a local build, the dev copy in a CI build. Logs: `~/Library/Logs/Dialectic.log` (the first lines say whether Accessibility and Screen Recording are granted), or run `app/mac/build/Dialectic.app/Contents/MacOS/Dialectic` from a terminal. `open "dialectic://hotkey?key=ask"` runs the same path as pressing ⌃⌥D, for testing.

**Render check (no permissions, no server):** `app/mac/build/Dialectic.app/Contents/MacOS/Dialectic --render /tmp/dialectic-render` draws every screen with stub data to PNGs, and runs the real Vision + page-fit code on a rendered copy of page 2, printing the fit next to the right answer. (Text boxes, checkboxes and native buttons show as yellow placeholders there; that's ImageRenderer, not the app.)

## First run (on the demo Mac)

1. **Pick who you are** in the menu-bar menu, or click **Use on Mac** on the web log-in page (`dialectic://login?user=<id>`).
2. **Accessibility** (⌃⌥D copies your selection): the first press shows macOS's prompt. Turn Dialectic on in System Settings → Privacy & Security → Accessibility.
3. **Screen Recording** (the highlights switch reads the page on screen; the drag-a-box fallback captures the box): the first use shows the prompt. Turn Dialectic on in System Settings → Privacy & Security → Screen Recording, then **quit and reopen** Dialectic. The screenshot stays on the Mac; only recognised text is sent.
4. **Grants and rebuilds:** `build.sh` signs with your Apple Development certificate if the Mac has one (`DIALECTIC_SIGN_ID` picks another), and then the grants survive rebuilds. Without one it signs ad hoc, the signature changes on every build, and macOS quietly stops trusting the app: remove Dialectic from both lists with **−**, add `app/mac/build/Dialectic.app` back with **+**, then quit and reopen it. Grant once more after the first certificate-signed build.

## Stubbed: `POST /api/locate` (needs Owen's OK, then SPEC §6)

The highlights need one server route that doesn't exist yet. Until it does, a 404/405 from the server makes the app load `stub-locate-response.json` (page 2 of the seed reading) and the pill shows **stub data**. Annotations still come from the real `GET /readings/{id}/annotations` when the server is up (the stub's own demo annotations are used only if the server can't be reached). Regenerate the stub with `swift make-stub.swift ../backend/seed/souls-of-black-folk-ch1.pdf > stub-locate-response.json`. Search for `STUB:` to remove it later.

Proposed shape (design.md §3.2), a thin wrapper round `locate.py`:

```
POST /api/locate        X-User-Id: <id>
{"text": "<the 8 longest recognised lines, joined by \n>"}

200 {"located": {"reading_id": 1, "reading_title": "...", "page": 2, "section": "Of Our Spiritual Strivings",
                 "reader_url": "/readings/1?page=2"},
     "lines": [{"text": "refused my card,—refused it peremptorily, ...", "rect": {"x": 0.1275, "y": 0.0935, "w": 0.7434, "h": 0.0168}}, ...]}
404 {"detail": "This passage isn't in a course reading."}
```

- `lines`: every text line on that page, with its box as page fractions (top-left origin), from pdfplumber as the seed does. The app fits these to the lines Vision finds on screen; that one fit places every annotation's `rects`, locked ones included.
- Server side: `find_page` on the text (try each line until one matches), then group the page's `chars` into lines (`round(top)` as `quote_rects` already does).

`POST /api/note {quote, body, share_with_future}` is in the backend (SPEC §6): it locates like `/ask` and saves a note with `via: "hotkey"`.

## Not built / edges

- Leader lines from margin cards to boxes; clicking a box on the page (the overlay is click-through).
- `TODO(edge)`: two pages side by side, rotated or scanned PDFs, several displays (uses the reading window's screen).

## SPEC change: approved

The reader-window wording below was approved by Owen (Sat 06:45) and is now in `SPEC.md` §3.9 and §4.

## Proposed SPEC change (pending Owen): one hotkey, one panel

Not in `SPEC.md` yet (josue's pick, Sat 08:57; needs Owen's OK). Proposed wording:

- **§3.9 step 1:** *"Press the hotkey (`⌃⌥D`, Control-Option-D, a constant at the top of the app)."* (replaces `⌥⇧D`).
- **§3.9 step 3:** *"**Ask or note.** One floating panel shows the captured text and two tabs, **Ask | Note** (the last one used is remembered). Ask sends `POST /api/ask` (§6) with `{quote, question}`; Note sends `POST /api/note` with `{quote, body, share_with_future}`. Both use the `X-User-Id` chosen in the app's menu."*
- **§3.9, new line:** *"**Classmates' highlights** over the reading window are a switch in the panel header and in the menu-bar menu, not a hotkey."*
- **§6, `/note` row:** "Hotkey note (⌥⇧N, §3.9)" becomes "Hotkey note (the Note tab of ⌃⌥D, §3.9)".

## Proposed change (pending Owen): saving a highlight without a note

Session highlights without a note are dropped today, because the server only saves notes. Proposed:

```
POST /api/highlight     X-User-Id: <id>
{"quote": "..."}        → locates like /note, saves kind = "highlight" (no body), via "hotkey"
200 {annotation}        404 {"detail": "This passage isn't in a course reading."}
```

Open question for SPEC §11: does a bare highlight count as engagement for the lock (§3.4)? Suggested default: **no**, only notes and questions open classmates' notes; a highlight is drawn in your colour but opens nothing.

