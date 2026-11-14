"""OCR every upload (SPEC §3.11), so scans and badly OCR'd PDFs get a usable text layer.

1. Find the scanned pages: images cover most of the page.
2. Strip those pages' old text layer (ocrmypdf --redo-ocr would keep it and double every letter).
3. ocrmypdf --skip-text: OCRs pages with no text, leaves born-digital pages alone, keeps the
   original images (so the file stays small).

Slow (4–6 s a page on the droplet), so main.py runs it in a background thread.
"""
import shutil
import subprocess
import tempfile

import pdfplumber
import pikepdf

SCAN_COVERAGE = 0.8  # a page whose images cover at least this share of its area is a scan
OCR_LANGUAGE = "eng"
OCRMYPDF_ARGS = ["--skip-text", "--output-type", "pdf", "-l", OCR_LANGUAGE]
BOX_OCR_DPI = 300  # box selections (SPEC §3.3) are rendered this sharp before Tesseract reads them
# TODO(edge): photo uploads (img2pdf + --rotate-pages --deskew), the §3.11 stretch.


def image_coverage(page):
    """Share of the page's area covered by its images (overlaps counted twice; capped at 1)."""
    area = 0.0
    for img in page.images:
        x0, x1 = max(img["x0"], 0), min(img["x1"], page.width)
        top, bottom = max(img["top"], 0), min(img["bottom"], page.height)
        if x1 > x0 and bottom > top:
            area += (x1 - x0) * (bottom - top)
    return min(area / (page.width * page.height), 1.0)


def find_pages(pdf_path):
    """Returns (scan_pages, textless_pages): 0-based page indexes."""
    scans, textless = [], []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            if image_coverage(page) >= SCAN_COVERAGE:
                scans.append(i)
            elif not page.chars:
                textless.append(i)
    return scans, textless


def without_text(pdf, content_owner):
    """The owner's (a page's or a Form XObject's) content stream with every text object (BT … ET) removed."""
    kept = []
    in_text = False
    for operands, operator in pikepdf.parse_content_stream(content_owner):
        op = str(operator)
        if op == "BT":
            in_text = True
        elif op == "ET":
            in_text = False
        elif not in_text:
            kept.append((operands, operator))
    return pikepdf.unparse_content_stream(kept)


def strip_form_text(pdf, resources):
    """Strip text from the Form XObjects in `resources`, and the forms inside them.
    Earlier OCR (ocrmypdf's included) puts its invisible text layer in such a form."""
    for xobject in resources.get("/XObject", {}).values():
        if xobject.get("/Subtype") == "/Form":
            xobject.write(without_text(pdf, xobject))
            if "/Resources" in xobject:
                strip_form_text(pdf, xobject.Resources)


def strip_text(pdf_path, out_path, page_indexes):
    """Copy the PDF with the text removed from the given pages; their images stay.

    TODO(edge): a form shared with a born-digital page loses its text there too.
    """
    with pikepdf.open(pdf_path) as pdf:
        for i in page_indexes:
            page = pdf.pages[i]
            page.Contents = pdf.make_stream(without_text(pdf, page))
            if "/Resources" in page.obj:
                strip_form_text(pdf, page.Resources)
        pdf.save(out_path)


def ocr_in_place(pdf_path):
    """OCR the PDF at pdf_path and replace it with the result. Raises on failure (fail loudly).

    Returns a short note of what happened, for the server log.
    """
    if shutil.which("ocrmypdf") is None:
        # A teammate's laptop: the upload still works, with whatever text the PDF had.
        return f"WARNING: ocrmypdf isn't installed, so {pdf_path} was NOT OCR'd (apt install ocrmypdf tesseract-ocr-eng)"

    scans, textless = find_pages(pdf_path)
    if not scans and not textless:
        return f"{pdf_path}: born-digital, no OCR needed"

    stripped = pdf_path.with_suffix(".stripped.pdf")
    ocred = pdf_path.with_suffix(".ocr.pdf")
    strip_text(pdf_path, stripped, scans)
    result = subprocess.run(["ocrmypdf", *OCRMYPDF_ARGS, str(stripped), str(ocred)],
                            capture_output=True, text=True)
    stripped.unlink()
    if result.returncode != 0:
        last_lines = "\n".join(result.stderr.strip().splitlines()[-5:])
        raise RuntimeError(f"ocrmypdf failed (exit {result.returncode}): {last_lines}")
    ocred.replace(pdf_path)
    return f"{pdf_path}: OCR'd {len(scans)} scanned + {len(textless)} textless pages"


def box_text(pdf_path, page_number, rect):
    """The text inside a box drawn on a page (SPEC §3.3 box selection): the PDF's own text there
    if it has any, else Tesseract on that area. "" if neither finds anything.

    `rect` is page fractions, top-left origin, like every highlight box.
    """
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_number - 1]
        bbox = (
            max(rect["x"], 0) * page.width,
            max(rect["y"], 0) * page.height,
            min(rect["x"] + rect["w"], 1) * page.width,
            min(rect["y"] + rect["h"], 1) * page.height,
        )
        area = page.crop(bbox)
        text = " ".join((area.extract_text() or "").split())
        if text:
            return text
        if shutil.which("tesseract") is None:
            print("WARNING: tesseract isn't installed, so a box selection got no text", flush=True)
            return ""
        with tempfile.TemporaryDirectory() as tmp:
            image_path = f"{tmp}/box.png"
            area.to_image(resolution=BOX_OCR_DPI).save(image_path)
            result = subprocess.run(["tesseract", image_path, "-", "-l", OCR_LANGUAGE],
                                    capture_output=True, text=True, check=True)
    return " ".join(result.stdout.split())
