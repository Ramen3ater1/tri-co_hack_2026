"""DEMO: Asks that were already answered, so Ask history, the source library and the charter's
"skipped sources" panel aren't empty in either course.

They were real Asks, run once (Sat 14 Nov) with
    uv run --env-file ../../.env seed_asks.py --generate   # after seed.py --reset; costs a few cents
which saved what they produced to seed/asks.json. seed.py --reset replays that file with no
network: the question, the AI's reply, the sources, the skipped results and the saved answer card.
The answer card's peer notes are found again by (author, body), so if you edit a seeded note that
an Ask quoted, seeding fails loudly: run --generate again (or fix the body in asks.json).
"""
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import db
import locate
import sections

ASKS_PATH = Path(__file__).parent / "seed" / "asks.json"

# DEMO: (course title prefix, reading title prefix, asker, page, exact quote, question, days ago).
ASKS = [
    ("PHIL 247", "Week 1", "Ana", 3, "the savage people in many parts of America have no government at all",
     "What did Europeans in 1651 actually know about how Indigenous American societies were governed?", 12),
    ("PHIL 247", "Week 1", "Leah", 2, "it is a war of every man against every man",
     "What was happening in England while Hobbes was writing Leviathan?", 11),
    ("PHIL 101", "Week 1", "Kemi", 3, "the judicious Hooker",
     "Who was Richard Hooker, and why would Locke quote him here?", 13),
    ("PHIL 101", "Week 2", "Caleb", 7, "His usual method of reasoning is to establish right by fact",
     "Who was Grotius, and why does Rousseau keep arguing with him?", 5),
    ("PHIL 101", "Week 2", "Jordan", 8, "The Greeks imprisoned in the cave of the Cyclops",
     "What happens in the Cyclops episode of the Odyssey?", 4),
    ("PHIL 101", "Week 2", "Priya", 14, "each individual will be forced to be free",
     "What does Rousseau mean by being forced to be free?", 2),
]


def find_reading(conn, course_prefix, reading_prefix):
    return conn.execute(
        """SELECT r.* FROM readings r JOIN course c ON c.id = r.course_id
           WHERE c.title LIKE ? AND r.title LIKE ?""", (course_prefix + "%", reading_prefix + "%")).fetchone()


def find_user(conn, course_id, name):
    return conn.execute("SELECT * FROM users WHERE course_id = ? AND name = ?", (course_id, name)).fetchone()


def when(days):
    return (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")


# ---------- generate (once, online)

def note_ref(conn, annotation_id):
    row = conn.execute("""SELECT u.name, a.body FROM annotations a JOIN users u ON u.id = a.user_id
                          WHERE a.id = ?""", (annotation_id,)).fetchone()
    return {"author": row["name"], "body": row["body"]}


def peer_ref(conn, peer):
    """How replay finds a peer note (and the note it replies to, if any) again: by author and body."""
    ref = note_ref(conn, peer["annotation_id"])
    ref["parent"] = note_ref(conn, peer["parent_id"]) if peer.get("parent_id") else None
    return ref


def generate():
    import ask
    conn = db.connect()
    out = {"asks": [], "sources": [], "charter_gaps": []}
    for course_prefix, reading_prefix, asker, page, quote, question, days in ASKS:
        reading = find_reading(conn, course_prefix, reading_prefix)
        user = find_user(conn, reading["course_id"], asker)
        rects = locate.quote_rects(reading["pdf_path"], page, quote)
        print(f"Asking as {asker}: {question}", flush=True)
        result = ask.answer(conn, reading, user, page, quote, rects, question)
        conn.commit()
        peers = [peer_ref(conn, peer) for peer in result["peer"]]
        sources = {s["id"]: s["url"] for s in conn.execute("SELECT id, url FROM sources")}
        cited = []
        if result["ai_answer"]:
            row = conn.execute("SELECT cited_source_ids FROM annotations WHERE id = ?",
                               (result["ai_answer"]["annotation_id"],)).fetchone()
            cited = [sources[i] for i in json.loads(row["cited_source_ids"] or "[]")]
        out["asks"].append({"ask": [course_prefix, reading_prefix, asker, page, quote, question, days],
                            "result": result, "peers": peers, "cited_urls": cited,
                            "source_urls": [sources[s["source_id"]] for s in result["sources"]]})
        print(f"  {len(result['peer'])} peers, {len(result['sources'])} sources, "
              f"AI: {'yes' if result['ai_answer'] else 'no'}, blocked: {[b['layer'] for b in result['blocked']]}")
    for s in conn.execute("""SELECT c.title course, s.title, s.url, s.excerpt, s.found_by FROM sources s
                             JOIN course c ON c.id = s.course_id ORDER BY s.id"""):
        out["sources"].append(dict(s))
    for g in conn.execute("""SELECT c.title course, g.kind, g.url, g.title FROM charter_gaps g
                             JOIN course c ON c.id = g.course_id ORDER BY g.id"""):
        out["charter_gaps"].append(dict(g))
    ASKS_PATH.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"Wrote {ASKS_PATH}")


# ---------- replay (every seed.py --reset, offline)

def find_note(conn, reading_id, ref):
    row = conn.execute(
        """SELECT a.id FROM annotations a JOIN users u ON u.id = a.user_id
           WHERE a.reading_id = ? AND u.name = ? AND a.body = ?""",
        (reading_id, ref["author"], ref["body"])).fetchone()
    assert row, f"seed_asks: the note by {ref['author']} quoted in an Ask is gone: {ref['body'][:60]!r}"
    return row["id"]


def add_asks(conn):
    data = json.loads(ASKS_PATH.read_text())
    course_ids = {r["title"]: r["id"] for r in conn.execute("SELECT id, title FROM course")}
    source_ids = {}
    for s in data["sources"]:
        source_ids[s["url"]] = conn.execute(
            "INSERT INTO sources (course_id, title, url, excerpt, found_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (course_ids[s["course"]], s["title"], s["url"], s["excerpt"], s["found_by"], db.now())).lastrowid
    ai_user_id = conn.execute("SELECT id FROM users WHERE role = 'ai'").fetchone()["id"]

    for entry in data["asks"]:
        course_prefix, reading_prefix, asker, page, quote, question, days = entry["ask"]
        reading = find_reading(conn, course_prefix, reading_prefix)
        user = find_user(conn, reading["course_id"], asker)
        rects = locate.quote_rects(reading["pdf_path"], page, quote)
        section = sections.section_for(conn, reading["id"], page, quote)
        section_id = section["id"] if section else None
        question_id = db.insert_annotation(conn, reading["id"], user["id"], "question", page, quote,
                                           json.dumps(rects), question, section_id=section_id)
        conn.execute("UPDATE annotations SET created_at = ? WHERE id = ?", (when(days), question_id))
        conn.execute("UPDATE sources SET first_question_id = ?, created_at = ? WHERE id IN (%s) AND first_question_id IS NULL"
                     % ",".join("?" * len(entry["source_urls"])),
                     (question_id, when(days), *[source_ids[u] for u in entry["source_urls"]]))

        result = entry["result"]
        result["question_id"] = question_id
        for peer, ref in zip(result["peer"], entry["peers"]):
            peer["annotation_id"] = find_note(conn, reading["id"], ref)
            if ref["parent"]:
                peer["parent_id"] = find_note(conn, reading["id"], ref["parent"])
        for source, url in zip(result["sources"], entry["source_urls"]):
            source["source_id"] = source_ids[url]
        if result["ai_answer"]:
            answer_id = db.insert_annotation(
                conn, reading["id"], ai_user_id, "ai_answer", page, None, None, result["ai_answer"]["body"],
                parent_id=question_id, cited_source_ids=[source_ids[u] for u in entry["cited_urls"]],
                section_id=section_id)
            conn.execute("UPDATE annotations SET created_at = ? WHERE id = ?", (when(days - 0.001), answer_id))
            result["ai_answer"]["annotation_id"] = answer_id
        conn.execute("UPDATE annotations SET answer_json = ? WHERE id = ?", (json.dumps(result), question_id))

    for g in data["charter_gaps"]:
        conn.execute(
            """INSERT INTO charter_gaps (course_id, kind, url, title, last_seen) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (course_id, url) DO NOTHING""",
            (course_ids[g["course"]], g["kind"], g["url"], g["title"], db.now()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true", required=True,
                        help="run the ASKS for real on the current database and save seed/asks.json")
    parser.parse_args()
    generate()
