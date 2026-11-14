"""POST /readings/{id}/ask: the three-layer answer (SPEC §3.5).

Order: save the question -> peer layer (no AI) -> toggles (code) -> gate (LLM) ->
sources (web with AI, or the course library without) -> AI explanation.
A blocked layer adds an entry to `blocked`; it never raises.
"""
import json
import re
import traceback
from urllib.parse import quote as url_quote

import httpx

import ai
import db
import search
import sections
import spend

PEER_LIMIT = 5
LIBRARY_LIMIT = 3
MAX_WEB_SOURCES = 3
MAX_PAGES_TO_READ = 5  # read up to this many pages that open, keep up to MAX_WEB_SOURCES with an answer
SAME_PAGE_BOOST = 2.0  # bm25 scores are negative (lower = better), so we subtract this
NO_SOURCES_LABEL = "No sources to base an explanation on yet"
AI_ERROR_LABEL = "Something went wrong with this step"  # shown with the real error as its reason
SAME_SECTION_BOOST = SAME_PAGE_BOOST  # with sections (SPEC §3.10) the boost is for the same section
# What the Ask panel says while each step runs (the streamed route sends these as `status` events).
STAGE_LABELS = {
    "peer": "Looking for classmates' answers…",
    "charter": "Checking the charter…",
    "sources": "Finding sources your charter permits…",
    "ai_answer": "Writing a short explanation…",
}
FRAGMENT_WORDS = 5     # long sentences link as textStart,textEnd with this many words each
FALLBACK_MIN_WORDS = 4  # shortest plain stretch worth a second, fallback link term (text_fragment_url)
# Words next to which sites often hide text (citation years, "[2]", "(1903)"); a link term that
# crosses hidden text doesn't match in the browser, so the fallback term avoids them (#5).
RISKY_WORD = re.compile(r"[\d()\[\]]")


def peer_layer(conn, reading_id, asker_id, page, section_id, quote, question, visibility):
    """Visible notes and replies on this reading that share keywords with the quote and question,
    boosted in the same section (or the same page, for a reading with no sections).

    Only kind = 'note': other questions and AI answers aren't answers from your class, and not
    the asker's own notes: this layer is what classmates said.
    """
    match = db.fts_query(f"{quote} {question}")
    if match is None:
        return []
    rows = conn.execute(
        f"""SELECT a.id, a.page, a.quote, a.body, a.parent_id, u.name, u.cohort
            FROM annotations_fts f
            JOIN annotations a ON a.id = f.rowid
            JOIN users u ON u.id = a.user_id
            WHERE annotations_fts MATCH :match
              AND a.reading_id = :reading_id AND a.kind = 'note' AND a.user_id != :asker_id
              AND {db.VISIBLE_SQL}
            ORDER BY bm25(annotations_fts) - CASE
                WHEN :section_id IS NOT NULL AND a.section_id = :section_id THEN :section_boost
                WHEN :section_id IS NULL AND a.page = :page THEN :page_boost
                ELSE 0 END
            LIMIT :limit""",
        {"match": match, "reading_id": reading_id, "asker_id": asker_id, "page": page, "section_id": section_id,
         "section_boost": SAME_SECTION_BOOST, "page_boost": SAME_PAGE_BOOST, "limit": PEER_LIMIT, **visibility},
    ).fetchall()
    return [
        {"annotation_id": r["id"], "author": r["name"], "cohort": r["cohort"], "page": r["page"],
         "quote": r["quote"], "body": r["body"], "parent_id": r["parent_id"]}
        for r in rows
    ]


def library_layer(conn, quote, question):
    """No-AI sources: the course library, searched with FTS. Returns source dicts incl. text."""
    match = db.fts_query(f"{quote} {question}")
    if match is None:
        return []
    rows = conn.execute(
        """SELECT s.id, s.title, s.url, s.excerpt,
                  snippet(sources_fts, 1, '', '', '…', 30) AS snippet
           FROM sources_fts JOIN sources s ON s.id = sources_fts.rowid
           WHERE sources_fts MATCH ? ORDER BY bm25(sources_fts) LIMIT ?""",
        (match, LIBRARY_LIMIT),
    ).fetchall()
    return [
        {"source_id": r["id"], "title": r["title"], "url": r["url"], "quote": r["snippet"], "text": r["excerpt"],
         "verified": False}
        for r in rows
    ]


def fragment_directive(words):
    """The `text=` value for these words: all of them, or textStart,textEnd for a long stretch."""
    def enc(s):
        return url_quote(s, safe="").replace("-", "%2D")
    if len(words) > 2 * FRAGMENT_WORDS:
        return enc(" ".join(words[:FRAGMENT_WORDS])) + "," + enc(" ".join(words[-FRAGMENT_WORDS:]))
    return enc(" ".join(words))


def longest_plain_stretch(words):
    """The longest run of words with no digits, brackets or parentheses."""
    best, run = [], []
    for word in words:
        if RISKY_WORD.search(word):
            run = []
            continue
        run.append(word)
        if len(run) > len(best):
            best = list(run)
    return best


def text_fragment_url(url, sentence):
    """Link that makes the browser scroll to and highlight `sentence` on the page.

    Up to two directives: the whole sentence, then its longest plain stretch if the sentence
    has citations or numbers. The browser highlights each one that matches and scrolls to the
    first, so when a site hides text inside its citations (screen-reader labels such as
    "Reference Du Bois") and the whole sentence can't match, the link still lands on it (#5).
    TODO(edge): some sites ignore text fragments entirely (Cambridge Core re-renders the page
    after load); there the link opens the top of the page, and the Ask panel copies the quote.
    """
    words = sentence.split()
    directives = [fragment_directive(words)]
    plain = longest_plain_stretch(words)
    if FALLBACK_MIN_WORDS <= len(plain) < len(words):
        directives.append(fragment_directive(plain))
    return f"{url.split('#')[0]}#:~:" + "&".join(f"text={d}" for d in directives)


def verify_library_sources(conn, meter, question, quote, sources):
    """Library sources only carry a keyword snippet. Before an explanation may cite them, find a
    real answering sentence in each (as for web sources) and link to it. Sources without one stay
    in the list for the student, but the explanation won't use them."""
    unverified = [s for s in sources if not s["verified"]]
    if not unverified:
        return
    sentences = ai.pick_sentences(conn, meter, question, quote, [{"title": s["title"], "text": s["text"]} for s in unverified])
    for index, source in enumerate(unverified):
        sentence = sentences.get(index)
        if sentence:
            source.update(quote=sentence, url=text_fragment_url(source["url"], sentence), verified=True)


def save_source(conn, title, url, text, question_id):
    """Add a source the AI used to the course library (or reuse it if it's there already)."""
    row = conn.execute("SELECT id FROM sources WHERE url = ?", (url,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        """INSERT INTO sources (title, url, excerpt, found_by, first_question_id, created_at)
           VALUES (?, ?, ?, 'ai', ?, ?)""",
        (title, url, text, question_id, db.now()),
    )
    return cur.lastrowid


def skipped_entry(result, why, reason):
    """why: 'not_permitted' (the charter rules it out: don't link it),
    'not_covered' (the charter doesn't mention this kind of source: don't link it either; the
    fix is for the class to amend the charter, see ideas/01-charter-gaps.md),
    'unreachable' (permitted but we couldn't open or read it) or
    'no_answer' (permitted and read, but nothing in it answered the question).
    The last two are fine sources, so the frontend links them for the student to read."""
    return {"url": result["url"], "title": result["title"], "why": why, "reason": reason}


def log_charter_gaps(conn, results, skipped):
    """Remember results skipped as `not_covered`, for the charter page's gaps list (SPEC §3.7,
    ideas/01-charter-gaps.md). Only the source and its kind: never who asked or what."""
    for s in skipped:
        if s["why"] != "not_covered":
            continue
        result = results[s["index"]]
        conn.execute(
            """INSERT INTO charter_gaps (kind, url, title, last_seen) VALUES (?, ?, ?, ?)
               ON CONFLICT (url) DO UPDATE SET kind = excluded.kind, last_seen = excluded.last_seen""",
            (s["kind"], result["url"], result["title"] or result["url"], db.now()),
        )


def web_layer(conn, meter, charter, reading_title, question_id, quote, question, search_query):
    """AI sources: web search -> charter filter -> fetch -> pick the answering sentence -> save to library.

    Returns (sources, skipped_sources).
    """
    results = search.search(conn, meter, search_query)
    if not results:
        return [], []
    verdict = ai.filter_sources(conn, meter, charter["permissible_sources"], reading_title, question, results)
    skipped = [skipped_entry(results[s["index"]], s["why"], s["reason"]) for s in verdict["skipped"]]
    log_charter_gaps(conn, results, verdict["skipped"])

    # Fetch every kept candidate at once (most useful first): some sites refuse us
    # (Britannica and The Atlantic answer 403) and some pages are just a landing page (JSTOR).
    pages = search.fetch_pages(conn, [results[index]["url"] for index in verdict["keep"]])
    fetched = []
    for index in verdict["keep"]:
        if len(fetched) == MAX_PAGES_TO_READ:
            break
        result = results[index]
        page = pages[result["url"]]
        if isinstance(page, httpx.HTTPError):
            # Not a bug, just a site that won't let us in: show it as skipped instead of failing /ask.
            print(f"fetch failed, skipping {result['url']}: {page}")
            skipped.append(skipped_entry(result, "unreachable", "Couldn't open this page"))
            continue
        if not page["text"]:
            skipped.append(skipped_entry(result, "unreachable", "Couldn't read any text on this page"))
            continue
        fetched.append({"title": result["title"] or page["title"], "url": result["url"], "text": page["text"]})
    if not fetched:
        return [], skipped

    # A page only counts as a source if the AI finds a real sentence in it that answers the question.
    sentences = ai.pick_sentences(conn, meter, question, quote, fetched)
    sources = []
    for index, source in enumerate(fetched):
        sentence = sentences.get(index)
        if sentence is None or len(sources) == MAX_WEB_SOURCES:
            skipped.append(skipped_entry(source, "no_answer", "Couldn't find a passage here that answers the question"))
            continue
        source_id = save_source(conn, source["title"], source["url"], source["text"], question_id)
        sources.append({
            "source_id": source_id,
            "title": source["title"],
            "url": text_fragment_url(source["url"], sentence),
            "quote": sentence,
            "text": source["text"],
            "verified": True,
        })
    return sources, skipped


def rule_block(charter, layer, decision):
    """A `blocked` entry for a layer the gate denied, quoting the rule it cited."""
    return {
        "layer": layer,
        "by": "rule",
        "label": ai.rule_label(charter["text_md"], decision.get("rule")),
        "reason": decision.get("reason", ""),
    }


def failed_block(layer, error):
    """A `blocked` entry for an AI layer that raised: a spending limit (SPEC §9.1: "by": "limit",
    the notice as the label, no reason) or a real failure (see ai_error_block)."""
    if isinstance(error, spend.LimitReached):
        return {"layer": layer, "by": "limit", "label": str(error)}
    return ai_error_block(layer, error)


def ai_error_block(layer, error):
    """A `blocked` entry for an AI layer that failed (the AI service or Kagi down, a bug).
    The panel shows the real message; the rest of the answer still arrives."""
    traceback.print_exception(error)
    return {"layer": layer, "by": "error", "label": AI_ERROR_LABEL, "reason": f"{type(error).__name__}: {error}"}


def status(stage):
    return {"event": "status", "stage": stage, "label": STAGE_LABELS[stage]}


def answer_steps(conn, reading, user, page, quote, rects, question, via="web", device_id=None, source_app=None):
    """Run the whole /ask flow, yielding progress events as it goes (SPEC §3.5, §6).

    Events, in this order: question, status/peer, status/blocked..., status/sources,
    status/ai_answer, then done with the full response. A `blocked` event can come after the
    charter check, after sources and after the explanation. via: 'web' or 'hotkey'.
    device_id: the X-Device-Id header, for the per-device spending limit (SPEC §9.1).
    source_app: for hotkey asks, the Mac app the text came from (e.g. "Notability"), if it said.
    """
    charter = conn.execute("SELECT * FROM charter").fetchone()
    ai_user_id = conn.execute("SELECT id FROM users WHERE role = 'ai'").fetchone()["id"]

    # 1. The question is a public annotation others can answer.
    section = sections.section_for(conn, reading["id"], page, quote)
    question_id = db.insert_annotation(
        conn, reading["id"], user["id"], "question", page, quote, json.dumps(rects), question, via=via,
        section_id=section["id"] if section else None, source_app=source_app,
    )
    conn.commit()
    yield {"event": "question", "question_id": question_id, "section": section["title"] if section else None}
    # Every paid call in this Ask goes through the meter: limits checked before, cost recorded after.
    meter = spend.Meter(conn, device_id, question_id)

    # 2. Peer layer: always on, no AI.
    yield status("peer")
    peer = peer_layer(conn, reading["id"], user["id"], page, section["id"] if section else None, quote, question,
                      db.visibility_params(conn, user))
    yield {"event": "peer", "peer": peer}

    # 3. Pass 0: toggles, in code. A layer the toggles rule out never reaches the model.
    can_find_sources, can_explain, blocked = ai.toggle_blocks(charter)

    # 4. Pass 1: the gate, only if some AI layer is still possible.
    search_query = None
    if can_find_sources or can_explain:
        yield status("charter")
        try:
            verdict = ai.gate(conn, meter, charter["text_md"], reading["title"], quote, question)
        except Exception as e:
            verdict = None
            if can_find_sources:
                blocked.append(failed_block("sources_ai", e))
            if can_explain:
                blocked.append(failed_block("ai_answer", e))
            can_find_sources = can_explain = False
        if verdict is not None:
            # Each layer is judged on its own, so a request can be partly allowed (e.g. sources yes,
            # explanation no). Only an explicit `true` allows a layer: anything else denies it.
            if can_find_sources and verdict["find_sources"]["allowed"] is not True:
                blocked.append(rule_block(charter, "sources_ai", verdict["find_sources"]))
                can_find_sources = False
            if can_explain and verdict["explain"]["allowed"] is not True:
                blocked.append(rule_block(charter, "ai_answer", verdict["explain"]))
                can_explain = False
            search_query = verdict.get("search_query") or question
    if blocked:
        yield {"event": "blocked", "blocked": list(blocked)}

    # 5. Pass 2, sources: the web with AI, otherwise the course library.
    yield status("sources")
    skipped_sources = []
    sources = []
    if can_find_sources:
        try:
            sources, skipped_sources = web_layer(conn, meter, charter, reading["title"], question_id, quote, question, search_query)
        except Exception as e:
            error = failed_block("sources_ai", e)
            blocked.append(error)
            yield {"event": "blocked", "blocked": [error]}
    if not sources:
        # No AI allowed, or the web gave nothing usable (e.g. every good site refused us, or it failed):
        # the course library is the fallback either way.
        sources = library_layer(conn, quote, question)
    yield {"event": "sources", "sources": public_sources(sources), "skipped_sources": skipped_sources}

    # 6. Pass 2, explanation: grounded only in sources with a verified sentence, posted publicly as the AI.
    ai_answer = None
    if can_explain:
        yield status("ai_answer")
        try:
            ai_answer = explain_layer(conn, meter, charter, reading, ai_user_id, page, quote, question, question_id, sources, via)
        except Exception as e:
            ai_answer = None
            error = failed_block("ai_answer", e)
            blocked.append(error)
            yield {"event": "blocked", "blocked": [error]}
        if ai_answer is None and not any(b["layer"] == "ai_answer" for b in blocked):
            # Allowed, but nothing to ground it in: say so rather than leave a silent gap.
            no_sources = {"layer": "ai_answer", "by": "no_sources", "label": NO_SOURCES_LABEL}
            blocked.append(no_sources)
            yield {"event": "blocked", "blocked": [no_sources]}
    yield {"event": "ai_answer", "ai_answer": ai_answer}

    result = {
        "question_id": question_id,
        "peer": peer,
        "sources": public_sources(sources),
        "ai_answer": ai_answer,
        "skipped_sources": skipped_sources,
        "blocked": blocked,
    }
    # Saved with the question, so anyone can reopen this answer card later (GET /questions/{id}/answer).
    conn.execute("UPDATE annotations SET answer_json = ? WHERE id = ?", (json.dumps(result), question_id))
    conn.commit()
    yield {"event": "done", "result": result}


def explain_layer(conn, meter, charter, reading, ai_user_id, page, quote, question, question_id, sources, via):
    """Write the explanation from the sources with a verified sentence and save it as the AI's
    reply to the question. Returns {annotation_id, body}, or None if no source is verified."""
    verify_library_sources(conn, meter, question, quote, sources)
    grounded = [s for s in sources if s["verified"]]
    if not grounded:
        return None
    body = ai.explain(
        conn, meter, charter["text_md"], reading["title"], quote, question,
        [{"title": s["title"], "text": s["text"], "sentence": s["quote"]} for s in grounded],
        charter["max_explanation_words"],
    )
    answer_id = db.insert_annotation(
        conn, reading["id"], ai_user_id, "ai_answer", page, None, None, body,
        parent_id=question_id, cited_source_ids=[s["source_id"] for s in grounded], via=via,
    )
    return {"annotation_id": answer_id, "body": body}


def public_sources(sources):
    """Sources as the student sees them: the full page text stays on the server."""
    return [{k: v for k, v in s.items() if k not in ("text", "verified")} for s in sources]


def answer(conn, reading, user, page, quote, rects, question, via="web", device_id=None):
    """The whole /ask flow in one go: the `done` event's response (SPEC §6)."""
    for event in answer_steps(conn, reading, user, page, quote, rects, question, via, device_id):
        if event["event"] == "done":
            return event["result"]
