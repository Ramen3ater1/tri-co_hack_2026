"""DEMO seed data (SPEC §10): two philosophy courses, both reading Rousseau's Social Contract.

    uv run seed.py --reset                 # starting state of demo step 1 (Rousseau not uploaded yet)
    uv run seed.py --reset --with-reading  # also add Rousseau, as if Prof. Rivera uploaded it
    uv run seed.py --reset --with-sources  # also preload the source library

PHIL 247 (this file) is the small seminar the demo runs in. It's week 2: last week's Hobbes is
well annotated, next week's Wollstonecraft is up with no notes yet, and this week's Rousseau is
uploaded live in demo step 1. Every reset also adds PHIL 101, the big lecture (seed_large.py),
with Locke (crowded), Rousseau (very crowded) and Mill (barely started).

The PDFs in seed/ are of two kinds on purpose:
  - born-digital, clean text: Rousseau and Hobbes (Jonathan Bennett's versions, earlymoderntexts.com)
  - real scans of old books, OCR'd by our own pipeline (ocr.py): Wollstonecraft (1891 edition,
    a clean scan), Locke (Digital Library of India, rough) and Mill (an 1859 xerox with a previous
    reader's underlining, very rough). Quotes on scans are as their OCR reads them.

The seeded Rousseau notes belong to the reading uploaded live, so `POST /readings` calls
add_demo_annotations() when the uploaded file is DEMO_PDF_NAME in this course.
The previous Du Bois seed is kept, runnable, in seed_dubois.py.
"""
import argparse
import json
import shutil
from pathlib import Path

import db
import locate
import sections
import seed_asks
import seed_large
from seed_notes import Rota, add_charter_comments, add_notes, add_reading, days_ago, stamp

BACKEND_DIR = Path(__file__).parent
UPLOADS_DIR = BACKEND_DIR / "uploads"
SEED_DIR = BACKEND_DIR / "seed"
DEMO_PDF_NAME = "rousseau-social-contract.pdf"
DEMO_PDF_PATH = SEED_DIR / DEMO_PDF_NAME
DEMO_READING_TITLE = "Week 2 · Rousseau, The Social Contract"

COURSE_TITLE = "PHIL 247: The Social Contract (seminar)"
CURRENT_COHORT = "Fall 2026"
PAST_COHORT = "Spring 2026"

# (name, role, cohort), all in PHIL 247 (course 1). The first four are the demo cast and come
# first in the log-in list: Ana writes a lot, Ben is the one who has to engage to see notes on
# Rousseau, Sam is last year's student whose notes are opted in.
USERS = [
    ("Prof. Rivera", "professor", CURRENT_COHORT),
    ("Ana", "student", CURRENT_COHORT),
    ("Ben", "student", CURRENT_COHORT),
    ("Sam", "student", PAST_COHORT),
    ("Chidi", "student", CURRENT_COHORT),
    ("Leah", "student", CURRENT_COHORT),
    ("Marco", "student", CURRENT_COHORT),
    ("Nora", "student", CURRENT_COHORT),
    ("Tariq", "student", CURRENT_COHORT),
    ("Yuki", "student", CURRENT_COHORT),
    ("Theo", "student", PAST_COHORT),
]
# Who writes the "None" notes below, in turn.
ROTA_CURRENT = ["Chidi", "Leah", "Marco", "Nora", "Tariq", "Yuki"]
ROTA_PAST = ["Sam", "Theo"]
# The AI serves every course, so it has none.
AI_USER_NAME = "Dialectic AI"

# Rule 2 is what the gate quotes in demo step 4: keep its wording. Rule 5 came from Ana's proposal.
CHARTER_TEXT = """1. We read first and ask each other second. AI comes last.
2. AI may point us to sources and give historical context. It may not interpret the text for us or suggest thesis statements.
3. Anything AI writes is public to the class and labelled as AI.
4. Annotations are shared with future classes unless you untick the box.
5. Quote the translation we read (Bennett's) when you annotate, and say so if you're working from the French."""

PERMISSIBLE_SOURCES = (
    "Scholarly encyclopedias (Stanford Encyclopedia of Philosophy, Internet Encyclopedia of Philosophy, "
    "Britannica), peer-reviewed scholarship (journal articles, university-press books), university and "
    "museum sites, and primary texts from 1600–1800 (Hobbes, Locke, Grotius, Rousseau's other works). "
    "No study-guide or essay-mill sites (SparkNotes, Course Hero, etc.). Wikipedia is fine for dates "
    "and names, not for interpretation."
)

# DEMO: charter proposals in every state. (who, body, status)
CHARTER_COMMENTS = [
    ("Ana", "Can we add a rule to quote Bennett's translation? Half of us have the Penguin (Cranston) and the "
            "wording doesn't line up, so our notes look like they disagree when they don't.", "added"),
    ("Leah", "Propose allowing SparkNotes, only for summaries of the Odyssey and Bible stories Rousseau "
             "mentions in passing.", "declined"),
    ("Chidi", "Could AI be allowed to point out objections to our own notes (not to the text)? "
              "Like a sparring partner after we've written something.", "open"),
]

# DEMO: Rousseau, sparse on purpose: added when the reading is uploaded (live in demo step 1).
# (author, page, exact quote from the PDF, body).
DEMO_ANNOTATIONS = [
    ("Prof. Rivera", 6, "Man is born free, and everywhere he is in chains.",
     "The most famous first line in political philosophy. Notice he says right away he can't explain how "
     "the change happened, only what could make it legitimate. Keep those two questions apart."),
    ("Prof. Rivera", 7, "His usual method of reasoning is to establish right by fact",
     "Hugo Grotius, Dutch jurist, author of The Rights of War and Peace (1625). He's Rousseau's main "
     "opponent in Book 1; count how often he's named."),
    ("Prof. Rivera", 8, "The Greeks imprisoned in the cave of the Cyclops",
     "Odyssey, Book 9: Polyphemus keeps Odysseus's men in his cave and eats them two at a time. "
     "Rousseau expects you to know the story."),
    ("Sam", 12, "Each of us puts his person and all his power in common under the supreme direction of the general will",
     "Last spring we spent a whole seminar on this sentence. You give everything to everyone, so you give "
     "yourself to no one in particular (see (iii) just above)."),
    ("Sam", 14, "each individual will be forced to be free",
     "The line everyone quotes against him. Read the sentence after it before deciding what you think."),
    ("Theo", 19, "The will of all is very different from the general will",
     "Will of all = add up what everyone privately wants. General will = what we want as members of the "
     "whole. Our group drew this as a diagram with the pluses and minuses cancelling."),
]

# Week 1, Hobbes: well annotated, mostly by Ana and the rota, two weeks ago.
HOBBES_PDF = SEED_DIR / "hobbes-leviathan-ch13-14.pdf"
HOBBES_TITLE = "Week 1 · Hobbes, Leviathan ch. 13–14"
HOBBES_NOTES = [
    (1, "Nature has made men so equal in their physical and mental capacities", "note", "Prof. Rivera",
     "Start here: Hobbes's argument for war begins from equality, not from people being wicked.", []),
    (1, "the weakest man is strong enough to kill the strongest", "note", "Ana",
     "Equality as equal vulnerability. Nobody is safe, so nobody can rule by strength alone.", [
         ("Ben", "Which is exactly what Rousseau picks on next week ('the strongest is never strong enough')."),
     ]),
    (1, "for he sees his own wisdom close up, and other men’s at a distance", "note", None,
     "This is the funniest line in the chapter.", []),
    (1, "there is no greater sign that something is equally distributed than that every man is contented with his share",
     "note", "Ana", "He's joking, but it's also an argument: everyone thinks they got enough wisdom.", []),
    (2, "the most reasonable way for any man to make himself safe is to strike first", "note", None,
     "Pre-emption is rational for each person and a disaster for everyone. Prisoner's dilemma before game theory.", [
         ("Ana", "And the people who conquer for fun make it worse for the modest ones (next sentence)."),
     ]),
    (2, "three principal causes of discord", "note", "Ana",
     "Competition (gain), distrust (safety), glory (reputation). I'm making a table of these for the paper.", []),
    (2, "the third use it for trifles—a word, a smile, a different opinion", "note", None,
     "Glory is the one that feels most modern. Wars over a smile.", []),
    (2, "it is a war of every man against every man", "note", "Ben",
     "Does he mean actual fighting all the time?", [
         ("Ana", "No, see the weather comparison right after: it's the disposition to fight."),
         ("Prof. Rivera", "Right. 'War' is a climate, not a storm. That matters for Locke and Rousseau too."),
     ]),
    (2, "what constitutes bad weather is not a rain-shower or two but an inclination to rain through many days together",
     "note", None, "Best analogy in the reading.", []),
    (3, "solitary, poor, nasty, brutish, and short", "note", "past",
     "Everyone knows the five words; almost nobody knows the list of what's missing before them "
     "(no industry, no navigation, no letters, no society).", []),
    (3, "solitary, poor, nasty, brutish, and short", "question", None,
     "Is 'solitary' meant literally? People in his state of nature still seem to have families.", [
         ("Ana", "He mentions 'small families' on this same page, so probably solitary as in no wider society."),
     ]),
    (3, "when going to sleep, you lock your doors", "note", "Ana",
     "The appeal to experience: you already act as if he's right.", []),
    (3, "the savage people in many parts of America have no government at all", "note", "Prof. Rivera",
     "This is a European claim about Indigenous peoples, and a false one. Worth asking what the argument "
     "needs it for and whether it survives without it.", [
         (None, "It seems like he only needs it as an example, since the next paragraphs use civil war and kings instead."),
     ]),
    (3, "Like gladiators, with their weapons pointing", "note", None,
     "International relations is still the state of nature for Hobbes. Realists in IR still cite this.", []),
    (3, "Where there is no common power, there is no law; and where there is no law, there is no injustice.",
     "note", "Ana", "So justice is created by the sovereign. Huge claim. Compare Locke, where the law of nature "
     "binds before any government.", []),
    (3, "In war the two chief virtues are force and fraud.", "note", "past",
     "Our class read this next to Machiavelli.", []),
    (4, "The passions that incline men to peace are fear of death", "note", None,
     "Fear gets us into war (distrust) and out of it. Same passion, different object.", []),
    (4, "The proper meaning of LIBERTY is the absence of external obstacles.", "note", "Ana",
     "Negative liberty. Rousseau's 'moral liberty' is going to be the opposite of this.", [
         ("Ben", "Bookmarking this for the Rousseau week."),
     ]),
    (4, "every man has a right to everything—even to someone else’s body", "note", None,
     "A right to everything is a right to nothing you can count on.", []),
    (5, "Seek peace and follow it.", "note", None, "The first law, and it's four words.", []),
    (5, "he should be willing (when others are too) to lay down his right to everything", "note", "Ana",
     "'When others are too' is doing all the work. The contract only makes sense if it's mutual.", []),
]

# Week 3, Wollstonecraft: uploaded early, nobody has opened it yet. A good 1891 scan.
WOLLSTONECRAFT_PDF = SEED_DIR / "wollstonecraft-vindication-ch5.pdf"
WOLLSTONECRAFT_TITLE = "Week 3 · Wollstonecraft, A Vindication of the Rights of Woman, ch. V (on Rousseau)"

# DEMO: preloaded by --with-sources, the fallback if web search fails on stage (SPEC §10).
# Fetched through search.fetch_page, so after one online run they come from web_cache.
DEMO_SOURCES = [
    "https://plato.stanford.edu/entries/rousseau/",
    "https://en.wikipedia.org/wiki/General_will",
]


DEMO_COURSE_ID = 1  # PHIL 247 is inserted first


def user_id(conn, name):
    # PHIL 247's people only: names can repeat across courses.
    return conn.execute("SELECT id FROM users WHERE name = ? AND course_id = ?", (name, DEMO_COURSE_ID)).fetchone()["id"]


def add_demo_annotations(conn, reading_id, pdf_path):
    for author, page, quote, body in DEMO_ANNOTATIONS:
        rects = locate.quote_rects(pdf_path, page, quote)
        section = sections.section_for(conn, reading_id, page, quote)
        db.insert_annotation(conn, reading_id, user_id(conn, author), "note", page, quote, json.dumps(rects), body,
                             section_id=section["id"] if section else None)


def add_demo_reading(conn):
    """Do what the live upload does, for when the upload fails on stage."""
    import main  # here, not at the top: main imports this module
    UPLOADS_DIR.mkdir(exist_ok=True)
    dest = UPLOADS_DIR / DEMO_PDF_NAME
    shutil.copy(DEMO_PDF_PATH, dest)
    reading_id = main.create_reading(conn, DEMO_COURSE_ID, DEMO_READING_TITLE, dest, user_id(conn, "Prof. Rivera"))
    add_demo_annotations(conn, reading_id, dest)


def add_demo_sources(conn):
    import search
    for url in DEMO_SOURCES:
        page = search.fetch_page(conn, url)
        conn.execute(
            "INSERT INTO sources (course_id, title, url, excerpt, found_by, created_at) VALUES (?, ?, ?, ?, 'professor', ?)",
            (DEMO_COURSE_ID, page["title"], url, page["text"], db.now()),
        )


def add_course(conn):
    """PHIL 247 without this week's reading: people, charter, proposals, Hobbes, Wollstonecraft."""
    course_id = conn.execute("INSERT INTO course (title, current_cohort) VALUES (?, ?)",
                             (COURSE_TITLE, CURRENT_COHORT)).lastrowid
    assert course_id == DEMO_COURSE_ID
    conn.executemany("INSERT INTO users (name, role, cohort, course_id) VALUES (?, ?, ?, ?)",
                     [(*u, DEMO_COURSE_ID) for u in USERS])
    conn.execute(
        "INSERT INTO charter (course_id, text_md, permissible_sources, updated_at) VALUES (?, ?, ?, ?)",
        (DEMO_COURSE_ID, CHARTER_TEXT, PERMISSIBLE_SOURCES, db.now()),
    )
    ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM users WHERE course_id = ?", (course_id,))}
    add_charter_comments(conn, course_id, ids, CHARTER_COMMENTS, days_ago(20), days_ago(6))

    prof = ids["Prof. Rivera"]
    hobbes_id, hobbes_pdf = add_reading(conn, course_id, HOBBES_TITLE, HOBBES_PDF, UPLOADS_DIR, prof, days_ago(16))
    add_notes(conn, hobbes_id, hobbes_pdf, HOBBES_NOTES, Rota(ids, ROTA_CURRENT, ROTA_PAST), days_ago(15), days_ago(9))
    add_reading(conn, course_id, WOLLSTONECRAFT_TITLE, WOLLSTONECRAFT_PDF, UPLOADS_DIR, prof, days_ago(2))
    return course_id


def reset(with_reading, with_sources):
    # Keep web_cache across resets (SPEC §9), so the demo replays cached web results,
    # and spend (SPEC §9.1), so reseeding never resets a budget.
    cache = []
    spent = []
    if db.DB_PATH.exists():
        old = db.connect()
        cache = old.execute("SELECT key, value, created_at FROM web_cache").fetchall()
        has_spend = old.execute("SELECT 1 FROM sqlite_master WHERE name = 'spend'").fetchone()
        if has_spend:  # databases from before the spend table don't have one
            spent = old.execute("SELECT at, service, units, usd, device_id FROM spend").fetchall()
        old.close()
        db.DB_PATH.unlink()
    # WAL mode keeps two side files; a stale one would be replayed into the new database.
    for suffix in ("-wal", "-shm"):
        side_file = db.DB_PATH.with_name(db.DB_PATH.name + suffix)
        if side_file.exists():
            side_file.unlink()
    if UPLOADS_DIR.exists():
        shutil.rmtree(UPLOADS_DIR)

    conn = db.connect()
    db.init_schema(conn)
    conn.executemany("INSERT INTO web_cache VALUES (?, ?, ?)", [tuple(r) for r in cache])
    # question_id isn't kept: the questions are gone. The device-hour count restarts; budgets don't.
    conn.executemany("INSERT INTO spend (at, service, units, usd, device_id) VALUES (?, ?, ?, ?, ?)",
                     [tuple(r) for r in spent])
    add_course(conn)
    conn.execute("INSERT INTO users (name, role, cohort) VALUES (?, 'ai', ?)", (AI_USER_NAME, CURRENT_COHORT))
    seed_large.add_course(conn, UPLOADS_DIR)
    seed_asks.add_asks(conn)
    if with_reading:
        add_demo_reading(conn)
    if with_sources:
        add_demo_sources(conn)
    conn.commit()
    conn.close()
    print(f"Seeded {db.DB_PATH} (kept {len(cache)} web_cache rows and {len(spent)} spend rows)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", required=True, help="delete the DB and uploads, then seed")
    parser.add_argument("--with-reading", action="store_true", help="also add the demo reading and its annotations")
    parser.add_argument("--with-sources", action="store_true", help="also preload the source library (web search fallback)")
    args = parser.parse_args()
    reset(args.with_reading, args.with_sources)
