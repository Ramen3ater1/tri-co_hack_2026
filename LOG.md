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
