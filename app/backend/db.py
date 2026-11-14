"""SQLite connection, schema and full-text-search helpers (SPEC §5)."""
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "dialectic.db"

# Engagement lock (SPEC §3.4): two highlights are "near" if they're on the same page and the
# vertical gap between their bounding boxes is at most this fraction of the page height
# (~a paragraph on the demo PDF). Tune it here.
NEAR_DISTANCE = 0.08

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('professor','student','ai')),
  cohort TEXT NOT NULL,
  course_id INTEGER REFERENCES course(id)  -- each person is in one course; null for the AI (it serves every course)
);

-- One row per course. Readings, the charter, its comments and gaps, and the source library are per course.
CREATE TABLE IF NOT EXISTS course (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  current_cohort TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS charter (
  id INTEGER PRIMARY KEY,
  course_id INTEGER NOT NULL UNIQUE REFERENCES course(id),
  text_md TEXT NOT NULL,
  permissible_sources TEXT NOT NULL,
  ai_enabled INTEGER NOT NULL DEFAULT 1,
  ai_find_sources INTEGER NOT NULL DEFAULT 1,
  ai_explanations INTEGER NOT NULL DEFAULT 1,
  max_explanation_words INTEGER NOT NULL DEFAULT 120,
  show_past_cohorts INTEGER NOT NULL DEFAULT 1,
  annotate_before_peers INTEGER NOT NULL DEFAULT 1,  -- the engagement lock (SPEC §3.4)
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS charter_comments (
  id INTEGER PRIMARY KEY,
  course_id INTEGER NOT NULL REFERENCES course(id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  body TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS readings (
  id INTEGER PRIMARY KEY,
  course_id INTEGER NOT NULL REFERENCES course(id),
  title TEXT NOT NULL,
  pdf_path TEXT NOT NULL,
  uploaded_by INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  -- OCR runs in the background after upload (SPEC §3.11): processing → ready, or failed with `error`.
  status TEXT NOT NULL DEFAULT 'ready' CHECK (status IN ('processing','ready','failed')),
  error TEXT
);

CREATE TABLE IF NOT EXISTS reading_pages (
  reading_id INTEGER NOT NULL REFERENCES readings(id),
  page INTEGER NOT NULL,
  text TEXT NOT NULL,
  PRIMARY KEY (reading_id, page)
);

CREATE TABLE IF NOT EXISTS reading_sections (
  id INTEGER PRIMARY KEY,
  reading_id INTEGER NOT NULL REFERENCES readings(id),
  title TEXT NOT NULL,
  start_page INTEGER NOT NULL,
  ord INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS annotations (
  id INTEGER PRIMARY KEY,
  reading_id INTEGER NOT NULL REFERENCES readings(id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  parent_id INTEGER REFERENCES annotations(id),
  kind TEXT NOT NULL CHECK (kind IN ('note','question','ai_answer')),
  page INTEGER NOT NULL,
  section_id INTEGER REFERENCES reading_sections(id),  -- null until sections are built (SPEC §3.10)
  via TEXT NOT NULL DEFAULT 'web' CHECK (via IN ('web','hotkey')),
  quote TEXT,
  rects_json TEXT,
  body TEXT NOT NULL,
  cited_source_ids TEXT,
  share_with_future INTEGER NOT NULL DEFAULT 1,
  source_app TEXT,   -- hotkey only: the Mac app the text came from (e.g. 'Notability'), if sent
  answer_json TEXT,  -- questions only: the finished /ask response, so the answer card can reopen
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY,
  course_id INTEGER NOT NULL REFERENCES course(id),
  title TEXT NOT NULL,
  url TEXT NOT NULL,
  excerpt TEXT NOT NULL,
  found_by TEXT NOT NULL CHECK (found_by IN ('ai','professor')),
  first_question_id INTEGER REFERENCES annotations(id),
  created_at TEXT NOT NULL,
  UNIQUE (course_id, url)
);

-- Search results the source filter skipped because the charter doesn't mention their kind
-- (SPEC §3.7 charter gaps). One row per URL; no user or question, on purpose.
CREATE TABLE IF NOT EXISTS charter_gaps (
  id INTEGER PRIMARY KEY,
  course_id INTEGER NOT NULL REFERENCES course(id),
  kind TEXT NOT NULL,          -- the filter's label, e.g. "journal articles"
  url TEXT NOT NULL,
  title TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  dismissed INTEGER NOT NULL DEFAULT 0,
  UNIQUE (course_id, url)
);

-- Every paid call that wasn't served from the cache (SPEC §9.1). Kept by seed.py --reset,
-- so reseeding never resets a budget.
CREATE TABLE IF NOT EXISTS spend (
  id INTEGER PRIMARY KEY,
  at TEXT NOT NULL,
  service TEXT NOT NULL CHECK (service IN ('ai','search')),
  units INTEGER NOT NULL,      -- tokens (in + out) for 'ai', searches for 'search'
  usd REAL NOT NULL,
  device_id TEXT NOT NULL,     -- X-Device-Id, or 'unknown'
  question_id INTEGER          -- the Ask it was for: the per-device limit counts distinct Asks
);

CREATE TABLE IF NOT EXISTS web_cache (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  created_at TEXT NOT NULL
);

-- Full-text search. External-content tables: the FTS index points at rows in
-- the real table, and these triggers keep the index in step with it.
CREATE VIRTUAL TABLE IF NOT EXISTS annotations_fts USING fts5(quote, body, content='annotations', content_rowid='id');
CREATE VIRTUAL TABLE IF NOT EXISTS sources_fts USING fts5(title, excerpt, content='sources', content_rowid='id');
CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(text, reading_id UNINDEXED, page UNINDEXED);

CREATE TRIGGER IF NOT EXISTS annotations_ai AFTER INSERT ON annotations BEGIN
  INSERT INTO annotations_fts(rowid, quote, body) VALUES (new.id, new.quote, new.body);
END;
CREATE TRIGGER IF NOT EXISTS annotations_ad AFTER DELETE ON annotations BEGIN
  INSERT INTO annotations_fts(annotations_fts, rowid, quote, body) VALUES ('delete', old.id, old.quote, old.body);
END;
CREATE TRIGGER IF NOT EXISTS sources_ai AFTER INSERT ON sources BEGIN
  INSERT INTO sources_fts(rowid, title, excerpt) VALUES (new.id, new.title, new.excerpt);
END;
CREATE TRIGGER IF NOT EXISTS sources_ad AFTER DELETE ON sources BEGIN
  INSERT INTO sources_fts(sources_fts, rowid, title, excerpt) VALUES ('delete', old.id, old.title, old.excerpt);
END;
"""

# Words too common to help a keyword search.
STOPWORDS = set("""
a about above after again against all am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have
having he her here hers herself him himself his how i if in into is it its itself just me more most my
myself no nor not now of off on once only or other our ours ourselves out over own same she should so
some such than that the their theirs them themselves then there these they this those through to too
under until up very was we were what when where which while who whom why will with would you your
yours yourself yourselves mean means meant idea come comes
""".split())


def now():
    return datetime.now().isoformat(timespec="seconds")


def connect():
    # FastAPI may open a request's connection (get_conn) on one worker thread and use or
    # close it on another; each request still has its own connection, so that's safe.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Many people writing at once (SPEC §9): WAL lets reads continue during a write, and
    # busy_timeout makes a writer wait up to 5 s for another instead of failing "database is locked".
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_schema(conn):
    conn.executescript(SCHEMA)


def fts_query(text):
    """Turn free text into an FTS5 query: keywords, each quoted, joined with OR.

    Returns None when no keywords are left (the caller should skip the search).
    """
    words = re.findall(r"[a-z0-9]+", text.lower())
    keywords = []
    for w in words:
        if w not in STOPWORDS and len(w) > 2 and w not in keywords:
            keywords.append(w)
    if not keywords:
        return None
    return " OR ".join(f'"{w}"' for w in keywords)


# The visibility rule (SPEC §3.4), as SQL over `annotations a JOIN users u ON u.id = a.user_id`.
# You see an annotation if it's from your cohort, or its author is the professor or the AI,
# or it's from a past cohort, shared with future classes, and the charter shows past cohorts.
VISIBLE_SQL = """(
  u.cohort = :viewer_cohort
  OR u.role IN ('professor', 'ai')
  OR (a.share_with_future = 1 AND :show_past = 1)
)"""


def visibility_params(conn, user):
    # Readings are per course and you only see your own course's, so your course's charter decides.
    show_past = conn.execute("SELECT show_past_cohorts FROM charter WHERE course_id = ?",
                             (user["course_id"],)).fetchone()[0]
    return {"viewer_cohort": user["cohort"], "show_past": show_past}


def insert_annotation(conn, reading_id, user_id, kind, page, quote, rects_json, body,
                      parent_id=None, share_with_future=True, cited_source_ids=None,
                      section_id=None, via="web", source_app=None):
    cur = conn.execute(
        """INSERT INTO annotations (reading_id, user_id, parent_id, kind, page, section_id, via, source_app, quote,
                                    rects_json, body, cited_source_ids, share_with_future, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (reading_id, user_id, parent_id, kind, page, section_id, via, source_app, quote, rects_json, body,
         json.dumps(cited_source_ids) if cited_source_ids is not None else None,
         int(share_with_future), now()),
    )
    return cur.lastrowid


# ---------- the engagement lock (SPEC §3.4) ----------

def vertical_extent(rects):
    """(top, bottom) of a highlight's rects as page fractions, or None if it has none."""
    if not rects:
        return None
    return min(r["y"] for r in rects), max(r["y"] + r["h"] for r in rects)


def is_near(page_a, extent_a, page_b, extent_b):
    if page_a != page_b or extent_a is None or extent_b is None:
        return False
    gap = max(extent_a[0], extent_b[0]) - min(extent_a[1], extent_b[1])  # negative if they overlap
    return gap <= NEAR_DISTANCE


def locked_groups(locked):
    """Cluster locked top-level annotations that sit near each other, for one lock card each.

    locked: [{"id", "page", "rects"}]. Returns {id: {"group", "group_notes"
    }}, where group is the smallest id in the cluster and group_notes its size ("2 notes near here").
    Deliberately no author information, not even a count of people.
    """
    group_of = {a["id"]: a["id"] for a in locked}

    def root(i):
        while group_of[i] != i:
            i = group_of[i]
        return i
    extents = {a["id"]: vertical_extent(a["rects"]) for a in locked}
    for a in locked:
        for b in locked:
            if a["id"] < b["id"] and is_near(a["page"], extents[a["id"]], b["page"], extents[b["id"]]):
                ra, rb = root(a["id"]), root(b["id"])
                group_of[max(ra, rb)] = min(ra, rb)
    members = {}
    for a in locked:
        members.setdefault(root(a["id"]), []).append(a)
    out = {}
    for group, items in members.items():
        for a in items:
            out[a["id"]] = {"group": group, "group_notes": len(items)}
    return out


def full_view_ids(conn, user, reading_id):
    """Ids of the annotations on this reading that `user` sees in full; every other visible one is locked.

    In full: the professor's, your own, ones near a note or question of yours, and replies or AI
    answers under one of those. With the charter's annotate_before_peers off, or for the professor
    (SPEC §3.4: the lock never applies to them), everything visible.
    """
    rows = conn.execute(
        f"""SELECT a.id, a.parent_id, a.user_id, a.page, a.rects_json, u.role
            FROM annotations a JOIN users u ON u.id = a.user_id
            WHERE a.reading_id = :reading_id AND {VISIBLE_SQL}""",
        {"reading_id": reading_id, **visibility_params(conn, user)},
    ).fetchall()
    lock_on = conn.execute("SELECT annotate_before_peers FROM charter WHERE course_id = ?",
                           (user["course_id"],)).fetchone()[0]
    if not lock_on or user["role"] == "professor":
        return {r["id"] for r in rows}

    # Where you've engaged: your own top-level notes and questions (they carry the highlight).
    engaged = [
        (r["page"], vertical_extent(json.loads(r["rects_json"]) if r["rects_json"] else None))
        for r in rows
        if r["user_id"] == user["id"] and r["parent_id"] is None
    ]
    by_id = {r["id"]: r for r in rows}

    def top_level_of(row):
        while row["parent_id"] is not None and row["parent_id"] in by_id:
            row = by_id[row["parent_id"]]
        return row

    def top_level_unlocked(row):
        if row["role"] == "professor" or row["user_id"] == user["id"]:
            return True
        extent = vertical_extent(json.loads(row["rects_json"]) if row["rects_json"] else None)
        return any(is_near(page, mine, row["page"], extent) for page, mine in engaged)

    full = set()
    for r in rows:
        if r["user_id"] == user["id"] or top_level_unlocked(top_level_of(r)):
            full.add(r["id"])
    return full
