"""Semantic search of readings: find passages by meaning, not by matching words (SPEC §3.8).

Each reading is cut into passages of a few sentences, and each passage gets an embedding
(a vector from DO inference's embedding model, same URL and key as the LLM). A query is
embedded the same way, and the passages closest to it win. Prototyped in spikes/1035-embeddings.

Readings are indexed lazily: the first meaning search that touches a reading embeds it
(~1.5 s for the Du Bois chapter), so seeding and uploads never need the network.

Privacy: only reading text and the query text leave the server, never who asked.
"""
import json
import math
import os
import re

import httpx

import db

EMBED_MODEL = "bge-m3"  # best of four on paraphrase queries in the spike
PASSAGE_CHARS = 400     # a passage is whole sentences, cut once it passes this length
EMBED_BATCH = 32        # passages per embedding call
RESULT_LIMIT = 8
MIN_SCORE = 0.45        # cosine below this is noise for bge-m3: good hits 0.54–0.62, "the weather in Paris" 0.42
# TODO(edge): DO's embedding price wasn't checked; this guess is generous so the budget stays conservative.
EMBED_USD_PER_MTOK = 0.10
TIMEOUT_S = 30


def split_passages(text):
    """Whole sentences, joined until a passage passes PASSAGE_CHARS."""
    passages, buf = [], ""
    for sentence in re.split(r"(?<=[.!?;])\s+", text.replace("\n", " ")):
        buf += sentence + " "
        if len(buf) > PASSAGE_CHARS:
            passages.append(buf.strip())
            buf = ""
    if buf.strip():
        passages.append(buf.strip())
    return passages


def embed(texts, meter):
    """One paid embedding call (spending limits checked first, cost recorded after)."""
    url = os.environ.get("DO_INFERENCE_URL")
    key = os.environ.get("DO_INFERENCE_KEY")
    if not (url and key):
        raise RuntimeError("DO_INFERENCE_URL and DO_INFERENCE_KEY must be set (put them in .env)")
    meter.check("ai")
    resp = httpx.post(
        f"{url.rstrip('/')}/embeddings",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": EMBED_MODEL, "input": texts},
        timeout=TIMEOUT_S,
    )
    resp.raise_for_status()
    data = resp.json()
    tokens = data["usage"]["prompt_tokens"]
    meter.record("ai", tokens, tokens * EMBED_USD_PER_MTOK / 1_000_000)
    return [item["embedding"] for item in data["data"]]


def index_reading(conn, reading_id, meter):
    """Embed a reading's passages, once. Later calls find them in reading_passages and return."""
    if conn.execute("SELECT 1 FROM reading_passages WHERE reading_id = ? LIMIT 1", (reading_id,)).fetchone():
        return
    rows = []  # (page, text)
    for page in conn.execute("SELECT page, text FROM reading_pages WHERE reading_id = ? ORDER BY page", (reading_id,)):
        rows += [(page["page"], passage) for passage in split_passages(page["text"])]
    for start in range(0, len(rows), EMBED_BATCH):
        batch = rows[start:start + EMBED_BATCH]
        vectors = embed([text for _, text in batch], meter)
        conn.executemany(
            "INSERT INTO reading_passages (reading_id, page, text, embedding) VALUES (?, ?, ?, ?)",
            [(reading_id, page, text, json.dumps(vec)) for (page, text), vec in zip(batch, vectors)],
        )
    conn.commit()


def embed_query(conn, query, meter):
    """The query's vector, cached in web_cache so a rehearsed demo query replays offline."""
    key = f"embed:{EMBED_MODEL}:{query}"
    row = conn.execute("SELECT value FROM web_cache WHERE key = ?", (key,)).fetchone()
    if row:
        return json.loads(row["value"])
    vector = embed([query], meter)[0]
    conn.execute("INSERT OR REPLACE INTO web_cache (key, value, created_at) VALUES (?, ?, ?)",
                 (key, json.dumps(vector), db.now()))
    conn.commit()
    return vector


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))


def search(conn, course_id, query, meter):
    """The course's reading passages closest in meaning to `query`, best first.
    Returns [{reading_id, reading_title, page, text, score}]. Reading text only, never annotations,
    so this can't get round the engagement lock."""
    readings = conn.execute(
        "SELECT id, title FROM readings WHERE course_id = ? AND status = 'ready'", (course_id,),
    ).fetchall()
    if not readings:
        return []
    for reading in readings:
        index_reading(conn, reading["id"], meter)
    query_vector = embed_query(conn, query, meter)
    titles = {r["id"]: r["title"] for r in readings}
    scored = []
    # Plain Python over every passage: a course has a few hundred at most.
    for row in conn.execute(
        f"SELECT reading_id, page, text, embedding FROM reading_passages WHERE reading_id IN ({','.join('?' * len(titles))})",
        list(titles),
    ):
        score = cosine(query_vector, json.loads(row["embedding"]))
        if score >= MIN_SCORE:
            scored.append({"reading_id": row["reading_id"], "reading_title": titles[row["reading_id"]],
                           "page": row["page"], "text": row["text"], "score": round(score, 2)})
    scored.sort(key=lambda r: -r["score"])
    return scored[:RESULT_LIMIT]
