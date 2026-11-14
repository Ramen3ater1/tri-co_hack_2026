import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { get } from '../api.js';
import NavHeader from '../components/NavHeader.jsx';
import Avatar from '../components/Avatar.jsx';
import ErrorNotice from '../components/ErrorNotice.jsx';

// S15: full-text search over the notes you can see and the readings' text. Snippets mark
// hits as [[word]]; we split the string and wrap hits in <mark>, never innerHTML
// (annotation bodies are user input). Locked notes never appear (the server leaves them out).
// "Meaning (AI)" mode finds reading passages by meaning instead (SPEC §3.8), if the charter's
// ai_semantic_search switch allows it; it searches the readings only, never notes.

function Snippet({ text, serif }) {
  const parts = text.split(/\[\[|\]\]/);
  return (
    <span className={`snippet${serif ? ' serif' : ''}`}>
      {parts.map((part, i) => (i % 2 === 1 ? <mark key={i}>{part}</mark> : part))}
    </span>
  );
}

const KIND_WORDS = { note: 'note', question: 'question', ai_answer: 'AI explanation' };

export default function Search() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') || '';
  const meaning = params.get('mode') === 'meaning';
  const [query, setQuery] = useState(q);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!q) {
      setResults(null);
      return;
    }
    setError(null);
    setResults(null);
    get(`/search?q=${encodeURIComponent(q)}${meaning ? '&mode=meaning' : ''}`).then(setResults).catch(setError);
  }, [q, meaning]);

  function search(event) {
    event.preventDefault();
    if (query.trim()) setParams({ q: query.trim(), ...(meaning ? { mode: 'meaning' } : {}) });
  }

  function setMode(toMeaning) {
    const next = {};
    if (query.trim()) next.q = query.trim();
    if (toMeaning) next.mode = 'meaning';
    setParams(next);
  }

  // Results of the other mode can briefly remain while the new search loads: check their shape.
  const wordResults = results && !meaning && results.annotations ? results : null;
  const meaningResults = results && meaning && results.passages ? results : null;
  const empty = (wordResults && wordResults.annotations.length === 0 && wordResults.pages.length === 0)
    || (meaningResults && !meaningResults.blocked && meaningResults.passages.length === 0);

  return (
    <>
      <NavHeader />
      <div className="page-body">
        <div className="page-title"><h1>Search the class's notes and readings</h1></div>
        <form className="search-form" onSubmit={search} role="search">
          <label htmlFor="q" className="visually-hidden">Search</label>
          <input id="q" className="input" type="search" autoFocus value={query} onChange={(e) => setQuery(e.target.value)} />
          <button type="submit" className="btn dark">Search</button>
        </form>
        <div className="select-toggle search-mode" role="radiogroup" aria-label="Search by">
          <button type="button" role="radio" aria-checked={!meaning} title="Find these words in notes and readings" onClick={() => setMode(false)}>
            Words
          </button>
          <button type="button" role="radio" aria-checked={meaning} title="AI finds passages in the readings that mean something like this, even in other words" onClick={() => setMode(true)}>
            Meaning (AI)
          </button>
        </div>
        <ErrorNotice error={error} title="Search failed" />

        {empty && (
          <div className="empty">
            <strong style={{ display: 'block', color: 'var(--ink)' }}>Nothing found for “{q}”</strong>
            {meaning
              ? 'Meaning search covers the readings only, not notes. Try describing the idea in other words.'
              : "Search covers the readings and the notes you can see. Notes still locked for you aren't searched."}
          </div>
        )}

        {meaningResults && meaningResults.blocked && (
          <div className="empty">
            <strong style={{ display: 'block', color: 'var(--ink)' }}>Meaning search is off</strong>
            {meaningResults.blocked.by === 'toggle'
              ? <>Your class charter has it switched off ({meaningResults.blocked.label}). <Link to="/charter">See the charter</Link>, or search by words.</>
              : meaningResults.blocked.label}
          </div>
        )}

        {meaningResults && meaningResults.passages.length > 0 && (
          <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <h2 className="section-label">Passages close in meaning · {meaningResults.passages.length}</h2>
            <div className="card list-card">
              {meaningResults.passages.map((p, i) => (
                <Link key={i} className="result" to={`/readings/${p.reading_id}?page=${p.page}`}>
                  <span className="what">
                    <span className="muted small">{p.reading_title} · p. {p.page}</span>
                    <span className="snippet serif">{p.text}</span>
                  </span>
                </Link>
              ))}
            </div>
            <span className="muted small">Found by AI from the readings only, closest first. Notes aren't searched this way.</span>
          </section>
        )}

        {wordResults && wordResults.annotations.length > 0 && (
          <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <h2 className="section-label">Notes and questions · {wordResults.annotations.length}</h2>
            <div className="card list-card">
              {wordResults.annotations.map((a) => (
                <Link key={a.annotation_id} className="result" to={`/readings/${a.reading_id}?page=${a.page}&annotation=${a.annotation_id}`}>
                  <Avatar person={{ id: a.author_id, name: a.author, role: a.badge === 'Professor' ? 'professor' : a.badge === 'AI' ? 'ai' : 'student' }} size="small" />
                  <span className="what">
                    <span className="muted small">
                      <strong style={{ color: 'var(--ink)' }}>{a.author}</strong>
                      {a.badge && a.badge !== 'Professor' && a.badge !== 'AI' && ` · ${a.badge}`}
                      {` · ${KIND_WORDS[a.kind] || a.kind}`}
                      {a.via === 'hotkey' && ' via Mac hotkey'}
                      {` · ${a.reading_title}, p. ${a.page}`}
                    </span>
                    <Snippet text={a.snippet} />
                  </span>
                </Link>
              ))}
            </div>
            <span className="muted small">Notes you haven't unlocked yet don't appear here.</span>
          </section>
        )}

        {wordResults && wordResults.pages.length > 0 && (
          <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <h2 className="section-label">In the readings · {wordResults.pages.length}</h2>
            <div className="card list-card">
              {wordResults.pages.map((p) => (
                <Link key={`${p.reading_id}-${p.page}`} className="result" to={`/readings/${p.reading_id}?page=${p.page}`}>
                  <span className="what">
                    <span className="muted small">{p.reading_title} · p. {p.page}</span>
                    <Snippet text={p.snippet} serif />
                  </span>
                </Link>
              ))}
            </div>
          </section>
        )}
      </div>
    </>
  );
}
