"""DEMO: a large lecture course on the same chapter, to show Dialectic with a crowded margin.

seed.py --reset adds it every time (it's mid-semester, so its reading is already uploaded and
annotated). Log in as Maya: she hasn't written anything yet, so the margin is all lock cards
("21 notes near here"); add a note on the double-consciousness passage and they open.
"""
import json
import shutil
from datetime import datetime, timedelta

import db
import locate
import sections

COURSE_TITLE = "AMST 101: Introduction to American Studies (lecture)"
CURRENT_COHORT = "Fall 2026"
PAST_COHORT = "Spring 2026"
PROFESSOR = "Prof. Okafor"
READING_TITLE = "The Souls of Black Folk, Ch. 1: Of Our Spiritual Strivings"
PDF_NAME = "amst101-souls-of-black-folk-ch1.pdf"  # its own copy, so it never triggers the HIST 214 upload hook

# Maya and Jordan are the ones to log in as: Maya has written nothing (sees lock cards everywhere),
# Jordan wrote a handful of notes. They come first in the log-in list.
FEATURED_STUDENTS = ["Maya", "Jordan"]

# The other current students. Names are only labels; they write the notes below in turn.
CLASSMATES = """
Aaliyah Abdul Adrian Aiden Amara Andre Ari Asha Ava Bea Caleb Camila Chloe Daniel Darius Destiny
Diego Elena Eli Emeka Esme Ethan Fatima Gabe Grace Hana Imani Isaac Jada Jalen Jasmine Kai Kemi Kenji
Lena Liam Lucia Malik Marcus Mateo Mei Naomi Nia Noah Olivia Omar Priya Quinn Rafael Riya Rosa Ruth
Sana Simone Talia Theo Tomas Uma Victor Wren Yusuf Zara Zoe
""".split()

# Last year's lecture: their notes show with a "Spring 2026" badge.
PAST_STUDENTS = ["Devon", "Harper", "Ines", "Jonah", "Kiara", "Luca", "Mira", "Nadia"]

CHARTER_TEXT = """1. Read the chapter first, then ask the class. AI comes last.
2. AI may find sources and give historical background. It may not tell us what the text means or write our response papers.
3. Anything AI writes is public to the class and labelled as AI.
4. There are a lot of us: reply to a thread on a passage before starting a new one on the same line.
5. Annotations are shared with future classes unless you untick the box."""

PERMISSIBLE_SOURCES = (
    "Scholarly encyclopedias (Stanford Encyclopedia of Philosophy, Britannica), peer-reviewed "
    "scholarship, university and museum sites, and primary sources from 1880–1920. "
    "No study-guide or essay-mill sites. Wikipedia only for dates and names."
)
MAX_EXPLANATION_WORDS = 100

# DEMO: the margin. (page, exact quote from the PDF, kind, author, body, [replies as (author, body)]).
# author None = the next classmate in turn; "past" = the next past student; else a name.
# Quotes must match the PDF text (letters only are compared) or seeding fails loudly.
NOTES = [
    # ---- page 1: the unasked question
    (1, "O water, voice of my heart, crying in the sand", "note", PROFESSOR,
     "Every chapter opens with two epigraphs: a European poem and a bar of a Sorrow Song. Watch the pairing all term.", []),
    (1, "O water, voice of my heart, crying in the sand", "note", None,
     "The poem never resolves - 'is it I, is it I?' - which sets up the chapter's question about identity.", []),
    (1, "there is ever an unasked question", "note", None,
     "Opening on what nobody says out loud. Very different from opening on a thesis.", [
         (None, "And he makes us, the readers, part of the 'other world' asking it."),
     ]),
    (1, "unasked by some through feelings of delicacy", "note", None,
     "'Delicacy' is doing a lot of ironic work here.", []),
    (1, "How does it feel to be a problem?", "note", None,
     "The 'Negro problem' was a standard phrase in 1903 newspapers. He turns a policy word into a feeling.", [
         (None, "Yes, and the chapter's last page comes back to 'the Negro Problem' as a test of the republic."),
         (PROFESSOR, "Good catch. Keep a list of where 'problem' appears; we'll use it in section."),
     ]),
    (1, "How does it feel to be a problem?", "note", "past",
     "Last year we argued about whether this is rhetorical. Our TA said it's the question the whole book answers.", []),
    (1, "How does it feel to be a problem?", "question", None,
     "Is he quoting someone here, or is this his own phrasing?", [
         (None, "I think it's his. The point is that nobody actually asks it."),
     ]),
    (1, "eye me curiously or compassionately", "note", None,
     "Both looks are the same problem: either way he's being looked at, not talked to.", []),

    # ---- page 2: the visiting card and the veil
    (2, "I answer seldom a word", "note", None,
     "Silence as a choice, not a lack. Compare 'reduce the boiling to a simmer'.", []),
    (2, "reduce the boiling to a simmer", "note", None,
     "Funny and bitter at the same time. He's managing other people's outrage for them.", []),
    (2, "being a problem is a strange experience", "note", None,
     "'Strange' is such an understatement after the opening paragraph.", []),
    (2, "save perhaps in babyhood and in Europe", "note", None,
     "He studied in Berlin 1892-94. Being in Europe is the one time he wasn't a 'problem'.", [
         (None, "Source? I want to cite that in my paper."),
         (None, "Lewis's biography covers it, chapter on Berlin. It's in the library."),
     ]),
    (2, "the dark Housatonic winds between Hoosac and Taghkanic to the sea", "note", None,
     "Great Barrington, Massachusetts. He grew up in a mostly white New England town.", []),
    (2, "buy gorgeous visiting-cards", "note", None,
     "Such a small, ordinary object for such a big moment.", []),
    (2, "refused it peremptorily, with a glance", "note", None,
     "No words at all, just a glance. The whole veil starts with someone looking.", [
         (None, "Which connects to 'looking at one's self through the eyes of others' on the next page."),
     ]),
    (2, "refused it peremptorily, with a glance", "note", "past",
     "This is the scene everyone remembers from this chapter.", []),
    (2, "in heart and life and longing", "note", None,
     "'Or like, mayhap' - he's not sure he's different. The difference is imposed, not felt.", []),
    (2, "in heart and life and longing", "question", None,
     "Is the veil something he can see through or not? Seems like it changes.", [
         (None, "Later 'darkly as through a veil' (p. 8) suggests you can see, just not clearly."),
         (None, "He also says he had 'no desire to tear down that veil' here, so at first it's a wall."),
     ]),
    (2, "I held all beyond it in common contempt", "note", None,
     "The kid's response is pride, not shame. That changes by the next paragraph.", []),
    (2, "a region of blue sky and great wandering shadows", "note", None,
     "Blue sky shows up again on p. 3 as 'the streak of blue above'.", []),
    (2, "That sky was bluest when I could beat my mates at examination-time", "note", None,
     "Competition as escape. Relatable, honestly.", []),

    # ---- page 3: prison-house, seventh son, double-consciousness (the crowded passage)
    (3, "their youth shrunk into tasteless sycophancy", "note", None,
     "Three responses to the veil: sycophancy, silent hatred, a bitter cry. He took a fourth, competing.", []),
    (3, "Why did God make me an outcast and a stranger in mine own house?", "note", None,
     "Sounds like a psalm. 'Stranger in mine own house' = a citizen who isn't treated as one.", []),
    (3, "The shades of the prison-house closed round about us all", "note", None,
     "Wordsworth's Intimations Ode: 'Shades of the prison-house begin to close / Upon the growing Boy'.", [
         (PROFESSOR, "Yes. Du Bois quotes the canon constantly; ask what the borrowing does each time."),
     ]),
    (3, "watch the streak of blue above", "note", None,
     "The last option is 'half hopelessly' watching. Bleak.", []),
    (3, "the Negro is a sort of seventh son", "note", PROFESSOR,
     "Folklore: a seventh son, or a child born with a caul (a 'veil'), was said to have second sight. Read the next 12 lines slowly; this is the most quoted passage in the book.", []),
    (3, "the Negro is a sort of seventh son", "note", None,
     "The list before it is a 19th-century race-history list. He adds a seventh 'people' to it.", []),
    (3, "gifted with second-sight in this American world", "note", None,
     "'Gifted'. The veil is a burden AND a gift.", [
         (None, "Agreed. People skip over this and only quote the painful part."),
     ]),
    (3, "gifted with second-sight in this American world", "note", "past",
     "Second sight = seeing what others can't. He knows America better than it knows itself.", []),
    (3, "yields him no true self-consciousness", "note", None,
     "'Self-consciousness' as in Hegel: knowing yourself through recognition by another.", [
         (None, "Is there evidence he read Hegel?"),
         (None, "Harvard philosophy with William James, then Berlin. The SEP entry on Du Bois discusses it."),
     ]),
    (3, "It is a peculiar sensation, this double-consciousness", "note", None,
     "The term existed before him in psychology (split personality). He changes what it means.", [
         (None, "Emerson uses 'double consciousness' too, in 'The Transcendentalist'."),
         (None, "Didn't know that. So he's borrowing from both."),
     ]),
    (3, "It is a peculiar sensation, this double-consciousness", "note", None,
     "'Peculiar' again. Same word as 'peculiar even for one who has never been anything else' on p. 2.", []),
    (3, "It is a peculiar sensation, this double-consciousness", "question", None,
     "Is double-consciousness a bad thing in this chapter, or is it also the gift from the line above?", [
         (None, "Both? The sentence moves from gift to 'torn asunder'."),
         (None, "I read it as bad here and the second-sight part as the upside."),
         ("past", "Our section decided it's deliberately both. He doesn't resolve it."),
     ]),
    (3, "It is a peculiar sensation, this double-consciousness", "note", "past",
     "We wrote our midterm on this sentence.", []),
    (3, "this sense of always looking at one’s self through the eyes of others", "note", None,
     "This is the line I'm writing my response on. It's the visiting-card glance turned inward.", []),
    (3, "this sense of always looking at one’s self through the eyes of others", "note", None,
     "Social media makes this feel weirdly current. Not the same thing, but related.", [
         (None, "Careful: he's talking about race and a whole society, not just self-image."),
         (None, "Fair. I meant the 'looking at yourself through others' part only."),
     ]),
    (3, "this sense of always looking at one’s self through the eyes of others", "note", None,
     "Notice 'always'. Not sometimes. It doesn't switch off.", []),
    (3, "of measuring one’s soul by the tape of a world that looks on in amused contempt and pity", "note", None,
     "A tape measure for a soul. Absurd on purpose.", []),
    (3, "of measuring one’s soul by the tape of a world that looks on in amused contempt and pity", "note", None,
     "'Contempt and pity' - the same pair as 'curiously or compassionately' on p. 1.", [
         (None, "Nice. Same two looks."),
     ]),
    (3, "One ever feels his two-ness", "note", None,
     "'Two-ness' - he coins a word because there isn't one.", []),
    (3, "One ever feels his two-ness", "question", None,
     "Is 'an American, a Negro' meant to be two identities or two ways of being seen?", [
         (None, "The next page says he wants to be both, so two identities he isn't allowed to hold together."),
     ]),
    (3, "two warring ideals in one dark body", "note", None,
     "The body holds it together, not the mind. 'Dogged strength'.", []),
    (3, "two warring ideals in one dark body", "note", None,
     "Warring, torn asunder - very violent language for an inner state.", []),
    (3, "two warring ideals in one dark body", "note", "past",
     "Compare with 'the contradiction of double aims' on the next page.", []),
    (3, "two unreconciled strivings", "note", None,
     "'Strivings' is in the chapter title. This is the spiritual striving.", []),

    # ---- page 4: merging, the kingdom of culture
    (4, "The history of the American Negro is the history of this strife", "note", None,
     "Personal story → history of a people. He scales up his own experience.", []),
    (4, "to merge his double self into a better and truer self", "note", None,
     "Merge, not choose. Neither self should be lost.", []),
    (4, "He would not Africanize America", "note", None,
     "Answering the people who said assimilation or emigration were the only options.", [
         (None, "Marcus Garvey's back-to-Africa movement is later (1910s), right?"),
         (None, "Yes, Garvey is later. But emigration ideas were around in the 1890s already."),
     ]),
    (4, "He would not bleach his Negro soul in a flood of white Americanism", "note", None,
     "'Bleach' - harsh image for assimilation.", []),
    (4, "He would not bleach his Negro soul in a flood of white Americanism", "note", None,
     "This and the Africanize line are perfectly balanced sentences. He writes like a speech.", []),
    (4, "to be both a Negro and an American", "note", None,
     "The simplest sentence in the chapter. The whole argument in nine words.", [
         (None, "And 'simply wishes' - he frames it as a modest ask."),
     ]),
    (4, "to be both a Negro and an American", "note", "past",
     "Our class put this on the board on the last day.", []),
    (4, "the doors of Opportunity closed roughly in his face", "note", None,
     "Capital O Opportunity, like it's a place.", []),
    (4, "a co-worker in the kingdom of culture", "note", PROFESSOR,
     "Hold on to this phrase: it's the goal the rest of the chapter measures progress against.", []),
    (4, "a co-worker in the kingdom of culture", "note", None,
     "Co-worker, not guest. He wants equal participation.", []),
    (4, "Ethiopia the Shadowy and of Egypt the Sphinx", "note", None,
     "Pointing to ancient African civilizations to answer claims that Africa had no history.", []),
    (4, "like falling stars", "note", None,
     "Talent that burns out because nobody 'gauges their brightness' in time.", []),
    (4, "it is the contradiction of double aims", "note", None,
     "Weakness is a misreading: what looks like weakness is being pulled two ways.", [
         (None, "That's double-consciousness applied to work, I think."),
     ]),

    # ---- page 5 is a bad scan; only the readable lines
    (5, "a twice-told tale to his white neighbors", "note", None,
     "The black scholar can't win: old news to one audience, 'Greek' to the other.", []),
    (5, "The innate love of harmony and beauty", "note", None,
     "Some of this page reads like stereotypes of the time ('innate'). How do we handle that?", [
         (PROFESSOR, "Good question for section. Read it historically, and also notice where he resists the stereotype."),
     ]),

    # ---- page 6: the promised land
    (6, "Emancipation was the key to a promised land", "note", None,
     "Exodus imagery: Israelites, promised land, Canaan later on p. 7.", []),
    (6, "Shout, you’re free", "note", None,
     "A spiritual. Sorrow Songs again, like the epigraph music.", []),
    (6, "forty years of national life", "note", None,
     "1863 to 1903: forty years, like the forty years in the wilderness.", [
         (None, "That's what I wrote too. The Exodus parallel is everywhere on this page."),
     ]),
    (6, "the swarthy spectre sits in its accustomed seat at the Nation’s feast", "note", None,
     "Banquo's ghost at the feast in Macbeth. The next quote is Macbeth too.", [
         (None, "'Take any shape but that' - yes, Act 3 Scene 4."),
     ]),
    (6, "Take any shape but that", "question", None,
     "Who is speaking in this quotation, the Nation or Du Bois?", [
         (None, "The Nation, I think. It's Macbeth scared of the ghost, and America scared of its 'problem'."),
     ]),
    (6, "the freedman has not yet found in freedom his promised land", "note", None,
     "The promised land didn't arrive. Reconstruction failed.", []),
    (6, "the freedman has not yet found in freedom his promised land", "note", "past",
     "Pair this with p. 7, 'the mountain path to Canaan'.", []),
    (6, "like a tantalizing will-o’-the-wisp", "note", None,
     "A light that leads you into a swamp. Freedom as a trick.", []),

    # ---- page 7: the ballot, book-learning
    (7, "the terrors of the Ku-Klux Klan", "note", None,
     "The first Klan, 1860s-70s.", []),
    (7, "the Fifteenth Amendment", "note", None,
     "1870: the vote can't be denied on account of race. Disenfranchisement came anyway.", []),
    (7, "the revolution of 1876", "note", None,
     "The Compromise of 1877 that ended Reconstruction. Why does he call it a revolution?", [
         (None, "Because it overturned everything Reconstruction built. A revolution backwards."),
         (PROFESSOR, "Both readings work. We'll cover 1876-77 in Thursday's lecture."),
     ]),
    (7, "the revolution of 1876", "question", None,
     "What happened in 1876 exactly?", []),
    (7, "another pillar of fire by night", "note", None,
     "Exodus again: the pillar of fire that guided the Israelites.", []),
    (7, "the mountain path to Canaan", "note", None,
     "Education as the slow road. Each ideal on this page is a different road to the same promised land.", []),

    # ---- page 8: the long climb
    (8, "The cold statistician wrote down the inches of progress", "note", None,
     "A dig at the sociologists measuring Black progress from outside. He was one, which makes it funnier.", []),
    (8, "the Canaan was always dim and far away", "note", None,
     "Same metaphor, now tired.", []),
    (8, "darkly as through a veil", "note", None,
     "1 Corinthians 13: 'through a glass, darkly'. And the veil from p. 2.", [
         (None, "So now the veil is something you can see through, not just a wall."),
     ]),
    (8, "he must be himself, and not another", "note", None,
     "The opposite of 'looking at one's self through the eyes of others'.", []),
    (8, "to be a poor race in a land of dollars is the very bottom of hardships", "note", None,
     "Economics enters. Not just feelings.", []),

    # ---- page 9
    (9, "the shadow of a vast despair", "note", None,
     "Shadows on almost every page.", []),
    (9, "the natural defence of culture against barbarism", "note", None,
     "He's quoting the racist argument so he can take it apart.", []),
    (9, "that nameless prejudice that leaps beyond all this", "note", None,
     "He'll grant prejudice against ignorance or crime, but not this. A strategic concession.", [
         (None, "I found the concession uncomfortable. Is that the point?"),
     ]),

    # ---- page 10
    (10, "from Toussaint to the devil", "note", None,
     "Toussaint Louverture, leader of the Haitian Revolution.", []),
    (10, "Be content to be servants", "note", None,
     "A swipe at the industrial-education program, Booker T. Washington's side. Chapter 3 says it directly.", [
         (PROFESSOR, "Hold this thought until Chapter 3, 'Of Mr. Booker T. Washington and Others'."),
     ]),
    (10, "So dawned the time of Sturm und Drang", "note", None,
     "German Romanticism, again from his Berlin years.", []),

    # ---- page 11
    (11, "all these ideals must be melted and welded into one", "note", None,
     "Freedom, the vote, education: not one OR another, all together.", []),
    (11, "else what shall save us from a second slavery?", "note", None,
     "Written in the middle of disenfranchisement. Not hypothetical.", []),
    (11, "not singly but together, not successively but together", "note", None,
     "Repeats 'together' twice. Answering people who said 'one thing at a time'.", []),
    (11, "two world-races may give each to each", "note", None,
     "Exchange, not absorption.", []),
    (11, "there is no true American music but the wild sweet melodies of the Negro slave", "note", None,
     "Big claim. Ch. 14 is all about the Sorrow Songs.", []),

    # ---- page 12
    (12, "a dusty desert of dollars and smartness", "note", None,
     "A critique of America itself, not just of racism.", []),
    (12, "the soul of the Sorrow Songs", "note", None,
     "Last mention of the songs that head each chapter.", []),
    (12, "Merely a concrete test of the underlying principles of the great republic is the Negro Problem", "note", None,
     "'Problem' again, but flipped: it's America being tested.", [
         (None, "Full circle from 'How does it feel to be a problem?'"),
     ]),
    (12, "that men may listen to the striving in the souls of black folk", "note", None,
     "Ends on 'listen'. The opening was about not being asked.", []),
]

# Jordan's own notes, so logging in as Jordan shows some of the margin open.
JORDAN_NOTES = [
    (3, "It is a peculiar sensation, this double-consciousness",
     "Writing my response paper on this. Notes from lecture: Hegel, Emerson, and the psychology term."),
    (6, "Emancipation was the key to a promised land",
     "The Exodus thread runs through pp. 6-8. Tracking it."),
]


def users():
    """(name, role, cohort) for this course, in log-in order: professor, featured students, the rest."""
    rows = [(PROFESSOR, "professor", CURRENT_COHORT)]
    rows += [(name, "student", CURRENT_COHORT) for name in FEATURED_STUDENTS + CLASSMATES]
    rows += [(name, "student", PAST_COHORT) for name in PAST_STUDENTS]
    return rows


def add_course(conn, demo_pdf_path, uploads_dir):
    """The course, its people and charter, its reading and every note above."""
    import main  # here, not at the top: main imports seed, which imports this
    course_id = conn.execute("INSERT INTO course (title, current_cohort) VALUES (?, ?)",
                             (COURSE_TITLE, CURRENT_COHORT)).lastrowid
    conn.executemany("INSERT INTO users (name, role, cohort, course_id) VALUES (?, ?, ?, ?)",
                     [(*u, course_id) for u in users()])
    conn.execute(
        """INSERT INTO charter (course_id, text_md, permissible_sources, max_explanation_words, updated_at)
           VALUES (?, ?, ?, ?, ?)""",
        (course_id, CHARTER_TEXT, PERMISSIBLE_SOURCES, MAX_EXPLANATION_WORDS, db.now()),
    )
    ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM users WHERE course_id = ?", (course_id,))}

    uploads_dir.mkdir(exist_ok=True)
    pdf_path = uploads_dir / PDF_NAME
    shutil.copy(demo_pdf_path, pdf_path)
    reading_id = main.create_reading(conn, course_id, READING_TITLE, pdf_path, ids[PROFESSOR])

    # Authors in turn, so the notes are spread over the class. Maya never writes.
    classmates = iter(CLASSMATES * 10)
    past = iter(PAST_STUDENTS * 10)

    def author(name):
        if name is None:
            return ids[next(classmates)]
        if name == "past":
            return ids[next(past)]
        return ids[name]

    # Spread the notes over the last week, oldest first, so "newest first" in the margin means something.
    clock = datetime.now() - timedelta(days=7)
    step = timedelta(days=7) / (len(NOTES) * 2 + len(JORDAN_NOTES) + 1)

    def insert(user_id, kind, page, quote, rects, body, parent_id=None, section_id=None):
        nonlocal clock
        clock += step
        annotation_id = db.insert_annotation(conn, reading_id, user_id, kind, page, quote, rects, body,
                                             parent_id=parent_id, section_id=section_id)
        conn.execute("UPDATE annotations SET created_at = ? WHERE id = ?",
                     (clock.isoformat(timespec="seconds"), annotation_id))
        return annotation_id

    def top_level(user_id, kind, page, quote, body):
        rects = json.dumps(locate.quote_rects(pdf_path, page, quote))
        section = sections.section_for(conn, reading_id, page, quote)
        section_id = section["id"] if section else None
        return insert(user_id, kind, page, quote, rects, body, section_id=section_id), section_id

    for page, quote, kind, who, body, replies in NOTES:
        note_id, section_id = top_level(author(who), kind, page, quote, body)
        for reply_who, reply_body in replies:
            insert(author(reply_who), "note", page, None, None, reply_body, parent_id=note_id, section_id=section_id)
    for page, quote, body in JORDAN_NOTES:
        top_level(ids["Jordan"], "note", page, quote, body)
    return course_id
