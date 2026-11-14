# Dialectic for Mac

Menu-bar app (SPEC §3.9, `design.md`). You read wherever you already read (Preview, Notability, a browser); Dialectic sits on top of the page. It also has a **reader window**: the web app itself, so every reader feature is built once, on the web. Same server and database as the web app; the Mac keeps nothing of its own.

| Key | Does |
| --- | --- |
| **⌥⇧D** | Ask about the selected text. Panel: From your class → Sources → "Still stuck? Show the AI explanation" (collapsed), then **Open in reader**. |
| **⌥⇧N** | Write a note on the selected text (`POST /api/note`). Says so when the passage is near a locked cluster: "N notes near here. Your note opens them." |
| **⌥⇧H** | Show / hide classmates' highlights over the reading window: boxes by role (professor green, classmates magenta, you blue), dashed outlines for locked clusters, numbered pins, a status pill, and a margin strip with the threads. Click a card for the thread and reply. |

If ⌥⇧D or ⌥⇧N copies nothing (Notability with scanned or annotated PDFs, images), a crosshair appears: drag a box round the passage. Vision reads it on the Mac, the image is deleted at once, and only the text is sent as the quote. Esc cancels. No text in the box: "Couldn't read any text in that box." Not in a course reading: the server's "This passage isn't in a course reading."

## Reader window

**Open Dialectic** (menu, ⌘O; also shown at launch) opens a 1280×860 window with the web app in a `WKWebView`, loading `READER_URL` (top of `ReaderWindow.swift`, default `SERVER_URL`: in production FastAPI serves the built frontend on the same port). **In development** point it at Vite instead: `npm run dev` in `app/frontend` serves on `http://localhost:5173` and forwards `/api` to `:8000`.

- **Same person in both:** before every page load the window sets the web app's `localStorage` user (`dialectic_user`, the whole user object, plus `dialectic_users`, as `app/frontend/src/api.js` and `colors.js` save them at log-in) to the user picked in the menu, and reloads when that changes (menu or `dialectic://login`).
- **Open in reader** (Ask and Note panels, thread view) opens `reader_url` in this window and brings it to the front. Links to other sites (sources) open in the default browser.
- **Server down:** the window says "Can't reach the Dialectic reader at <URL>. Is the server running?" with **Retry**.

Code: `Sources/Dialectic/` — `DialecticApp.swift` (constants, menu, hotkeys, copy selection), `Panels.swift` (Ask, Note), `Overlay.swift` (capture, Vision, page fit, overlay windows, margin, thread), `ReaderWindow.swift` (the web reader window), `Style.swift` (canvas tokens and shared pieces), `API.swift` (shapes and HTTP), `RenderCheck.swift` (the check below). Tunables are constants at the top of each file; `SERVER_URL` is in `DialecticApp.swift`.

## Report a problem

Menu-bar menu → **Report a problem…** opens the same GitHub feedback form as the web app's button (`CLAUDE.md`, *Feedback issues*), prefilled with "Mac app", the server, the page open in the reader window, who you are, the app's build (`version.txt` in CI builds) and the macOS version.

## Download a build (no Xcode needed)

Every push to `main` that touches `app/mac/` is built on GitHub's macOS runners (`.github/workflows/mac-app.yml`, ~1 min). Open the latest **Mac app** run under the repo's **Actions** tab and download **Dialectic-dev-mac** (a zip of `Dialectic.app`). That build talks to the **dev copy**, `https://dialectic-dev.yaggy.dev`, not localhost; the commit it was built from is in `Dialectic.app/Contents/Resources/version.txt`. It's ad-hoc signed, so the first time: right-click → **Open**, then grant permissions as in *First run* below. The same run's **render-check** artifact has PNGs of every screen (stub data), for reviewing UI changes without a Mac.

## Build and run

```bash
./app/mac/build.sh                     # swift build + app/mac/build/Dialectic.app, ad-hoc signed
open app/mac/build/Dialectic.app
```

Needs Xcode or the Command Line Tools (Swift 5.9+), **macOS 14+** (ScreenCaptureKit screenshots). **Pick the server in the menu-bar menu → Server** (Dev, Demo, Sandbox or This Mac); the pick is remembered and the user list, reader window and highlights follow it. A fresh install starts on `DEFAULT_SERVER_URL` (top of `DialecticApp.swift`): `localhost:8000` in a local build, the dev copy in a CI build. Logs: run `app/mac/build/Dialectic.app/Contents/MacOS/Dialectic` from a terminal.

**Render check (no permissions, no server):** `app/mac/build/Dialectic.app/Contents/MacOS/Dialectic --render /tmp/dialectic-render` draws every screen with stub data to PNGs, and runs the real Vision + page-fit code on a rendered copy of page 2, printing the fit next to the right answer. (Text boxes, checkboxes and native buttons show as yellow placeholders there; that's ImageRenderer, not the app.)

## First run (on the demo Mac)

1. **Pick who you are** in the menu-bar menu, or click **Use on Mac** on the web log-in page (`dialectic://login?user=<id>`).
2. **Accessibility** (⌥⇧D and ⌥⇧N copy your selection): the first press shows macOS's prompt. Turn Dialectic on in System Settings → Privacy & Security → Accessibility.
3. **Screen Recording** (⌥⇧H reads the page on screen; the drag-a-box fallback captures the box): the first ⌥⇧H shows the prompt. Turn Dialectic on in System Settings → Privacy & Security → Screen Recording, then **quit and reopen** Dialectic. The screenshot stays on the Mac; only recognised text is sent.
4. After a rebuild the ad-hoc signature changes and macOS may quietly stop trusting the app: remove Dialectic from both lists and add it again.

## Stubbed: `POST /api/locate` (needs Owen's OK, then SPEC §6)

⌥⇧H needs one server route that doesn't exist yet. Until it does, a 404/405 from the server makes the app load `stub-locate-response.json` (page 2 of the seed reading) and the pill shows **stub data**. Annotations still come from the real `GET /readings/{id}/annotations` when the server is up (the stub's own demo annotations are used only if the server can't be reached). Regenerate the stub with `swift make-stub.swift ../backend/seed/souls-of-black-folk-ch1.pdf > stub-locate-response.json`. Search for `STUB:` to remove it later.

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
