"""Everything that talks to the LLM, plus the charter's code-level checks (SPEC §7).

Privacy rule: the functions here take only text (charter, quote, question, reading title,
source text). They never receive a user, an id or anyone else's annotation, so nothing
personal can end up in a prompt. (The `meter` they pass along is spend.Meter: it checks the
spending limits and records costs in the database; nothing from it goes into a prompt.)
"""
import hashlib
import json
import os
import re

import httpx

TEMPERATURE = 0.2
# What the model costs (SPEC §9.1): Claude Sonnet 5.5 on DigitalOcean, USD per million tokens.
LLM_USD_PER_MTOK_IN = 2.00
LLM_USD_PER_MTOK_OUT = 10.00
TIMEOUT_S = 30
EMPTY_REPLY_RETRIES = 1  # see chat()
CONTEXT_CHARS = 1500  # the explanation sees this much text either side of each verified sentence
EXPLAIN_WORD_MARGIN = 20  # ask the model for this many words fewer than the charter's maximum
# Reasoning effort per call: None = the model's default (full reasoning), or "low" (DO's
# reasoning_effort; "none" isn't supported). By default the model reasons in ~700-1,300 hidden
# tokens before answering, which is most of each call's time. Change one word to switch a call.
# Measured 03:00 Sat on the source filter: low ~4 s but dropped allowed sources 1 run in 3;
# full ~8.5 s and consistent. Sentence picking is safe at low: a wrong sentence is caught by
# the substring check in pick_sentences, and a missed one only drops that source.
GATE_EFFORT = None
FILTER_EFFORT = None
PICK_EFFORT = "low"
EXPLAIN_EFFORT = None

# Structured output: the API forces the reply into a schema. Without it, at low effort the model
# sometimes "thinks out loud" after its JSON ("Wait, corrections needed...") and the parse fails.
FILTER_DECISIONS = ["keep", "ruled_out", "not_covered", "off_topic"]
USEFULNESS = ["high", "medium", "low", "none"]  # kept results are tried in this order, then search order


def filter_schema(n_results):
    """One decision per search result, in order: the schema forces exactly n_results entries."""
    decision = {
        "type": "object", "additionalProperties": False, "required": ["n", "decision", "usefulness", "kind"],
        "properties": {"n": {"type": "integer"}, "decision": {"type": "string", "enum": FILTER_DECISIONS},
                       "usefulness": {"type": "string", "enum": USEFULNESS}, "kind": {"type": "string"}},
    }
    return {
        "type": "object", "additionalProperties": False, "required": ["decisions"],
        "properties": {"decisions": {"type": "array", "items": decision, "minItems": n_results, "maxItems": n_results}},
    }


PICK_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["sentences"],
    "properties": {"sentences": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["n", "sentence"],
        "properties": {"n": {"type": "integer"}, "sentence": {"type": "string"}},
    }}},
}

# What the student sees for a skipped result; {kind} is the filter's label, e.g. "study-guide sites".
RULED_OUT_REASON = "Your charter rules out {kind}"
NOT_COVERED_REASON = "Your charter doesn't mention {kind}"


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

The class is reading "{reading_title}". A student asks: "{question}"

Web search results:

{results}

Give each result, in order, exactly one decision:
- keep: a kind of source the description allows, AND it helps answer the question.
  Rate how much it helps as usefulness: high, medium or low.
- ruled_out: the description EXPLICITLY excludes this kind of source, by name or by kind
  (e.g. "no study-guide sites"), or allows it only for other kinds of questions.
- not_covered: the description neither allows nor excludes this kind of source; it just
  doesn't mention it (e.g. blog posts, when the description never mentions blogs).
- off_topic: an allowed kind of source that doesn't help with this question. A copy of the
  reading itself is off_topic: the student already has it.

For every result, also name its kind of source as a short plural phrase a student would
understand, e.g. "study-guide sites", "journal articles", "blog posts". Give usefulness
"none" for anything that isn't kept."""

PICK_SENTENCE_PROMPT = """A student asks: "{question}" about this passage: "{quote}"

For each numbered source below, copy the ONE sentence that best helps answer the question.
Copy it exactly, character for character, from that source's text. If a source has no useful
sentence, leave it out.

{sources}

Reply with JSON only: {{"sentences": [{{"n": 1, "sentence": "..."}}]}}"""

EXPLAIN_PROMPT = """You are a teaching assistant bound by this class charter:

<charter>
{charter}
</charter>

A student reading "{reading_title}" highlighted: "{quote}"
They ask: "{question}"

Using only the numbered sources below, give historical and cultural context in at most
{max_words} words. Cite sources as [1], [2]. Don't interpret the passage for the student and
don't suggest a thesis. Don't end with a question, and don't suggest what they should ask or
think about next.

Write plain text: no Markdown, no headings, no label (the app already marks this as AI).
Stay on the student's question. If a source has nothing relevant, just don't cite it.

{sources}

Reply with the explanation text only."""


# ---------- the one LLM call ----------

def chat(system, user, meter, effort=None, schema=None):
    """One chat completion. effort: None (the model's default) or a reasoning_effort like "low".
    schema: a JSON schema the reply must follow (structured output).

    The model very occasionally replies with nothing at all (about 1 in 20 structured calls on
    Saturday), so an empty reply is retried once. Nothing else is retried: errors raise."""
    for attempt in range(1 + EMPTY_REPLY_RETRIES):
        text = chat_once(system, user, meter, effort, schema)
        if text:
            return text
        print(f"empty reply from the model (attempt {attempt + 1}), asking again")
    raise RuntimeError(f"The model returned an empty reply {1 + EMPTY_REPLY_RETRIES} times")


def chat_once(system, user, meter, effort, schema):
    """One paid model call: check the spending limits first (raises spend.LimitReached),
    then record its cost from the reply's token counts."""
    url = os.environ.get("DO_INFERENCE_URL")
    key = os.environ.get("DO_INFERENCE_KEY")
    model = os.environ.get("DO_MODEL")
    if not (url and key and model):
        raise RuntimeError(
            "DO_INFERENCE_URL, DO_INFERENCE_KEY and DO_MODEL must be set (put them in .env), "
            "or turn off 'AI enabled' in the charter"
        )
    meter.check("ai")
    resp = httpx.post(
        f"{url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "temperature": TEMPERATURE,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            **({"reasoning_effort": effort} if effort else {}),
            **({"response_format": {"type": "json_schema", "json_schema": {"name": "reply", "strict": True, "schema": schema}}}
               if schema else {}),
        },
        timeout=TIMEOUT_S,
    )
    resp.raise_for_status()
    data = resp.json()
    tokens_in, tokens_out = data["usage"]["prompt_tokens"], data["usage"]["completion_tokens"]
    meter.record("ai", tokens_in + tokens_out,
                 (tokens_in * LLM_USD_PER_MTOK_IN + tokens_out * LLM_USD_PER_MTOK_OUT) / 1_000_000)
    return (data["choices"][0]["message"]["content"] or "").strip()


def chat_json(conn, meter, prompt, effort=None, schema=None):
    """Ask for JSON and parse it. A reply that isn't JSON raises (fail loudly, SPEC §7).

    Cached in web_cache by the exact prompt (DEMO safety and speed): the same question replays
    the same gate verdict, search query, filter and sentences in a second or two. Any change
    to the inputs (charter text, question, search results) is a new prompt, so it runs fresh.
    """
    key = "llm:" + hashlib.sha256(f"{effort}|{json.dumps(schema)}|{prompt}".encode()).hexdigest()
    row = conn.execute("SELECT value FROM web_cache WHERE key = ?", (key,)).fetchone()
    if row:
        return json.loads(row["value"])
    text = chat("You reply with JSON only, no prose.", prompt, meter, effort=effort, schema=schema)
    # Models often wrap JSON in a ```json fence; that's formatting, not an error.
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM didn't return JSON: {text[:500]!r}") from e
    conn.execute(
        "INSERT OR REPLACE INTO web_cache (key, value, created_at) VALUES (?, ?, datetime('now'))",
        (key, json.dumps(parsed)),
    )
    conn.commit()
    return parsed


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

def gate(conn, meter, charter_text, reading_title, quote, question):
    return chat_json(conn, meter, GATE_PROMPT.format(
        charter=charter_text, reading_title=reading_title, quote=quote, question=question,
    ), effort=GATE_EFFORT)


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

def filter_sources(conn, meter, permissible_sources, reading_title, question, results):
    """A simple decision per search result: keep / ruled_out / not_covered / off_topic.

    results: [{title, url, snippet}]. Returns, with 0-based indexes:
    {"keep": [most useful first], "skipped": [{"index", "why", "reason"}]}, where why is
    "not_permitted" (the charter rules it out) or "not_covered" (the charter doesn't mention it).
    Off-topic results are simply left out.
    """
    numbered = "\n\n".join(
        f"[{n}] {r['title']}\nURL: {r['url']}\n{r['snippet']}" for n, r in enumerate(results, start=1)
    )
    reply = chat_json(conn, meter, FILTER_SOURCES_PROMPT.format(
        permissible_sources=permissible_sources, reading_title=reading_title, question=question, results=numbered,
    ), effort=FILTER_EFFORT, schema=filter_schema(len(results)))
    keep, skipped = [], []
    for item in reply["decisions"]:
        index = item["n"] - 1
        if not 0 <= index < len(results):
            continue
        if item["decision"] == "keep":
            keep.append((USEFULNESS.index(item["usefulness"]), index))
        elif item["decision"] == "ruled_out":
            skipped.append({"index": index, "why": "not_permitted", "kind": item["kind"],
                            "reason": RULED_OUT_REASON.format(kind=item["kind"])})
        elif item["decision"] == "not_covered":
            skipped.append({"index": index, "why": "not_covered", "kind": item["kind"],
                            "reason": NOT_COVERED_REASON.format(kind=item["kind"])})
    return {"keep": [index for _, index in sorted(keep)], "skipped": skipped}


def normalize_space(text):
    return re.sub(r"\s+", " ", text).strip()


def pick_sentences(conn, meter, question, quote, sources):
    """sources: [{title, text}]. Returns {index: sentence}, keeping only sentences really in the source."""
    numbered = "\n\n".join(
        f"[{n}] {s['title']}\n{s['text'][:6000]}" for n, s in enumerate(sources, start=1)
    )
    reply = chat_json(conn, meter, PICK_SENTENCE_PROMPT.format(question=question, quote=quote, sources=numbered),
                      effort=PICK_EFFORT, schema=PICK_SCHEMA)
    picked = {}
    for item in reply["sentences"]:
        index = item["n"] - 1
        if not 0 <= index < len(sources):
            continue
        sentence = normalize_space(item["sentence"])
        # The model must quote, not paraphrase: drop anything not literally in the source.
        if sentence and sentence in normalize_space(sources[index]["text"]):
            picked[index] = sentence
    return picked


def around_sentence(text, sentence):
    """The text either side of `sentence` (whitespace normalised, as pick_sentences checked it)."""
    flat = normalize_space(text)
    at = flat.find(sentence)
    if at == -1:  # pick_sentences only keeps sentences it found, so this is a bug: fail loudly
        raise ValueError(f"Verified sentence not in its source: {sentence[:80]!r}")
    return flat[max(0, at - CONTEXT_CHARS): at + len(sentence) + CONTEXT_CHARS]


def explain(conn, meter, charter_text, reading_title, quote, question, sources, max_words):
    """sources: [{title, text, sentence}], cited as [1], [2] in this order. Each source is shown to
    the model as the text around its verified sentence, so the answer is grounded in what we checked.
    Returns the explanation, at most max_words.

    Cached in web_cache by the exact prompt, like chat_json: a replayed question gets the same
    explanation, word for word, for free (so it doesn't count against the device limit either)."""
    numbered = "\n\n".join(
        f"[{n}] {s['title']}\n{around_sentence(s['text'], s['sentence'])}" for n, s in enumerate(sources, start=1)
    )
    # Models overshoot word limits, so ask for a bit less than the charter's maximum.
    target = max(40, max_words - EXPLAIN_WORD_MARGIN)
    prompt = EXPLAIN_PROMPT.format(
        charter=charter_text, reading_title=reading_title, quote=quote, question=question,
        max_words=target, sources=numbered,
    )
    key = "llm:" + hashlib.sha256(f"explain|{EXPLAIN_EFFORT}|{prompt}".encode()).hexdigest()
    row = conn.execute("SELECT value FROM web_cache WHERE key = ?", (key,)).fetchone()
    if row:
        return cut_to_words(json.loads(row["value"]), max_words)
    text = chat("You are a careful teaching assistant.", prompt, meter, effort=EXPLAIN_EFFORT)
    conn.execute(
        "INSERT OR REPLACE INTO web_cache (key, value, created_at) VALUES (?, ?, datetime('now'))",
        (key, json.dumps(text)),
    )
    conn.commit()
    return cut_to_words(text, max_words)


def cut_to_words(text, max_words):
    """Enforce the charter's word limit by cutting the explanation short."""
    if len(text.split()) <= max_words:
        return text
    return " ".join(text.split()[:max_words]) + "…"
