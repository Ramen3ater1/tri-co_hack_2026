import { useEffect, useState } from 'react';
import { del, get, isProfessor, post } from '../api.js';
import NavHeader from '../components/NavHeader.jsx';
import ErrorNotice from '../components/ErrorNotice.jsx';

// S14: the course source library. Every source the AI used lands here; when AI is off,
// Ask searches this instead. The professor can add one by URL or remove one.

function site(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

function when(createdAt) {
  const date = new Date(createdAt);
  return Date.now() - date < 86400000 ? 'today' : date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

export default function Sources() {
  const professor = isProfessor();
  const [sources, setSources] = useState(null);
  const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    get('/sources').then(setSources).catch(setError);
  }, []);

  async function add(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setSources(await post('/sources', { url: url.trim() }));
      setUrl('');
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  async function remove(source) {
    if (!window.confirm(`Remove "${source.title}" from the library?`)) return;
    try {
      setSources(await del(`/sources/${source.id}`));
    } catch (e) {
      setError(e);
    }
  }

  return (
    <>
      <NavHeader />
      <div className="page-body">
        <div className="page-title">
          <h1>Source library</h1>
          <span className="muted">Every source the AI used for a question lands here. When AI is off, Ask searches this library instead, so the class needs AI less over time.</span>
        </div>
        {professor && (
          <form className="inline-form" onSubmit={add}>
            <label htmlFor="source-url" className="visually-hidden">Source URL</label>
            <input id="source-url" className="input" type="url" placeholder="Source URL" required value={url} onChange={(e) => setUrl(e.target.value)} />
            <button type="submit" className="btn dark" disabled={busy || !url.trim()}>{busy ? 'Adding…' : 'Add source'}</button>
          </form>
        )}
        <ErrorNotice error={error} title="Source library error" />
        {sources && sources.length === 0 && (
          <div className="empty">
            <strong style={{ display: 'block', color: 'var(--ink)' }}>No sources yet</strong>
            Sources the AI finds for questions are saved here, so later classes can use them without AI.{professor && ' You can also add one by URL.'}
          </div>
        )}
        {sources && sources.length > 0 && (
          <div className="card list-card">
            {sources.map((s) => (
              <div key={s.id} className="list-row">
                <span className="what">
                  <a href={s.url} target="_blank" rel="noreferrer">{s.title}</a>
                  <span className="muted small">
                    {site(s.url)} · {s.first_question
                      ? <>found for {s.first_question_author}'s question: “{s.first_question}”</>
                      : 'added by hand'}
                  </span>
                </span>
                <span className={`pill ${s.found_by === 'ai' ? 'sky' : 'mint'}`}>{s.found_by === 'ai' ? 'Found by AI' : 'Added by your professor'}</span>
                <span className="muted small">{when(s.created_at)}</span>
                {professor && <button type="button" className="link-button danger" onClick={() => remove(s)}>Remove</button>}
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
