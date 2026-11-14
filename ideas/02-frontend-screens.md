# 02 · Frontend screens: the build slate

Status: **draft for the build** (replaces nothing). The visual designs for every web screen in SPEC §3, mapped to pages, components, routes and states, so a Claude Code session can start building `app/frontend/` from this file plus the spec.

**Designs:** the "Build slate" page of the design canvas, https://claude.ai/artifact/485yVaRimmN7xgDwDMzvSc (anyone with the link can view it). Frames are 1280×860 and link to each other, so you can click through the demo path. The "Explorations" page holds earlier drafts; ignore it when building.

The spec wins if this file and the spec disagree. Open product questions stay in SPEC §11, not here.

## Visual style

Plain CSS, one `src/styles.css` with these as custom properties at the top:

| Token | Value | Use |
| --- | --- | --- |
| `--bg` | `#F7F5F0` | Page background (warm paper) |
| `--card` | `#FFFFFF` | Cards, panels; radius 12–16px; shadow `0 1px 2px rgba(40,30,10,.06), 0 8px 24px rgba(40,30,10,.05)` |
| `--ink` / `--muted` | `#22201C` / `#5F5A50` | Text / secondary text |
| `--line` / `--line-soft` / `--field` | `#E2DCCF` / `#F0ECE4` / `#ECE8DF` | Input borders / row dividers / header border |
| `--accent` | `#2B5BB5` | Links, primary buttons, focus ring `#8DB5E8` |
| `--quote` | `#FFF4C9` | A quoted sentence from a source |
| `--notice-bg` / `--notice-icon` / `--notice-ink` | `#FFF4E0` / `#FFE2AE` / `#4F3F1F` | Charter notices (blocked layers) |

**Fonts:** Inter for the interface, Source Serif 4 for reading text (charter rules, quotes, source sentences). The PDF itself is the PDF.

**Person colours** (highlight background / avatar text). Assign by author: professor always mint, then a small fixed palette by `author.id`, so a person keeps one colour everywhere (highlight, avatar, margin card).

| | Background | Text |
| --- | --- | --- |
| Professor | `#CFEFD9` mint | `#1E4D2E` |
| Student 1 | `#FFDCCB` peach | `#6B2E14` |
| Student 2 | `#E4DBF7` lavender | `#3D2A6B` |
| Student 3 / you | `#D3E6FA` sky | `#1F3E66` |
| AI | `#22201C` badge "AI" | `#FFFFFF` |

Highlights are these backgrounds on the `HighlightLayer` with `mix-blend-mode: multiply` **on the layer, not on each box** (spike S1 found the per-box version hides the text). Icons are inline SVG, no emoji, no icon library.

## Pages

| Frame | Page (`src/pages/`) | Route | API | Notes |
| --- | --- | --- | --- | --- |
| S01 | `Login` | `/login` | `GET /users` | One row per seeded user: avatar, name, role/cohort. Click → `localStorage` + `/`. Small **Use on Mac** link per row (`dialectic://login?user=<id>`). |
| S02 | `Course` | `/` | `GET /course`, `POST /readings`, `GET /charter` | Header nav: Readings · Charter · Sources · Search. Reading cards. Professor only: dashed upload card (title + PDF). Charter summary card with the switches as pills. |
| S03–S11 | `Reader` | `/readings/:id?page=&annotation=` | see below | The core screen. |
| S12 | `Charter` (professor) | `/charter` | `GET`/`PUT /charter` | Rules textarea (Markdown), sources-we-trust textarea, **Save charter**. Switches panel on the right, one checkbox each, with one-line help; `max_explanation_words` as a number under "AI may write explanations". Proposals listed read-only. |
| S13 | `Charter` (student) | `/charter` | `GET /charter`, `POST /charter/comments` | Same page, `role !== 'professor'`: numbered rules (render the Markdown list), sources text, "What AI may do here" as On/Off pills, proposals + composer. |
| S14 | `Sources` | `/sources` | `GET`/`POST`/`DELETE /sources` | List: title (link), site, "found for <question>", pill **Found by AI** (sky) or **Added by <prof>** (mint), date. Professor only: URL form + Remove buttons. |
| S15 | `Search` | `/search?q=` | `GET /search?q=` | Two sections: "Notes and questions" and "In the readings". Each result links to the reader at that page/annotation. Turn `[[word]]` into `<mark>` by splitting the string in JS, **never** `innerHTML` (bodies are user input). |

Nav header (S02, S12–S15): wordmark, the four tabs (current one `background:#F3EFE6; font-weight:600`), avatar + name on the right. The reader has its own header instead (below).

## Reader (S03–S11)

**Header:** wordmark · breadcrumb "Readings › <title>" · green **Live** dot (polling is running) · zoom − / % / + · **Class charter** pill (→ `/charter`) · your avatar.

**Layout:** PDF column (centred, scrolls) + 360px margin on the right.

### Components (`src/components/`)

- **`PdfPage`**: one page: pdf.js canvas + text layer + `HighlightLayer`. Take the rendering code from `spikes/0306-pdf-selection/index.html` (text layer built before painting; `--scale-factor` on the container; `rangeToRects` → page fractions merged per line). Rebuild it in React; don't import the spike.
- **`HighlightLayer`**: absolutely positioned boxes from `rects` (fractions × page size). Not drawn for locked annotations. The selected/active one gets a `0 0 0 2px #8DB5E8` ring. Click → scroll the margin to that card.
- **`Margin`**: "Margin · p. N" heading, then cards for the current page in the order they sit on the page:
  - **Annotation card**: avatar, name, badge (`badge` from the API: "Professor", "Spring 2026", "AI"), body, replies indented under it with a small reply input. Your own cards get **Delete** and a "Shared with future classes" line. Questions asked from the Mac show "via the Mac hotkey" (`via: "hotkey"`).
  - **Lock card** (S03): dashed border, lock icon, "**N notes near here.** Add a note or ask a question to see them." (A count of notes, not people: locked annotations carry no author.) One per cluster of locked annotations, placed at their height. Group locked ones whose rects are near each other on the same page (same `NEAR_DISTANCE` idea as the server, 0.08 of page height).
- **Selection popover** (S04, S06): appears above the selection with two tabs, **Annotate** | **Ask**.
- **`Composer`** (S04): note textarea, "Share with future classes" checkbox (on by default), **Save note**. Saving refetches annotations, which unlocks the nearby cards (S05).
- **`AskPanel`** (S06–S11): the Ask tab is a question textarea and an **Ask** button, nothing else. **No suggested questions, no "Try:" chips, no rephrasing hints** (product decision: students write their own questions).

### Ask answer card (S07–S11)

A card anchored under the highlighted passage, over the page (not in the margin), ~560px wide with a little pointer to the passage. Header: the question + "You · posted to the class margin" + close. The question also appears as a card in the margin straight away.

Sections, **always in this order**, each only if it has content:

1. **From your class** (peer): avatar, name, badge, body. Click → scroll to that annotation.
2. **Sources**: numbered square chip, title (link with the `#:~:text=` fragment), site, the quoted sentence on `--quote` in Source Serif. Then a collapsed `<details>` "**N results skipped**" from `skipped_sources`: `not_permitted` and `not_covered` show title + reason **without a link**; `unreachable` and `no_answer` are linked.
3. **AI explanation**: starts collapsed as a dashed button with an "AI" badge: **"Still stuck? Show the AI explanation"** (S08). Open (S09): when it opens, peers and sources collapse to one summary row each; the explanation shows "Dialectic AI · public · N of M words", body with `[1]`/`[2]` rendered as the source chips, and replies like any annotation.

States:

| Frame | State | What drives it |
| --- | --- | --- |
| S07 | Loading | `/ask/stream`: render each section as its event arrives, but only in its slot. Under them a checklist of the `status` labels seen so far (✓ for finished, spinner on the latest). Peers usually arrive in under a second. |
| S08 | Answer, AI collapsed | `done` |
| S09 | AI explanation open | the button |
| S10 | Toggle off | `blocked` with `by: "toggle"`: amber notice in the AI slot, "Your class charter doesn't allow AI explanations." + the `label` + link to the charter. |
| S11 | Partly refused by a rule | `by: "rule"`: amber notice quoting the rule (`label`, e.g. "RULE 2" + text) and the `reason`. Other layers still show. |
| not drawn | `by: "no_sources"` | Same amber notice, `label` only. |
| not drawn | `by: "error"` / stream `error` | Same notice in red-ish (`#FBE4DE` / `#A1402A`), showing the real message. Keep what's already shown (SPEC: fail loudly). |

Use the plain `/ask` first if streaming isn't built yet (SPEC §8 #8 fallback: one spinner).

### Live updates

Poll `GET /readings/:id/annotations` every `POLL_MS = 5000` while `document.visibilityState === 'visible'`, and on window focus. The **Live** dot in the header is just a visible sign that this is running.

## Mac hotkey panel (S16, S17)

Drawn for josoup's Swift app (§3.9), not built in React; the same display rules apply. S16: captured text on `--quote`, "Found in <reading> · p. N" once located, question box, ⌥⇧D shown in the header, and "the PDF never leaves your Mac". S17: the same answer sections, AI collapsed, **Open in reader** (`SERVER_URL + located.reader_url`).

## Not drawn yet

- Charter gaps section on the charter page (§3.7, `GET /charter/gaps`, `ideas/01-charter-gaps.md`).
- Past-student opt-out (`PUT /me/sharing`, `PATCH /annotations/{id}`): a per-card "Shared with future classes" toggle exists in S05; a global switch would go in a user menu.
- Empty states (no readings, no annotations on a page, no search results) and the 404 "This passage isn't in a course reading" in the Mac panel.

## Build order (follows SPEC §8)

1. `api.js` (adds `X-User-Id`), `Login`, `Course` (S01–S02).
2. `Reader` with `PdfPage`, `HighlightLayer`, `Margin`, `Composer`, lock cards, polling (S03–S05). **Demo steps 1–2.**
3. `AskPanel` + answer card on plain `/ask`, AI collapsed (S06, S08, S09). **Demo step 3.**
4. Blocked notices (S10, S11) and the `Charter` page (S12, S13). **Demo step 4.**
5. Streaming states (S07), then `Sources`, `Search` (S14, S15).
