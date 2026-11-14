"""POST /readings/{id}/ask: the three-layer answer (SPEC §3.5).

Order: save the question -> peer layer (no AI) -> toggles (code) -> gate (LLM) ->
sources (web with AI, or the course library without) -> AI explanation.
A blocked layer adds an entry to `blocked`; it never raises.
"""
import json
from urllib.parse import quote as url_quote

import httpx

import ai
import db
import search

PEER_LIMIT = 5
LIBRARY_LIMIT = 3
MAX_WEB_SOURCES = 3
MAX_PAGES_TO_READ = 5  # fetch up to this many permitted pages, keep up to MAX_WEB_SOURCES with an answer
SAME_PAGE_BOOST = 2.0  # bm25 scores are negative (lower = better), so we subtract this
FRAGMENT_WORDS = 5     # long sentences link as textStart,textEnd with this many words each


def peer_layer(conn, reading_id, page, quote, question, visibility):
    """Visible notes and replies on this reading that share keywords with the quote and question.

    Only kind = 'note': other questions and AI answers aren't answers from your class.
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
              AND a.reading_id = :reading_id AND a.kind = 'note' AND {db.VISIBLE_SQL}
            ORDER BY bm25(annotations_fts) - CASE WHEN a.page = :page THEN :boost ELSE 0 END
            LIMIT :limit""",
        {"match": match, "reading_id": reading_id, "page": page,
         "boost": SAME_PAGE_BOOST, "limit": PEER_LIMIT, **visibility},
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
        {"source_id": r["id"], "title": r["title"], "url": r["url"], "quote": r["snippet"], "text": r["excerpt"]}
        for r in rows
    ]


def text_fragment_url(url, sentence):
    """Link that makes the browser scroll to and highlight `sentence` on the page."""
    def enc(s):
        return url_quote(s, safe="").replace("-", "%2D")
    words = sentence.split()
    if len(words) > 2 * FRAGMENT_WORDS:
        directive = enc(" ".join(words[:FRAGMENT_WORDS])) + "," + enc(" ".join(words[-FRAGMENT_WORDS:]))
    else:
        directive = enc(sentence)
    return f"{url.split('#')[0]}#:~:text={directive}"


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
    'unreachable' (permitted but we couldn't open or read it) or
    'no_answer' (permitted and read, but nothing in it answered the question).
    The last two are fine sources, so the frontend links them for the student to read."""
    return {"url": result["url"], "title": result["title"], "why": why, "reason": reason}


def web_layer(conn, charter, question_id, quote, question, search_query):
    """AI sources: web search -> charter filter -> fetch -> pick the answering sentence -> save to library.

    Returns (sources, skipped_sources).
    """
    results = search.search(conn, search_query)
    if not results:
        return [], []
    verdict = ai.filter_sources(conn, charter["permissible_sources"], question, results)
    skipped = [skipped_entry(results[s["index"]], "not_permitted", s["reason"]) for s in verdict["skipped"]]

    # Fetch a few more pages than we need, best first: some sites refuse us (Britannica and
    # The Atlantic answer 403) and some pages are just a landing page (JSTOR).
    fetched = []
    for index in verdict["keep"]:
        if len(fetched) == MAX_PAGES_TO_READ:
            break
        result = results[index]
        try:
            page = search.fetch_page(conn, result["url"])
        except httpx.HTTPError as e:
            # Not a bug, just a site that won't let us in: show it as skipped instead of failing /ask.
            print(f"fetch failed, skipping {result['url']}: {e}")
            skipped.append(skipped_entry(result, "unreachable", "Couldn't open this page"))
            continue
        if not page["text"]:
            skipped.append(skipped_entry(result, "unreachable", "Couldn't read any text on this page"))
            continue
        fetched.append({"title": result["title"] or page["title"], "url": result["url"], "text": page["text"]})
    if not fetched:
        return [], skipped

    # A page only counts as a source if the AI finds a real sentence in it that answers the question.
    sentences = ai.pick_sentences(conn, question, quote, fetched)
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


def answer(conn, reading, user, page, quote, rects, question, via="web"):
    """Run the whole /ask flow and return the response dict (SPEC §6). via: 'web' or 'hotkey'."""
    charter = conn.execute("SELECT * FROM charter").fetchone()
    ai_user_id = conn.execute("SELECT id FROM users WHERE role = 'ai'").fetchone()["id"]

    # 1. The question is a public annotation others can answer.
    question_id = db.insert_annotation(
        conn, reading["id"], user["id"], "question", page, quote, json.dumps(rects), question, via=via,
    )
    conn.commit()

    # 2. Peer layer: always on, no AI.
    peer = peer_layer(conn, reading["id"], page, quote, question, db.visibility_params(conn, user))

    # 3. Pass 0: toggles, in code. A layer the toggles rule out never reaches the model.
    can_find_sources, can_explain, blocked = ai.toggle_blocks(charter)

    # 4. Pass 1: the gate, only if some AI layer is still possible.
    search_query = None
    if can_find_sources or can_explain:
        verdict = ai.gate(conn, charter["text_md"], reading["title"], quote, question)
        if can_find_sources and not verdict["find_sources"]["allowed"]:
            blocked.append(rule_block(charter, "sources_ai", verdict["find_sources"]))
            can_find_sources = False
        if can_explain and not verdict["explain"]["allowed"]:
            blocked.append(rule_block(charter, "ai_answer", verdict["explain"]))
            can_explain = False
        search_query = verdict.get("search_query") or question

    # 5. Pass 2, sources: the web with AI, otherwise the course library.
    skipped_sources = []
    sources = []
    if can_find_sources:
        sources, skipped_sources = web_layer(conn, charter, question_id, quote, question, search_query)
    if not sources:
        # No AI allowed, or the web gave nothing usable (e.g. every good site refused us):
        # the course library is the fallback either way.
        sources = library_layer(conn, quote, question)

    # 6. Pass 2, explanation: only grounded in the sources above, posted publicly as the AI.
    ai_answer = None
    if can_explain and sources:
        body = ai.explain(
            charter["text_md"], reading["title"], quote, question,
            [{"title": s["title"], "text": s["text"]} for s in sources], charter["max_explanation_words"],
        )
        answer_id = db.insert_annotation(
            conn, reading["id"], ai_user_id, "ai_answer", page, None, None, body,
            parent_id=question_id, cited_source_ids=[s["source_id"] for s in sources], via=via,
        )
        ai_answer = {"annotation_id": answer_id, "body": body}
    conn.commit()

    for s in sources:
        del s["text"]  # full page text stays on the server
    return {
        "question_id": question_id,
        "peer": peer,
        "sources": sources,
        "ai_answer": ai_answer,
        "skipped_sources": skipped_sources,
        "blocked": blocked,
    }
