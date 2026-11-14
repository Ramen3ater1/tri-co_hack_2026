# Dialectic demo video: shot list (Rousseau seed)

Rewritten Sat 14 Nov for the philosophy seed (SPEC §2, §10). Course: **PHIL 247: The Social Contract (seminar)**. Reading: **Week 2 · Rousseau, The Social Contract** (Bennett's version). The earlier Du Bois version of this list is in git history.

## Before recording

1. Reseed the copy you're filming: `uv run seed.py --reset --with-reading` (or upload `rousseau-social-contract.pdf` as Prof. Rivera).
2. **Log in as Ana** and write her note on the general-will sentence, p. 12: *"Each of us puts his person and all his power in common under the supreme direction of the general will"*. Something like: "So the contract isn't with a king, it's with everyone at once, and I'm on both sides of it." Shot 3 needs it there: Ben's lock card counts Ana's note and Sam's.
3. **Run shots 4, 5 and 6's questions once** and read the answers, so they're cached and you know what's coming. Note how many results each Ask skipped (shot 4's voiceover says the number).
4. On the Mac for shot 6, open the same PDF in Preview: `~/Documents/Dialectic demo readings/PHIL 247 seminar/Week 2 - Rousseau, The Social Contract.pdf` (same file as the seed), at p. 7.

## Shots

| # | Time | What to record | Voiceover | Editing notes |
| --- | --- | --- | --- | --- |
| 1 | 0:00–0:12 | Title card, or the course home page (PHIL 247, three weeks of readings) | "Students read hard texts alone, then ask ChatGPT in private. Dialectic is a shared reader where classmates answer first, and AI helps only the way the class allows." | — |
| 2 | 0:12–0:20 | Prof. Rivera's charter page: rules, permissible-sources description, toggles | "Each class writes a charter: plain-English rules for AI, and what counts as a trustworthy source." | Pan slowly over rule 2 ("It may not interpret the text for us"); shot 5 depends on it. Rule 5 and the "Added to the charter" proposal under it show students shaping the rules too, so keep them in frame if it's quick |
| 3 | 0:20–0:42 | Ben opens Rousseau at p. 12 and sees "2 notes near here" beside the general-will sentence. He selects it, writes a note and saves it; Ana's and Sam's notes appear | "This is Rousseau's Social Contract. Ben sees two notes on its most famous sentence, but not what they say, until he writes his own. Think first, then see what others think. Sam's note is from last spring's class." | Zoom in on the lock card; don't cut the moment the notes appear. Prof. Rivera's notes elsewhere (p. 6, "Man is born free") are visible from the start |
| 4 | 0:42–1:10 | Ben asks "Where does the idea of the general will come from, and what did it mean in 1762?": classmates → sources → he opens the AI explanation | "Classmates first. Then sources: the AI searched the web and kept only what fits the charter, and skipped [N] sites it doesn't allow. Each one links to the exact sentence. The AI explanation comes last: public, labelled, open to replies." | Cut the wait to 1–2 s but keep "Checking the charter…"; zoom in on "N skipped"; click one source link to show it jumping to the sentence |
| 5 | 1:10–1:28 | Ben asks "What does Rousseau mean by the general will?": the explanation opens by saying, under rule 2, it won't interpret the text, then gives only the term's background; sources still appear | "Ask the AI to interpret the text for you, and it won't. It quotes the class's own rule, gives only the history of the idea, and still points you to sources. The interpreting is left to Ben." | Zoom in on the opening sentence that cites rule 2. **For a flat refusal instead,** set `GATE_CONTEXT_ONLY = False` in `app/backend/ai.py` on the copy you film, and change the voiceover to "it refuses, quoting the class's own rule, but still points you to sources" (re-check the verdict first) |
| 6 | 1:28–1:50 | Ana, in Preview, selects "His usual method of reasoning is to establish right by fact" (p. 7), presses ctrl cmd D and asks "Who was Grotius, and what did he write?"; the floating panel shows Prof. Rivera's Grotius note, sources and the answer | "You don't even have to open Dialectic. Highlight in any app, press the hotkey, and the question is saved to the class's copy of the reading." | Split screen: Ana's Preview on the left, Ben's web margin at p. 7 on the right; the question appears on the right a few seconds later |
| 7 | 1:50–2:00 | Closing card. Optional 2–3 s cutaway before it: Maya in the 70-person PHIL 101 lecture, p. 12 showing "10 notes near here" | "The AI sees only the passage, never names. Free for any class, from a seminar to a seventy-person lecture; a university can run it on its own AI. First customer: the Tri-Co." | Drop the lecture phrase if you skip the cutaway |

## Checked so far

- Gate verdicts on the seminar charter (Sat 11:55, one run each): shot 4 and shot 6 are fully allowed; shot 5 is context-only under rule 2. Not yet filmed or clicked through in a browser.
- The answers themselves aren't cached yet: run each once first (step 3 above).
