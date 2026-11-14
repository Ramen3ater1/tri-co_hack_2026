"""DEMO seed data (SPEC §10).

    uv run seed.py --reset                 # starting state of demo step 1 (no reading yet)
    uv run seed.py --reset --with-reading  # also add the reading, as if Prof. Rivera uploaded it
    uv run seed.py --reset --with-sources  # also preload the source library

Seeded annotations (Sam's past-cohort notes, the professor's) belong to the demo reading.
The demo uploads that reading live, so `POST /readings` calls add_demo_annotations()
when the uploaded file is the demo PDF. See DEMO_PDF_NAME.
"""
import argparse
import json
import shutil
from pathlib import Path

import db
import locate

BACKEND_DIR = Path(__file__).parent
UPLOADS_DIR = BACKEND_DIR / "uploads"
DEMO_PDF_NAME = "souls-of-black-folk-ch1.pdf"
DEMO_PDF_PATH = BACKEND_DIR / "seed" / DEMO_PDF_NAME
DEMO_READING_TITLE = "The Souls of Black Folk, Ch. 1: Of Our Spiritual Strivings"

COURSE_TITLE = "HIST 214: Black Intellectual Traditions"
CURRENT_COHORT = "Fall 2026"

# (name, role, cohort). Ids follow this order: Rivera = 1, Ana = 2, Ben = 3, Sam = 4, AI = 5.
USERS = [
    ("Prof. Rivera", "professor", CURRENT_COHORT),
    ("Ana", "student", CURRENT_COHORT),
    ("Ben", "student", CURRENT_COHORT),
    ("Sam", "student", "Spring 2026"),
    ("Dialectic AI", "ai", CURRENT_COHORT),
]
AI_USER_NAME = "Dialectic AI"

CHARTER_TEXT = """1. We read first and ask each other second. AI comes last.
2. AI may point us to sources and give historical context. It may not interpret the text for us or suggest thesis statements.
3. Anything AI writes is public to the class and labelled as AI.
4. Annotations are shared with future classes unless you untick the box."""

PERMISSIBLE_SOURCES = (
    "Scholarly encyclopedias (Stanford Encyclopedia of Philosophy, Britannica), university and "
    "museum sites, and primary sources from 1890–1920. No study-guide or essay-mill sites "
    "(SparkNotes, Course Hero, etc.). Wikipedia is fine for dates and names, not for interpretation."
)

# DEMO: annotations on the demo reading. (author name, page, exact quote from the PDF, body).
# Quotes must match the PDF text (curly apostrophes included) or seeding fails loudly.
DEMO_ANNOTATIONS = [
    ("Sam", 1, "How does it feel to be a problem?",
     "He never answers this directly. The whole chapter is the answer, told as a story instead."),
    ("Prof. Rivera", 2, "shut out from their world by a vast veil",
     "First appearance of the Veil, one of the book's governing images. Track where it returns in later chapters."),
    ("Prof. Rivera", 2, "a sort of seventh son, born with a veil, and gifted with second-sight",
     "Folklore: a seventh son born with a caul (a 'veil') was said to have second sight. Du Bois turns the veil into a gift as well as a barrier."),
    ("Sam", 2, "this double-consciousness, this sense of always looking at one’s self through the eyes of others",
     "Our seminar read this as both a wound and a kind of insight: you see yourself as the world sees you, and also see the world more clearly. Compare the 'second-sight' line just above."),
    ("Ben", 4, "the freedman has not yet found in freedom his promised land",
     "Forty years since Emancipation, and 'promised land' - is he echoing the Israelites' forty years in the wilderness?"),
]


# DEMO: preloaded by --with-sources, the fallback if web search fails on stage (SPEC §10).
# Fetched through search.fetch_page, so after one online run they come from web_cache.
# Britannica and The Atlantic refuse our fetcher (403), so they're not here.
DEMO_SOURCES = [
    "https://plato.stanford.edu/entries/dubois/",
    "https://en.wikipedia.org/wiki/Double_consciousness",
]


def user_id(conn, name):
    return conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()["id"]


def add_demo_annotations(conn, reading_id, pdf_path):
    for author, page, quote, body in DEMO_ANNOTATIONS:
        rects = locate.quote_rects(pdf_path, page, quote)
        conn.execute(
            """INSERT INTO annotations (reading_id, user_id, kind, page, quote, rects_json, body, created_at)
               VALUES (?, ?, 'note', ?, ?, ?, ?, ?)""",
            (reading_id, user_id(conn, author), page, quote, json.dumps(rects), body, db.now()),
        )


def add_demo_reading(conn):
    """Do what the live upload does, for when the upload fails on stage."""
    import main  # here, not at the top: main imports this module
    UPLOADS_DIR.mkdir(exist_ok=True)
    dest = UPLOADS_DIR / DEMO_PDF_NAME
    shutil.copy(DEMO_PDF_PATH, dest)
    reading_id = main.create_reading(conn, DEMO_READING_TITLE, dest, user_id(conn, "Prof. Rivera"))
    add_demo_annotations(conn, reading_id, dest)


def add_demo_sources(conn):
    import search
    for url in DEMO_SOURCES:
        page = search.fetch_page(conn, url)
        conn.execute(
            "INSERT INTO sources (title, url, excerpt, found_by, created_at) VALUES (?, ?, ?, 'professor', ?)",
            (page["title"], url, page["text"], db.now()),
        )


def reset(with_reading, with_sources):
    # Keep web_cache across resets (SPEC §9), so the demo replays cached web results.
    cache = []
    if db.DB_PATH.exists():
        old = db.connect()
        cache = old.execute("SELECT key, value, created_at FROM web_cache").fetchall()
        old.close()
        db.DB_PATH.unlink()
    if UPLOADS_DIR.exists():
        shutil.rmtree(UPLOADS_DIR)

    conn = db.connect()
    db.init_schema(conn)
    conn.executemany("INSERT INTO web_cache VALUES (?, ?, ?)", [tuple(r) for r in cache])
    conn.executemany("INSERT INTO users (name, role, cohort) VALUES (?, ?, ?)", USERS)
    conn.execute("INSERT INTO course (title, current_cohort) VALUES (?, ?)", (COURSE_TITLE, CURRENT_COHORT))
    conn.execute(
        "INSERT INTO charter (text_md, permissible_sources, updated_at) VALUES (?, ?, ?)",
        (CHARTER_TEXT, PERMISSIBLE_SOURCES, db.now()),
    )
    if with_reading:
        add_demo_reading(conn)
    if with_sources:
        add_demo_sources(conn)
    conn.commit()
    conn.close()
    print(f"Seeded {db.DB_PATH} (kept {len(cache)} web_cache rows)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", required=True, help="delete the DB and uploads, then seed")
    parser.add_argument("--with-reading", action="store_true", help="also add the demo reading and its annotations")
    parser.add_argument("--with-sources", action="store_true", help="also preload the source library (web search fallback)")
    args = parser.parse_args()
    reset(args.with_reading, args.with_sources)
