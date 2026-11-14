import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { get } from '../api.js';
import NavHeader from '../components/NavHeader.jsx';
import Avatar from '../components/Avatar.jsx';
import ErrorNotice from '../components/ErrorNotice.jsx';

// S15: full-text search over the notes you can see and the readings' text. Snippets mark
// hits as [[word]]; we split the string and wrap hits in <mark>, never innerHTML
// (annotation bodies are user input). Locked notes never appear (the server leaves them out).

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
  const [query, setQuery] = useState(q);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!q) {
      setResults(null);
      return;
    }
    setError(null);
    get(`/search?q=${encodeURIComponent(q)}`).then(setResults).catch(setError);
  }, [q]);

  function search(event) {
    event.preventDefault();
    if (query.trim()) setParams({ q: query.trim() });
  }

  const empty = results && results.annotations.length === 0 && results.pages.length === 0;

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
        <ErrorNotice error={error} title="Search failed" />

        {empty && (
          <div className="empty">
            <strong style={{ display: 'block', color: 'var(--ink)' }}>Nothing found for “{q}”</strong>
            Search covers the readings and the notes you can see. Notes still locked for you aren't searched.
          </div>
        )}

        {results && results.annotations.length > 0 && (
          <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <h2 className="section-label">Notes and questions · {results.annotations.length}</h2>
            <div className="card list-card">
              {results.annotations.map((a) => (
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

        {results && results.pages.length > 0 && (
          <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <h2 className="section-label">In the readings · {results.pages.length}</h2>
            <div className="card list-card">
              {results.pages.map((p) => (
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
