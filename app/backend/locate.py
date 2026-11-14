"""Find a quoted passage in the course readings (SPEC §3.9 step 4), and its highlight boxes.

Text copied from Preview or Notability rarely matches the PDF's extracted text exactly:
curly vs straight quotes, line breaks, hyphenation, ligatures. So we compare only letters
and digits, lowercased: "one’s self,—" and "one's self —" both become "onesself".
"""
import unicodedata

import pdfplumber

import db


def squash(text):
    """Letters and digits only, lowercased, with ligatures like 'ﬁ' expanded."""
    out = []
    for ch in unicodedata.normalize("NFKD", text):
        if ch.isalnum():
            out.append(ch.lower())
    return "".join(out)


def find_page(conn, quote, course_id):
    """Returns (reading_id, page) of the first page in this course's readings whose text contains the quote, or None.

    FTS ranks the candidate pages, then the squashed-substring check decides.
    TODO(edge): a quote that runs across a page break isn't found.
    """
    target = squash(quote)
    if not target:
        return None
    match = db.fts_query(quote)
    if match is not None:
        candidates = conn.execute(
            """SELECT f.reading_id, f.page, f.text FROM pages_fts f JOIN readings r ON r.id = f.reading_id
               WHERE pages_fts MATCH ? AND r.course_id = ? ORDER BY bm25(pages_fts) LIMIT 10""",
            (match, course_id),
        ).fetchall()
        for row in candidates:
            if target in squash(row["text"]):
                return row["reading_id"], row["page"]
    # Very short quotes may be all stopwords; just scan every page.
    for row in conn.execute(
            """SELECT p.reading_id, p.page, p.text FROM reading_pages p JOIN readings r ON r.id = p.reading_id
               WHERE r.course_id = ? ORDER BY p.reading_id, p.page""", (course_id,)):
        if target in squash(row["text"]):
            return row["reading_id"], row["page"]
    return None


def quote_rects(pdf_path, page, quote):
    """The quote's highlight boxes on `page` (1-based): one rect per line, as page fractions.

    Coordinates are top-left origin, matching what the frontend gets from getClientRects().
    Raises ValueError if the quote isn't on that page.
    """
    target = squash(quote)
    with pdfplumber.open(pdf_path) as pdf:
        p = pdf.pages[page - 1]
        # Squash the page's characters too, remembering which PDF character each letter came from.
        letters = []
        owners = []
        for i, ch in enumerate(p.chars):
            for letter in squash(ch["text"]):
                letters.append(letter)
                owners.append(i)
        start = "".join(letters).find(target)
        if not target or start == -1:
            raise ValueError(f"Quote not found on page {page}: {quote!r}")
        chars = [p.chars[i] for i in sorted(set(owners[start:start + len(target)]))]

        lines = {}
        for ch in chars:
            key = round(ch["top"])
            box = lines.setdefault(key, [ch["x0"], ch["top"], ch["x1"], ch["bottom"]])
            box[0] = min(box[0], ch["x0"])
            box[1] = min(box[1], ch["top"])
            box[2] = max(box[2], ch["x1"])
            box[3] = max(box[3], ch["bottom"])
        return [
            {
                "x": round(x0 / p.width, 4),
                "y": round(top / p.height, 4),
                "w": round((x1 - x0) / p.width, 4),
                "h": round((bottom - top) / p.height, 4),
            }
            for x0, top, x1, bottom in lines.values()
        ]


def find_page_from_lines(conn, text, course_id):
    """The Mac overlay sends a few OCR'd lines from the screen (one per line, not contiguous).
    Each line votes for the page it's found on; the page with most votes wins. None if no line is found."""
    votes = {}
    for line in text.splitlines():
        if len(squash(line)) < 12:  # short OCR lines match too many pages
            continue
        found = find_page(conn, line, course_id)
        if found is not None:
            votes[found] = votes.get(found, 0) + 1
    if not votes:
        return None
    return max(votes, key=votes.get)


COLUMN_GAP = 18  # points; a wider gap between words on one line means a new column


def page_lines(pdf_path, page):
    """Every text line on `page` (1-based) with its box as page fractions (top-left origin).
    Two-column pages give two lines per row, like the screen OCR sees them."""
    with pdfplumber.open(pdf_path) as pdf:
        p = pdf.pages[page - 1]
        rows = {}
        for word in p.extract_words():
            rows.setdefault(round(word["top"]), []).append(word)
        lines = []
        for top in sorted(rows):
            words = sorted(rows[top], key=lambda w: w["x0"])
            run = [words[0]]
            for word in words[1:]:
                if word["x0"] - run[-1]["x1"] > COLUMN_GAP:
                    lines.append(run)
                    run = []
                run.append(word)
            lines.append(run)
        return [
            {
                "text": " ".join(w["text"] for w in run),
                "rect": {
                    "x": round(run[0]["x0"] / p.width, 4),
                    "y": round(min(w["top"] for w in run) / p.height, 4),
                    "w": round((run[-1]["x1"] - run[0]["x0"]) / p.width, 4),
                    "h": round((max(w["bottom"] for w in run) - min(w["top"] for w in run)) / p.height, 4),
                },
            }
            for run in lines
        ]
