# Dialectic: spec

**Status:** draft for review (Sat 00:20). **Deadline:** demo path working by 15:00, submission 16:00 Saturday.

Dialectic is a collaborative reading platform for college courses (e.g. Haverford). Students annotate course texts together, ask questions about hard passages, and get answers from their peers first. AI is available only in the ways the class has agreed to, in a charter that students and the professor write together.

---

## 1. Principles (and what they mean for the build)

| Principle | What it means in the product |
| --- | --- |
| **Collaboration** | Annotations are visible to the whole class by default. Questions are annotations too, so others can answer them. Peer answers show before anything else. |
| **Friction** | AI never writes your answer for you. It finds sources, or it posts a short explanation that is **public, labelled and open to replies**, never a private shortcut. |
| **Charter governs AI** | Two passes. **Pass 1 (gate):** the charter's toggles are checked in code, then an LLM call asks "does the charter allow this request?" and answers per layer, naming the rule. **Pass 2:** only allowed layers make the real query. |
| **Sources the class trusts** | The charter describes **permissible sources** in plain language ("scholarly work and primary sources from the period; no study-guide sites"). The AI searches the web, keeps only results that fit that description, and every source it uses is saved to the course library, so the library grows without anyone curating it by hand. |
| **Privacy** | The AI provider gets only the highlighted passage, the question, the charter text and source excerpts. Kagi (search) gets only a generated search query. **No names, IDs or other annotations' authors** go to either. Students can delete their annotations and choose whether future classes may see them. |

---

## 2. The demo path (build exactly this first)

Seed users: **Prof. Rivera** (professor), **Ana** and **Ben** (students), plus **Sam (Spring 2026)**, a past student whose annotations are opted in.

1. **Professor sets up the course.** Prof. Rivera logs in, uploads `souls-of-black-folk-ch1.pdf` (Ch. 1, "Of Our Spiritual Strivings") and fills in the charter: rules text, a plain-language **permissible sources** description, and toggles, with all AI toggles **on**.
2. **Ana annotates; Ben sees it.** Ana highlights the "double-consciousness" passage and writes a note. Ben logs in, opens the reading and sees Ana's highlight and note in the margin. He also sees Sam's note from last year, marked "Spring 2026".
3. **Ben asks a question.** Ben highlights "double-consciousness" → **Ask** → "Where does this idea come from, and what did it mean in 1903?" The answer panel shows, in order:
   1. **From your class:** matching peer, past-student and professor annotations (Ana's, Sam's), each linking to its place in the text.
   2. **Sources:** sources the AI found on the web that fit the charter's permissible-sources description, each linking out to the exact sentence that answers the question. A small note shows what was filtered out ("2 results skipped: study-guide sites aren't permitted").
   3. **AI explanation** (if allowed): a short summary citing the sources above, posted as a public annotation by "Dialectic AI" that Ana can reply to.
4. **The charter changes the answer.** Two versions; pick whichever lands better in rehearsal:
   - **Toggle:** Prof. Rivera turns off "AI may write explanations". Ben asks the same question and gets peer annotations and sources only, plus a notice: *"Your class charter doesn't allow AI explanations (AI may write explanations — off)."*
   - **Rule text (shows the gate):** the class adds the rule "AI may not interpret the text for us." Ben asks "What does Du Bois *mean* by double-consciousness?" and the gate refuses the AI layers, quoting that rule. He rephrases to "Where did the term come from?" and the gate allows it. Peer annotations show both times.

**Non-goals:** real auth, multiple courses, notifications, mobile polish. Also out: offline/service worker, charter version history, editing PDFs, a hand-curated source library UI beyond a simple add form.

---

## 3. Features

### 3.1 Log in as

A page listing the seeded users. Clicking one stores their `user_id` in `localStorage` and sends it as an `X-User-Id` header. No passwords. `TODO(edge)`: anyone can be anyone.

### 3.2 Course home

One course, seeded (`HIST 214: Black Intellectual Traditions`, or similar). Shows: readings, a link to the charter, the search box. Professor sees an **Upload reading** form (title + PDF file).

### 3.3 Reader (the core screen)

- Left: the PDF, rendered with **`react-pdf`** (pdf.js) **with its text layer on**, so text is selectable.
- Right: margin panel listing annotations on the current page, newest first, each with author, cohort badge ("Spring 2026", "Professor", "AI"), text and replies.
- Highlights from all visible annotations are drawn over the page as translucent boxes. Clicking one scrolls the margin to it.
- Selecting text shows a small popover: **Annotate** | **Ask**.

**Anchoring (the risky part; see spike S1).** On selection we store:
- `page` (1-based),
- `quote` (the selected text, exact),
- `rects`: the selection's `getClientRects()` converted to **fractions of the page's width/height**, so they redraw correctly at any zoom.

Redraw from `rects`; use `quote` for search, for the AI prompt and as a human-readable fallback. No fuzzy re-anchoring: PDFs don't change after upload.

### 3.4 Annotations

One table covers notes, questions, AI answers and replies:

- `kind`: `note` | `question` | `ai_answer`
- `parent_id`: set for replies (one level of nesting shown; deeper replies display flat).
- Author can delete their own. Deleting removes it from the repository and search immediately.
- `share_with_future` (default on, checkbox on the composer): whether future cohorts may see it.

**Visibility rule:** you see an annotation if it's from your cohort, or it's from a past cohort with `share_with_future = 1`, or its author is the professor or the AI.

### 3.5 Asking a question

`POST /api/readings/{id}/ask` with `page`, `quote`, `rects`, `question`. The server:

1. Saves the question as an annotation (`kind = question`), so it's public and answerable.
2. **Peer layer (always on, no AI):** FTS5 search over visible annotations using keywords from `quote + question`, boosted for annotations on the same page. Top 5.
3. **Pass 1, the gate** (only if `ai_enabled`): toggles are checked in code first; any layer whose toggle is off is blocked without asking the model. If any AI layer is still possible, one LLM call (`GATE_PROMPT`, §7) reads the charter text, the quote and the question, and returns per layer `allowed` + the `rule` it relied on + a one-line `reason`, plus a web `search_query` to use if source finding is allowed. A denied layer is blocked with that rule quoted to the student.
4. **Pass 2, source layer:**
   - **No AI** (`ai_find_sources` off or denied): FTS5 over the course source library, which holds every source the AI has found before. Top 3. This is how the class gets less dependent on AI over time.
   - **AI** (allowed): search the web with `search_query` (8 results) → one LLM call filters the results' titles, URLs and snippets against the charter's **permissible sources** description, keeping up to 3 and giving a short reason for each one dropped → fetch those pages and extract the main text (`trafilatura`) → the LLM **quotes the exact sentence** in each that answers the question → link out with a text fragment (`url#:~:text=<sentence>`), so the browser jumps to and highlights that sentence. Each used source is saved to `sources` (`found_by = 'ai'`) with its extracted text, so it's searchable from then on.
5. **Pass 2, AI explanation layer** (allowed): the LLM writes at most `max_explanation_words` words from the sources above, citing them as `[1]`, `[2]`. Saved as an annotation (`kind = ai_answer`, author = the "Dialectic AI" user, `parent_id` = the question), so it shows in the margin and takes replies.
6. Returns all three layers, a `blocked` list (each with the toggle or charter rule that blocked it) and a `skipped_sources` list, so the UI can explain itself.

### 3.6 Permissible sources and the course source library

**Nobody has to curate a list.** The charter has a `permissible_sources` field in plain language, written with the rest of the charter, e.g.:

> Scholarly encyclopedias (Stanford Encyclopedia of Philosophy, Britannica), university and museum sites, and primary sources from 1890–1920. No study-guide or essay-mill sites (SparkNotes, Course Hero, etc.). Wikipedia is fine for dates and names, not for interpretation.

The AI's web search is filtered against this description (§3.5). Every source it uses is stored in the **course source library** (`sources`), which:
- is what the no-AI mode searches, so once a question has been asked with AI, later students get the same sources without AI;
- is visible on a **Sources** tab (title, link, who/what found it, which question it answered);
- lets the professor **add** a source by URL (the server fetches and extracts its text) or **remove** one. That's the whole curation UI.

**Demo safety:** the live web is the most fragile part of the demo. Seed the library with the sources the demo question will find, cache search results and fetched pages by URL in the DB, and run the demo question once before presenting.

### 3.7 Class charter

One charter per course: Markdown rules text, a plain-language permissible-sources description (§3.6), and toggles. Everyone can read it at `/charter`; it's also linked in the reader header. The professor edits it; for the MVP, "co-creation" means **students can leave comments/proposals under it**, which the professor works into the text (stretch: see §8).

| Toggle | Default | Enforced how |
| --- | --- | --- |
| `ai_enabled` | on | Master switch: off means no LLM calls at all. |
| `ai_find_sources` | on | Off: no web search; plain FTS over the course library. |
| `ai_explanations` | on | Off: no AI explanation layer. |
| `max_explanation_words` | 120 | Passed into the prompt and truncated server-side. |
| `show_past_cohorts` | on | Off: visibility rule drops past-cohort annotations. |
| `annotate_before_peers` | off | **Stretch.** On: you see others' annotations on a page only after writing one of your own there. |

**Enforcement is two-pass.** Toggles are hard limits, checked in code before any call. The charter **text** is enforced by the gate (pass 1), which decides per layer whether the request is allowed and names the rule; it's also included in the pass-2 prompts so the answer itself stays within the rules (e.g. context, not interpretation). Rules are numbered in the text so the gate can cite them.

**Seed charter text (DEMO):**
> 1. We read first and ask each other second. AI comes last.
> 2. AI may point us to sources and give historical context. It may not interpret the text for us or suggest thesis statements.
> 3. Anything AI writes is public to the class and labelled as AI.
> 4. Annotations are shared with future classes unless you untick the box.

### 3.8 Repository search

A search page (`/search?q=`) over all visible annotations **and** the reading text, via FTS5. Each result shows the snippet (FTS5 `snippet()`), the reading and page, and links to the reader at that page with the annotation open.

---

## 4. Stack and layout

- **Backend:** Python 3.12, managed with **uv** (`app/backend/pyproject.toml` + `uv.lock`), FastAPI, `sqlite3` from the standard library (no ORM), `pypdf` for PDF text, `httpx` for the LLM and search calls, `trafilatura` to extract a web page's main text. `uvicorn` to serve.
- **Web search:** **Kagi Search API** (preview, ~$12 per 1,000 queries, billed to a Kagi account; a day of building and the demo is a dollar or two). Chosen for the privacy story alongside DigitalOcean inference, and for results with little SEO spam, which helps keep study-guide sites out. All of it lives in one function, `search(query) -> [{title, url, snippet}]` in `search.py`, so swapping providers is a small change.
  - Call (check the current docs at help.kagi.com when building; the API is in preview): `GET https://kagi.com/api/v0/search?q=<query>&limit=8` with header `Authorization: Bot $KAGI_API_KEY`. Results are the items in `data` with `t == 0` (`url`, `title`, `snippet`); `t == 1` items are related searches, ignore them.
  - Fallback if Kagi misbehaves on the day: Brave Search API, same function signature.
- **Frontend:** React + Vite, `react-router`, `react-pdf`. Plain CSS. No state library.
- **PWA:** a `manifest.webmanifest` and icon, nothing more.
- **LLM:** DigitalOcean serverless inference, which is OpenAI-compatible (`POST {DO_INFERENCE_URL}/chat/completions`). Model name in `.env`.

```
app/
  backend/
    main.py          # FastAPI app, all routes (split only if it passes ~400 lines)
    db.py            # connect(), schema SQL, FTS helpers
    ai.py            # charter checks, gate, prompt text as constants, the one LLM call
    search.py        # web search + page fetch/extract, cached in the DB
    seed.py          # DEMO: users, course, charter, sources, past-student annotations
    seed/            # DEMO: souls-of-black-folk-ch1.pdf
    uploads/         # gitignored
    pyproject.toml   # uv project; uv.lock pins versions
  frontend/
    src/
      api.js         # fetch wrapper that adds X-User-Id
      pages/         # Login, Course, Reader, Charter, Search
      components/    # PdfPage, HighlightLayer, Margin, AskPanel, Composer
    public/manifest.webmanifest
.env.example         # DO_INFERENCE_URL, DO_INFERENCE_KEY, DO_MODEL, KAGI_API_KEY
```

In production FastAPI serves the built frontend (`frontend/dist`) as static files, so it's **one process on one port**.

---

## 5. Data model (SQLite)

```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('professor','student','ai')),
  cohort TEXT NOT NULL            -- 'Fall 2026' (current), 'Spring 2026' (past)
);

CREATE TABLE course (             -- exactly one row (non-goal: multiple courses)
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  current_cohort TEXT NOT NULL
);

CREATE TABLE charter (            -- exactly one row
  id INTEGER PRIMARY KEY,
  text_md TEXT NOT NULL,             -- numbered rules
  permissible_sources TEXT NOT NULL, -- plain-language description (§3.6)
  ai_enabled INTEGER NOT NULL DEFAULT 1,
  ai_find_sources INTEGER NOT NULL DEFAULT 1,
  ai_explanations INTEGER NOT NULL DEFAULT 1,
  max_explanation_words INTEGER NOT NULL DEFAULT 120,
  show_past_cohorts INTEGER NOT NULL DEFAULT 1,
  annotate_before_peers INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);

CREATE TABLE charter_comments (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  body TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE readings (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  pdf_path TEXT NOT NULL,
  uploaded_by INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL
);

CREATE TABLE reading_pages (      -- extracted text, for search and AI context
  reading_id INTEGER NOT NULL REFERENCES readings(id),
  page INTEGER NOT NULL,
  text TEXT NOT NULL,
  PRIMARY KEY (reading_id, page)
);

CREATE TABLE annotations (
  id INTEGER PRIMARY KEY,
  reading_id INTEGER NOT NULL REFERENCES readings(id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  parent_id INTEGER REFERENCES annotations(id),
  kind TEXT NOT NULL CHECK (kind IN ('note','question','ai_answer')),
  page INTEGER NOT NULL,
  quote TEXT,                     -- null for replies
  rects_json TEXT,                -- [{x,y,w,h}] as page fractions; null for replies
  body TEXT NOT NULL,
  cited_source_ids TEXT,          -- JSON array, ai_answer only
  share_with_future INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);

CREATE TABLE sources (             -- the course source library
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  excerpt TEXT NOT NULL,           -- extracted main text (trimmed to ~20k chars)
  found_by TEXT NOT NULL CHECK (found_by IN ('ai','professor')),
  first_question_id INTEGER REFERENCES annotations(id),
  created_at TEXT NOT NULL
);

CREATE TABLE web_cache (           -- DEMO safety: replay search results and fetched pages
  key TEXT PRIMARY KEY,            -- 'search:<query>' or 'page:<url>'
  value TEXT NOT NULL,
  created_at TEXT NOT NULL
);

-- Full-text search. External-content tables + triggers keep them in sync.
CREATE VIRTUAL TABLE annotations_fts USING fts5(quote, body, content='annotations', content_rowid='id');
CREATE VIRTUAL TABLE sources_fts     USING fts5(title, excerpt, content='sources', content_rowid='id');
CREATE VIRTUAL TABLE pages_fts       USING fts5(text, reading_id UNINDEXED, page UNINDEXED);
```

Insert/delete triggers on `annotations` and `sources` keep their FTS tables current. `pages_fts` is filled once at upload.

**FTS query building:** lowercase `quote + question`, drop stopwords, quote each remaining word, join with `OR`, rank with `bm25()`. Good enough for the demo. `TODO(edge)`: phrase matching, stemming (`tokenize='porter'` is a cheap upgrade).

---

## 6. API

All routes are under `/api`; all except `/users` need `X-User-Id`. Professor-only routes return 403 for students.

| Method | Path | Who | Purpose |
| --- | --- | --- | --- |
| GET | `/users` | anyone | Log-in-as list |
| GET | `/course` | all | Course, readings list, current user |
| POST | `/readings` | prof | Multipart upload: title + PDF; extracts pages with `pypdf` |
| GET | `/readings/{id}` | all | Metadata + page count |
| GET | `/readings/{id}/pdf` | all | The PDF file |
| GET | `/readings/{id}/annotations` | all | Visible annotations (with replies), all pages |
| POST | `/readings/{id}/annotations` | all | Create note or reply |
| DELETE | `/annotations/{id}` | author | Delete own annotation (and its replies) |
| POST | `/readings/{id}/ask` | all | The three-layer answer (§3.5) |
| GET | `/charter` | all | Text, toggles, comments |
| PUT | `/charter` | prof | Update text and/or toggles |
| POST | `/charter/comments` | all | Student proposal/comment |
| GET | `/sources` | all | The course source library |
| POST · DELETE | `/sources`, `/sources/{id}` | prof | Add by URL (fetched + extracted) / remove |
| GET | `/search?q=` | all | FTS over visible annotations + reading text |

`/ask` response:

```json
{
  "question_id": 41,
  "peer": [{"annotation_id": 7, "author": "Ana", "cohort": "Fall 2026", "page": 3, "quote": "...", "body": "..."}],
  "sources": [{"source_id": 2, "title": "...", "url": "...#:~:text=...", "quote": "..."}],
  "ai_answer": {"annotation_id": 42, "body": "... [1] ..."},
  "skipped_sources": [{"url": "https://www.sparknotes.com/...", "reason": "Study-guide sites aren't permitted"}],
  "blocked": [
    {"layer": "ai_answer", "by": "toggle", "label": "AI may write explanations — off"},
    {"layer": "sources_ai", "by": "rule", "label": "Rule 2: AI may not interpret the text for us", "reason": "The question asks what the passage means."}
  ]
}
```

`ai_answer` is `null` when blocked or when no sources matched (no ungrounded answers).

Annotation shape (`GET /readings/{id}/annotations` returns a list of these, newest first; `POST` returns one):

```json
{"id": 4, "reading_id": 1, "parent_id": null, "kind": "note", "page": 2,
 "quote": "...", "rects": [{"x": 0.12, "y": 0.66, "w": 0.43, "h": 0.015}], "body": "...",
 "cited_source_ids": null, "share_with_future": true, "created_at": "2026-11-14T01:25:52",
 "author": {"id": 4, "name": "Sam", "role": "student", "cohort": "Spring 2026"},
 "badge": "Spring 2026",
 "replies": [ /* same shape, oldest first; replies to replies are flattened here */ ]}
```

`badge` is `"Professor"`, `"AI"`, a past cohort's name, or `null` for current classmates. `POST /readings/{id}/annotations` takes `{"page", "quote", "rects", "body", "share_with_future"}` for a note, or `{"parent_id", "body"}` for a reply (page comes from the parent). `rects` are page fractions, top-left origin.

---

## 7. AI calls (`ai.py`)

One function, `chat(system, user) -> str`, using `httpx` against the DO endpoint, `temperature=0.2`, with a 30 s timeout and no retries (fail loudly). The prompts are constants at the top of `ai.py`. Calls that return JSON ask for JSON only and are parsed with `json.loads`; a parse failure is a loud error.

**What gets sent (privacy rule, enforced by building the payload in one place):** charter text, permissible-sources description, the highlighted `quote`, the `question`, the reading title, and source titles/snippets/text. **Never** user names, IDs, cohorts or other students' annotations. Kagi gets only the gate's `search_query`.

A full AI answer is four calls: gate → filter results → pick sentences → explain. That's slow-ish (expect 10–20 s); the Ask panel shows the peer layer immediately and the AI layers with a "Checking the charter… / Finding sources… / Writing…" status as they arrive (stretch: if this is fiddly, one spinner and one response is fine).

- **`GATE_PROMPT`** (pass 1): "You enforce a class's AI charter. Rules: {charter}. A student highlighted: {quote}. They ask: {question}. For each AI action — `find_sources` (search the web for relevant sources) and `explain` (write a short contextual explanation) — decide whether the charter allows it for this request." Returns `{"find_sources": {"allowed": true, "rule": null, "reason": "..."}, "explain": {"allowed": false, "rule": "2", "reason": "..."}, "search_query": "..."}`. When unsure, the gate should **deny** (friction is the point).
- **`FILTER_SOURCES_PROMPT`**: given the permissible-sources description and 8 numbered search results (title, URL, snippet), return `{"keep": [3, 1], "skipped": [{"n": 5, "reason": "..."}]}`, keep at most 3.
- **`PICK_SENTENCE_PROMPT`**: given the question and numbered source texts, return `[{"n": 2, "sentence": "<exact sentence copied from source 2>"}]`. The server checks that each `sentence` really occurs in that source's text and drops it if not.
- **`EXPLAIN_PROMPT`** (pass 2): "You are a teaching assistant bound by this class charter: {charter}. Using only the numbered sources, give historical/cultural context for the passage in at most {n} words. Cite as [1]. Don't interpret the passage for the student; end with one question that sends them back to the text."

**Check order:** `ai_enabled` → layer toggles (code) → gate (LLM) → pass-2 calls for allowed layers. A blocked layer adds a `blocked` entry; it never raises an error.

---

## 8. Build order (Saturday)

Checkpoints are the times things must work by. If a checkpoint slips by more than 45 minutes, cut the next stretch item, not the demo path.

**At every checkpoint, promote to `stable`** (see `CLAUDE.md`, *Branches*): click through the demo steps that work so far, then `git push origin main:stable` and tag it `good-HHMM`. Also promote whenever something you'd hate to lose starts working.

| By | What | Notes |
| --- | --- | --- |
| 01:30 | **S1 spike:** `react-pdf` + text-layer selection → page-fraction rects → redraw boxes | In `spikes/`, timeboxed to 1 h. **Fallback if it fights us:** render each page's extracted text as HTML paragraphs and annotate whole paragraphs (store `page` + paragraph index). |
| 02:30 | Backend skeleton: schema, seed, `/users`, `/course`, `/readings` upload + PDF serve | |
| 04:00 | Reader: PDF + highlights + margin + create/delete note + replies | **Demo steps 1–2 work.** |
| 06:00 | `/ask` peer + library layers (no AI) + Ask panel UI | Get the Kagi API key in parallel. |
| 08:00 | `ai.py` + `search.py`: gate, web search, filter, fetch, pick sentence, explanation as annotation, web cache | **Demo step 3 works.** If web search fights us, fall back to seeded library + LLM sentence picking, and keep the gate. |
| 09:00 | Charter page: view, prof edit (rules, permissible sources, toggles); blocked notices in the Ask panel | **Demo step 4 works.** |
| 10:30 | Deploy to droplet on the domain; run the full demo there | Deploy early so the last hours aren't spent on it. |
| 12:00 | Search page; charter comments | Stretch #1 |
| 12:00+ | Polish only: copy, empty states, seed data quality, demo script in `demo/` | Per CLAUDE.md: no new features after noon. |
| 15:00 | Full demo path rehearsed on the deployed URL | |

Stretch, in order: search page → charter comments → `annotate_before_peers` → past-student opt-out UI on profile.

**Parallel split (suggestion):** one person on the frontend reader (S1 → reader), one on the backend (schema → `/ask` → `ai.py`), one on seed data + charter page + demo script. Agree the API shapes in §6 first; the frontend can stub `/ask` with the JSON above.

---

## 9. Deployment (existing DigitalOcean droplet)

1. **The droplet deploys only from `stable`** (`git checkout stable && git pull`), so the live URL always shows something that works. To roll back, check out the previous `good-…` tag there; never rewrite `stable`. Then `cd app/backend && uv sync` (installs uv's pinned Python 3.12 and the locked deps into `app/backend/.venv`).
2. `cd app/frontend && npm ci && npm run build`.
3. `.env` on the droplet only (never in git).
4. Run `uv run --env-file ../../.env uvicorn main:app --host 127.0.0.1 --port 8000` (from `app/backend`) under a small **systemd** unit (`Restart=always`).
5. **Domain:** `dialectic.space` if we buy it, otherwise a subdomain of an existing domain (e.g. `dialectic.<existing-domain>`). Either way, an `A` record to the droplet's IP. Do this **early** (by 08:00) so DNS has time to propagate.
6. Put it behind whatever reverse proxy is already on the droplet. If there isn't one, **Caddy** gets the HTTPS certificate automatically:
   ```
   dialectic.space {
     reverse_proxy 127.0.0.1:8000
   }
   ```
   HTTPS matters here: text-fragment links and the PWA manifest both behave better on a secure origin.
7. Reseed with `uv run seed.py --reset` (from `app/backend`) before the demo (it keeps `web_cache`).
8. **Submit `stable`** (or the last `good-…` tag before 16:00). GitHub shows `main` by default, so either link the submission to `stable` or fast-forward `main` to it at the end.

SQLite file lives at `app/backend/dialectic.db` (gitignored), backed up with `cp` before the demo.

---

## 10. Seed data (DEMO)

- **Reading:** Ch. 1 of *The Souls of Black Folk* (1903, public domain), from Project Gutenberg (#408) printed to PDF. Keep it short (~10 pages) so the demo loads fast.
- **Charter:** the rules in §3.7 plus the permissible-sources text in §3.6.
- **Source library:** start **empty** for the live demo, so step 3 visibly finds sources and step 4 can show the no-AI path reusing them. Keep a `--with-sources` seed flag that preloads them (SEP "W.E.B. Du Bois", a primary text from the period, …) in case the web search fails on stage. The `web_cache` covers the normal case.
- **Annotations:** Sam (Spring 2026) on the double-consciousness passage; Prof. Rivera on "the Veil"; two or three others spread across pages so the margin doesn't look empty.

Write the seed so `seed.py --reset` gives the exact starting state of demo step 1, **minus** the upload. Also add a `--with-reading` flag in case the live upload fails during the demo.

Because the reading is uploaded live, the seeded annotations can't exist before it: **uploading a file named `souls-of-black-folk-ch1.pdf` adds them** (Sam's and the professor's notes, with highlight rects computed from the PDF). The PDF is in `app/backend/seed/`.

---

## 11. Open questions for review

1. **Co-creation of the charter:** is "students comment, professor edits" enough for the MVP, or should students be able to propose an edit that the professor accepts with one click?
2. **AI explanation visibility:** the spec makes every AI explanation public, as in the vision. Should the asker be able to discard it before it's posted?
3. ~~**Search API**~~ **Decided:** Kagi (Brave as fallback). Set a budget alert or check usage on the Kagi billing page before the demo.
4. **Past students:** the spec fakes them with a seeded cohort. OK for the demo?
5. **Model:** which model on DO serverless inference? It must return reliable JSON for the gate, filter and sentence picking. Test the gate on the step-4 questions early: a gate that wrongly allows "what does it mean" breaks the demo's best moment.
6. **Domain:** `dialectic.space` or a subdomain of an existing domain? Decide by 08:00 so DNS can propagate.
