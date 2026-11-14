# Dialectic for Mac

Menu-bar app (SPEC §3.9, `design.md`). You read wherever you already read (Preview, Notability, a browser); Dialectic sits on top of the page. Same server and database as the web app; the Mac keeps nothing of its own.

| Key | Does |
| --- | --- |
| **⌥⇧D** | Ask about the selected text. Panel: From your class → Sources → "Still stuck? Show the AI explanation" (collapsed), then **Open in reader**. |
| **⌥⇧N** | Write a note on the selected text (`POST /api/note`). Says so when the passage is near a locked cluster: "N notes near here. Your note opens them." |

If ⌥⇧D or ⌥⇧N copies nothing (Notability with scanned or annotated PDFs, images), a crosshair appears: drag a box round the passage. Vision reads it on the Mac, the image is deleted at once, and only the text is sent as the quote. Esc cancels. No text in the box: "Couldn't read any text in that box." Not in a course reading: the server's "This passage isn't in a course reading."
| **⌥⇧H** | Show / hide classmates' highlights over the reading window: boxes by role (professor green, classmates magenta, you blue), dashed outlines for locked clusters, numbered pins, a status pill, and a margin strip with the threads. Click a card for the thread and reply. |

Code: `Sources/Dialectic/` — `DialecticApp.swift` (constants, menu, hotkeys, copy selection), `Panels.swift` (Ask, Note), `Overlay.swift` (capture, Vision, page fit, overlay windows, margin, thread), `Style.swift` (canvas tokens and shared pieces), `API.swift` (shapes and HTTP), `RenderCheck.swift` (the check below). Tunables are constants at the top of each file; `SERVER_URL` is in `DialecticApp.swift`.

## Build and run

```bash
./app/mac/build.sh                     # swift build + app/mac/build/Dialectic.app, ad-hoc signed
open app/mac/build/Dialectic.app
```

Needs Xcode or the Command Line Tools (Swift 5.9+), **macOS 14+** (ScreenCaptureKit screenshots). `SERVER_URL` defaults to `http://localhost:8000`; point it at the deployed site for the demo and rebuild. Logs: run `app/mac/build/Dialectic.app/Contents/MacOS/Dialectic` from a terminal.

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
