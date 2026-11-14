"""DEMO: shared by seed.py and seed_large.py. Add a seeded reading and its margin notes.

A note is (page, exact quote from the PDF's text, kind, who, body, [replies as (who, body)]).
who: a name in the course; None = the next current student in the course's rota; "past" = the
next past-cohort student. Quotes are compared letters-only (locate.squash), so punctuation,
line-break hyphens and ligatures don't matter, but a letter that differs from the PDF's text
(OCR slips included) makes seeding fail loudly.
"""
import json
import shutil
from datetime import datetime, timedelta
from itertools import cycle

import db
import locate
import sections


def days_ago(days):
    return datetime.now() - timedelta(days=days)


def stamp(conn, table, row_id, when):
    conn.execute(f"UPDATE {table} SET created_at = ? WHERE id = ?", (when.isoformat(timespec="seconds"), row_id))


def add_reading(conn, course_id, title, src_pdf, uploads_dir, uploaded_by, when):
    """Copy the PDF into uploads and add it as a ready reading, uploaded at `when`."""
    import main  # here, not at the top: main imports seed, which imports this
    uploads_dir.mkdir(exist_ok=True)
    pdf_path = uploads_dir / src_pdf.name
    shutil.copy(src_pdf, pdf_path)
    reading_id = main.create_reading(conn, course_id, title, pdf_path, uploaded_by)
    stamp(conn, "readings", reading_id, when)
    return reading_id, pdf_path


class Rota:
    """Hands out authors in turn, so seeded notes are spread over the class."""

    def __init__(self, ids, current, past):
        self.ids = ids
        self.current = cycle(current)
        self.past = cycle(past)

    def author(self, who):
        if who is None:
            return self.ids[next(self.current)]
        if who == "past":
            return self.ids[next(self.past)]
        return self.ids[who]


def add_notes(conn, reading_id, pdf_path, notes, rota, start, end):
    """Insert the notes and their replies, timestamps spread evenly from `start` to `end`, oldest first."""
    count = len(notes) + sum(len(n[5]) for n in notes)
    step = (end - start) / (count + 1)
    clock = start
    for page, quote, kind, who, body, replies in notes:
        clock += step
        rects = json.dumps(locate.quote_rects(pdf_path, page, quote))
        section = sections.section_for(conn, reading_id, page, quote)
        section_id = section["id"] if section else None
        note_id = db.insert_annotation(conn, reading_id, rota.author(who), kind, page, quote, rects, body,
                                       section_id=section_id)
        stamp(conn, "annotations", note_id, clock)
        for reply_who, reply_body in replies:
            clock += step
            reply_id = db.insert_annotation(conn, reading_id, rota.author(reply_who), "note", page, None, None,
                                            reply_body, parent_id=note_id, section_id=section_id)
            stamp(conn, "annotations", reply_id, clock)


def add_charter_comments(conn, course_id, ids, comments, start, end):
    """Charter proposals: (who, body, status) with status 'open', 'added' or 'declined'."""
    step = (end - start) / (len(comments) + 1)
    for i, (who, body, status) in enumerate(comments, start=1):
        comment_id = conn.execute(
            "INSERT INTO charter_comments (course_id, user_id, body, created_at, status) VALUES (?, ?, ?, ?, ?)",
            (course_id, ids[who], body, db.now(), status)).lastrowid
        stamp(conn, "charter_comments", comment_id, start + step * i)
