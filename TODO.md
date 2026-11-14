# To do

Open problems we've decided to come back to: things found while building that aren't anyone's current task. Not for planned features (those are in `SPEC.md` §8) or history (that's `LOG.md`).

Each item: a short title, **Owner** (or "anyone"), **Status** (`open`, `in progress`, `done HH:MM`), what's wrong, and what we know. Mark items done instead of deleting them, so the reasoning stays findable; clear out done items only if this file gets long.

---

## Rehearsed hotkey answer is weak (1891 folklore instead of encyclopedia entries)

**Owner:** Owen · **Status:** open · **Found:** 03:19 Sat (`LOG.md`)

The cached answer for the hotkey demo question ("Where does the idea of a seventh son born with a veil come from?") cites only an 1891 Isle of Man folklore collection, and the explanation hedges ("parallel belief, not proof"). An earlier run (02:45) found two Encyclopedia.com entries ("Veil, in African American Culture", "Seventh Son"), which made a much better answer.

**What we know:** the search was fine: its results included both Encyclopedia.com entries (results 9 and 10). The source filter, running at low reasoning effort, marked them `not_covered` ("online encyclopedia entries") although the charter allows scholarly encyclopedias, and that run was cached. On the same 15 results, low effort kept them in 2 of 3 runs (~4 s), full effort in 3 of 3 (~8.5 s).

**Done so far:** the filter is back on full effort (`FILTER_EFFORT` in `app/backend/ai.py`, 03:30 Sat; each call's effort is now a one-word constant at the top of that file). Re-asked on a dev DB at 03:35: both Encyclopedia.com entries are sources again and the explanation covers the caul and seventh-son beliefs (23 s fresh, 8 s replay). That's one run, so not proof.

**Still to decide:** whether this is enough, and how we check rehearsed answers before the demo (each demo question's cached result is what plays on stage; clearing its `llm:` rows in `web_cache` and re-asking gives it a fresh run).

**Update (06:00):** every run since 05:00 cited both Encyclopedia.com entries plus the folklore chapter, and explanations are now cached too, so a rehearsed question replays its last answer word for word. **To close this:** after the demo copy is reseeded and each demo question has been asked once (SPEC §9 step 7), someone reads each demo question's answer once, on the demo copy. If one is weak, clear that question's `llm:` rows in `web_cache`, ask it again, and read it again. Then mark this done.

## The Mac app doesn't say which app the text came from

**Owner:** josoup (Mac app) · **Status:** open, server side done 05:55 · **Found:** 04:50 Sat (design frame S05)

The design shows a hotkey question in the margin as "from Notability via the Mac hotkey". The server only knows `via: "hotkey"`: `POST /api/ask` takes just `{quote, question}`.

**What it would take:** the Mac app sends the frontmost app's name (e.g. `NSWorkspace.shared.frontmostApplication?.localizedName`) as an optional `source_app` in `/api/ask` and `/api/ask/stream`; the server stores it on the question (a new `annotations.source_app` column) and returns it in the annotation shape (SPEC §6). Until then the card just says "via the Mac hotkey".

**Done so far (05:55):** the server side. `/api/ask`, `/api/ask/stream` and `/api/note` accept an optional `source_app`, store it, and annotations return `"source_app"` (or `null`). Left: the Mac app sends it, and the margin card shows "from <source_app> via the Mac hotkey" when it's set.


## The AI explanation isn't cached, so "replays" still cost and count

**Owner:** anyone (backend) · **Status:** done 05:55 · **Found:** 05:23 Sat, local check of main before promoting

Re-asking an identical question replays the gate, search, filter and sentence picks from `web_cache`, but `ai.explain` calls `chat()` directly, not `chat_json`, so the explanation is generated again every time (~1 cent, ~6 s). Effects: (1) a replay counts as a **paid Ask** against `DEVICE_ASKS_PER_HOUR`, contrary to SPEC §9.1 ("replays are free"); with the limit at 2, ask, replay, new question → the new question is blocked; (2) on stage, a rehearsed question regenerates its explanation, so the wording can differ from rehearsal.

**What it would take:** cache the explanation text in `web_cache` keyed by its exact prompt, like `chat_json` does (`llm:` + hash).

**Done (05:55):** `ai.explain` caches its text that way. Tested through the real routes: two users on two devices replaying the hotkey demo question made no paid calls, got the same explanation word for word, and none counted against the device limit. One caveat found while testing: fetch failures aren't cached, so a site that refused us once (here a CUNY Commons page, 403) and opens on a later try changes that question's sources once, and that run pays for a new sentence pick and explanation. After that it replays free again.

## Ask's peer layer includes the asker's own note

**Owner:** anyone (backend) · **Status:** done 05:55 · **Found:** 05:23 Sat, same check

Ben's Ask returned his own note ("Is this the same idea as being split in two?") under peers, alongside Sam's. SPEC §3.5 means *classmates'* answers. Small, but it reads oddly in the demo ("From your class: Ben"). **Fix:** exclude `a.user_id = <asker>` in `peer_layer`. **Done (05:55):** tested: Prof. Rivera asking about her own annotated passage now gets only Sam's note.

## Mac stub data still points at the old PDF's pages

**Owner:** josoup (Mac app) · **Status:** open · **Found:** 06:41 Sat, CI render check

The seed reading is now the 1903 scan (SPEC §3.11, §10), and passages moved: "a sort of seventh son" and the double-consciousness line are on **page 3** now (were page 2), the freedman line on page 6. `app/mac/stub-locate-response.json` (and anything else hard-coding page 2) was generated from the old PDF, so ⌥⇧H's stub and the render check show old positions. **Fix:** `swift make-stub.swift ../backend/seed/souls-of-black-folk-ch1.pdf > stub-locate-response.json` on a Mac (or adapt make-stub to the new page), and check the render-check PNGs in the next **Mac app** Actions run.

## Page 4 of the seed scan OCRs to gibberish

**Owner:** Owen · **Status:** in progress · **Found:** 07:10 Sat, while fixing section headings

Page 4 of `seed/souls-of-black-folk-ch1.pdf` comes out as noise ("4 COTA Mes RL ER: Oy ee 2) RL DY", "Via diary it hee Vinrtana…"), both from the seeded OCR and from re-running it. So that page can't be searched, selected sensibly, located by the hotkey or quoted to the AI. No seeded note or rehearsed question is on it, so the demo path is fine. Probably a faint or skewed page in the Cornell scan. **To try:** look at the page image; OCR just that page with `--deskew --clean` or at a higher DPI.
