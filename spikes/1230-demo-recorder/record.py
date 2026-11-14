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
GLIDE_STEPS = 18          # mouse-move steps per glide: more = slower, smoother cursor
SEMINAR = "PHIL 247: The Social Contract (seminar)"
READING_PREFIX = "Week 2"

GENERAL_WILL_START = "Each of us puts"
GENERAL_WILL_END_AFTER = "direction of the general"   # the sentence ends at the next "will"
BEN_NOTE = ("Wait, so I'm both the one giving orders and the one obeying them? "
            "Where did he get this idea of a will that belongs to everyone?")
SAM_NOTE_START = "Last spring we spent"               # appears once Ben's note is saved

# A drawn cursor: recordings don't show the real pointer. Follows mouse events, pulses on press.
CURSOR_JS = """
window.addEventListener('DOMContentLoaded', () => {
  const c = document.createElement('div');
  c.id = 'demo-cursor';
  c.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 2l15 11-7 1.2L8.6 21z" fill="#111" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/></svg>';
  Object.assign(c.style, {position: 'fixed', left: '-40px', top: '-40px', zIndex: 2147483647,
    pointerEvents: 'none', transition: 'transform 120ms ease', transformOrigin: '4px 2px'});
  document.body.appendChild(c);
  const move = (e) => { c.style.left = (e.clientX - 4) + 'px'; c.style.top = (e.clientY - 2) + 'px'; };
  window.addEventListener('mousemove', move, true);
  window.addEventListener('mousedown', () => { c.style.transform = 'scale(0.82)'; }, true);
  window.addEventListener('mouseup', () => { c.style.transform = 'scale(1)'; }, true);
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
        if a.get("author", {}).get("id") == ben["id"] and not a.get("parent_id"):
            api(base, "DELETE", f"/api/annotations/{a['id']}", ben["id"])


# ---------- recording helpers

class Take:
    def __init__(self, page):
        self.page = page
        self.t0 = time.monotonic()
        self.start = 0.0
        self.x, self.y = VIEWPORT["width"] * 0.6, VIEWPORT["height"] * 0.5

    def beat(self, label, start=False):
        """Print when this happens. start=True also marks where the saved video begins (loading is cut)."""
        if start:
            self.start = time.monotonic() - self.t0
        print(f"  {time.monotonic() - self.t0 - self.start:6.1f} s  {label}", flush=True)

    def glide(self, x, y, steps=GLIDE_STEPS):
        self.page.mouse.move(x, y, steps=steps)
        self.x, self.y = x, y

    def glide_to(self, locator, steps=GLIDE_STEPS):
        box = locator.bounding_box()
        self.glide(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps)

    def click(self, locator):
        self.glide_to(locator)
        self.page.wait_for_timeout(150)
        self.page.mouse.down()
        self.page.wait_for_timeout(90)
        self.page.mouse.up()

    def pause(self, seconds):
        self.page.wait_for_timeout(int(seconds * 1000))


def open_reader(take, base, ben, reading_id):
    page = take.page
    page.goto(f"{base}/readings/{reading_id}")
    page.wait_for_selector('.pdf-page[data-page="12"] .textLayer span', timeout=60000)
    # Jump straight to the passage (off camera: trim up to the "on p. 12" beat).
    spot = page.evaluate(RANGE_JS, [12, GENERAL_WILL_START, GENERAL_WILL_END_AFTER, "will"])
    page.evaluate("""(y) => { const col = document.querySelector('.pdf-column');
                              col.scrollTop += y - col.clientHeight * 0.32; }""", spot["center"])
    page.wait_for_selector(".lock-card")
    take.pause(1.5)  # let the margin settle on p. 12


def select_passage(take):
    spot = take.page.evaluate(RANGE_JS, [12, GENERAL_WILL_START, GENERAL_WILL_END_AFTER, "will"])
    take.glide(spot["x0"], spot["y0"])
    take.pause(0.3)
    take.page.mouse.down()
    take.glide(spot["x1"], spot["y1"], steps=24)
    take.page.mouse.up()


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
    take.glide_to(page.get_by_text(SAM_NOTE_START).first, steps=50)
    take.pause(4)
    take.beat("end of the shot")


SHOTS = {"shot3": shot3}
# File names, matching demo/video-shot-list.md.
LABELS = {"shot3": "shot 3 - Ben unlocks the notes"}


def record(name, base, headed):
    from playwright.sync_api import sync_playwright
    ben, reading_id = setup(base)
    reset_ben(base, ben, reading_id)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_dir = Path(tempfile.mkdtemp(prefix="demo-take-"))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(viewport=VIEWPORT, 
                                      record_video_dir=str(raw_dir),
                                      record_video_size=VIEWPORT)
        context.add_init_script(CURSOR_JS)
        # "Log in as Ben" the way the log-in page does: the user object in localStorage.
        context.add_init_script(f"localStorage.setItem('dialectic_user', {json.dumps(json.dumps(ben))});")
        page = context.new_page()
        print(f"Recording {name} against {base}")
        take = Take(page)
        SHOTS[name](take, base, ben, reading_id)
        context.close()  # finishes writing the video
        webm = Path(page.video.path())
        browser.close()
    mp4 = OUT_DIR / f"{LABELS[name]} - {time.strftime('%H%M')}.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{take.start:.2f}", "-i", str(webm), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "18", str(mp4)], check=True)
    shutil.rmtree(raw_dir)
    print(f"Saved {mp4}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("shot", choices=sorted(SHOTS))
    parser.add_argument("--base", default=BASE)
    parser.add_argument("--headed", action="store_true", help="show the browser window while recording")
    args = parser.parse_args()
    record(args.shot, args.base.rstrip("/"), args.headed)
