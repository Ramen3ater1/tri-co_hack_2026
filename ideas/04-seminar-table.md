# 04: Seminar table, a roundtable home page with a graph of the class's insights

**Status:** exploring (Sat 11:05). Not built; for the pitch's "what's next", not today's demo (past the 12:00 feature cutoff by the time it could land). Replaces nothing: it would be a new **Seminar** view next to the reader, not a replacement for it. Open question: SPEC §11 #11.

**Mockup (clickable):** https://claude.ai/artifact/AWnEUjMrTmBSHkHijy46Fq, built from josue's sketch (8 seats round a table, spokes into a knot in the middle, charter box top left, a per-student panel: annotations, sources, AI influence).

## The idea

The page a student lands on is a round table, like a Socratic seminar. Classmates sit round it (the professor and past cohorts too, badged as in the margin). The middle of the table is **the reading**: its discussed passages, as a knot. Each note, question or reply sits on the spoke between its author's seat and its passage, so you can see at a glance how everyone's thinking connects through the text. Click anything for its thread, a seat for that person's open annotations, sources and AI influence, a passage to join that part of the discussion. Readings, your notes, the course sources and AI context sit in a rail beside it; the charter sits on the table.

## Rules it keeps

- **Engagement lock (§3.4):** a locked cluster is a dashed ring with a count on its passage. No line to any seat, no text, and seat panels never count it, so a seat never reveals who wrote a locked note. Writing a note or asking near it opens it, and only then do the lines to the authors' seats appear.
- **AI comes last (charter rule 1):** AI has no seat. An AI explanation hangs off the question that asked for it, is hidden on the table by default, starts collapsed in the panel, and names the charter rule that allowed it.
- **The reading is the centre:** every line runs to a passage, so the graph is always about the text. A free-floating idea web drifts away from it and turns into a hairball at 70 students.
- **No new data:** every line is something the API already returns: author, `parent_id` (replies), the peers saved in each question's `answer_json` ("answered by"), and the sources it cited. One extra read route at most, to get a whole reading's threads with their answers at once.

## Tradeoffs

- It's a home view, not the place you read. Annotating still happens in the reader; every node opens it at its passage.
- Seats can make silence visible. Never show who hasn't posted (no "0 notes" seats, no empty-seat styling).
- At lecture scale (AMST 101, ~70 students) seats need folding: show the people near the passages you've engaged with, the rest as "+62".
- Natural home: the iPad app, with the Apple Pencil highlighting being built there.

## Pitch line

"Today the margin shows you your classmates one passage at a time. Next, the seminar table shows you the whole conversation: who's thinking about what, how their ideas answer each other, and where you haven't joined in yet."
