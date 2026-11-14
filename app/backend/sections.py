"""Sections of a reading (SPEC §3.10): found once at upload, then used to place each annotation.

A section is a heading plus everything up to the next heading. Headings come from the PDF's
outline (bookmarks) if it has one, otherwise from lines that look like headings. A reading
with fewer than MIN_HEADINGS headings is split one section per page instead.
"""
import re

import pypdf

import locate

MIN_HEADINGS = 2
MAX_HEADING_WORDS = 10
PAGE_SECTION_TITLE = "Page {page}"  # the title of a section in the one-per-page fallback

# "I.", "IV.", "3.", "12" on a line of its own: a chapter/section number.
NUMBER_LINE = re.compile(r"^(?:[IVXLC]+|\d+)\.?$")
# A heading may only contain these besides letters and digits; OCR noise is full of other symbols.
HEADING_CHARS = set(" .'’-:&")
HEADER_LINES = 3  # running headers are looked for this far down a page (OCR specks can sit above them)
MIN_HEADING_LETTERS = 3  # a lone "V" or "I" from OCR noise isn't a heading
VOWELS = set("aeiouyAEIOUY")
# Words that stay lower case in a Title Case heading.
SMALL_WORDS = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into", "of", "on",
               "or", "the", "to", "with"}


def looks_like_heading(line):
    """Short, on its own line, no sentence punctuation at the end, and Title Case or ALL CAPS."""
    words = line.split()
    if not words or len(words) > MAX_HEADING_WORDS:
        return False
    if line[-1] in ".,;:!?—–-\"”’)" or "," in line:
        return False
    if any(not ch.isalnum() and ch not in HEADING_CHARS for ch in line):
        return False
    if sum(ch.isalpha() for ch in line) < MIN_HEADING_LETTERS:
        return False
    # OCR of an illustration or a smudged page gives ALL CAPS lines like "CNC CD AOE": every
    # real word has a vowel (numbers aside). TODO(edge): no dictionary check for "LSMLMNTAD".
    if any(not any(ch.isdigit() for ch in word) and not VOWELS & set(word) for word in words):
        return False
    if line.isupper():
        return True
    for word in words:
        if word.lower() in SMALL_WORDS:
            continue
        if not word[0].isupper() and not word[0].isdigit():
            return False
    return True


def running_header_key(line):
    """The line with a page number at either end removed: "OF OUR SPIRITUAL STRIVINGS 3",
    "2 THE SOULS OF BLACK FOLK" -> the bare title. OCR misreads page numbers ("STRIVINGS T"
    for 7, "il" for 11), so any end word of one or two characters counts as one."""
    words = line.split()
    if words and (words[0].isdigit() or len(words[0]) <= 2):
        words = words[1:]
    if words and (words[-1].isdigit() or len(words[-1]) <= 2):
        words = words[:-1]
    return " ".join(words).upper()


def top_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()][:HEADER_LINES]


def running_header_keys(page_texts):
    """Keys (see running_header_key) of lines near the top of two or more pages: running headers."""
    pages_with = {}
    for text in page_texts:
        for key in {running_header_key(line) for line in top_lines(text)}:
            if key:
                pages_with[key] = pages_with.get(key, 0) + 1
    return {key for key, n in pages_with.items() if n > 1}


def headings_from_text(page_texts):
    """[(title, page)] for heading-like lines. A number on its own line joins the line after it
    ("I." + "Of Our Spiritual Strivings" -> "I. Of Our Spiritual Strivings")."""
    found = []
    header_keys = running_header_keys(page_texts)
    for page, text in enumerate(page_texts, start=1):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        # Drop running headers near the top of the page.
        lines = [line for n, line in enumerate(lines)
                 if not (n < HEADER_LINES and running_header_key(line) in header_keys)]
        i = 0
        while i < len(lines):
            line = lines[i]
            if NUMBER_LINE.match(line) and i + 1 < len(lines) and looks_like_heading(lines[i + 1]):
                found.append((f"{line} {lines[i + 1]}", page))
                i += 2
                continue
            if looks_like_heading(line):
                found.append((line, page))
            i += 1
    # Lines repeated on several pages are running headers or footers, not headings.
    counts = {}
    for title, _ in found:
        counts[title] = counts.get(title, 0) + 1
    return [(title, page) for title, page in found if counts[title] == 1]


def headings_from_outline(pdf):
    """[(title, page)] from the PDF's bookmarks, top level and nested, in order."""
    found = []

    def walk(items):
        for item in items:
            if isinstance(item, list):
                walk(item)
            else:
                found.append((item.title.strip(), pdf.get_destination_page_number(item) + 1))
    walk(pdf.outline)
    return found


def add_sections(conn, reading_id, pdf_path, page_texts):
    """Find the reading's sections and store them in reading_sections (in reading order)."""
    headings = headings_from_outline(pypdf.PdfReader(pdf_path))
    if len(headings) < MIN_HEADINGS:
        headings = headings_from_text(page_texts)
    if len(headings) < MIN_HEADINGS:
        headings = [(PAGE_SECTION_TITLE.format(page=page), page) for page in range(1, len(page_texts) + 1)]
    for ord_, (title, page) in enumerate(headings):
        conn.execute(
            "INSERT INTO reading_sections (reading_id, title, start_page, ord) VALUES (?, ?, ?, ?)",
            (reading_id, title, page, ord_),
        )


def section_for(conn, reading_id, page, quote):
    """The section a highlight on `page` falls in: the last heading before it.

    Returns {"id", "title"} or None (readings uploaded before sections were built have none).
    A heading on the same page counts only if it comes before the quote in the page's text.
    """
    sections = conn.execute(
        "SELECT id, title, start_page FROM reading_sections WHERE reading_id = ? AND start_page <= ? ORDER BY ord",
        (reading_id, page),
    ).fetchall()
    if not sections:
        return None
    page_text = locate.squash(conn.execute(
        "SELECT text FROM reading_pages WHERE reading_id = ? AND page = ?", (reading_id, page),
    ).fetchone()["text"])
    # TODO(edge): a quote not found on its page (e.g. across a page break) counts as the page's start.
    quote_at = max(page_text.find(locate.squash(quote)), 0) if quote else 0
    current = None
    for section in sections:
        if section["start_page"] < page:
            current = section
            continue
        heading_at = page_text.find(locate.squash(section["title"]))
        if heading_at <= quote_at:  # -1 (heading text not found, e.g. "Page 3") counts as the page's start
            current = section
    if current is None:
        return None  # TODO(edge): text before the first heading belongs to no section
    return {"id": current["id"], "title": current["title"]}
