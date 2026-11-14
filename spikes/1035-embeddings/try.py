"""Spike: does DO inference's embedding API find reading paragraphs by meaning? Run from repo root."""
import json, math, os, sqlite3, sys, time, httpx
from dotenv import load_dotenv
load_dotenv(".env")
URL = os.environ["DO_INFERENCE_URL"] + "/embeddings"
KEY = os.environ["DO_INFERENCE_KEY"]
QUERIES = ["feeling like two people at once", "being seen through other people's eyes",
           "money and economic exploitation after emancipation", "education as a path to freedom"]

def embed(model, texts):
    r = httpx.post(URL, headers={"Authorization": f"Bearer {KEY}"}, json={"model": model, "input": texts}, timeout=60)
    r.raise_for_status()
    return [d["embedding"] for d in r.json()["data"]]

def cos(a, b):
    return sum(x*y for x, y in zip(a, b)) / math.sqrt(sum(x*x for x in a) * sum(y*y for y in b))

conn = sqlite3.connect("app/backend/dialectic.db")
rows = conn.execute("SELECT reading_id, page, text FROM pages_fts ORDER BY reading_id, page").fetchall()
reading = rows[0][0]
chunks = []  # paragraphs ~ split on blank lines, merged up to ~800 chars
for rid, page, text in rows:
    if rid != reading: continue
    import re
    buf = ""
    for sent in re.split(r"(?<=[.!?;])\s+", text.replace("\n", " ")):
        buf += sent + " "
        if len(buf) > 400:
            chunks.append((page, buf.strip())); buf = ""
    if buf.strip(): chunks.append((page, buf.strip()))
print(f"reading {reading}: {len(chunks)} chunks")
for model in sys.argv[1:]:
    t = time.time(); vecs = []
    for i in range(0, len(chunks), 32):
        vecs += embed(model, [c[1] for c in chunks[i:i+32]])
    print(f"\n== {model}: indexed in {time.time()-t:.1f}s")
    for q in QUERIES:
        qv = embed(model, [q])[0]
        best = sorted(range(len(chunks)), key=lambda i: -cos(qv, vecs[i]))[:2]
        print(f"  Q: {q}")
        for i in best:
            print(f"    p{chunks[i][0]} {cos(qv, vecs[i]):.2f} {chunks[i][1][:110]!r}")
