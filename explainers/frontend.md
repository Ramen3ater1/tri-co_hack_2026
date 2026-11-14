# How the frontend works

A high-level tour of `app/frontend/`, written Saturday 04:48, **before any of it was built**: it describes the planned shape so whoever builds it (and their teammates) can find their way around. `SPEC.md` says *what* we're building and `ideas/02-frontend-screens.md` says *what each screen looks like*; this explains *how the code is arranged*. As the frontend gets built, keep this file true: if the code and this file disagree, the code wins, so fix this file.

## The shape of it

The frontend is a **React single-page app built with Vite**: `react-router` for pages, `react-pdf` (which wraps pdf.js) for the reading, **plain CSS** and **no state library**. Each page fetches what it needs with `fetch` when it mounts and keeps it in `useState`. There is no global store, no cache layer and no generated API client: one small `api.js` does every request.

```
browser
  └─ React app (Vite)
       pages/ ──▶ api.js ──HTTP + X-User-Id──▶ /api/... (FastAPI, explainers/backend.md)
       Reader ──▶ react-pdf ──GET /api/readings/{id}/pdf
```

- **In development** Vite runs on its own port and **proxies `/api` to `localhost:8000`** (the backend has no CORS, so the proxy is what makes this work).
- **In production** `npm run build` writes `app/frontend/dist/`, and the backend serves it: `main.py` mounts `dist/assets` and sends `index.html` for every other non-`/api` path, so `react-router` can handle deep links like `/readings/1?page=3`. One process, one port, behind Caddy.

## The files (planned)

| File | What it's for | Screens |
| --- | --- | --- |
| `src/api.js` | `get`, `post`, `put`, `patch`, `del`, plus `askStream()`. Adds the `X-User-Id` header from `localStorage`; on a non-2xx response it throws an `Error` carrying the server's `detail`. | all |
| `src/main.jsx` | Router setup: the routes in the table below, and a redirect to `/login` if no user is stored. | |
| `src/styles.css` | The one stylesheet. Colour and font tokens as custom properties at the top (`--bg`, `--card`, `--accent`, `--quote`, `--notice-*`…, from ideas/02 *Visual style*). | |
| `src/colors.js` | Person colours: professor mint, AI black, then a fixed palette picked by `author.id`, so a person keeps one colour on their highlight, avatar and card. | |
| `src/pages/Login.jsx` | `/login` | S01 |
| `src/pages/Course.jsx` | `/`: reading cards, the professor's upload card, the charter summary card. | S02, S21 |
| `src/pages/Reader.jsx` | `/readings/:id`: the core screen. Owns the annotations list, polling, the current selection and the open answer card. | S03–S11 |
| `src/pages/Charter.jsx` | `/charter`: one page; the professor gets editors, students get the read-only view and a proposal box. Charter gaps live here too. | S12, S13, S18 |
| `src/pages/Sources.jsx` | `/sources`: the course source library. | S14 |
| `src/pages/Search.jsx` | `/search?q=` | S15 |
| `src/components/NavHeader.jsx` | Wordmark, the four tabs, avatar + the user menu (sharing switch, Switch user, Use on Mac). Not used by the reader. | S02, S12–S15, S19 |
| `src/components/PdfPage.jsx` | One page: pdf.js canvas + text layer + `HighlightLayer`. | S03 |
| `src/components/HighlightLayer.jsx` | The coloured boxes for a page's annotations. | S03 |
| `src/components/Margin.jsx` | The right-hand column: annotation cards, lock cards, reply inputs. | S03, S05 |
| `src/components/Composer.jsx` | The note form inside the selection popover. | S04 |
| `src/components/AskPanel.jsx` | The question box, and the answer card it opens. | S06–S11, S20 |

`public/manifest.webmanifest` + an icon is the whole PWA (SPEC §4). Split a file only when it gets hard to read; don't add folders beyond `pages/` and `components/`.

## Who you are

There are no passwords (SPEC §3.1). `Login` lists `GET /api/users`; clicking a row stores the id in `localStorage` and goes to `/`. `api.js` reads it on every request and sends it as **`X-User-Id`**. The current user (with `role`) comes back in `GET /api/course`; a page that needs to know "am I the professor?" checks `user.role === 'professor'`. That only decides what to *show*: the server enforces who may do what (a student's `PUT /charter` gets a 403 whatever the UI does).

A 401 means the stored id is unknown (for example after `seed.py --reset`): clear it and go to `/login`.

## The reader

Everything that makes the demo is on this one screen, so it's worth knowing how its pieces fit.

```
Reader (state: reading, annotations, selection, openAnswer, zoom)
 ├─ reader header (breadcrumb, Live dot, zoom, Class charter pill, avatar)
 ├─ PDF column:  PdfPage × page_count
 │                 ├─ canvas (pdf.js)
 │                 ├─ HighlightLayer   ← annotations for this page
 │                 └─ text layer       ← where selection happens
 │               selection popover: [Annotate | Ask] → Composer / AskPanel
 │               answer card (anchored under the passage)
 └─ Margin (360px): cards for the current page, in page order
```

### Drawing the PDF and highlights

The hard part was proven in spike S1 (`spikes/0306-pdf-selection/`): **rebuild its approach in React, don't import it** (CLAUDE.md: `app/` never imports a spike).

- **Rects are page fractions** (`{x, y, w, h}`, 0–1, top-left origin). The highlight boxes are positioned in `%`, so they stay on the right words at any zoom with nothing recomputed. That's why zoom is cheap: it just re-renders the pages at the new scale.
- **Layer order matters.** The highlight layer sits *under* the text layer, with `mix-blend-mode: multiply` **on the layer, not on each box** (per box, it hides the text). The text layer must stay on top or you can't select.
- **Text layers before canvases.** Build every page's text layer first, then paint canvases, so the page is selectable sooner.
- **Making a selection into rects:** `rangeToRects(range, pageEl)` takes `range.getClientRects()`, converts each to fractions of the page element, and merges them into one box per line. Store that with `page` and `quote` (the selected text) when you save a note or ask.
- Selections spanning two pages keep the first page only (`TODO(edge)`).

### The margin and the engagement lock

`GET /readings/{id}/annotations` returns every annotation you can see, on all pages, newest first. The reader keeps that whole list and **filters by page** for the margin and each page's highlights.

- A **full** annotation has an author, body, badge and `replies`. The card shows avatar, name, badge ("Professor", "Spring 2026", "AI", or nothing for current classmates), body, replies indented, and a reply input. Your own cards also get **Delete** and the share-with-future checkbox. `via: "hotkey"` adds "via the Mac hotkey"; `answer_summary` on a question adds "Answered: 2 classmates, 1 source, AI context" and clicking reopens the answer (`GET /questions/{id}/answer`).
- A **locked** annotation is only `{id, page, rects, locked: true, group, group_notes}`: no author, no text. Draw **no highlight** for it, and **one lock card per `group`**: "**N notes near here.** Add a note or ask a question to see them.", placed at the group's height. The server did the grouping; the frontend just collects by `group`.
- **Nothing about unlocking lives in the frontend.** After you save a note (or ask), refetch the annotations; the server now sends the nearby ones in full and the lock cards disappear. That refetch is demo step 2.

### Live updates

While the tab is visible, the reader refetches annotations every **`POLL_MS = 5000`** and on window focus. The green **Live** dot in the header only shows that polling is running. Replacing the list wholesale on each poll is fine; don't try to merge.

### Notes and replies

The selection popover has two tabs, **Annotate** and **Ask**. Annotate opens the `Composer`: textarea, "Share with future classes" (on by default), **Save note** → `POST /readings/{id}/annotations` with `{page, quote, rects, body, share_with_future}`. A reply is `{parent_id, body}` to the same route. Delete is `DELETE /annotations/{id}`. Each one refetches afterwards.

## Asking a question

`AskPanel` is a question textarea and an **Ask** button. **No suggested questions, "Try:" chips or rephrasing hints anywhere** (product decision: students write their own).

### Plain first, then streamed

1. **Plain** (build this first): `POST /readings/{id}/ask` with `{page, quote, rects, question}`, one spinner, then render the response. Takes about 22–25 s the first time a question is asked and about 7 s on replay.
2. **Streamed** (S07, SPEC §8 #8): `POST /readings/{id}/ask/stream` returns **newline-delimited JSON**. Read it with `fetch` + `response.body.getReader()`, split on `\n`, `JSON.parse` each line (not `EventSource`, which can't POST). `askStream(path, body, onEvent)` in `api.js` hides this; the panel just handles events:

| Event | What the panel does |
| --- | --- |
| `question` | The question is saved: refetch annotations so it appears in the margin straight away. |
| `status` | Add its `label` to the checklist (✓ the earlier ones, spinner on this one). |
| `peer` | Fill the *From your class* slot. |
| `blocked` | Add to the notices (it can come more than once). |
| `sources` | Fill *Sources* and the "N results skipped" details. |
| `ai_answer` | Fill the AI slot (still collapsed), or nothing if `null`. |
| `done` | `result` is the full `/ask` response: replace everything with it. Stop the checklist. |
| `error` | Keep what's shown; add the red "Couldn't answer this question" with `detail` and **Ask again**. |

Each section only ever renders **in its own slot**, so the card doesn't jump around as events arrive.

### The answer card

Always in this order, each only if it has content:

1. **From your class** (`peer`): click → scroll to that annotation.
2. **Sources**: numbered chip, title linked to the `#:~:text=` URL (opens the source scrolled to the sentence), site, and the quoted sentence. Then `<details>` "N results skipped": `not_permitted` and `not_covered` show title + reason **without a link**; `unreachable` and `no_answer` **are linked**.
3. **AI explanation**: starts collapsed as "Still stuck? Show the AI explanation". Opening it collapses the other two to a summary row each. `[1]`, `[2]` in the body become the source chips.

**Charter notices** come from `blocked[]`, shown in the slot of the layer they block:

| `by` | Looks like |
| --- | --- |
| `toggle` | Amber: "Your class charter doesn't allow AI explanations." + `label` + link to the charter (S10). |
| `rule` | Amber, quoting the rule (`label`) and the `reason` (S11). Other layers still show: partial refusals are normal. |
| `no_sources` | Amber, `label` only. |
| `error` | Red, the real error in monospace (S20). For sources, say the library was used instead. |

Until the backend is reachable, you can render the card from the example `/ask` JSON in SPEC §6 (the Mac app did the same with a stub).

## Safety rules the frontend must keep

- **Never `innerHTML` user text.** Annotation bodies, quotes and search snippets are user input. Search marks hits as `[[word]]`: split the string in JS and wrap the hits in `<mark>` elements. React escapes everything else by default; don't use `dangerouslySetInnerHTML`.
- **Don't link sources the charter ruled out** (`not_permitted`, `not_covered`). Showing them is the point; linking them would route around the charter.
- **Fail loudly** (CLAUDE.md). Every `api.js` error carries the server's `detail` (a 500's is the real error, e.g. a missing API key). Show it on screen; never swallow it or fall back silently.

## The other pages, briefly

- **Course** (`GET /course`): reading cards ("7 pages · 2 notes · 0 questions"); professor-only dashed upload card → `POST /readings` as multipart (`FormData` with `title` + `file`; don't set `Content-Type` yourself). Charter summary card with the toggles as pills.
- **Charter** (`GET`/`PUT /charter`, `POST /charter/comments`): the professor edits the rules (Markdown), the sources-we-trust text and the toggles, then **Save charter** (`PUT` takes any subset of fields). Students see numbered rules, On/Off pills and a proposal box. **Charter gaps** (`GET /charter/gaps`): Allow / Rule out append a sentence to the unsaved sources text; nothing applies until Save. Dismiss is `POST /charter/gaps/dismiss`.
- **Sources** (`GET`/`POST`/`DELETE /sources`): the library, "found for Ben's question" or "Added by Prof. Rivera"; professor gets a URL form and Remove.
- **Search** (`GET /search?q=`): "Notes and questions" and "In the readings", each linking to `/readings/:id?page=…&annotation=…`. Locked notes aren't searched; the empty state says so.
- **User menu** (S19): `PUT /me/sharing` for all your notes; it returns `{updated}` for the confirmation line. **Use on Mac** is a plain link to `dialectic://login?user=<id>` (does nothing if the Mac app isn't installed).

## Where to change things

| To change… | Edit |
| --- | --- |
| Colours, fonts, radii | The custom properties at the top of `src/styles.css` |
| Who gets which highlight colour | `src/colors.js` |
| How often the reader refreshes | `POLL_MS` at the top of `Reader.jsx` |
| Copy (empty states, notice wording, lock card text) | Named constants at the top of the component that shows it |
| Where `/api` points in development | The `server.proxy` block in `vite.config.js` |
| A request or response shape | **Not here first:** `SPEC.md` §6 is the contract; change it there (and the backend) in the same commit, then follow it here |

## Running it

Start the backend first (see `explainers/backend.md`, *Running and poking it*), then from `app/frontend`:

```sh
npm install
npm run dev          # Vite dev server; /api is proxied to localhost:8000
npm run build        # writes dist/, which the backend then serves on :8000
```

Log in as Ben (student) and Prof. Rivera (professor) in two browsers (or a private window) to see the engagement lock and live updates working against each other.

## Build order and status

From ideas/02, following SPEC §8. Mark each one as it lands:

1. `api.js`, `Login`, `Course` (S01–S02). *Not started.*
2. `Reader` with `PdfPage`, `HighlightLayer`, `Margin`, `Composer`, lock cards, polling (S03–S05): **demo steps 1–2.** *Not started.*
3. `AskPanel` + answer card on plain `/ask`, AI collapsed (S06, S08, S09): **demo step 3.** *Not started.*
4. Blocked notices (S10, S11) and the `Charter` page (S12, S13): **demo step 4.** *Not started.*
5. Streaming (S07) and errors (S20), then `Sources`, `Search` (S14, S15) and empty states (S21). *Not started.*
6. Sharing menu (S19), then charter gaps (S18). *Not started.*

The backend for all of these already exists (see `explainers/backend.md`, *Known gaps*: the streamed Ask, charter gaps and opt-out routes are built server side with no UI yet).
