"""Dialectic API (SPEC §6). Run from app/backend:

    uv run --env-file ../../.env uvicorn main:app --reload
"""
import json
import re
import threading
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

import pypdf
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Literal

import ask
import db
import locate
import ocr
import search
import sections
import seed
import semantic
import spend

UPLOADS_DIR = Path(__file__).parent / "uploads"
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

app = FastAPI(title="Dialectic")

_conn = db.connect()
db.migrate(_conn)  # add any new columns to an older database
_conn.close()


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

def get_course(conn, course_id):
    return dict(conn.execute("SELECT * FROM course WHERE id = ?", (course_id,)).fetchone())


def get_charter(conn, course_id):
    return dict(conn.execute("SELECT * FROM charter WHERE course_id = ?", (course_id,)).fetchone())


def get_reading_or_404(conn, reading_id, user):
    """A reading in the user's course. Other courses' readings are 404, as if they didn't exist."""
    row = conn.execute("SELECT * FROM readings WHERE id = ?", (reading_id,)).fetchone()
    if row is None or row["course_id"] != user["course_id"]:
        raise HTTPException(404, f"No reading {reading_id} in your course")
    return row


def get_ready_reading(conn, reading_id, user):
    """Like get_reading_or_404, but 409 while the scan is still being OCR'd (SPEC §3.11)."""
    reading = get_reading_or_404(conn, reading_id, user)
    if reading["status"] != "ready":
        raise HTTPException(409, "This reading is still being processed. Try again in a minute."
                            if reading["status"] == "processing" else f"This reading failed to process: {reading['error']}")
    return reading


def require_quote(quote):
    """Asking needs the passage's text: peers, sources and the AI all work from it. A box over an
    unreadable scan has none until the student types it in (SPEC §3.3)."""
    if not quote.strip():
        raise HTTPException(422, "Type the passage you're asking about: this box has no readable text.")


def create_reading(conn, course_id, title, pdf_path, uploaded_by, status="ready"):
    """Insert a reading. With status 'ready' (seed.py), also extract its pages and sections now."""
    cur = conn.execute(
        "INSERT INTO readings (course_id, title, pdf_path, uploaded_by, created_at, status) VALUES (?, ?, ?, ?, ?, ?)",
        (course_id, title, str(pdf_path), uploaded_by, db.now(), status),
    )
    reading_id = cur.lastrowid
    if status == "ready":
        extract_pages(conn, reading_id, pdf_path)
    return reading_id


def extract_pages(conn, reading_id, pdf_path):
    """Page text (for search, peers, the hotkey's locate, the AI prompt) and sections."""
    page_texts = [page.extract_text() or "" for page in pypdf.PdfReader(pdf_path).pages]
    for i, text in enumerate(page_texts, start=1):
        conn.execute("INSERT INTO reading_pages VALUES (?, ?, ?)", (reading_id, i, text))
        conn.execute("INSERT INTO pages_fts (text, reading_id, page) VALUES (?, ?, ?)", (text, reading_id, i))
    sections.add_sections(conn, reading_id, pdf_path, page_texts)


def process_upload(reading_id, pdf_path, is_demo_pdf):
    """Background thread (SPEC §3.11): OCR, extract pages, then mark the reading ready or failed."""
    # TODO(edge): a server restart mid-OCR leaves the reading "processing" for good; upload it again.
    conn = db.connect()  # its own connection: the request's is closed by now
    try:
        # DEMO: the seed PDF is already OCR'd (and its seeded quotes match that OCR exactly),
        # so the live upload on stage doesn't wait ~50 s to redo it.
        if not is_demo_pdf:
            print(ocr.ocr_in_place(pdf_path), flush=True)
        extract_pages(conn, reading_id, pdf_path)
        # DEMO: last year's annotations on the demo reading appear the moment it's ready.
        if is_demo_pdf:
            seed.add_demo_annotations(conn, reading_id, pdf_path)
        conn.execute("UPDATE readings SET status = 'ready' WHERE id = ?", (reading_id,))
        conn.commit()
    except Exception as exc:
        conn.rollback()
        traceback.print_exc()
        conn.execute("UPDATE readings SET status = 'failed', error = ? WHERE id = ?",
                     (f"{type(exc).__name__}: {exc}", reading_id))
        conn.commit()
    finally:
        conn.close()


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
        "source_app": row["source_app"],
        "quote": row["quote"],
        "rects": json.loads(row["rects_json"]) if row["rects_json"] else None,
        "body": row["body"],
        "cited_source_ids": json.loads(row["cited_source_ids"]) if row["cited_source_ids"] else None,
        "share_with_future": bool(row["share_with_future"]),
        "created_at": row["created_at"],
        "author": {"id": row["user_id"], "name": row["name"], "role": row["role"], "cohort": row["cohort"]},
        "badge": badge(row, current_cohort),
        "answer_summary": answer_summary(row),
    }


def answer_summary(row):
    """For a question's margin card ("Answered: 1 classmate, 3 sources, AI context"): counts
    from its saved answer, or None (not a question, or asked before answers were saved)."""
    if row["kind"] != "question" or not row["answer_json"]:
        return None
    answer = json.loads(row["answer_json"])
    return {
        "peer": len(answer["peer"]),
        "peer_authors": len({p["author"] for p in answer["peer"]}),
        "sources": len(answer["sources"]),
        "ai_answer": answer["ai_answer"] is not None,
    }


def load_annotation(conn, annotation_id, user):
    row = conn.execute(
        """SELECT a.*, u.name, u.role, u.cohort, s.title AS section_title FROM annotations a JOIN users u ON u.id = a.user_id
           LEFT JOIN reading_sections s ON s.id = a.section_id WHERE a.id = ?""",
        (annotation_id,),
    ).fetchone()
    return annotation_json(row, get_course(conn, user["course_id"])["current_cohort"])


# ---------- routes: users, course, readings ----------

@app.get("/api/users")
def list_users(conn=Depends(get_conn)):
    # The AI isn't someone you can log in as. The log-in page groups people by course.
    rows = conn.execute(
        """SELECT u.*, c.title AS course_title, c.current_cohort FROM users u JOIN course c ON c.id = u.course_id
           WHERE u.role != 'ai' ORDER BY u.course_id, u.id"""
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/course")
def course(user=Depends(current_user), conn=Depends(get_conn)):
    """Each reading carries what its card shows: file name, pages, and how many notes and
    questions you can see on it (top level only; locked ones count too, they're there)."""
    readings = conn.execute(
        f"""SELECT r.id, r.title, r.pdf_path, r.created_at, r.status, r.error,
                   (SELECT COUNT(*) FROM reading_pages p WHERE p.reading_id = r.id) AS page_count,
                   (SELECT COUNT(*) FROM annotations a JOIN users u ON u.id = a.user_id
                     WHERE a.reading_id = r.id AND a.parent_id IS NULL AND a.kind = 'note' AND {db.VISIBLE_SQL}) AS note_count,
                   (SELECT COUNT(*) FROM annotations a JOIN users u ON u.id = a.user_id
                     WHERE a.reading_id = r.id AND a.kind = 'question' AND {db.VISIBLE_SQL}) AS question_count
            FROM readings r WHERE r.course_id = :course_id ORDER BY r.id""",
        {"course_id": user["course_id"], **db.visibility_params(conn, user)},
    ).fetchall()
    cards = []
    for r in readings:
        card = dict(r)
        # Uploads are saved as "<timestamp>-<name>.pdf": show the name the professor uploaded.
        card["filename"] = re.sub(r"^\d+-", "", Path(card.pop("pdf_path")).name)
        cards.append(card)
    return {"course": get_course(conn, user["course_id"]), "readings": cards, "user": user}


@app.post("/api/readings")
def upload_reading(title: str = Form(), file: UploadFile = File(), user=Depends(professor), conn=Depends(get_conn)):
    UPLOADS_DIR.mkdir(exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename)
    dest = UPLOADS_DIR / f"{int(time.time())}-{safe_name}"
    dest.write_bytes(file.file.read())
    # OCR takes ~5 s a page, longer than Cloudflare's 100 s request limit for a long reading,
    # so return at once with status "processing" and do the work in a thread (SPEC §3.11).
    reading_id = create_reading(conn, user["course_id"], title, dest, user["id"], status="processing")
    conn.commit()
    # DEMO: only the demo course's upload of the demo PDF gets the shortcut and seeded notes (SPEC §10).
    is_demo_pdf = (file.filename == seed.DEMO_PDF_NAME
                   and get_course(conn, user["course_id"])["title"] == seed.COURSE_TITLE)
    threading.Thread(target=process_upload, args=(reading_id, dest, is_demo_pdf), daemon=True).start()
    return reading_info(reading_id, user, conn)


@app.get("/api/readings/{reading_id}")
def reading_info(reading_id: int, user=Depends(current_user), conn=Depends(get_conn)):
    reading = get_reading_or_404(conn, reading_id, user)
    pages = conn.execute("SELECT COUNT(*) FROM reading_pages WHERE reading_id = ?", (reading_id,)).fetchone()[0]
    return {"id": reading["id"], "title": reading["title"], "page_count": pages, "created_at": reading["created_at"],
            "status": reading["status"], "error": reading["error"]}


@app.get("/api/readings/{reading_id}/pdf")
def reading_pdf(reading_id: int, user=Depends(current_user), conn=Depends(get_conn)):
    reading = get_reading_or_404(conn, reading_id, user)
    return FileResponse(reading["pdf_path"], media_type="application/pdf")


# ---------- routes: annotations ----------

@app.get("/api/readings/{reading_id}/annotations")
def list_annotations(reading_id: int, user=Depends(current_user), conn=Depends(get_conn)):
    """Visible top-level annotations, newest first, each with its visible replies (oldest first).
    Ones the engagement lock hides come back as {id, page, rects, locked: true} only."""
    get_reading_or_404(conn, reading_id, user)
    rows = conn.execute(
        f"""SELECT a.*, u.name, u.role, u.cohort, s.title AS section_title FROM annotations a JOIN users u ON u.id = a.user_id
            LEFT JOIN reading_sections s ON s.id = a.section_id
            WHERE a.reading_id = :reading_id AND {db.VISIBLE_SQL}
            ORDER BY a.created_at, a.id""",
        {"reading_id": reading_id, **db.visibility_params(conn, user)},
    ).fetchall()
    current_cohort = get_course(conn, user["course_id"])["current_cohort"]
    full_ids = db.full_view_ids(conn, user, reading_id)
    # One lock card per cluster of nearby locked notes ("2 notes near here").
    groups = db.locked_groups([
        {"id": r["id"], "page": r["page"],
         "rects": json.loads(r["rects_json"]) if r["rects_json"] else None}
        for r in rows if r["id"] not in full_ids and r["parent_id"] is None
    ])
    by_id = {}
    top_level = []
    for row in rows:
        if row["id"] in full_ids:
            item = annotation_json(row, current_cohort)
            item["locked"] = False
        else:
            # Engagement lock (SPEC §3.4): position only. No author, cohort or text leaves the server.
            item = {"id": row["id"], "parent_id": row["parent_id"], "page": row["page"],
                    "rects": json.loads(row["rects_json"]) if row["rects_json"] else None, "locked": True,
                    **groups.get(row["id"], {})}
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
            del item["parent_id"]  # the locked shape is exactly {id, page, rects, locked, group...} (SPEC §6)
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
    get_ready_reading(conn, reading_id, user)
    if new.parent_id is not None:
        parent = conn.execute("SELECT * FROM annotations WHERE id = ?", (new.parent_id,)).fetchone()
        if parent is None or parent["reading_id"] != reading_id:
            raise HTTPException(404, f"No annotation {new.parent_id} on this reading")
        page, quote, rects_json = parent["page"], None, None
        section_id = parent["section_id"]  # replies copy the parent's section
    else:
        # The quote may be empty: a box drawn over a picture or an unreadable scan (SPEC §3.3).
        if new.page is None or not new.rects:
            raise HTTPException(422, "A new note needs page and rects")
        page, quote, rects_json = new.page, new.quote or "", json.dumps(new.rects)
        section = sections.section_for(conn, reading_id, page, quote)
        section_id = section["id"] if section else None
    annotation_id = db.insert_annotation(
        conn, reading_id, user["id"], "note", page, quote, rects_json, new.body,
        parent_id=new.parent_id, share_with_future=new.share_with_future, section_id=section_id,
    )
    conn.commit()
    return load_annotation(conn, annotation_id, user)


class BoxRequest(BaseModel):
    page: int
    rect: dict  # {x, y, w, h}, page fractions


@app.post("/api/readings/{reading_id}/box-text")
def box_text(reading_id: int, box: BoxRequest, user=Depends(current_user), conn=Depends(get_conn)):
    """The text inside a box drawn on the page (SPEC §3.3), to prefill the passage it's about."""
    reading = get_ready_reading(conn, reading_id, user)
    return {"text": ocr.box_text(reading["pdf_path"], box.page, box.rect)}


@app.get("/api/questions/{question_id}/answer")
def saved_answer(question_id: int, user=Depends(current_user), conn=Depends(get_conn)):
    """Reopen a question's answer card: the /ask response saved when it was asked.
    TODO(edge): peers and sources are as they were then (a deleted note still shows here)."""
    row = conn.execute(
        f"""SELECT a.* FROM annotations a JOIN users u ON u.id = a.user_id
            WHERE a.id = :id AND a.kind = 'question' AND {db.VISIBLE_SQL}""",
        {"id": question_id, **db.visibility_params(conn, user)},
    ).fetchone()
    if row is not None:
        get_reading_or_404(conn, row["reading_id"], user)  # 404 for another course's question
    if row is None or row["id"] not in db.full_view_ids(conn, user, row["reading_id"]):
        raise HTTPException(404, f"No question {question_id} you can see")
    if not row["answer_json"]:
        raise HTTPException(404, f"Question {question_id} has no saved answer (asked before answers were saved)")
    return json.loads(row["answer_json"])


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
    return load_annotation(conn, annotation_id, user)


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
def ask_question(reading_id: int, req: AskRequest, user=Depends(current_user), conn=Depends(get_conn),
                 x_device_id: str | None = Header(None)):
    reading = get_ready_reading(conn, reading_id, user)
    require_quote(req.quote)
    return ask.answer(conn, reading, user, req.page, req.quote, req.rects, req.question, device_id=x_device_id)


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
def ask_question_stream(reading_id: int, req: AskRequest, user=Depends(current_user), conn=Depends(get_conn),
                        x_device_id: str | None = Header(None)):
    """The same answer as /ask, sent step by step so the Ask panel can show its stages."""
    reading = dict(get_ready_reading(conn, reading_id, user))
    require_quote(req.quote)

    def events():
        # Its own connection: the stream runs after this route returns, in another thread.
        stream_conn = db.connect()
        try:
            yield from ask.answer_steps(stream_conn, reading, user, req.page, req.quote, req.rects, req.question,
                                        device_id=x_device_id)
        finally:
            stream_conn.close()
    return stream_events(events)


class HotkeyAskRequest(BaseModel):
    quote: str
    question: str
    source_app: str | None = None  # the app the text came from, e.g. "Notability" (optional)


def locate_quote(conn, quote, user):
    """The Mac hotkey only sends text: find its reading (in your course), page and highlight boxes. 404 if it's in none."""
    found = locate.find_page(conn, quote, user["course_id"])
    if found is None:
        raise HTTPException(404, "This passage isn't in a course reading.")
    reading_id, page = found
    reading = dict(get_reading_or_404(conn, reading_id, user))
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


def hotkey_steps(conn, reading, user, page, rects, req, device_id):
    """answer_steps with a `located` event right after the question is saved, and `located` in the result."""
    located = None
    for event in ask.answer_steps(conn, reading, user, page, req.quote, rects, req.question, via="hotkey",
                                  device_id=device_id, source_app=req.source_app):
        if event["event"] == "question":
            located = located_json(reading, page, event)
            yield event
            yield {"event": "located", "located": located}
            continue
        if event["event"] == "done":
            event["result"]["located"] = located
        yield event


@app.post("/api/ask")
def hotkey_ask(req: HotkeyAskRequest, user=Depends(current_user), conn=Depends(get_conn),
               x_device_id: str | None = Header(None)):
    """The Mac hotkey (SPEC §3.9), all at once."""
    reading, page, rects = locate_quote(conn, req.quote, user)
    for event in hotkey_steps(conn, reading, user, page, rects, req, x_device_id):
        if event["event"] == "done":
            return event["result"]


@app.post("/api/ask/stream")
def hotkey_ask_stream(req: HotkeyAskRequest, user=Depends(current_user), conn=Depends(get_conn),
                      x_device_id: str | None = Header(None)):
    """The Mac hotkey, step by step. Locating happens first, so a passage in no reading is still a plain 404."""
    reading, page, rects = locate_quote(conn, req.quote, user)

    def events():
        stream_conn = db.connect()
        try:
            yield from hotkey_steps(stream_conn, reading, user, page, rects, req, x_device_id)
        finally:
            stream_conn.close()
    return stream_events(events)


class HotkeyNoteRequest(BaseModel):
    quote: str
    body: str
    share_with_future: bool = True
    source_app: str | None = None  # as for HotkeyAskRequest


@app.post("/api/note")
def hotkey_note(req: HotkeyNoteRequest, user=Depends(current_user), conn=Depends(get_conn)):
    """A note from the Mac hotkey (⌥⇧N): like POST /readings/{id}/annotations, but the server
    finds the reading, page and rects from the quote, as /ask does."""
    reading, page, rects = locate_quote(conn, req.quote, user)
    section = sections.section_for(conn, reading["id"], page, req.quote)
    annotation_id = db.insert_annotation(
        conn, reading["id"], user["id"], "note", page, req.quote, json.dumps(rects), req.body,
        share_with_future=req.share_with_future, section_id=section["id"] if section else None, via="hotkey",
        source_app=req.source_app,
    )
    conn.commit()
    result = load_annotation(conn, annotation_id, user)
    result["reader_url"] = f"/readings/{reading['id']}?page={page}&annotation={annotation_id}"
    return result


# ---------- routes: charter ----------

CHARTER_TOGGLES = ["ai_enabled", "ai_find_sources", "ai_explanations", "ai_semantic_search",
                   "show_past_cohorts", "annotate_before_peers"]


@app.get("/api/charter")
def charter(user=Depends(current_user), conn=Depends(get_conn)):
    data = get_charter(conn, user["course_id"])
    for toggle in CHARTER_TOGGLES:
        data[toggle] = bool(data[toggle])
    comments = conn.execute(
        """SELECT c.id, c.body, c.created_at, c.status, u.name AS author, u.role AS author_role
           FROM charter_comments c JOIN users u ON u.id = c.user_id WHERE c.course_id = ? ORDER BY c.id""",
        (user["course_id"],),
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
    ai_semantic_search: bool | None = None
    max_explanation_words: int | None = None
    show_past_cohorts: bool | None = None
    annotate_before_peers: bool | None = None


@app.put("/api/charter")
def update_charter(update: CharterUpdate, user=Depends(professor), conn=Depends(get_conn)):
    changes = update.model_dump(exclude_none=True)
    if "permissible_sources" in changes:
        # Gaps were judged against the old description: start the list again.
        conn.execute("DELETE FROM charter_gaps WHERE course_id = ?", (user["course_id"],))
    for field, value in changes.items():
        # Field names come from CharterUpdate, never from the request, so the f-string is safe.
        conn.execute(f"UPDATE charter SET {field} = ? WHERE course_id = ?",
                     (int(value) if isinstance(value, bool) else value, user["course_id"]))
    conn.execute("UPDATE charter SET updated_at = ? WHERE course_id = ?", (db.now(), user["course_id"]))
    conn.commit()
    return charter(user, conn)


class NewComment(BaseModel):
    body: str


@app.post("/api/charter/comments")
def add_charter_comment(new: NewComment, user=Depends(current_user), conn=Depends(get_conn)):
    conn.execute(
        "INSERT INTO charter_comments (course_id, user_id, body, created_at) VALUES (?, ?, ?, ?)",
        (user["course_id"], user["id"], new.body, db.now()),
    )
    conn.commit()
    return charter(user, conn)


class CommentStatus(BaseModel):
    status: Literal["open", "added", "declined"]


@app.patch("/api/charter/comments/{comment_id}")
def set_charter_comment_status(comment_id: int, update: CommentStatus, user=Depends(professor), conn=Depends(get_conn)):
    # The professor's answer to a proposal: worked into the charter, declined, or reopened.
    found = conn.execute("UPDATE charter_comments SET status = ? WHERE id = ? AND course_id = ?",
                         (update.status, comment_id, user["course_id"])).rowcount
    if not found:
        raise HTTPException(404, f"No proposal {comment_id} in your course")
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
           WHERE course_id = ? AND dismissed = 0 AND last_seen >= ? ORDER BY last_seen DESC""",
        (user["course_id"], (datetime.now() - timedelta(days=GAPS_DAYS)).isoformat(timespec="seconds")),
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
    conn.execute("UPDATE charter_gaps SET dismissed = 1 WHERE course_id = ? AND lower(kind) = lower(?)",
                 (user["course_id"], dismissal.kind))
    conn.commit()
    return charter_gaps(user, conn)


# ---------- routes: the course source library ----------

@app.get("/api/sources")
def list_sources(user=Depends(current_user), conn=Depends(get_conn)):
    rows = conn.execute(
        """SELECT s.id, s.title, s.url, s.found_by, s.created_at, s.first_question_id,
                  q.body AS first_question, qu.name AS first_question_author
           FROM sources s LEFT JOIN annotations q ON q.id = s.first_question_id
           LEFT JOIN users qu ON qu.id = q.user_id
           WHERE s.course_id = ? ORDER BY s.id DESC""",
        (user["course_id"],),
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
        """INSERT INTO sources (course_id, title, url, excerpt, found_by, created_at) VALUES (?, ?, ?, ?, 'professor', ?)
           ON CONFLICT (course_id, url) DO NOTHING""",
        (user["course_id"], page["title"], new.url, page["text"], db.now()),
    )
    conn.commit()
    return list_sources(user, conn)


@app.delete("/api/sources/{source_id}")
def delete_source(source_id: int, user=Depends(professor), conn=Depends(get_conn)):
    conn.execute("DELETE FROM sources WHERE id = ? AND course_id = ?", (source_id, user["course_id"]))
    conn.commit()
    return list_sources(user, conn)


# ---------- routes: spending (SPEC §9.1) ----------

@app.get("/api/spend")
def spending(conn=Depends(get_conn)):
    """Each paid service's total against this copy's budget. Read-only, nothing per device, and no
    X-User-Id needed, so it can be checked from a phone browser."""
    return spend.totals(conn)


# ---------- routes: repository search ----------

SEARCH_LIMIT = 20


# Shown when the charter (or a spending limit) stops a meaning search.
SEMANTIC_OFF_LABELS = {
    "ai_enabled": "AI enabled — off",
    "ai_semantic_search": "AI may search readings by meaning — off",
}


@app.get("/api/search")
def search_repository(q: str, mode: str = "words", user=Depends(current_user), conn=Depends(get_conn),
                      x_device_id: str | None = Header(None)):
    """mode=words: FTS over visible annotations and the readings' text. Snippets mark hits as
    [[word]]: render them as text, never as HTML.
    mode=meaning: reading passages closest in meaning (semantic.py), if the charter allows it."""
    if mode == "meaning":
        return search_by_meaning(conn, user, q, x_device_id)
    match = db.fts_query(q)
    if match is None:
        return {"annotations": [], "pages": []}
    annotations = conn.execute(
        f"""SELECT a.id AS annotation_id, a.reading_id, r.title AS reading_title, a.page, a.kind, a.via,
                   u.id AS author_id, u.name AS author, u.role, u.cohort,
                   snippet(annotations_fts, -1, '[[', ']]', '…', 20) AS snippet
            FROM annotations_fts f
            JOIN annotations a ON a.id = f.rowid
            JOIN users u ON u.id = a.user_id
            JOIN readings r ON r.id = a.reading_id
            WHERE annotations_fts MATCH :match AND r.course_id = :course_id AND {db.VISIBLE_SQL}
            ORDER BY bm25(annotations_fts) LIMIT :limit""",
        {"match": match, "limit": SEARCH_LIMIT, "course_id": user["course_id"], **db.visibility_params(conn, user)},
    ).fetchall()
    pages = conn.execute(
        """SELECT p.reading_id, r.title AS reading_title, p.page,
                  snippet(pages_fts, 0, '[[', ']]', '…', 20) AS snippet
           FROM pages_fts p JOIN readings r ON r.id = p.reading_id
           WHERE pages_fts MATCH ? AND r.course_id = ? ORDER BY bm25(pages_fts) LIMIT ?""",
        (match, user["course_id"], SEARCH_LIMIT),
    ).fetchall()
    # Locked annotations never appear: search is not a way around the engagement lock (SPEC §3.8).
    full_ids = {}
    unlocked = []
    current_cohort = get_course(conn, user["course_id"])["current_cohort"]
    for r in annotations:
        if r["reading_id"] not in full_ids:
            full_ids[r["reading_id"]] = db.full_view_ids(conn, user, r["reading_id"])
        if r["annotation_id"] in full_ids[r["reading_id"]]:
            result = dict(r)
            result["badge"] = badge(r, current_cohort)
            del result["role"]
            unlocked.append(result)
    return {"annotations": unlocked, "pages": [dict(r) for r in pages]}


def search_by_meaning(conn, user, q, device_id):
    """Reading passages only, never annotations: no way round the engagement lock (SPEC §3.8)."""
    charter = get_charter(conn, user["course_id"])
    for toggle in ["ai_enabled", "ai_semantic_search"]:
        if not charter[toggle]:
            return {"passages": [], "blocked": {"by": "toggle", "label": SEMANTIC_OFF_LABELS[toggle]}}
    if not q.strip():
        return {"passages": [], "blocked": None}
    try:
        passages = semantic.search(conn, user["course_id"], q.strip(), spend.Meter(conn, device_id, None))
    except spend.LimitReached as exc:
        return {"passages": [], "blocked": {"by": "limit", "label": str(exc)}}
    return {"passages": passages, "blocked": None}


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
