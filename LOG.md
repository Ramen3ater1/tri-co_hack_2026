# Log

Append only, newest at the bottom. Format: `- HH:MM (Day) — what, and why. [who/session]`

- 16:05 (Fri) — Repo created. Theme/prompt not yet announced.
- 16:14 (Fri) — Added hackathon code style to CLAUDE.md: MVP, happy path, fail loudly, hand-editable. [Owen/Claude]
- 00:25 (Sat) — Idea chosen: Dialectic (collaborative annotation + class-charter-governed AI). Wrote SPEC.md for review: SQLite/FTS5, react-pdf anchoring spike first, DO droplet deploy. [Owen/Claude]
- 00:24 (Sat) — SPEC: AI charter filter is now two-pass (code toggles + LLM gate citing rules, then real query). Sources: plain-language 'permissible sources' in the charter filters a web search; used sources saved to the course library for no-AI reuse. Domain: dialectic.space or a subdomain. [Owen/Claude]
- 00:29 (Sat) — Moved to the team repo tri-co_hack_2026: copied the scaffold (CLAUDE.md, LOG.md, ideas/, spikes/, demo/, app/) alongside SPEC.md. Entries above are from the scaffold repo. [Owen/Claude]
- 00:30 (Sat) — Search API: Kagi (privacy story, low SEO spam; ~$12/1k, preview). Brave is the fallback; search.py keeps it to one function. [Owen/Claude]
- 00:58 (Sat) — Added agent co-development rules to CLAUDE.md: pull --rebase, claim tasks in LOG.md, push small to main, no PRs. [Owen/Claude]
- 01:12 (Sat) — CLAUDE.md: plain-English spec edits through Claude; SPEC.md stays the only copy. [Owen/Claude]
- 01:17 (Sat) — Added a stable branch: main for fast iteration, stable = always submittable, promoted by a human at each checkpoint (tagged good-HHMM); droplet deploys from stable. [Owen/Claude]
- 01:22 (Sat) — starting: backend (schema, seed, routes, /ask, ai.py, search.py) in app/backend/. [Owen/Claude]
- 01:23 (Sat) — Backend env uses uv: app/backend/pyproject.toml + uv.lock, Python pinned to 3.12; .env loaded via `uv run --env-file`. SPEC §4/§9 updated (no requirements.txt). [Owen/Claude]
- 01:24 (Sat) — Added README.md with a Development section (install uv and Node, .env, uv sync, run, uv add not pip). [Owen/Claude]
- 01:26 (Sat) — Made the seed PDF: Gutenberg #408 Ch. 1 printed with headless Chrome (7 pages, Letter), in app/backend/seed/. [Owen/Claude]
- 01:26 (Sat) — Seed annotations attach when the demo PDF is uploaded (it's uploaded live in step 1, so they can't be seeded before). Rects computed with pdfplumber (new dep, seed only) and checked visually. SPEC §10. [Owen/Claude]
- 01:26 (Sat) — Backend skeleton + annotations done: /users, /course, /readings upload+pdf, annotations list/create/reply/delete with the visibility rule. Annotation JSON shape added to SPEC §6. [Owen/Claude]
- 01:31 (Sat) — /ask done end to end (peer, toggles, gate, web sources, library fallback, AI explanation) plus /charter, /sources, /search; tested with a faked LLM + Kagi since we have no keys yet. /ask logic lives in ask.py (main.py would have passed ~400 lines). [Owen/Claude]
- 01:31 (Sat) — Peer layer searches notes/replies only: in testing it returned the asker's own earlier questions as "answers". SPEC §3.5. [Owen/Claude]
- 01:31 (Sat) — Gate risk to test with the real model: the demo question "what did it *mean* in 1903?" contains "mean", the word the rule-text demo uses to trigger a denial. [Owen/Claude]
- 01:31 (Sat) — Search snippets mark hits as [[word]], not <b>, so the frontend never renders user text as HTML. 500s return the real error in "detail". SPEC §6. [Owen/Claude]
- 01:32 (Sat) — Added explainers/ (plain-language tours of the code; row added to CLAUDE.md layout) with backend.md. [Owen/Claude]
- 01:33 (Sat) — Britannica and The Atlantic 403 our page fetcher: /ask now skips pages that won't open (listed in skipped_sources) and the filter keeps up to 5 spares. Added seed.py --with-sources (SEP Du Bois + Wikipedia 'Double consciousness'). SPEC §3.5. [Owen/Claude]
- 01:40 (Sat) — SPEC: Mac hotkey app (§3.9) so students ask from any reading app (Notability, Preview…); screen read on-device with Vision, only text sent; POST /api/ask locates reading/page/section and notes the Q+A as annotations. Web reader kept. Peer boost is now same section (§3.10, headings at upload, page fallback). New reading_sections table, annotations.section_id + via. Parallel track by 09:00, other checkpoints unchanged. [josoup/Claude]
- 01:45 (Sat) — Model: Claude Sonnet 5.5 on DO (anthropic-claude-sonnet-5.5, default in .env.example). Kagi: v1 (POST /api/v1/search, Bearer, data.search) works; legacy v0 returns 401 with our key, so search.py's v0 call needs switching. SPEC §4. [Owen/Claude]
- 01:50 (Sat) — SPEC §8: ranked priority list (must/should/could, cut bottom-up). Mac hotkey reframed as an independent track: Swift-only in app/mac/, builds against a stub of the §6 response; server POST /api/ask is a small backend task after step 3. Sections are a could-have (same page until then). Frontend reader still has no owner: priority #1. [Owen/Claude]
- 01:59 (Sat) — starting: Kagi v1 in search.py, real-key test of the AI path (gate on demo questions), section_id/via columns, then POST /api/ask (hotkey route). [Owen/Claude]
