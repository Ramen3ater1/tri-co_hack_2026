import { useEffect, useRef, useState } from 'react';
import { get, isProfessor, patch, post, put } from '../api.js';
import NavHeader from '../components/NavHeader.jsx';
import Avatar from '../components/Avatar.jsx';
import ErrorNotice from '../components/ErrorNotice.jsx';

// The class charter (S12 professor, S13 student, S18 charter gaps). One page: the
// professor edits and answers proposals, students read and post proposals. Switches save the moment they
// change (they're hard limits, and demo step 4 flips one live); the two texts save
// with "Save charter".

const GAPS_SHOWN = 5; // the most-skipped kinds; the rest sit behind "Show N more"

// The switches, in the order shown, with their one-line help.
const SWITCHES = [
  { key: 'ai_enabled', label: 'AI enabled', help: 'Off means no AI calls at all.', student: null },
  { key: 'ai_find_sources', label: 'AI may find sources', help: 'Off: only the course library is searched.', student: 'Find sources' },
  { key: 'ai_explanations', label: 'AI may write explanations', help: 'Short, public, labelled, open to replies.', student: 'Write explanations' },
  { key: 'ai_semantic_search', label: 'AI may search readings by meaning', help: 'Finds passages that say something in other words. Off: search matches words only.', student: 'Search readings by meaning' },
  { key: 'show_past_cohorts', label: "Show past classes' notes", help: 'Only notes their authors shared.', student: "Past classes' notes" },
  { key: 'annotate_before_peers', label: 'Write before you read peers', help: "Classmates' notes stay hidden until a student writes a note or asks near them. Your notes are always visible.", student: 'Write before you read peers' },
];

// What the gaps buttons add to "Sources we trust" (S18).
function allowSentence(kind) {
  return `${kind[0].toUpperCase()}${kind.slice(1)} are allowed.`;
}
function ruleOutSentence(kind) {
  return `No ${kind}.`;
}

// A student's "Propose allowing" proposal starts with this; the professor's button then adds
// the sentence to "Sources we trust" instead of the rules.
const SOURCES_PROPOSAL = 'Could we add this to "Sources we trust": ';

// How a proposal's status reads, for everyone.
const STATUS_WORDS = { added: 'Added to the charter', declined: 'Declined' };

// Append a proposal to the rules as the next numbered rule (or a plain line if they aren't numbered).
function withRule(rules, body) {
  const lines = rules.split('\n').filter((line) => line.trim());
  const numbered = lines.filter((line) => /^\s*\d+[.)]\s+/.test(line));
  const line = numbered.length === lines.length ? `${numbered.length + 1}. ${body}` : body;
  return `${rules.trimEnd()}\n${line}`;
}

function when(createdAt) {
  const date = new Date(createdAt);
  const days = Math.floor((Date.now() - date) / 86400000);
  if (days < 1) return 'today';
  if (days < 2) return 'yesterday';
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

// The rules are Markdown, but in practice a numbered list: show "1. …" lines as an
// ordered list and anything else as plain paragraphs (never as HTML).
function Rules({ text }) {
  const lines = text.split('\n').filter((line) => line.trim());
  const numbered = lines.filter((line) => /^\s*\d+[.)]\s+/.test(line));
  if (numbered.length === lines.length) {
    return <ol className="rules">{numbered.map((line, i) => <li key={i}>{line.replace(/^\s*\d+[.)]\s+/, '')}</li>)}</ol>;
  }
  return <div className="rules-text">{text}</div>;
}

function Proposals({ comments, professor, onPost, onAnswer, onUse, using, draft, setDraft, draftRef }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const open = comments.filter((c) => c.status === 'open').length;

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onPost(draft.trim());
      setDraft('');
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  async function answer(id, status) {
    setError(null);
    try {
      await onAnswer(id, status);
    } catch (e) {
      setError(e);
    }
  }

  // The professor's buttons for one proposal.
  function Actions({ c }) {
    if (using[c.id]) return <span className="muted small">In the text above · marked added when you save</span>;
    if (c.status !== 'open') {
      return (
        <span className="actions">
          <span className={`pill ${c.status === 'added' ? 'mint' : 'off'}`}>{STATUS_WORDS[c.status]}</span>
          <button type="button" className="btn small" onClick={() => answer(c.id, 'open')}>Reopen</button>
        </span>
      );
    }
    const forSources = c.body.startsWith(SOURCES_PROPOSAL);
    return (
      <span className="actions">
        <button type="button" className="btn small" onClick={() => onUse(c, forSources)}>{forSources ? 'Add to sources' : 'Add to rules'}</button>
        <button type="button" className="btn small" onClick={() => answer(c.id, 'added')} title="You've already worked it into the text">Mark added</button>
        <button type="button" className="btn small" onClick={() => answer(c.id, 'declined')}>Decline</button>
      </span>
    );
  }

  return (
    <section className="card charter-block">
      <div>
        <h2>Proposals from the class · {professor ? `${open} open` : comments.length}</h2>
        {professor && <span className="muted small">Add one to the text (then edit and save), mark it added if you've worked it in yourself, or decline it. Students see your answer.</span>}
      </div>
      {comments.length === 0 && <span className="muted">No proposals yet.</span>}
      <div>
        {comments.map((c) => (
          <div key={c.id} className="comment">
            <Avatar person={{ name: c.author, role: c.author_role }} size="small" />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
              <span>
                <strong>{c.author}</strong> <span className="muted">· {when(c.created_at)}</span>
                {!professor && c.status !== 'open' && <> <span className={`pill ${c.status === 'added' ? 'mint' : 'off'}`}>{STATUS_WORDS[c.status]}</span></>}
              </span>
              <span style={{ whiteSpace: 'pre-wrap' }}>{c.body}</span>
              {professor && <Actions c={c} />}
            </div>
          </div>
        ))}
      </div>
      {!professor && (
        <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <label htmlFor="proposal" className="muted small">Propose a change. Your professor works proposals into the charter.</label>
          <textarea id="proposal" ref={draftRef} className="textarea" rows={2} value={draft} onChange={(e) => setDraft(e.target.value)} />
          <button type="submit" className="btn" style={{ alignSelf: 'flex-start' }} disabled={busy || !draft.trim()}>Post proposal</button>
        </form>
      )}
      <ErrorNotice error={error} title={professor ? "Couldn't update that proposal" : "Couldn't post your proposal"} />
    </section>
  );
}

function Gaps({ gaps, professor, onAdd, onDismiss, onPropose, added }) {
  const [showAll, setShowAll] = useState(false);
  const shown = showAll ? gaps : gaps.slice(0, GAPS_SHOWN);
  return (
    <section className="card charter-block">
      <div>
        <h2>Not covered by your charter</h2>
        <span className="muted small">Last 7 days · the AI skipped these because “Sources we trust” doesn't mention them. Who asked is never stored.</span>
      </div>
      {gaps.length === 0 && <span className="muted">Nothing skipped in the last 7 days.</span>}
      <div>
        {shown.map((gap) => (
          <div key={gap.kind} className="gap-row">
            <span className="count-pill">{gap.count}</span>
            <span className="what">
              <strong>{gap.kind[0].toUpperCase() + gap.kind.slice(1)}</strong>
              {gap.examples[0] && (
                <span className="muted small">
                  e.g. <a href={gap.examples[0].url} target="_blank" rel="noreferrer">{gap.examples[0].title}</a>
                </span>
              )}
            </span>
            {added[gap.kind] ? (
              <span className="muted small">Added to the text above</span>
            ) : professor ? (
              <span className="actions">
                <button type="button" className="btn small" onClick={() => onAdd(gap.kind, allowSentence(gap.kind))}>Allow</button>
                <button type="button" className="btn small" onClick={() => onAdd(gap.kind, ruleOutSentence(gap.kind))}>Rule out</button>
                <button type="button" className="btn small" onClick={() => onDismiss(gap.kind)}>Dismiss</button>
              </span>
            ) : (
              <span className="actions">
                <button type="button" className="btn small" onClick={() => onPropose(gap.kind)}>Propose allowing</button>
              </span>
            )}
          </div>
        ))}
      </div>
      {gaps.length > shown.length && (
        <button type="button" className="btn small" style={{ alignSelf: 'flex-start' }} onClick={() => setShowAll(true)}>
          Show {gaps.length - shown.length} more
        </button>
      )}
    </section>
  );
}

// A switch as a student sees it: AI switches only count while AI is enabled at all.
function StudentPill({ charter, switchKey }) {
  const aiSwitch = ['ai_find_sources', 'ai_explanations', 'ai_semantic_search'].includes(switchKey);
  const on = aiSwitch ? charter.ai_enabled && charter[switchKey] : charter[switchKey];
  const words = switchKey === 'show_past_cohorts' ? (on ? 'Shown' : 'Hidden') : (on ? 'On' : 'Off');
  return <span className={`pill ${on ? 'mint' : 'off'}`}>{words}</span>;
}

export default function Charter() {
  const professor = isProfessor();
  const [charter, setCharter] = useState(null);
  const [gaps, setGaps] = useState([]);
  const [rules, setRules] = useState('');
  const [editingRules, setEditingRules] = useState(false); // professor: the rules show as a list until Edit
  const [sources, setSources] = useState('');
  const [added, setAdded] = useState({}); // gap kinds whose sentence was added, unsaved
  const [using, setUsing] = useState({}); // proposal ids added to the text, marked 'added' on save
  const [saved, setSaved] = useState(null);
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState('');
  const draftRef = useRef(null);

  function show(next) {
    setCharter(next);
    setRules(next.text_md);
    setSources(next.permissible_sources);
  }

  useEffect(() => {
    get('/charter').then(show).catch(setError);
    get('/charter/gaps').then(setGaps).catch(setError);
  }, []);

  const unsaved = charter && (rules !== charter.text_md || sources !== charter.permissible_sources);
  const changes = charter ? (rules !== charter.text_md) + (sources !== charter.permissible_sources) : 0;

  async function save() {
    setError(null);
    try {
      const sourcesChanged = sources !== charter.permissible_sources;
      let next = await put('/charter', { text_md: rules, permissible_sources: sources });
      for (const id of Object.keys(using)) next = await patch(`/charter/comments/${id}`, { status: 'added' });
      show(next);
      setAdded({});
      setUsing({});
      setSaved('Charter saved.');
      setEditingRules(false);
      // New source text clears the gaps list on the server (it was judged against the old text).
      if (sourcesChanged) setGaps(await get('/charter/gaps'));
    } catch (e) {
      setError(e);
    }
  }

  async function setSwitch(key, value) {
    setError(null);
    setCharter((c) => ({ ...c, [key]: value })); // flip it now; the server's reply follows
    try {
      const next = await put('/charter', { [key]: value });
      setCharter(next); // keep any unsaved text edits
      setSaved('Switch saved. It applies to the next question asked.');
    } catch (e) {
      setError(e);
    }
  }

  function addSentence(kind, sentence) {
    setSources((text) => `${text.trim()} ${sentence}`);
    setAdded((a) => ({ ...a, [kind]: true }));
    setSaved(null);
  }

  async function dismiss(kind) {
    try {
      setGaps(await post('/charter/gaps/dismiss', { kind }));
    } catch (e) {
      setError(e);
    }
  }

  function propose(kind) {
    setDraft(`Could we add this to "Sources we trust": ${allowSentence(kind)}`);
    draftRef.current?.focus();
    draftRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  async function postProposal(body) {
    show(await post('/charter/comments', { body }));
  }

  // Professor: put a proposal into the text; it's marked added when the charter is saved.
  function useProposal(comment, forSources) {
    if (forSources) {
      setSources((text) => `${text.trim()} ${comment.body.slice(SOURCES_PROPOSAL.length).trim()}`);
    } else {
      setRules((text) => withRule(text, comment.body));
    }
    setUsing((u) => ({ ...u, [comment.id]: true }));
    setSaved(null);
  }

  // Professor: answer a proposal. Only the comments come from the reply, so unsaved text edits stay.
  async function answerProposal(id, status) {
    const next = await patch(`/charter/comments/${id}`, { status });
    setCharter((c) => ({ ...c, comments: next.comments }));
  }

  return (
    <>
      <NavHeader />
      <div className="page-body">
        <div className="page-title" style={{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'flex-end', gap: 16 }}>
          <div style={{ flex: 1, minWidth: 260, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <h1>{professor ? 'Class charter' : 'Our charter'}</h1>
            <span className="muted">
              {professor ? 'Everyone can read it. Number the rules so answers can cite them.' : `Last changed ${charter ? when(charter.updated_at) : '…'}`}
            </span>
          </div>
          {professor && (
            <div className="save-bar">
              {unsaved && <span className="muted small">{changes} unsaved change{changes === 1 ? '' : 's'}</span>}
              {!unsaved && saved && <span className="small" style={{ color: '#1E4D2E' }} role="status">{saved}</span>}
              <button type="button" className="btn primary" disabled={!unsaved} onClick={save}>Save charter</button>
            </div>
          )}
        </div>
        <ErrorNotice error={error} title="Charter error" />

        {charter && (
          <div className="charter-grid">
            <div className="charter-main">
              <section className="card charter-block">
                {professor && !editingRules && rules === charter.text_md ? (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <h2>Rules</h2>
                      <button type="button" className="btn small" onClick={() => setEditingRules(true)}>Edit rules</button>
                    </div>
                    <Rules text={charter.text_md} />
                  </>
                ) : professor ? (
                  <>
                    <label htmlFor="rules"><h2>Rules <span className="muted small" style={{ fontWeight: 400 }}>· Markdown</span></h2></label>
                    <textarea id="rules" className={`textarea${rules !== charter.text_md ? ' changed' : ''}`} rows={7} value={rules} onChange={(e) => setRules(e.target.value)} />
                  </>
                ) : (
                  <Rules text={charter.text_md} />
                )}
              </section>

              <section className="card charter-block">
                {professor ? (
                  <>
                    <label htmlFor="sources">
                      <h2>Sources we trust <span className="muted small" style={{ fontWeight: 400 }}>· in plain words; the AI's web search is filtered by this</span></h2>
                    </label>
                    <textarea id="sources" className={`textarea${sources !== charter.permissible_sources ? ' changed' : ''}`} rows={5} value={sources} onChange={(e) => setSources(e.target.value)} />
                    {Object.keys(added).length > 0 && <span className="muted small">The buttons below added a sentence at the end. Edit it into your own words before saving if you like.</span>}
                  </>
                ) : (
                  <>
                    <h2>Sources we trust</h2>
                    <div className="rules-text" style={{ fontSize: 15 }}>{charter.permissible_sources}</div>
                  </>
                )}
              </section>

              <Gaps gaps={gaps} professor={professor} added={added} onAdd={addSentence} onDismiss={dismiss} onPropose={propose} />

              <Proposals
                comments={charter.comments}
                professor={professor}
                onPost={postProposal}
                onAnswer={answerProposal}
                onUse={useProposal}
                using={using}
                draft={draft}
                setDraft={setDraft}
                draftRef={draftRef}
              />
            </div>

            <aside>
              <section className="card charter-block">
                <div>
                  <h2>{professor ? 'Switches' : 'What AI may do here'}</h2>
                  {professor && <span className="muted small">Hard limits, checked before any AI call.</span>}
                </div>
                <div>
                  {SWITCHES.filter((s) => professor || s.student).map((s) => (
                    professor ? (
                      <label key={s.key} className="toggle-row">
                        <input type="checkbox" checked={charter[s.key]} onChange={(e) => setSwitch(s.key, e.target.checked)} />
                        <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                          <strong>{s.label}</strong>
                          <span className="muted small">{s.help}</span>
                          {s.key === 'ai_explanations' && (
                            <span className="words" onClick={(e) => e.preventDefault()}>
                              <span className="muted">Longest explanation</span>
                              <input
                                className="input"
                                type="number"
                                min={20}
                                max={400}
                                defaultValue={charter.max_explanation_words}
                                aria-label="Longest explanation, in words"
                                onBlur={(e) => Number(e.target.value) !== charter.max_explanation_words && setSwitch('max_explanation_words', Number(e.target.value))}
                              />
                              <span className="muted">words</span>
                            </span>
                          )}
                        </span>
                      </label>
                    ) : (
                      <div key={s.key} className="toggle-row" style={{ alignItems: 'center' }}>
                        <span style={{ flex: 1 }}>{s.student}</span>
                        <StudentPill charter={charter} switchKey={s.key} />
                      </div>
                    )
                  ))}
                </div>
              </section>
            </aside>
          </div>
        )}
      </div>
    </>
  );
}
