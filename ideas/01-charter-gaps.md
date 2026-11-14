# 01: Show the class what its charter doesn't cover

**Status:** backend built Sat 04:20 (`charter_gaps` table, `GET /charter/gaps`, dismiss; SPEC §3.7); the charter-page section isn't built yet. Replaces nothing.

## The problem

The charter's **permissible sources** description is plain language written by students and the professor, so it will always leave things out. The AI's source filter reads it literally (it has to: the charter is the authority, not the AI's guess at what the class meant). So whatever the description doesn't mention is quietly dropped.

We hit this on Saturday: the first seed text listed encyclopedias, university and museum sites and primary sources, and every journal article was dropped. Nobody would have noticed without reading the filter's output.

## What's built (option B)

The filter gives every search result one decision: `keep`, `ruled_out` (the charter excludes it), `not_covered` (the charter doesn't mention it) or `off_topic`. A student sees the difference in the Ask panel's skipped list: "Your charter rules out study-guide sites" vs "Your charter doesn't mention journal articles". That's visible per question, but nobody sees the pattern across questions.

## The idea (option C)

Collect the `not_covered` decisions and show them on the **charter page**, grouped by kind of source:

> **Not covered by your charter** (last 7 days)
> - journal articles: 12 results skipped, e.g. *W. E. B. Du Bois's Theory of Double Consciousness* (cambridge.org)
> - blog posts: 5 results skipped
>
> [Allow journal articles] [Rule out blog posts] [Dismiss]

The buttons don't edit the charter by themselves. They append a line to the permissible-sources text (or start a charter comment for students, who can't edit), so the change stays in the class's own words, made in the open. That keeps the charter co-created and makes the AI's literal reading something the class can steer.

## What it would take

- **Backend:** a `skipped_sources_log` table (`kind`, `url`, `title`, `question_id`, `created_at`) written in `ask.web_layer` for `not_covered` results; `GET /charter/gaps` grouping by `kind` (the filter's labels vary a little, e.g. "journal articles" vs "scholarly journal articles", so group case-insensitively and accept some duplicates).
- **Frontend:** one section on the charter page, and the two buttons wired to `PUT /charter` (professor) or `POST /charter/comments` (students).
- **Privacy:** store only the source and kind, never who asked.

About 2 hours across both. Worth it only after the demo path and the could-haves above it in SPEC §8 are done.
