"""Everything that talks to the LLM, plus the charter's code-level checks (SPEC §7).

Privacy rule: the functions here take only text (charter, quote, question, reading title,
source text). They never receive a user, an id or anyone else's annotation, so nothing
personal can end up in a prompt.
"""
import json
import os
import re

import httpx

TEMPERATURE = 0.2
TIMEOUT_S = 30
MAX_FILTER_KEEP = 5  # spares: ask.py stops after MAX_WEB_SOURCES pages that actually open

# Shown to the student when a toggle blocks a layer (SPEC §2 step 4).
TOGGLE_LABELS = {
    "ai_enabled": "AI enabled — off",
    "ai_find_sources": "AI may find sources — off",
    "ai_explanations": "AI may write explanations — off",
}

GATE_PROMPT = """You enforce a class's AI charter. The class wrote these rules together:

<charter>
{charter}
</charter>

A student reading "{reading_title}" highlighted this passage:
<quote>{quote}</quote>

They ask: <question>{question}</question>

Decide, for each AI action, whether the charter allows it FOR THIS REQUEST:
- find_sources: search the web for sources relevant to the question.
- explain: write a short contextual explanation for the student, based on those sources.

Judge what the request actually asks for, not just its wording. If a rule forbids it, say which
rule (by its number) and why, in one plain sentence addressed to the student. When unsure, deny:
friction is the point of this class.

Also write search_query: a short web search query (under 10 words) that would find scholarly
sources for this question. Use only words about the topic; nothing about the student.

Reply with JSON only, exactly this shape:
{{"find_sources": {{"allowed": true, "rule": null, "reason": "..."}},
  "explain": {{"allowed": false, "rule": "2", "reason": "..."}},
  "search_query": "..."}}"""

FILTER_SOURCES_PROMPT = """A class only uses sources that fit this description, which they wrote together:

<permissible_sources>
{permissible_sources}
</permissible_sources>

Here are web search results for a student's question "{question}":

{results}

Keep at most {max_keep} results that fit the description AND look useful for the question, best
first. For every result you don't keep because it doesn't fit the description, give a short reason
a student would understand (e.g. "Study-guide sites aren't permitted"). Results you drop only
because they're less useful don't need a reason.

Reply with JSON only: {{"keep": [3, 1], "skipped": [{{"n": 5, "reason": "..."}}]}}"""

PICK_SENTENCE_PROMPT = """A student asks: "{question}" about this passage: "{quote}"

For each numbered source below, copy the ONE sentence that best helps answer the question.
Copy it exactly, character for character, from that source's text. If a source has no useful
sentence, leave it out.

{sources}

Reply with JSON only: [{{"n": 1, "sentence": "..."}}]"""

EXPLAIN_PROMPT = """You are a teaching assistant bound by this class charter:

<charter>
{charter}
</charter>

A student reading "{reading_title}" highlighted: "{quote}"
They ask: "{question}"

Using only the numbered sources below, give historical and cultural context in at most
{max_words} words. Cite sources as [1], [2]. Don't interpret the passage for the student and
don't suggest a thesis. End with one question that sends them back to the text.

{sources}

Reply with the explanation text only."""


# ---------- the one LLM call ----------

def chat(system, user):
    url = os.environ.get("DO_INFERENCE_URL")
    key = os.environ.get("DO_INFERENCE_KEY")
    model = os.environ.get("DO_MODEL")
    if not (url and key and model):
        raise RuntimeError(
            "DO_INFERENCE_URL, DO_INFERENCE_KEY and DO_MODEL must be set (put them in .env), "
            "or turn off 'AI enabled' in the charter"
        )
    resp = httpx.post(
        f"{url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "temperature": TEMPERATURE,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        },
        timeout=TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def chat_json(prompt):
    """Ask for JSON and parse it. A reply that isn't JSON raises (fail loudly, SPEC §7)."""
    text = chat("You reply with JSON only, no prose.", prompt)
    # Models often wrap JSON in a ```json fence; that's formatting, not an error.
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM didn't return JSON: {text[:500]!r}") from e


# ---------- pass 0: toggles, checked in code ----------

def toggle_blocks(charter):
    """Which AI layers the toggles rule out, before any LLM call.

    Returns (can_find_sources, can_explain, blocked) where blocked is the list of
    {layer, by, label} entries for the /ask response.
    """
    if not charter["ai_enabled"]:
        label = TOGGLE_LABELS["ai_enabled"]
        return False, False, [
            {"layer": "sources_ai", "by": "toggle", "label": label},
            {"layer": "ai_answer", "by": "toggle", "label": label},
        ]
    blocked = []
    if not charter["ai_find_sources"]:
        blocked.append({"layer": "sources_ai", "by": "toggle", "label": TOGGLE_LABELS["ai_find_sources"]})
    if not charter["ai_explanations"]:
        blocked.append({"layer": "ai_answer", "by": "toggle", "label": TOGGLE_LABELS["ai_explanations"]})
    return bool(charter["ai_find_sources"]), bool(charter["ai_explanations"]), blocked


# ---------- pass 1: the gate ----------

def gate(charter_text, reading_title, quote, question):
    return chat_json(GATE_PROMPT.format(
        charter=charter_text, reading_title=reading_title, quote=quote, question=question,
    ))


def rule_label(charter_text, rule):
    """'Rule 2: AI may point us to sources...' from the rule number the gate cited."""
    if not rule:
        return "The class charter"
    number = str(rule).strip().rstrip(".")
    for line in charter_text.splitlines():
        if line.strip().startswith(f"{number}."):
            return f"Rule {number}: {line.strip()[len(number) + 1:].strip()}"
    return f"Rule {number}"


# ---------- pass 2: sources and explanation ----------

def filter_sources(permissible_sources, question, results):
    """results: [{title, url, snippet}]. Returns {"keep": [indexes], "skipped": [{"index", "reason"}]}, 0-based."""
    numbered = "\n\n".join(
        f"[{n}] {r['title']}\nURL: {r['url']}\n{r['snippet']}" for n, r in enumerate(results, start=1)
    )
    reply = chat_json(FILTER_SOURCES_PROMPT.format(
        permissible_sources=permissible_sources, question=question, results=numbered, max_keep=MAX_FILTER_KEEP,
    ))
    keep = [n - 1 for n in reply["keep"] if 1 <= n <= len(results)][:MAX_FILTER_KEEP]
    skipped = [{"index": s["n"] - 1, "reason": s["reason"]} for s in reply.get("skipped", []) if 1 <= s["n"] <= len(results)]
    return {"keep": keep, "skipped": skipped}


def normalize_space(text):
    return re.sub(r"\s+", " ", text).strip()


def pick_sentences(question, quote, sources):
    """sources: [{title, text}]. Returns {index: sentence}, keeping only sentences really in the source."""
    numbered = "\n\n".join(
        f"[{n}] {s['title']}\n{s['text'][:6000]}" for n, s in enumerate(sources, start=1)
    )
    reply = chat_json(PICK_SENTENCE_PROMPT.format(question=question, quote=quote, sources=numbered))
    picked = {}
    for item in reply:
        index = item["n"] - 1
        if not 0 <= index < len(sources):
            continue
        sentence = normalize_space(item["sentence"])
        # The model must quote, not paraphrase: drop anything not literally in the source.
        if sentence and sentence in normalize_space(sources[index]["text"]):
            picked[index] = sentence
    return picked


def explain(charter_text, reading_title, quote, question, sources, max_words):
    """sources: [{title, text}], cited as [1], [2] in this order. Returns the explanation, cut to max_words."""
    numbered = "\n\n".join(
        f"[{n}] {s['title']}\n{s['text'][:4000]}" for n, s in enumerate(sources, start=1)
    )
    text = chat("You are a careful teaching assistant.", EXPLAIN_PROMPT.format(
        charter=charter_text, reading_title=reading_title, quote=quote, question=question,
        max_words=max_words, sources=numbered,
    ))
    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words]) + "…"
    return text
