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
