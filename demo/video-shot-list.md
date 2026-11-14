# Dialectic demo video: shot list (Rousseau seed)

Rewritten Sat 14 Nov for the philosophy seed (SPEC §2, §10). Course: **PHIL 247: The Social Contract (seminar)**. Reading: **Week 2 · Rousseau, The Social Contract** (Bennett's version). The earlier Du Bois version of this list is in git history.

## Before recording (done Sat 14 Nov ~12:10)

Two copies are ready. Shot 5 has two versions; film both and pick in the edit.

| Copy | URL | Shot 5 behaves as | Use it for |
| --- | --- | --- | --- |
| **Dev** | `https://dialectic-dev.yaggy.dev` | **5A**, context-only (the default) | shots 1–4, 5A, 6 (the Mac hotkey app talks to a deployed copy) |
| **Owen's laptop** | `http://localhost:8765` (backend started with `GATE_CONTEXT_ONLY=0`, serving a fresh `frontend/dist` build) | **5B**, flat refusal | 5B; also 1–4 if you'd rather film the whole web part locally |

On both: the seed is reset with Rousseau uploaded; **Ana's note is on the p. 12 general-will sentence** ("So the contract isn't with a king, it's with everyone at once, and I'm on both sides of it: a member of the sovereign and a subject."), so Ben's card there reads "2 notes near here"; and shots 4, 5 and 6 were each asked once (as Chidi, then deleted, so Ben's margin is untouched) so their AI steps replay from the cache in a second or two.

- **Replay only works if Ben selects the same text.** The cache matches the exact passage, so select the whole sentence "Each of us puts his person … of the general will" on p. 12 (and the whole Grotius sentence on p. 7). A different selection still works; it just runs live (~20 s) and may answer a little differently. Cut the wait.
- **Dev reseeds itself** whenever someone pushes a change to `seed.py` or `db.py`. That wipes Ana's note (the cache survives). Before filming, check Ben's p. 12 card still says "2 notes"; if not, re-run the prep (`prep_filming.py` in Owen's Claude session, or write Ana's note by hand).
- To restart the laptop copy: `cd app/backend && GATE_CONTEXT_ONLY=0 uv run --env-file ../../.env uvicorn main:app --port 8765`.
- For shot 6, open `~/Documents/Dialectic demo readings/PHIL 247 seminar/Week 2 - Rousseau, The Social Contract.pdf` in Preview at p. 7, with the Mac app pointed at dev.

What each answer says (read once, Sat ~12:10):

- **Shot 4 (dev):** class: Sam, Ana, Theo. 1 source (*Three General Wills in Rousseau*, Review of Politics), **14 skipped** (Wikipedia, general encyclopedias, social media…). AI: traces the idea through the Discourse on Political Economy (1755), the Geneva Manuscript and the 1762 text, with three conceptions. Its first sentence ("The supplied source … says nothing about earlier thinkers") is a bit stiff; the local copy's version is better (3 sources incl. IEP and the Cambridge Companion, 12 skipped, mentions Plato, Montesquieu and the 1762 ban).
- **Shot 5A (dev):** same source, 14 skipped. AI opens "Under Rule 2, I won't explain what Rousseau means by the general will", then the term's history and how scholars have disagreed about it.
- **Shot 5B (laptop):** 1 source, 14 skipped, and the explanation is blocked: "Rule 2: AI may point us to sources and give historical context. It may not interpret the text for us…", reason "Asking what Rousseau 'means' by the general will asks the AI to interpret the text for you…".
- **Shot 6 (dev):** Prof. Rivera's Grotius note first; sources IEP "Grotius, Hugo" and two Wikipedia pages; AI: Delft, the escape in a chest of books, *De jure belli ac pacis* (1625), "father of international law".
- In 5A/5B the class layer also shows two unrelated Rivera notes (Cyclops, Grotius), since the peer layer fills up to five; keep them out of the zoom.

## Shots

| # | Time | What to record | Voiceover | Editing notes |
| --- | --- | --- | --- | --- |
| 1 | 0:00–0:12 | Title card, or the course home page (PHIL 247, three weeks of readings) | "Students read hard texts alone, then ask ChatGPT in private. Dialectic is a shared reader where classmates answer first, and AI helps only the way the class allows." | — |
| 2 | 0:12–0:20 | Prof. Rivera's charter page: rules, permissible-sources description, toggles | "Each class writes a charter: plain-English rules for AI, and what counts as a trustworthy source." | Pan slowly over rule 2 ("It may not interpret the text for us"); shot 5 depends on it. Rule 5 and the "Added to the charter" proposal under it show students shaping the rules too, so keep them in frame if it's quick |
| 3 | 0:20–0:42 | Ben opens Rousseau at p. 12 and sees "2 notes near here" beside the general-will sentence. He selects it, writes a note and saves it: *"Wait, so I'm both the one giving orders and the one obeying them? Where did he get this idea of a will that belongs to everyone?"* Ana's and Sam's notes appear | "This is Rousseau's Social Contract. Ben sees two notes on its most famous sentence, but not what they say, until he writes his own. Think first, then see what others think. Sam's note is from last spring's class." | Zoom in on the lock card; don't cut the moment the notes appear. Ben's note is short enough to type on camera; its question sets up shot 4. Prof. Rivera's notes elsewhere (p. 6, "Man is born free") are visible from the start |
| 4 | 0:42–1:10 | Ben asks "Where does the idea of the general will come from, and what did it mean in 1762?": classmates → sources → he opens the AI explanation | "Classmates first. Then sources: the AI searched the web and kept only what fits the charter, and skipped fourteen sites it doesn't allow. Each one links to the exact sentence. The AI explanation comes last: public, labelled, open to replies." | Cut the wait to 1–2 s but keep "Checking the charter…"; zoom in on "14 skipped" (12 if filmed on the laptop copy); click one source link to show it jumping to the sentence |
| 5A | 1:10–1:28 | *Context-only (dev).* Ben asks "What does Rousseau mean by the general will?": the explanation opens "Under Rule 2, I won't explain what Rousseau means by the general will", then gives only the term's history; sources still appear | "Ask the AI to interpret the text for you, and it won't. It quotes the class's own rule, gives only the history of the idea, and still points you to sources. The interpreting is left to Ben." | Zoom in on the opening sentence that cites rule 2 |
| 5B | 1:10–1:28 | *Refusal (laptop copy).* Same question: the AI explanation is refused, citing rule 2; sources still appear | "Ask the AI to interpret the text for you, and it refuses, quoting the class's own rule, but still points you to sources." | Zoom in on the rule quoted in the refusal notice. Film both 5A and 5B; pick one in the edit |
| 6 | 1:28–1:50 | Ana, in Preview, selects "His usual method of reasoning is to establish right by fact" (p. 7), presses ctrl cmd D and asks "Who was Grotius, and what did he write?"; the floating panel shows Prof. Rivera's Grotius note, sources and the answer | "You don't even have to open Dialectic. Highlight in any app, press the hotkey, and the question is saved to the class's copy of the reading." | Split screen: Ana's Preview on the left, Ben's web margin at p. 7 on the right; the question appears on the right a few seconds later |
| 7 | 1:50–2:00 | Closing card. Optional 2–3 s cutaway before it: Maya in the 70-person PHIL 101 lecture, p. 12 showing "10 notes near here" | "The AI sees only the passage, never names. Free for any class, from a seminar to a seventy-person lecture; a university can run it on its own AI. First customer: the Tri-Co." | Drop the lecture phrase if you skip the cutaway |

## Checked so far

- Sat ~12:10: everything under *Before recording* was run against both copies through the API (not clicked through in a browser). Gate verdicts match the plan: 4 and 6 fully allowed; 5 context-only on dev, refused on the laptop copy.
