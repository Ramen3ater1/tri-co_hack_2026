"""Dialectic API (SPEC §6). Run from app/backend:

    uv run --env-file ../../.env uvicorn main:app --reload
"""
import json
import re
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

import pypdf
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import ask
import db
import locate
import search
import sections
import seed

UPLOADS_DIR = Path(__file__).parent / "uploads"
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

app = FastAPI(title="Dialectic")


@app.exception_handler(Exception)
def show_errors(request: Request, exc: Exception):
    """Fail loudly: send the real error message to the browser (the traceback is still logged)."""
    traceback.print_exception(exc)
    return JSONResponse({"detail": f"{type(exc).__name__}: {exc}"}, status_code=500)


# ---------- who is asking ----------

def get_conn():
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


def current_user(x_user_id: int = Header(), conn=Depends(get_conn)):
    """Every route except /users needs X-User-Id. TODO(edge): anyone can be anyone (SPEC §3.1)."""
    user = conn.execute("SELECT * FROM users WHERE id = ?", (x_user_id,)).fetchone()
    if user is None:
        raise HTTPException(401, f"Unknown user id {x_user_id}")
    return dict(user)


def professor(user=Depends(current_user)):
    if user["role"] != "professor":
        raise HTTPException(403, "Professor only")
    return user


# ---------- shared helpers ----------

def get_course(conn):
    return dict(conn.execute("SELECT * FROM course").fetchone())


def get_charter(conn):
    return dict(conn.execute("SELECT * FROM charter").fetchone())


def get_reading_or_404(conn, reading_id):
    row = conn.execute("SELECT * FROM readings WHERE id = ?", (reading_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"No reading {reading_id}")
    return row


def create_reading(conn, title, pdf_path, uploaded_by):
    """Insert a reading and its extracted page text. Used by the upload route and seed.py."""
    cur = conn.execute(
        "INSERT INTO readings (title, pdf_path, uploaded_by, created_at) VALUES (?, ?, ?, ?)",
        (title, str(pdf_path), uploaded_by, db.now()),
    )
    reading_id = cur.lastrowid
    page_texts = [page.extract_text() or "" for page in pypdf.PdfReader(pdf_path).pages]
    for i, text in enumerate(page_texts, start=1):
        conn.execute("INSERT INTO reading_pages VALUES (?, ?, ?)", (reading_id, i, text))
        conn.execute("INSERT INTO pages_fts (text, reading_id, page) VALUES (?, ?, ?)", (text, reading_id, i))
    sections.add_sections(conn, reading_id, pdf_path, page_texts)
    return reading_id


def badge(row, current_cohort):
    """The margin badge: 'Professor', 'AI', a past cohort's name, or None for your classmates."""
    if row["role"] == "professor":
        return "Professor"
    if row["role"] == "ai":
        return "AI"
    if row["cohort"] != current_cohort:
        return row["cohort"]
    return None


def annotation_json(row, current_cohort):
    return {
        "id": row["id"],
        "reading_id": row["reading_id"],
        "parent_id": row["parent_id"],
        "kind": row["kind"],
        "page": row["page"],
        "section": row["section_title"],
        "via": row["via"],
        "quote": row["quote"],
        "rects": json.loads(row["rects_json"]) if row["rects_json"] else None,
        "body": row["body"],
        "cited_source_ids": json.loads(row["cited_source_ids"]) if row["cited_source_ids"] else None,
        "share_with_future": bool(row["share_with_future"]),
        "created_at": row["created_at"],
        "author": {"id": row["user_id"], "name": row["name"], "role": row["role"], "cohort": row["cohort"]},
        "badge": badge(row, current_cohort),
    }


def load_annotation(conn, annotation_id):
    row = conn.execute(
        """SELECT a.*, u.name, u.role, u.cohort, s.title AS section_title FROM annotations a JOIN users u ON u.id = a.user_id
           LEFT JOIN reading_sections s ON s.id = a.section_id WHERE a.id = ?""",
        (annotation_id,),
    ).fetchone()
    return annotation_json(row, get_course(conn)["current_cohort"])


# ---------- routes: users, course, readings ----------

@app.get("/api/users")
def list_users(conn=Depends(get_conn)):
    # The AI isn't someone you can log in as.
    rows = conn.execute("SELECT * FROM users WHERE role != 'ai' ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.get("/api/course")
def course(user=Depends(current_user), conn=Depends(get_conn)):
    readings = conn.execute("SELECT id, title, created_at FROM readings ORDER BY id").fetchall()
    return {"course": get_course(conn), "readings": [dict(r) for r in readings], "user": user}


@app.post("/api/readings")
def upload_reading(title: str = Form(), file: UploadFile = File(), user=Depends(professor), conn=Depends(get_conn)):
    UPLOADS_DIR.mkdir(exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename)
    dest = UPLOADS_DIR / f"{int(time.time())}-{safe_name}"
    dest.write_bytes(file.file.read())
    reading_id = create_reading(conn, title, dest, user["id"])
    # DEMO: last year's annotations on the demo reading appear the moment it's uploaded.
    if file.filename == seed.DEMO_PDF_NAME:
        seed.add_demo_annotations(conn, reading_id, dest)
    conn.commit()
    return reading_info(reading_id, user, conn)


@app.get("/api/readings/{reading_id}")
def reading_info(reading_id: int, user=Depends(current_user), conn=Depends(get_conn)):
    reading = get_reading_or_404(conn, reading_id)
    pages = conn.execute("SELECT COUNT(*) FROM reading_pages WHERE reading_id = ?", (reading_id,)).fetchone()[0]
    return {"id": reading["id"], "title": reading["title"], "page_count": pages, "created_at": reading["created_at"]}


@app.get("/api/readings/{reading_id}/pdf")
def reading_pdf(reading_id: int, user=Depends(current_user), conn=Depends(get_conn)):
    reading = get_reading_or_404(conn, reading_id)
    return FileResponse(reading["pdf_path"], media_type="application/pdf")


# ---------- routes: annotations ----------

@app.get("/api/readings/{reading_id}/annotations")
def list_annotations(reading_id: int, user=Depends(current_user), conn=Depends(get_conn)):
    """Visible top-level annotations, newest first, each with its visible replies (oldest first).
    Ones the engagement lock hides come back as {id, page, rects, locked: true} only."""
    get_reading_or_404(conn, reading_id)
    rows = conn.execute(
        f"""SELECT a.*, u.name, u.role, u.cohort, s.title AS section_title FROM annotations a JOIN users u ON u.id = a.user_id
            LEFT JOIN reading_sections s ON s.id = a.section_id
            WHERE a.reading_id = :reading_id AND {db.VISIBLE_SQL}
            ORDER BY a.created_at, a.id""",
        {"reading_id": reading_id, **db.visibility_params(conn, user)},
    ).fetchall()
    current_cohort = get_course(conn)["current_cohort"]
    full_ids = db.full_view_ids(conn, user, reading_id)
    by_id = {}
    top_level = []
    for row in rows:
        if row["id"] in full_ids:
            item = annotation_json(row, current_cohort)
            item["locked"] = False
        else:
            # Engagement lock (SPEC §3.4): position only. No author, cohort or text leaves the server.
            item = {"id": row["id"], "parent_id": row["parent_id"], "page": row["page"],
                    "rects": json.loads(row["rects_json"]) if row["rects_json"] else None, "locked": True}
        item["replies"] = []
        by_id[item["id"]] = item
    for item in by_id.values():
        if item["parent_id"] is None:
            top_level.append(item)
            continue
        # Show nesting one level deep: a reply to a reply goes under the top-level annotation.
        parent = by_id.get(item["parent_id"])
        while parent is not None and parent["parent_id"] is not None:
            parent = by_id.get(parent["parent_id"])
        if parent is not None and not parent["locked"]:  # replies under hidden or locked ones stay hidden
            parent["replies"].append(item)
    top_level.reverse()
    for item in top_level:
        if item["locked"]:
            del item["parent_id"]  # the locked shape is exactly {id, page, rects, locked} (SPEC §6)
            del item["replies"]
    return top_level


class NewAnnotation(BaseModel):
    body: str
    parent_id: int | None = None   # set for a reply; page/quote/rects then come from the parent
    page: int | None = None
    quote: str | None = None
    rects: list[dict] | None = None
    share_with_future: bool = True


@app.post("/api/readings/{reading_id}/annotations")
def create_annotation(reading_id: int, new: NewAnnotation, user=Depends(current_user), conn=Depends(get_conn)):
    get_reading_or_404(conn, reading_id)
    if new.parent_id is not None:
        parent = conn.execute("SELECT * FROM annotations WHERE id = ?", (new.parent_id,)).fetchone()
        if parent is None or parent["reading_id"] != reading_id:
            raise HTTPException(404, f"No annotation {new.parent_id} on this reading")
        page, quote, rects_json = parent["page"], None, None
        section_id = parent["section_id"]  # replies copy the parent's section
    else:
        if new.page is None or not new.quote or not new.rects:
            raise HTTPException(422, "A new note needs page, quote and rects")
        page, quote, rects_json = new.page, new.quote, json.dumps(new.rects)
        section = sections.section_for(conn, reading_id, page, quote)
        section_id = section["id"] if section else None
    annotation_id = db.insert_annotation(
        conn, reading_id, user["id"], "note", page, quote, rects_json, new.body,
        parent_id=new.parent_id, share_with_future=new.share_with_future, section_id=section_id,
    )
    conn.commit()
    return load_annotation(conn, annotation_id)


@app.delete("/api/annotations/{annotation_id}")
def delete_annotation(annotation_id: int, user=Depends(current_user), conn=Depends(get_conn)):
    row = conn.execute("SELECT * FROM annotations WHERE id = ?", (annotation_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"No annotation {annotation_id}")
    if row["user_id"] != user["id"]:
        raise HTTPException(403, "You can only delete your own annotations")
    # The annotation and every reply under it, at any depth.
    ids = [r[0] for r in conn.execute(
        """WITH RECURSIVE tree(id) AS (
             SELECT ? UNION ALL SELECT a.id FROM annotations a JOIN tree ON a.parent_id = tree.id)
           SELECT id FROM tree""",
        (annotation_id,),
    )]
    marks = ",".join("?" * len(ids))
    # Sources found for a deleted question stay in the library; they just lose the link back.
    conn.execute(f"UPDATE sources SET first_question_id = NULL WHERE first_question_id IN ({marks})", ids)
    # Delete children before parents so the foreign keys hold. The FTS triggers fire per row.
    for annotation in reversed(ids):
        conn.execute("DELETE FROM annotations WHERE id = ?", (annotation,))
    conn.commit()
    return {"deleted": ids}


class SharingUpdate(BaseModel):
    share_with_future: bool


@app.patch("/api/annotations/{annotation_id}")
def update_sharing(annotation_id: int, update: SharingUpdate, user=Depends(current_user), conn=Depends(get_conn)):
    """Opt one of your annotations in or out of being shown to future classes."""
    row = conn.execute("SELECT * FROM annotations WHERE id = ?", (annotation_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"No annotation {annotation_id}")
    if row["user_id"] != user["id"]:
        raise HTTPException(403, "You can only change your own annotations")
    conn.execute("UPDATE annotations SET share_with_future = ? WHERE id = ?", (int(update.share_with_future), annotation_id))
    conn.commit()
    return load_annotation(conn, annotation_id)


@app.put("/api/me/sharing")
def update_all_sharing(update: SharingUpdate, user=Depends(current_user), conn=Depends(get_conn)):
    """Opt every annotation you've written in or out at once (the past-student opt-out)."""
    cur = conn.execute("UPDATE annotations SET share_with_future = ? WHERE user_id = ?",
                       (int(update.share_with_future), user["id"]))
    conn.commit()
    return {"updated": cur.rowcount, "share_with_future": update.share_with_future}


# ---------- routes: ask ----------

class AskRequest(BaseModel):
    page: int
    quote: str
    rects: list[dict]
    question: str


@app.post("/api/readings/{reading_id}/ask")
def ask_question(reading_id: int, req: AskRequest, user=Depends(current_user), conn=Depends(get_conn)):
    reading = get_reading_or_404(conn, reading_id)
    return ask.answer(conn, reading, user, req.page, req.quote, req.rects, req.question)


def stream_events(events):
    """Send events as newline-delimited JSON, one line each as soon as it's ready (SPEC §6).

    Once streaming has started the HTTP status is already 200, so a crash becomes a last
    {"event": "error", "detail": ...} line; the panel keeps what it has and shows the error.
    """
    def lines():
        try:
            for event in events():
                yield json.dumps(event) + "\n"
        except Exception as e:
            traceback.print_exception(e)
            yield json.dumps({"event": "error", "detail": f"{type(e).__name__}: {e}"}) + "\n"
    return StreamingResponse(lines(), media_type="application/x-ndjson")


@app.post("/api/readings/{reading_id}/ask/stream")
def ask_question_stream(reading_id: int, req: AskRequest, user=Depends(current_user), conn=Depends(get_conn)):
    """The same answer as /ask, sent step by step so the Ask panel can show its stages."""
    reading = dict(get_reading_or_404(conn, reading_id))

    def events():
        # Its own connection: the stream runs after this route returns, in another thread.
        stream_conn = db.connect()
        try:
            yield from ask.answer_steps(stream_conn, reading, user, req.page, req.quote, req.rects, req.question)
        finally:
            stream_conn.close()
    return stream_events(events)


class HotkeyAskRequest(BaseModel):
    quote: str
    question: str


def locate_quote(conn, quote):
    """The Mac hotkey only sends text: find its reading, page and highlight boxes. 404 if it's in none."""
    found = locate.find_page(conn, quote)
    if found is None:
        raise HTTPException(404, "This passage isn't in a course reading.")
    reading_id, page = found
    reading = dict(get_reading_or_404(conn, reading_id))
    rects = locate.quote_rects(reading["pdf_path"], page, quote)
    return reading, page, rects


def located_json(reading, page, question_event):
    return {
        "reading_id": reading["id"],
        "reading_title": reading["title"],
        "page": page,
        "section": question_event["section"],
        "reader_url": f"/readings/{reading['id']}?page={page}&annotation={question_event['question_id']}",
    }


def hotkey_steps(conn, reading, user, page, rects, req):
    """answer_steps with a `located` event right after the question is saved, and `located` in the result."""
    located = None
    for event in ask.answer_steps(conn, reading, user, page, req.quote, rects, req.question, via="hotkey"):
        if event["event"] == "question":
            located = located_json(reading, page, event)
            yield event
            yield {"event": "located", "located": located}
            continue
        if event["event"] == "done":
            event["result"]["located"] = located
        yield event


@app.post("/api/ask")
def hotkey_ask(req: HotkeyAskRequest, user=Depends(current_user), conn=Depends(get_conn)):
    """The Mac hotkey (SPEC §3.9), all at once."""
    reading, page, rects = locate_quote(conn, req.quote)
    for event in hotkey_steps(conn, reading, user, page, rects, req):
        if event["event"] == "done":
            return event["result"]


@app.post("/api/ask/stream")
def hotkey_ask_stream(req: HotkeyAskRequest, user=Depends(current_user), conn=Depends(get_conn)):
    """The Mac hotkey, step by step. Locating happens first, so a passage in no reading is still a plain 404."""
    reading, page, rects = locate_quote(conn, req.quote)

    def events():
        stream_conn = db.connect()
        try:
            yield from hotkey_steps(stream_conn, reading, user, page, rects, req)
        finally:
            stream_conn.close()
    return stream_events(events)


# ---------- routes: charter ----------

CHARTER_TOGGLES = ["ai_enabled", "ai_find_sources", "ai_explanations", "show_past_cohorts", "annotate_before_peers"]


@app.get("/api/charter")
def charter(user=Depends(current_user), conn=Depends(get_conn)):
    data = get_charter(conn)
    for toggle in CHARTER_TOGGLES:
        data[toggle] = bool(data[toggle])
    comments = conn.execute(
        """SELECT c.id, c.body, c.created_at, u.name AS author, u.role AS author_role
           FROM charter_comments c JOIN users u ON u.id = c.user_id ORDER BY c.id"""
    ).fetchall()
    data["comments"] = [dict(c) for c in comments]
    return data


class CharterUpdate(BaseModel):
    # Every field is optional: send only what changed.
    text_md: str | None = None
    permissible_sources: str | None = None
    ai_enabled: bool | None = None
    ai_find_sources: bool | None = None
    ai_explanations: bool | None = None
    max_explanation_words: int | None = None
    show_past_cohorts: bool | None = None
    annotate_before_peers: bool | None = None


@app.put("/api/charter")
def update_charter(update: CharterUpdate, user=Depends(professor), conn=Depends(get_conn)):
    changes = update.model_dump(exclude_none=True)
    if "permissible_sources" in changes:
        # Gaps were judged against the old description: start the list again.
        conn.execute("DELETE FROM charter_gaps")
    for field, value in changes.items():
        # Field names come from CharterUpdate, never from the request, so the f-string is safe.
        conn.execute(f"UPDATE charter SET {field} = ?", (int(value) if isinstance(value, bool) else value,))
    conn.execute("UPDATE charter SET updated_at = ?", (db.now(),))
    conn.commit()
    return charter(user, conn)


class NewComment(BaseModel):
    body: str


@app.post("/api/charter/comments")
def add_charter_comment(new: NewComment, user=Depends(current_user), conn=Depends(get_conn)):
    conn.execute(
        "INSERT INTO charter_comments (user_id, body, created_at) VALUES (?, ?, ?)",
        (user["id"], new.body, db.now()),
    )
    conn.commit()
    return charter(user, conn)


GAPS_DAYS = 7          # the charter page lists gaps seen in the last week
GAPS_EXAMPLES = 3      # example sources shown per kind


@app.get("/api/charter/gaps")
def charter_gaps(user=Depends(current_user), conn=Depends(get_conn)):
    """Kinds of source the AI skipped because the charter doesn't mention them, most often first
    (SPEC §3.7, ideas/01-charter-gaps.md). Grouped by the filter's label, ignoring case."""
    rows = conn.execute(
        """SELECT kind, url, title FROM charter_gaps
           WHERE dismissed = 0 AND last_seen >= ? ORDER BY last_seen DESC""",
        ((datetime.now() - timedelta(days=GAPS_DAYS)).isoformat(timespec="seconds"),),
    ).fetchall()
    groups = {}
    for r in rows:
        group = groups.setdefault(r["kind"].lower(), {"kind": r["kind"].lower(), "count": 0, "examples": []})
        group["count"] += 1
        if len(group["examples"]) < GAPS_EXAMPLES:
            group["examples"].append({"title": r["title"], "url": r["url"]})
    return sorted(groups.values(), key=lambda g: -g["count"])


class GapDismissal(BaseModel):
    kind: str


@app.post("/api/charter/gaps/dismiss")
def dismiss_charter_gap(dismissal: GapDismissal, user=Depends(current_user), conn=Depends(get_conn)):
    """Hide a kind from the gaps list (the [Dismiss] button). Anyone can: it changes no rule."""
    conn.execute("UPDATE charter_gaps SET dismissed = 1 WHERE lower(kind) = lower(?)", (dismissal.kind,))
    conn.commit()
    return charter_gaps(user, conn)


# ---------- routes: the course source library ----------

@app.get("/api/sources")
def list_sources(user=Depends(current_user), conn=Depends(get_conn)):
    rows = conn.execute(
        """SELECT s.id, s.title, s.url, s.found_by, s.created_at, s.first_question_id,
                  q.body AS first_question
           FROM sources s LEFT JOIN annotations q ON q.id = s.first_question_id
           ORDER BY s.id DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


class NewSource(BaseModel):
    url: str


@app.post("/api/sources")
def add_source(new: NewSource, user=Depends(professor), conn=Depends(get_conn)):
    page = search.fetch_page(conn, new.url)
    if not page["text"]:
        raise HTTPException(422, f"Couldn't extract any text from {new.url}")
    conn.execute(
        """INSERT INTO sources (title, url, excerpt, found_by, created_at) VALUES (?, ?, ?, 'professor', ?)
           ON CONFLICT (url) DO NOTHING""",
        (page["title"], new.url, page["text"], db.now()),
    )
    conn.commit()
    return list_sources(user, conn)


@app.delete("/api/sources/{source_id}")
def delete_source(source_id: int, user=Depends(professor), conn=Depends(get_conn)):
    conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    conn.commit()
    return list_sources(user, conn)


# ---------- routes: repository search ----------

SEARCH_LIMIT = 20


@app.get("/api/search")
def search_repository(q: str, user=Depends(current_user), conn=Depends(get_conn)):
    """FTS over visible annotations and the readings' text. Snippets mark hits as [[word]]: render them as text, never as HTML."""
    match = db.fts_query(q)
    if match is None:
        return {"annotations": [], "pages": []}
    annotations = conn.execute(
        f"""SELECT a.id AS annotation_id, a.reading_id, r.title AS reading_title, a.page, a.kind,
                   u.name AS author, snippet(annotations_fts, -1, '[[', ']]', '…', 20) AS snippet
            FROM annotations_fts f
            JOIN annotations a ON a.id = f.rowid
            JOIN users u ON u.id = a.user_id
            JOIN readings r ON r.id = a.reading_id
            WHERE annotations_fts MATCH :match AND {db.VISIBLE_SQL}
            ORDER BY bm25(annotations_fts) LIMIT :limit""",
        {"match": match, "limit": SEARCH_LIMIT, **db.visibility_params(conn, user)},
    ).fetchall()
    pages = conn.execute(
        """SELECT p.reading_id, r.title AS reading_title, p.page,
                  snippet(pages_fts, 0, '[[', ']]', '…', 20) AS snippet
           FROM pages_fts p JOIN readings r ON r.id = p.reading_id
           WHERE pages_fts MATCH ? ORDER BY bm25(pages_fts) LIMIT ?""",
        (match, SEARCH_LIMIT),
    ).fetchall()
    # Locked annotations never appear: search is not a way around the engagement lock (SPEC §3.8).
    full_ids = {}
    unlocked = []
    for r in annotations:
        if r["reading_id"] not in full_ids:
            full_ids[r["reading_id"]] = db.full_view_ids(conn, user, r["reading_id"])
        if r["annotation_id"] in full_ids[r["reading_id"]]:
            unlocked.append(dict(r))
    return {"annotations": unlocked, "pages": [dict(r) for r in pages]}


# ---------- the built frontend (production: one process, one port) ----------

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def frontend(path: str):
        """Serve built files; any other path gets index.html so react-router can handle it."""
        if path.startswith("api/"):
            raise HTTPException(404, f"No API route /{path}")
        file = (FRONTEND_DIST / path).resolve()
        if path and file.is_file() and file.is_relative_to(FRONTEND_DIST.resolve()):
            return FileResponse(file)
        return FileResponse(FRONTEND_DIST / "index.html")
