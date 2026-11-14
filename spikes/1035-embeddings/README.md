Tests whether DO inference (same URL and key as the LLM) can embed reading text for semantic search.
Result: yes. `POST $DO_INFERENCE_URL/embeddings` (OpenAI shape) works with bge-m3, gte-large-en-v1.5,
qwen3-embedding-0.6b (1024 dims) and multi-qa-mpnet-base-dot-v1 (768). Du Bois ch. 1 in ~400-char chunks = 40
chunks, indexed in ~1.5 s. bge-m3 was best on paraphrase queries ("being seen through other people's
eyes" → the "second-sight… through the eyes of others" passage; "feeling like two people" → "twoness").
Run: `app/backend/.venv/bin/python spikes/1035-embeddings/try.py bge-m3`
