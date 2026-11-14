# Tri-Co Hackathon

Team hackathon project. Submission deadline: **Saturday 2026-11-14, 16:00**. Things move fast and get thrown away; these rules keep the repo readable at hour 20.

## Layout

| Path | Holds | Rule |
| --- | --- | --- |
| `LOG.md` | Timestamped decisions, pivots, dead ends | Append only, newest at the bottom. Never rewrite old entries. |
| `ideas/` | One file per idea, draft or plan: `NN-short-name.md` | Don't rewrite a superseded idea; write a new numbered file and note in it what it replaces. |
| `spikes/` | Throwaway experiments, one dir each: `spikes/HHMM-what/` | Never imported by `app/`. When a spike works, rebuild the good part properly in `app/`. |
| `app/` | The thing we demo | Only working code that's meant to ship. |
| `demo/` | Pitch, demo script, screenshots, submission text | |
| `explainers/` | Plain-language explanations of how parts of the code work, e.g. `backend.md` | Update one when you change what it describes. |

## Code style: hackathon mode

We're building an MVP for a demo, not production software. Optimise for speed and for code a teammate can read and change by hand.

- **Happy path first.** Build the simplest thing that makes the demo work end to end. No abstractions, base classes, plugin systems or config layers until something is actually repeated three times.
- **Skip edge cases the demo won't hit.** No exhaustive validation, retries or fallbacks. Leave a one-line `TODO(edge): …` comment instead of handling it.
- **Fail loudly.** Let errors crash or print clearly; don't swallow exceptions or add silent defaults that hide bugs. A visible error is fixable in a minute; a silent one breaks the live demo.
- **Readable over clever.** Plain names, short functions, flat control flow, no one-liner tricks. Comment only the *why* when it isn't obvious.
- **Easy to edit by hand.** Put tunables, prompt text, copy and URLs as named constants at the top of the file (or one `config` file), not buried in logic. Hardcoding demo data is fine; mark it `DEMO:`.
- **Boring stack, few dependencies.** Prefer well-known libraries and what's already in the repo; ask before adding a new framework or service.
- **No ceremony.** No test suites, CI, linters, Docker or type gymnastics unless asked. A quick test for one tricky core function is fine.
- **Small, local changes.** Don't refactor or reformat code you weren't asked to touch: teammates are editing it too. Ask before a large restructure.
- **Never cut corners on secrets** (keep them out of git) or on anything handling real people's data.

## Rules for agents

- **Log as you go.** After any decision, pivot, dead end or notable finding, append to `LOG.md`: `- HH:MM (Day) — what, and why. [who/session]`. One line where possible. "Tried X, didn't work because Y" is worth logging.
- **Experiments go in `spikes/`**, never straight into `app/`. Say in the spike's README (one or two lines) what it tests and the result.
- **Commit early and often**, small commits with plain messages. Don't rewrite shared history (no force-push, no rebase of pushed branches).
- **Parallel sessions use git worktrees** (`git worktree add ../tri-co_hack_2026-<task> -b <task>`) so they don't edit the same files at once.
- **Keep secrets out of git**: API keys go in `.env` (gitignored); keep `.env.example` up to date with the variable names.
- **Watch the clock.** Past Saturday 12:00, prefer finishing and polishing over new features; the demo path must work end to end by 15:00.

## Working alongside other people's agents

Several people, each with their own Claude sessions, share one `main`. Keep it simple: **no PRs, no long-lived branches.**

1. **Pull first.** `git pull --rebase` before starting a task and again right before pushing. If a rebase conflicts in code you didn't write, stop and ask your human rather than guessing.
2. **Claim the task.** Append `- HH:MM (Day) — starting: <task>. [who]` to `LOG.md`, then commit and push it, so other agents see it on their next pull. Check `LOG.md` for claims before picking something up.
3. **Stay in your area.** The split is in `SPEC.md` §8. If you need to change someone else's files, keep the change minimal and say so in `LOG.md`.
4. **The API in `SPEC.md` §6 is the contract.** If you change a route or a response shape, update `SPEC.md` in the same commit and log it.
5. **Push small and often, straight to `main`.** Only push code that runs (the app still starts); half-done work stays local.
6. **Worktrees** (above) are only for your own parallel sessions on one machine: merge the branch into `main` and push within the hour, then delete it.

## Editing the spec

`SPEC.md` is the only copy of the spec: no Google Doc or other mirror. Teammates who'd rather not write Markdown ask their Claude session for changes in plain English ("add that students can vote on charter rules"). When you get such a request:

1. Pull first, then find every section the change touches, not just the obvious one. A feature change usually also touches the demo path (§2), the data model (§5), the API (§6) and the build order (§8).
2. Make the edit in the spec's existing style. Don't reformat or reword sections you weren't asked about.
3. If the change conflicts with something already in the spec, or would move a checkpoint in §8, say so and ask before writing it.
4. Show the person a short summary of what changed (in plain language, not a diff), then log it in `LOG.md`, commit and push.

## Branches

- **`main`** is where everyone works: push small changes here often (see above). It may be briefly broken.
- **`stable`** is always the best version we could submit right now. It only moves forward, by fast-forward from `main`, and has no commits of its own. The droplet deploys only from `stable`, and we submit `stable`.
- **Agents never push to `stable`, never promote and never deploy.** Promotion is a human's call, made after clicking through the demo path: `git push origin main:stable`, then tag it `good-HHMM` and push the tag. If your human asks you to run those commands, that's fine; just don't decide to on your own.
- If `stable` turns out to be broken, don't rewrite it: fix it on `main` and promote again, or redeploy the previous `good-…` tag.
