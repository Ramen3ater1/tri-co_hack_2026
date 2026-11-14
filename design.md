# Dialectic: design (Mac app first)

**Status:** draft for review (Sat 03:45). **Owner:** josoup. **Reviewers:** Owen, Lyles, Shaun.

This file reconciles the two design outputs we have and says what the **Mac app** (`app/mac/`, SPEC §3.9) should look like and do. Where the two disagree it picks one and says why. `SPEC.md` is still the contract: anything here that would change a route or a checkpoint is marked **Needs SPEC change** and isn't in effect until it's agreed and written into `SPEC.md`.

**The two sources**

| | josue's canvas | Owen's spike |
| --- | --- | --- |
| What | Claude Design canvas, 12 boards: Library, Reader with peers, Repository search (+ class / web / AI variants), Charter, AI response, Teacher heatmap, Tools over any page (overlay), Peer reply with references, AI points to a source | `spikes/0306-pdf-selection/` (S1): the seed PDF with pdf.js text selection, page-fraction highlight boxes, Annotate / Ask popover, margin cards |
| Link | https://claude.ai/artifact/2rcYPxJfXHVsLhM9GtYiVj | http://130.58.222.155:8766/spikes/0306-pdf-selection/index.html |
| Strength | The overlay idea and the look | The thread model as built: how annotations anchor, show and connect, backed by SPEC §3.3–3.5 and §6 |

**Note on Owen's link:** it's a private network address, and it couldn't be opened from here. This draft uses the copy in the repo at the same path (`spikes/0306-pdf-selection/index.html`, committed by Owen at 03:12), plus the thread rules in `SPEC.md`, which Owen wrote. If the page Owen is serving has more than the committed copy (reply threads, for example), commit it or send an export, and this file gets updated.

---

## 1. What the Mac app is for

You read wherever you already read (Preview, Notability, a browser). Dialectic sits on top of that page instead of pulling you into its own reader. Three things, in priority order:

> **Update (Sat 05:25, josue):** the Mac app now *does* have a reader window, but not a native one: it shows the web app in a `WKWebView`, signed in as the Mac menu's user, and **Open in reader** opens there. Reader features are built once, on the web. The overlay and hotkeys below are unchanged. (`app/mac/README.md`, "Reader window".)


1. **Ask** about a passage without leaving the page (built: `⌥⇧D`).
2. **See where classmates highlighted**, drawn straight onto the page on your screen, with their threads in a margin beside it (new, §3).
3. **Write a note** on a passage, the same as Annotate in the web reader (new, §4).

Everything goes through the one server and database the web app uses (SPEC §3.9, "Same server, same person, same data"). The Mac app keeps nothing of its own and enforces no rules; it captures text and draws JSON.

---

## 2. The thread model (from Owen's spec and spike)

The Mac app shows threads exactly as the web reader does. Nothing below is new; it's collected here so the Swift side has one list to build against.

- **One kind of object.** Notes, questions, AI answers and replies are all annotations (SPEC §3.4): `kind` is `note` | `question` | `ai_answer`; a reply has `parent_id`.
- **One level of nesting.** A thread is a root annotation plus its replies, oldest first. Replies to replies show flat under the root.
- **Anchored by page fractions.** A root has `page`, `quote` and `rects` (`{x, y, w, h}` as fractions of the page, top-left origin, one box per line). Rects are what get drawn; `quote` is for search, the AI and as a readable fallback. This is the S1 result, and it's what makes the screen overlay possible (§3.2).
- **Who wrote it shows as a badge,** not a colour per person: `"Professor"`, `"AI"`, a past cohort (`"Spring 2026"`), or none for a current classmate.
- **The engagement lock.** A classmate's annotation is **locked** until you've written a note or asked a question near it (same page, vertical gap ≤ `NEAR_DISTANCE`). A locked one arrives as `{id, page, rects, locked: true}`, with no author or text. The professor's are always open. The Mac app must never try to work round this: it only ever gets what the server sends.
- **An answer is three layers, always in this order:** From your class → Sources → AI explanation. Empty layers are hidden; a layer the charter blocked shows its one-line notice in its place; the AI explanation starts collapsed behind **"Still stuck? Show the AI explanation"** (SPEC §3.5).
- **Every hotkey question is a normal annotation** (`via: "hotkey"`), public and open to replies, and shows up in the web margin within 5 s (web polling, SPEC §3.3).
- **Sources the charter skipped** are listed but not linked when `why` is `not_permitted` or `not_covered`; `unreachable` and `no_answer` are linked (SPEC §6).

From the spike's UI, carried over as is:

- **Margin card:** initial avatar, name, `p. N`, kind (`· question`), the quote as a chip (cut at ~48 characters), then the body. Clicking a card flashes its highlight (a 1.4 s outline pulse).
- **Composer copy:** Ask says *"Visible to the class. Classmates answer first."*; a note says *"Shared with the class."*
- **Highlights sit under the text and blend (multiply),** so the words stay readable through them.

---

## 3. New: classmates' highlights on your screen

**What the user sees.** You're reading the chapter in Preview. You press **`⌥⇧H`**. Translucent boxes appear over the passages classmates highlighted, on Preview's own page, and a thin **margin strip** appears down the right edge of the Preview window with one card per thread, level with its highlight and joined to it by a leader line. Scroll or zoom and the boxes follow. Press `⌥⇧H` again to hide them.

- **Open** annotations: filled box in the author's role colour (§5), with a margin card.
- **Locked** ones: a dashed outline, no fill, and in the margin a single card per cluster: *"2 classmates annotated near here. Add a note or ask a question to see theirs."* (same words as the web, SPEC §2 step 2). Locked ones *are* drawn on screen as outlines, because the server already sends their `rects`: the lock hides who and what, not where.
- **Your own:** blue box.
- Clicking a margin card opens that **thread panel** (§4.3).
- After you ask or note near a locked cluster, the next refresh (≤ 5 s) shows it open. That's the friction moment from demo step 2, on the Mac.

### 3.1 How it finds the page on screen

1. **Capture the front window.** Screenshot of the frontmost window (`CGWindowListCreateImage` or ScreenCaptureKit), in memory only. Needs **Screen Recording** permission (already required for the box capture in SPEC §3.9).
2. **Read it on the Mac.** Vision (`VNRecognizeTextRequest`, `.accurate`) gives text lines with their bounding boxes in window coordinates. The image never leaves the Mac (SPEC §1, Privacy).
3. **Locate.** Send the recognised text to the server, which matches it to a reading and page the same way the hotkey ask already does (`locate.py`: letters and digits only). It returns the page, plus the text lines of that page with their page-fraction boxes.
4. **Fit page to screen.** Match the OCR lines to the server's lines (same letters-and-digits comparison). Each matched line gives a pair: its box as a page fraction, and its box on screen. With two or more pairs, fit `screen_x = a·x + b`, `screen_y = c·y + d` (least squares). That one mapping turns **every** annotation's `rects` into screen boxes, locked ones included, with no per-quote matching.
5. **Fetch threads.** `GET /api/readings/{id}/annotations` (existing route), keep the ones on that page.
6. **Draw.** A borderless, transparent, click-through window over the reading window (`ignoresMouseEvents = true`, level just above the reading app) draws the boxes; a second small window is the margin strip, which takes clicks.

**Keeping up.** While the overlay is on: re-capture and re-fit every `OVERLAY_REFRESH_S` (1.0 s) and hide the boxes while the fit is stale (window moving or scrolling) rather than draw them in the wrong place; refetch annotations every `POLL_S` (5 s), like the web. Locate is re-run only when the matched lines stop fitting (you turned the page).

**Why fit lines instead of searching for each quote on screen:** locked annotations have no quote to search for, and the fit gives all boxes from one calculation, the same boxes the web draws. Searching each quote in the OCR text is the fallback if the fit fails (fewer than 2 matched lines): then only open annotations are drawn.

**Privacy.** Only recognised text from the front window goes to the server, and only while the overlay is on, which you turned on yourself. To keep it small, send the `LOCATE_SAMPLE_LINES` (8) longest lines, not the whole window. Text that isn't from a course reading gets a 404 and the overlay shows *"This page isn't a course reading."* and turns itself off.

`TODO(edge)`: two pages side by side or a page break mid-screen (use the page with the most matched lines); rotated or scanned PDFs; multiple displays (use the reading window's screen).

### 3.2 What it needs from the server

**Needs SPEC change (§6, backend owner):** one new route, a thin wrapper around `locate.py`, which already exists for `POST /api/ask`.

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| POST | `/locate` | `{"text": "<recognised lines, joined by \n>"}` or `{"quote": "..."}` | `{"located": {reading_id, reading_title, page, section, reader_url}, "lines": [{"text", "rect": {x, y, w, h}}], "rects": [...]}` |

- `lines`: every text line on that page with its page-fraction box (pdfplumber, as the seed already does). For the fit in §3.1.
- `rects`: only when `quote` is sent: the quote's boxes, for creating a note from the hotkey (§4.2).
- 404 `{"detail": "This passage isn't in a course reading."}` as for `/ask`.
- No user data in or out; it still needs `X-User-Id` like every route.

Annotations come from the existing `GET /readings/{id}/annotations`; no change.

---

## 4. The Mac app's screens

> **Update (Sat 08:57, josue): one hotkey, one panel.** The three hotkeys below (`⌥⇧D` ask, `⌥⇧N` note, `⌥⇧H` highlights) are replaced by **one, `⌃⌥D`** (Control-Option-D). It opens one panel with **Ask | Note** tabs (the last one used is remembered) sharing the quote and a "section, p. N" line; the highlights overlay is a **switch** in that panel's header and in the menu-bar menu (the pill says "· Hide"). §4.1 and §4.2 now describe the two tabs of that panel; the rest stands. (`app/mac/README.md`; SPEC wording pending Owen.)

### 4.1 Ask panel (`⌥⇧D`, built)

Floating panel near the selection: the quote as a chip, a question box, Enter to send. The answer fills in the three layers (§2), then **Open in reader**. Already built in `DialecticApp.swift`; changes:

- Use the margin-card layout (§2) for "From your class" entries, so a peer answer looks the same in the panel, the margin strip and the web.
- Add **What was sent** (from josue's AI board) as a one-line disclosure under the AI layer: *"Sent to the AI: your question, the highlighted passage, the charter and the source excerpts. No names."* Static text that matches SPEC §7; no new data.
- After an answer, if the overlay is on, it refreshes at once so the new question's box appears.

### 4.2 Note (`⌥⇧N`, new)

Select text, press `⌥⇧N`: same panel with *"Your note…"* and *"Shared with the class."* and a **Share with future classes** checkbox (on by default, SPEC §3.4). Save calls `POST /locate` with `{quote}` to get reading, page and rects, then the existing `POST /readings/{id}/annotations`.

**Needs SPEC change (§6):** the note body should accept `"via": "hotkey"`, so a Mac note is marked like a Mac question. Small, optional; without it the note is saved as `via: "web"`.

### 4.3 Thread panel (new)

Opened from a margin card or an Ask-panel peer entry. The root annotation as a card, its replies below oldest first, a reply box at the bottom (`POST /readings/{id}/annotations` with `parent_id`). An AI answer in a thread is labelled **AI** and lists its cited sources. Delete on your own annotations only (`DELETE /annotations/{id}`). **Open in reader** at the bottom.

### 4.4 Menu-bar menu (built)

Who you are (from `GET /api/users`), the hotkeys with their labels, **Show classmates' highlights** (same as `⌥⇧H`), Quit.

---

## 5. Look

The Mac app follows josue's canvas; the web app can adopt the same tokens if its owner wants. **Light mode only.**

| Token | Value | From |
| --- | --- | --- |
| Background | `#F4F3EE` | canvas |
| Ink | `#161513` | canvas |
| Muted text | `#5A5750` | canvas |
| Line | `rgba(90,87,80,0.35)`, 1 px | canvas |
| Panel | `#FFFFFF`, radius 16, padding 16 | canvas |
| Reading text, quotes | Literata (Georgia if not installed) | canvas |
| UI text | system font (SF Pro) on the Mac, Inter on the web | canvas / native |
| Touch target | 44 px minimum | canvas |

**Highlight colours, by role, not by person:**

| Who | On screen | Margin card |
| --- | --- | --- |
| Classmate (any cohort) | `#D83FB7` at 22% fill | 3 px magenta left edge, cohort badge if past |
| Professor | `#2F8F5B` at 22% fill | green left edge, "Professor" badge |
| You | `#2B5BB5` at 22% fill | blue left edge |
| Locked cluster | `#D83FB7` 1.5 px dashed outline, no fill | count card, no author |
| AI | not drawn (AI answers hang off a question) | "AI" badge |

---

## 6. Where the designs disagree, and what we pick

| # | Topic | Canvas (josue) | Spike / SPEC (Owen) | Pick | Why |
| --- | --- | --- | --- | --- | --- |
| 1 | Hotkeys | `⌃⌥` + letter, a palette of 5: M mark, Q ask the class, P peer marks, A ask AI, S search | One hotkey, `⌥⇧D` (built and in SPEC) | **`⌥⇧` family:** D ask, N note, H highlights | `⌥⇧D` is built and in the spec and README; three keys cover the demo. No palette: one more window for no new action. |
| 2 | Asking the AI directly | "Ask AI about this" is its own action | AI is the third layer of Ask, after peers and sources, collapsed, gated by the charter | **Spec.** No separate AI key | It's the product's thesis (SPEC §1, Friction; charter rule 1: "AI comes last"). |
| 3 | Private notes | "Your mark: private unless you share it" | Visible to the class by default; only "share with future classes" is optional | **Spec** | Collaboration is the point, and the lock relies on notes being shared. |
| 4 | Peer marks visible at once | Overlay shows peer marks straight away | Engagement lock: locked until you note or ask nearby | **Spec,** shown as dashed outlines + count | Demo step 2 depends on it; the server enforces it anyway. |
| 5 | Words | "mark" | "note", "question", "annotation" | **Spec's words** in the UI ("note", "question") | One vocabulary across web, Mac and the demo script. |
| 6 | Highlight colour | One magenta for all peers | A pastel colour per person | **By role** (§5) | Per-person colours don't scale to a class and mean nothing to a reader; role tells you whose guidance it is. |
| 7 | Palette and type | Warm off-white, Literata + Inter, radius 16 | Similar off-white, Inter + Georgia, blue accent, radius 12 | **Canvas** for the Mac; blue kept for "you" | Mac is josue's track; the two are close enough that the web can match later without rework. |
| 8 | References on peer replies | A reply lists typed references (passage, article, doc, online) | Replies are text only; only AI answers cite sources (`cited_source_ids`) | **Spec for now;** reply references are a stretch | Needs a schema and API change; not on the demo path. |
| 9 | Search in the overlay | Class / web / AI search tabs over the page | Search is a web page, could-have #11; no web search for students outside Ask | **Not in the Mac app** | Ask already covers "find me sources" under the charter; web search outside it would bypass the charter. |
| 10 | "Pauses" and the teacher heatmap | Reader and heatmap count pauses (time spent per page) | No reading-time tracking in the spec | **Out of scope;** if a heatmap is built, count notes and questions per page, keep "fewer than 5 students hidden" | Tracking reading time is new data about real students; not worth it on the day. |
| 11 | "AI points to a source" | A leader line from the AI card to the passage on screen, "Show in reading" | Sources link out with a text fragment (`#:~:text=`); "Open in reader" | **Both,** using the overlay: if the cited passage is on screen, flash its box; otherwise open the link | The overlay gives us the on-screen pointer for free once §3 works. |
| 12 | "What was sent" panel | Shown under every AI answer | Privacy rule exists (SPEC §7), no UI | **Canvas,** as one static line (§4.1) | Cheap, true, and it makes the privacy story visible in the demo. |
| 13 | Charter page | Ratification box with a vote count, version history | Professor edits, students comment; version history is a non-goal | **Spec** (web only; not a Mac screen) | Matches §3.7 and the non-goals. |

---

## 7. Build order for the Mac app

Nothing here moves a SPEC §8 checkpoint: the Mac app stays an independent track. Cut from the bottom.

1. **Ask panel polish** (§4.1): peer entries as margin cards, "What was sent". Small, demoable now.
2. **Screen capture + Vision** (§3.1 steps 1–2). Shared with the box capture already planned (SPEC §8 #9), so this is one piece of work for both.
3. **`POST /api/locate`** (§3.2): backend, small. Ask Owen or do it with his OK, then update SPEC §6.
4. **Highlights overlay** (§3): fit, draw boxes, margin strip, `⌥⇧H`. This is the demo moment for the Mac.
5. **Thread panel with replies** (§4.3).
6. **Note hotkey** (§4.2).
7. Fallbacks and edges: quote-search fallback when the fit fails, "isn't a course reading" message.

**Demo line for the overlay** (add to SPEC §2 if we keep it): Ben has the chapter open in Preview, presses `⌥⇧H`, and sees Prof. Rivera's green box on "born with a veil" and a dashed outline on double-consciousness ("2 classmates annotated near here"). He selects the passage, `⌥⇧N`, writes a note; a few seconds later the outline fills in magenta and Ana's and Sam's notes appear in the margin strip.

---

## 8. Open questions

1. **`⌥⇧H` and the new route:** OK with Owen to add `POST /api/locate` (§3.2) and `via` on notes? Both need SPEC §6.
2. **Overlay in the demo:** does it go into the SPEC §2 demo path (as above), or stay a bonus if it works by 12:00?
3. **Owen's served page:** is there anything at the 130.58.222.155 link that isn't in the committed spike?
4. **Web tokens:** does the web reader's owner want the canvas palette (§5), or keep the spike's?
