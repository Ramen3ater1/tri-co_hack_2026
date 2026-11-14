# 03: Tell the professor which charter rules the app can actually enforce

**Status:** exploring (Sat 10:35). Not built; build only if there's time before the 12:00 feature cutoff. Replaces nothing; sits next to `01-charter-gaps.md` on the charter page. Open question: SPEC §11 #10.

## The problem

The charter is plain language, so a professor can write any rule. But the app only enforces a few kinds:

- **Toggles**, checked in code (§3.7).
- **The gate**, which judges each Ask request per layer: `find_sources` and `explain` (§3.5). The rules also go into `EXPLAIN_PROMPT`, so they shape what the AI writes.
- **Things the app always does**, e.g. AI answers are always public and labelled.

Anything else is honour-system: "don't use AI on your essays" can't be enforced from inside a reading app. Nothing tells the professor this, so a charter can look stricter than it is. The text can also **contradict the toggles** ("AI may give historical context" while `ai_explanations` is off), and a vague rule makes the gate deny whenever it's unsure, which adds friction nobody meant.

## The idea

An AI pass over the saved charter that sorts each numbered rule by how it's enforced, and feeds that back to the professor so they can write a charter the app can actually hold students to.

Taking the seed charter as an example:

| Rule | Enforced by |
| --- | --- |
| 1. Read first, ask each other second, AI last | Partly: the engagement lock (`annotate_before_peers`) and the Ask panel's order. Nothing stops another tab. |
| 2. AI may give sources/context, not interpret | The gate, per request, and `EXPLAIN_PROMPT`. |
| 3. AI output public and labelled | Always true in the app. |
| 4. Shared with future classes unless unticked | `share_with_future` / `show_past_cohorts`. |

Each rule would get one of these:
- `toggle` (names the toggle and says whether its current setting matches the text)
- `gate`
- `by_design`
- `partial`
- `honour_system`
- `unclear`

Each also gets a one-line note and, where it helps, a suggested rewording. Toggle/text conflicts are listed at the top.

## What it would take (~1–1.5 h)

- **Backend:** a `CHARTER_CAPABILITIES` constant in `ai.py` that describes in plain words what the app can enforce (toggles, gate layers, by-design behaviour). Add a `CHECK_CHARTER_PROMPT` and one LLM call that takes the charter text, the permissible-sources description, the current toggles and the capabilities. Cache it by prompt like the other calls. A route such as `GET /charter/check` (professor only), run on save or from a button.
- **Frontend:** a professor-only section on the charter page, beside charter gaps.
- **No new table** if it runs on demand and relies on the prompt cache.

## Risks

- **`CHARTER_CAPABILITIES` is another source of truth.** It has to be updated whenever a toggle is added (semantic search is adding `ai_semantic_search` right now). It might be possible to generate part of it from the toggle table.
- **It's advice, not enforcement.** It doesn't change what the gate does. Its wording must not imply that a `gate` rule is guaranteed: the gate is an LLM and can be wrong.
- **One more LLM call per save.** It's cheap, and editing the charter already re-runs the gate.
