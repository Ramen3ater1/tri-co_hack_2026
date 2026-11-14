"""Record demo video shots in a scripted Chromium, with a visible fake cursor (spike).

    cd spikes/1230-demo-recorder
    uv run --no-project --with playwright==1.65.2 python record.py shot3 [--base URL] [--headed]

One-time: uv run --no-project --with playwright==1.65.2 playwright install chromium
Each take resets itself first (deletes Ben's own notes on Rousseau through the API), so it can be
run again and again. Videos land in OUT_DIR (~/Transfer) as .mp4, named by shot-list number. The script prints when
each beat happens (seconds into the video), for trimming and for laying the voiceover on.
"""
import argparse
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

# ---------- tunables
BASE = "http://100.90.161.78:8765"  # the laptop copy over Tailscale; dev is https://dialectic-dev.yaggy.dev
OUT_DIR = Path.home() / "Transfer"  # named by shot-list number, e.g. "shot 3 - Ben unlocks the notes - 1243.mp4"
VIEWPORT = {"width": 1920, "height": 1080}  # Playwright records at 1x, so this is the video size
TYPE_DELAY_MS = 40        # per character, so typing reads at human speed
GLIDE_MS_BASE = 380       # every cursor move takes this long, plus GLIDE_MS_PER_PX per pixel...
GLIDE_MS_PER_PX = 0.45
GLIDE_MS_MAX = 1100       # ...but never longer than this
CURVE = 0.12              # how far a move bows to one side, as a share of its length (0 = straight)
FRAME_MS = 16             # one mouse event per ~frame while gliding (Playwright manages ~15 a second)
SMOOTHING = 45            # ms: the drawn cursor's lag behind the mouse. Higher = smoother but laggier
SEMINAR = "PHIL 247: The Social Contract (seminar)"
READING_PREFIX = "Week 2"

GENERAL_WILL_START = "Each of us puts"
GENERAL_WILL_END_AFTER = "direction of the general"   # the sentence ends at the next "will"
BEN_NOTE = ("Wait, so I'm both the one giving orders and the one obeying them? "
            "Where did he get this idea of a will that belongs to everyone?")
SAM_NOTE_START = "Last spring we spent"               # appears once Ben's note is saved
QUESTION_4 = "Where does the idea of the general will come from, and what did it mean in 1762?"
QUESTION_5 = "What does Rousseau mean by the general will?"
ANSWER_TIMEOUT_MS = 120000   # a cached answer takes a few seconds; a live one ~20 s
SOURCE_PAGE_SECONDS = 5      # how long shot 4 stays on the source page it opens

# A drawn cursor: recordings don't show the real pointer. A macOS-style arrow with a soft shadow that
# follows mouse events, dips on press, and leaves a fading ripple at each click.
CURSOR_JS = """
window.addEventListener('DOMContentLoaded', () => {
  const style = document.createElement('style');
  style.textContent = `
    #demo-cursor { position: fixed; left: -60px; top: -60px; z-index: 2147483647; pointer-events: none;
      transition: transform 110ms ease-out; transform-origin: 5px 3px;
      filter: drop-shadow(0 2px 3px rgba(0,0,0,.35)); }
    #demo-cursor.down { transform: scale(0.86); }
    .demo-ripple { position: fixed; z-index: 2147483646; pointer-events: none; width: 36px; height: 36px;
      margin: -18px 0 0 -18px; border-radius: 50%; background: rgba(255, 255, 255, .25);
      border: 2.5px solid rgba(255, 255, 255, .95); box-shadow: 0 0 0 1.5px rgba(0, 0, 0, .35);
      animation: demo-ripple 520ms ease-out forwards; }
    @keyframes demo-ripple { from { transform: scale(.35); opacity: 1; } to { transform: scale(1.5); opacity: 0; } }`;
  document.head.appendChild(style);
  const c = document.createElement('div');
  c.id = 'demo-cursor';
  c.innerHTML = '<svg width="30" height="30" viewBox="0 0 24 24"><path d="M5 3v16.2l4.1-3.9 2.7 6.2 2.6-1.1-2.7-6.1h5.8z" fill="#000" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  document.body.appendChild(c);
  // Playwright can only send ~15 mouse events a second, so the drawn cursor doesn't jump to each one:
  // every animation frame it closes part of the gap to the latest mouse position.
  let tx = -60, ty = -60, cx = -60, cy = -60, first = true;
  window.addEventListener('mousemove', (e) => {
    tx = e.clientX; ty = e.clientY;
    if (first) { cx = tx; cy = ty; first = false; }
  }, true);
  let last = performance.now();
  const frame = (now) => {
    // Time-based, not per-frame: the reader draws few frames while PDF pages render.
    const k = 1 - Math.exp(-(now - last) / SMOOTHING); last = now;
    cx += (tx - cx) * k; cy += (ty - cy) * k;
    c.style.left = (cx - 5) + 'px'; c.style.top = (cy - 3) + 'px';
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
  window.addEventListener('mousedown', (e) => {
    c.classList.add('down');
    const r = document.createElement('div'); r.className = 'demo-ripple';
    r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px';
    document.body.appendChild(r); setTimeout(() => r.remove(), 600);
  }, true);
  window.addEventListener('mouseup', () => c.classList.remove('down'), true);
});
"""

# Client rects of a stretch of the PDF text layer: from START to the end of the first "will" after END_AFTER.
RANGE_JS = """
([pageNo, start, endAfter, endWord]) => {
  const layer = document.querySelector(`.pdf-page[data-page="${pageNo}"] .textLayer`);
  const walker = document.createTreeWalker(layer, NodeFilter.SHOW_TEXT);
  const nodes = []; let text = '';
  while (walker.nextNode()) { nodes.push([walker.currentNode, text.length]); text += walker.currentNode.data; }
  const s = text.indexOf(start);
  const after = text.indexOf(endAfter, s);
  const e = text.indexOf(endWord, after + endAfter.length) + endWord.length;
  if (s < 0 || after < 0 || e < endWord.length) throw new Error('passage not found in the text layer');
  const at = (i) => { for (let k = nodes.length - 1; k >= 0; k--) if (nodes[k][1] <= i) return [nodes[k][0], i - nodes[k][1]]; };
  const range = document.createRange();
  range.setStart(...at(s)); range.setEnd(...at(e));
  const rects = [...range.getClientRects()].filter((r) => r.width > 1);
  const first = rects[0], last = rects[rects.length - 1];
  return {x0: first.left + 1, y0: first.top + first.height / 2, x1: last.right - 1, y1: last.top + last.height / 2,
          center: first.top + (last.bottom - first.top) / 2};
}
"""


# ---------- API (setup and reset only; the shot itself is all clicks and typing)

def api(base, method, path, user_id, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method, headers={
        "X-User-Id": str(user_id), "Content-Type": "application/json",
        "User-Agent": "curl/8.5.0"})  # Cloudflare (dev) refuses Python's default agent
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def setup(base):
    users = {(u["name"], u["course_title"]): u for u in api(base, "GET", "/api/users", 1)}
    ben = users[("Ben", SEMINAR)]
    readings = api(base, "GET", "/api/course", ben["id"])["readings"]
    reading_id = [r for r in readings if r["title"].startswith(READING_PREFIX)][0]["id"]
    return ben, reading_id


def reset_ben(base, ben, reading_id):
    """Delete Ben's own notes and questions on the reading, so the lock card is back."""
    for a in api(base, "GET", f"/api/readings/{reading_id}/annotations", ben["id"]):
        if (a.get("author") or {}).get("id") == ben["id"] and not a.get("parent_id"):
            api(base, "DELETE", f"/api/annotations/{a['id']}", ben["id"])


# ---------- recording helpers

def ease_in_out(t):
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


class Take:
    def __init__(self, page):
        self.page = page
        self.t0 = time.monotonic()
        self.start = 0.0
        self.x, self.y = VIEWPORT["width"] * 0.62, VIEWPORT["height"] * 0.55
        self.track = []  # (seconds, event, x, y): the cursor's path, saved next to the video
        self.label = None  # a shot can name its own file (shot 5: 5A or 5B)
        self.extra = []    # (page, label): other tabs the shot opened, saved as their own videos

    def now(self):
        return time.monotonic() - self.t0

    def beat(self, label, start=False):
        """Print when this happens. start=True also marks where the saved video begins (loading is cut)."""
        if start:
            self.start = self.now()
            self.page.mouse.move(self.x, self.y)  # park the cursor so it's on screen from the first frame
        print(f"  {self.now() - self.start:6.1f} s  {label}", flush=True)

    def log(self, event):
        self.track.append((round(self.now(), 3), event, round(self.x, 1), round(self.y, 1)))

    def glide(self, x, y, curve=CURVE):
        """Move like a hand: ease in and out, bowing slightly to one side (a quadratic Bezier)."""
        x0, y0 = self.x, self.y
        dx, dy = x - x0, y - y0
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < 1:
            return
        ms = min(GLIDE_MS_BASE + dist * GLIDE_MS_PER_PX, GLIDE_MS_MAX)
        # Control point: the midpoint, pushed sideways. Alternate sides by direction so it doesn't look mechanical.
        side = 1 if dx >= 0 else -1
        cx, cy = x0 + dx / 2 - dy * curve * side, y0 + dy / 2 + dx * curve * side
        began = time.monotonic()
        while True:
            t = min((time.monotonic() - began) * 1000 / ms, 1.0)
            e = ease_in_out(t)
            bx = (1 - e) ** 2 * x0 + 2 * (1 - e) * e * cx + e ** 2 * x
            by = (1 - e) ** 2 * y0 + 2 * (1 - e) * e * cy + e ** 2 * y
            self.page.mouse.move(bx, by)
            self.x, self.y = bx, by
            self.log("move")
            if t >= 1.0:
                break
            self.page.wait_for_timeout(FRAME_MS)

    def glide_to(self, locator, curve=CURVE):
        box = locator.bounding_box()
        self.glide(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, curve)

    def down(self):
        self.page.mouse.down()
        self.log("down")

    def up(self):
        self.page.mouse.up()
        self.log("up")

    def click(self, locator):
        self.glide_to(locator)
        self.pause(0.18)
        self.down()
        self.pause(0.09)
        self.up()

    def pause(self, seconds):
        self.page.wait_for_timeout(int(seconds * 1000))


def open_reader(take, base, ben, reading_id, wait_for=".lock-card"):
    page = take.page
    page.goto(f"{base}/readings/{reading_id}")
    page.wait_for_selector('.pdf-page[data-page="12"] .textLayer span', timeout=60000)
    # Jump straight to the passage (off camera: trim up to the "on p. 12" beat).
    spot = page.evaluate(RANGE_JS, [12, GENERAL_WILL_START, GENERAL_WILL_END_AFTER, "will"])
    page.evaluate("""(y) => { const col = document.querySelector('.pdf-column');
                              col.scrollTop += y - col.clientHeight * 0.32; }""", spot["center"])
    page.wait_for_selector(wait_for)
    take.pause(1.5)  # let the margin settle on p. 12


def select_passage(take):
    spot = take.page.evaluate(RANGE_JS, [12, GENERAL_WILL_START, GENERAL_WILL_END_AFTER, "will"])
    take.glide(spot["x0"], spot["y0"])
    take.pause(0.3)
    take.down()
    take.glide(spot["x1"], spot["y1"], curve=0)  # a drag along the text, not a swoop
    take.pause(0.1)
    take.up()


# The passage's highlight boxes as page fractions, one per line, as the reader saves them.
RECTS_JS = """
([pageNo, start, endAfter, endWord]) => {
  const layer = document.querySelector(`.pdf-page[data-page="${pageNo}"] .textLayer`);
  const box = document.querySelector(`.pdf-page[data-page="${pageNo}"] .react-pdf__Page`).getBoundingClientRect();
  const walker = document.createTreeWalker(layer, NodeFilter.SHOW_TEXT);
  const nodes = []; let text = '';
  while (walker.nextNode()) { nodes.push([walker.currentNode, text.length]); text += walker.currentNode.data; }
  const s = text.indexOf(start), after = text.indexOf(endAfter, s);
  const e = text.indexOf(endWord, after + endAfter.length) + endWord.length;
  const at = (i) => { for (let k = nodes.length - 1; k >= 0; k--) if (nodes[k][1] <= i) return [nodes[k][0], i - nodes[k][1]]; };
  const range = document.createRange(); range.setStart(...at(s)); range.setEnd(...at(e));
  const lines = [];
  for (const r of range.getClientRects()) {
    if (r.width < 1) continue;
    const line = lines.find((l) => Math.abs(l.top - r.top) < r.height / 2);
    if (line) { line.left = Math.min(line.left, r.left); line.right = Math.max(line.right, r.right); line.bottom = Math.max(line.bottom, r.bottom); }
    else lines.push({left: r.left, right: r.right, top: r.top, bottom: r.bottom});
  }
  // The reader quotes window.getSelection().toString() (which turns the text layer's <br>s into spaces), so do the same.
  const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
  const quote = sel.toString().replace(/\\s+/g, ' ').trim(); sel.removeAllRanges();
  return {quote,
          rects: lines.map((l) => ({x: (l.left - box.left) / box.width, y: (l.top - box.top) / box.height,
                                    w: (l.right - l.left) / box.width, h: (l.bottom - l.top) / box.height}))};
}
"""


def restore_bens_note(take, base, ben, reading_id):
    """Off camera: Ben's note from shot 3, so the passage is already unlocked."""
    page = take.page
    page.goto(f"{base}/readings/{reading_id}")
    page.wait_for_selector('.pdf-page[data-page="12"] .textLayer span', timeout=60000)
    where = page.evaluate(RECTS_JS, [12, GENERAL_WILL_START, GENERAL_WILL_END_AFTER, "will"])
    api(base, "POST", f"/api/readings/{reading_id}/annotations", ben["id"],
        {"body": BEN_NOTE, "page": 12, "quote": where["quote"], "rects": where["rects"]})


def smooth_scroll_to(take, locator):
    locator.evaluate("(el) => el.scrollIntoView({behavior: 'smooth', block: 'nearest'})")
    take.pause(0.9)


def ask(take, question):
    """Select the passage, switch to Ask, type the question and send it."""
    page = take.page
    select_passage(take)
    page.wait_for_selector("#note")
    take.pause(0.5)
    take.click(page.get_by_role("tab", name="Ask"))
    page.wait_for_selector("#question")
    take.pause(0.3)
    take.click(page.locator("#question"))  # the Ask tab keeps focus, so click into the box like a person would
    take.pause(0.3)
    page.keyboard.type(question, delay=TYPE_DELAY_MS)
    take.pause(0.6)
    take.click(page.locator(".popover").get_by_role("button", name="Ask", exact=True))
    take.beat("question sent")


def wait_for_answer(take):
    """Until the answer is complete: the AI button, or a charter notice where the explanation would be."""
    page = take.page
    page.locator(".ai-button, .answer-card .notice:has-text('No AI explanation')").first.wait_for(timeout=ANSWER_TIMEOUT_MS)
    take.beat("answer complete")


# ---------- shots

def shot3(take, base, ben, reading_id):
    page = take.page
    open_reader(take, base, ben, reading_id)
    take.beat("on p. 12, lock card visible: start of the shot", start=True)
    take.pause(1)
    lock = page.locator(".lock-card").filter(has_text="2 notes near here").first
    take.glide_to(lock)
    take.beat("cursor on '2 notes near here'")
    take.pause(2)
    select_passage(take)
    take.beat("passage selected, note box open")
    page.wait_for_selector("#note")
    take.pause(0.8)
    page.keyboard.type(BEN_NOTE, delay=TYPE_DELAY_MS)
    take.beat("note typed")
    take.pause(0.8)
    take.click(page.get_by_role("button", name="Save note"))
    page.get_by_text(SAM_NOTE_START).first.wait_for(timeout=20000)
    take.beat("notes unlocked: Ana's and Sam's appear")
    take.glide_to(page.get_by_text(SAM_NOTE_START).first)
    take.pause(4)
    take.beat("end of the shot")


def shot4(take, base, ben, reading_id):
    page = take.page
    restore_bens_note(take, base, ben, reading_id)
    open_reader(take, base, ben, reading_id, wait_for=f"text={BEN_NOTE[:30]}")
    take.beat("on p. 12, Ben's note in the margin: start of the shot", start=True)
    take.pause(0.8)
    ask(take, QUESTION_4)
    wait_for_answer(take)
    card = page.locator(".answer-card")
    take.pause(0.6)
    take.glide_to(card.locator(".peer-item").first)
    take.beat("classmates")
    take.pause(1.8)
    skipped = card.locator("details.skipped summary")
    smooth_scroll_to(take, skipped)
    take.glide_to(skipped)
    take.beat("'N results skipped' (zoom here)")
    take.pause(2.2)
    link = card.locator(".source-item a").first
    take.glide_to(link)
    take.pause(0.4)
    with page.context.expect_page() as opened:
        take.click(link)
    source_page = opened.value
    take.beat("source link clicked (its page is saved as a separate video)")
    source_page.wait_for_load_state("domcontentloaded")
    source_page.wait_for_timeout(SOURCE_PAGE_SECONDS * 1000)
    take.extra.append((source_page, "shot 4 - the source page it opens"))
    source_page.close()
    page.bring_to_front()
    take.pause(0.5)
    ai_button = card.locator(".ai-button")
    smooth_scroll_to(take, ai_button)
    take.click(ai_button)
    explanation = card.locator(".ai-explanation")
    explanation.wait_for()
    take.beat("AI explanation open")
    smooth_scroll_to(take, explanation)
    take.glide_to(explanation)
    take.pause(5)
    take.beat("end of the shot")


def shot5(take, base, ben, reading_id):
    page = take.page
    restore_bens_note(take, base, ben, reading_id)
    open_reader(take, base, ben, reading_id, wait_for=f"text={BEN_NOTE[:30]}")
    take.beat("on p. 12: start of the shot", start=True)
    take.pause(0.8)
    ask(take, QUESTION_5)
    wait_for_answer(take)
    card = page.locator(".answer-card")
    take.pause(0.6)
    refusal = card.locator(".notice:has-text('No AI explanation')")
    if refusal.count():
        take.label = "shot 5B - refusal citing rule 2"
        smooth_scroll_to(take, refusal)
        take.glide_to(refusal)
        take.beat("refusal notice quoting rule 2 (zoom here)")
        take.pause(3)
        source = card.locator(".source-item").first
        smooth_scroll_to(take, source)
        take.glide_to(source)
        take.beat("sources still there")
        take.pause(3)
    else:
        take.label = "shot 5A - context-only explanation"
        ai_button = card.locator(".ai-button")
        smooth_scroll_to(take, ai_button)
        take.click(ai_button)
        explanation = card.locator(".ai-explanation")
        explanation.wait_for()
        smooth_scroll_to(take, explanation)
        take.glide_to(explanation)
        take.beat("explanation opens 'Under Rule 2, I won't…' (zoom here)")
        take.pause(5)
    take.beat("end of the shot")


def shot1(take, base, ben, reading_id):
    """The course home page as Ben: the seminar, its three readings, the charter card."""
    page = take.page
    page.goto(f"{base}/")
    page.get_by_text(READING_PREFIX).first.wait_for()
    take.pause(1)
    take.beat("course home: start of the shot", start=True)
    take.pause(1.5)
    for row in page.locator(".reading-card").all()[:3]:
        take.glide_to(row)
        take.pause(1.2)
    take.beat("readings")
    take.glide_to(page.get_by_text("Class charter").first)
    take.beat("charter card")
    take.pause(3)
    take.beat("end of the shot")


def shot2(take, base, ben, reading_id):
    """The charter as the professor sees it: rules (dwell on rule 2), sources, switches, then the proposals."""
    page = take.page
    page.goto(f"{base}/charter")
    page.locator("#rules").wait_for()
    take.pause(1)
    take.beat("charter page: start of the shot", start=True)
    take.pause(1.2)
    # Rule 2 is the textarea's second and third lines.
    rules = page.locator("#rules").bounding_box()
    line = page.locator("#rules").evaluate("(el) => parseFloat(getComputedStyle(el).lineHeight)")
    y2 = rules["y"] + 8 + line * 2
    take.glide(rules["x"] + 40, y2)
    take.pause(0.4)
    take.glide(rules["x"] + rules["width"] * 0.8, y2 + line * 0.6, curve=0.03)  # trace along rule 2
    take.beat("rule 2: 'It may not interpret the text for us' (zoom here)")
    take.pause(2.5)
    take.glide_to(page.locator("#sources"))
    take.beat("sources we trust")
    take.pause(2)
    take.glide_to(page.get_by_text("Switches").first)
    take.beat("switches")
    take.pause(2)
    added = page.get_by_text("Added to the charter").first
    added.evaluate("(el) => el.scrollIntoView({behavior: 'smooth', block: 'center'})")
    take.pause(1.2)
    take.glide_to(added)
    take.beat("Ana's proposal, added to the charter (rule 5)")
    take.pause(3)
    take.beat("end of the shot")


SHOTS = {"shot1": shot1, "shot2": shot2, "shot3": shot3, "shot4": shot4, "shot5": shot5}
# Who each shot is logged in as (default Ben).
SHOT_USER = {"shot2": "Prof. Rivera"}
# File names, matching demo/video-shot-list.md.
LABELS = {"shot1": "shot 1 - course home",
          "shot2": "shot 2 - the class charter",
          "shot3": "shot 3 - Ben unlocks the notes",
          "shot4": "shot 4 - Ben asks, classmates then sources then AI",
          "shot5": "shot 5"}  # shot 5 names itself 5A or 5B from what the copy answered


def to_mp4(webm, mp4, start):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{start:.2f}", "-i", str(webm), "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-crf", "18", str(mp4)], check=True)


def record(name, base, headed, cursor):
    from playwright.sync_api import sync_playwright
    ben, reading_id = setup(base)
    reset_ben(base, ben, reading_id)
    who = SHOT_USER.get(name)
    viewer = ben if not who else [u for u in api(base, "GET", "/api/users", 1)
                                  if u["name"] == who and u["course_title"] == SEMINAR][0]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_dir = Path(tempfile.mkdtemp(prefix="demo-take-"))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(viewport=VIEWPORT, 
                                      record_video_dir=str(raw_dir),
                                      record_video_size=VIEWPORT)
        if cursor:
            context.add_init_script(CURSOR_JS.replace('SMOOTHING', str(SMOOTHING)))
        # "Log in as Ben" the way the log-in page does: the user object in localStorage.
        context.add_init_script(f"localStorage.setItem('dialectic_user', {json.dumps(json.dumps(viewer))});")
        page = context.new_page()
        print(f"Recording {name} against {base}")
        take = Take(page)
        SHOTS[name](take, base, ben, reading_id)
        context.close()  # finishes writing the videos
        webm = Path(page.video.path())
        extra = [(Path(p.video.path()), label) for p, label in take.extra]
        browser.close()
    reset_ben(base, ben, reading_id)  # leave the copy as prepared
    copy = "dev" if "dialectic-dev" in base else "laptop"
    tag = f"({copy}{'' if cursor else ', no cursor'}) {time.strftime('%H%M')}"
    mp4 = OUT_DIR / f"{take.label or LABELS[name]} {tag}.mp4"
    # The cursor's path, in seconds from the start of the saved video, to redraw it in an editor.
    track = [{"t": round(t - take.start, 3), "event": e, "x": x, "y": y} for t, e, x, y in take.track if t >= take.start]
    mp4.with_suffix(".cursor.json").write_text(json.dumps({"video": mp4.name, "size": VIEWPORT, "track": track}))
    to_mp4(webm, mp4, take.start)
    for extra_webm, label in extra:
        extra_mp4 = OUT_DIR / f"{label} {tag}.mp4"
        to_mp4(extra_webm, extra_mp4, 0)
        print(f"Saved {extra_mp4}")
    shutil.rmtree(raw_dir)
    print(f"Saved {mp4}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("shot", choices=sorted(SHOTS))
    parser.add_argument("--base", default=BASE)
    parser.add_argument("--headed", action="store_true", help="show the browser window while recording")
    parser.add_argument("--no-cursor", action="store_true", help="don't draw a cursor (its path is still saved)")
    args = parser.parse_args()
    record(args.shot, args.base.rstrip("/"), args.headed, cursor=not args.no_cursor)
