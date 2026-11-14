"""SQLite connection, schema and full-text-search helpers (SPEC §5)."""
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "dialectic.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('professor','student','ai')),
  cohort TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS course (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  current_cohort TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS charter (
  id INTEGER PRIMARY KEY,
  text_md TEXT NOT NULL,
  permissible_sources TEXT NOT NULL,
  ai_enabled INTEGER NOT NULL DEFAULT 1,
  ai_find_sources INTEGER NOT NULL DEFAULT 1,
  ai_explanations INTEGER NOT NULL DEFAULT 1,
  max_explanation_words INTEGER NOT NULL DEFAULT 120,
  show_past_cohorts INTEGER NOT NULL DEFAULT 1,
  annotate_before_peers INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS charter_comments (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  body TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS readings (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  pdf_path TEXT NOT NULL,
  uploaded_by INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reading_pages (
  reading_id INTEGER NOT NULL REFERENCES readings(id),
  page INTEGER NOT NULL,
  text TEXT NOT NULL,
  PRIMARY KEY (reading_id, page)
);

CREATE TABLE IF NOT EXISTS annotations (
  id INTEGER PRIMARY KEY,
  reading_id INTEGER NOT NULL REFERENCES readings(id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  parent_id INTEGER REFERENCES annotations(id),
  kind TEXT NOT NULL CHECK (kind IN ('note','question','ai_answer')),
  page INTEGER NOT NULL,
  quote TEXT,
  rects_json TEXT,
  body TEXT NOT NULL,
  cited_source_ids TEXT,
  share_with_future INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  excerpt TEXT NOT NULL,
  found_by TEXT NOT NULL CHECK (found_by IN ('ai','professor')),
  first_question_id INTEGER REFERENCES annotations(id),
  created_at TEXT NOT NULL
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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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
    show_past = conn.execute("SELECT show_past_cohorts FROM charter").fetchone()[0]
    return {"viewer_cohort": user["cohort"], "show_past": show_past}


def insert_annotation(conn, reading_id, user_id, kind, page, quote, rects_json, body,
                      parent_id=None, share_with_future=True, cited_source_ids=None):
    cur = conn.execute(
        """INSERT INTO annotations (reading_id, user_id, parent_id, kind, page, quote, rects_json, body,
                                    cited_source_ids, share_with_future, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (reading_id, user_id, parent_id, kind, page, quote, rects_json, body,
         json.dumps(cited_source_ids) if cited_source_ids is not None else None,
         int(share_with_future), now()),
    )
    return cur.lastrowid
