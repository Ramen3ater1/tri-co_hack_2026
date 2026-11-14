import { useState } from 'react';
import ErrorNotice from './ErrorNotice.jsx';

// The popover over a fresh selection (S04, S06): two tabs, Annotate | Ask.
// Annotate saves a note; Ask is a question box and a button, nothing else
// (no suggested questions anywhere: students write their own).

function shorten(text, max = 60) {
  return text.length > max ? text.slice(0, max - 1) + '…' : text;
}

// A box drawn with "Select area" (SPEC §3.3) has no selected text: show what the server read in
// it, editable, since a bad scan may have misread it (or have no text at all).
function BoxPassage({ selection, onQuoteChange }) {
  return (
    <label className="box-passage">
      <span className="muted small">
        {selection.readingBox ? 'Reading the text in this box…' : 'Passage in this box (fix it if the scan misread it, or type it in)'}
      </span>
      <textarea
        className="textarea"
        rows={2}
        value={selection.quote}
        disabled={selection.readingBox}
        placeholder={selection.readingBox ? '' : 'No readable text here. Type the passage, or leave it empty for a note about a picture.'}
        onChange={(e) => onQuoteChange(e.target.value)}
      />
    </label>
  );
}

export default function Composer({ selection, tab, onTab, onSaveNote, onAsk, onQuoteChange }) {
  const [note, setNote] = useState('');
  const [share, setShare] = useState(true);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function saveNote(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSaveNote(note.trim(), share);
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }

  function ask(event) {
    event.preventDefault();
    onAsk(question.trim());
  }

  return (
    <div className="popover" role="dialog" aria-label={tab === 'ask' ? 'Ask about this passage' : 'Write a note'}>
      <div className="pointer" />
      <div className="tabs" role="tablist" aria-label="Action">
        <button type="button" role="tab" aria-selected={tab === 'annotate'} onClick={() => onTab('annotate')}>Annotate</button>
        <button type="button" role="tab" aria-selected={tab === 'ask'} onClick={() => onTab('ask')}>Ask</button>
      </div>
      {selection.box && <div className="popover-body" style={{ paddingBottom: 0 }}><BoxPassage selection={selection} onQuoteChange={onQuoteChange} /></div>}
      {tab === 'annotate' ? (
        <form className="popover-body" onSubmit={saveNote}>
          <label htmlFor="note" className="visually-hidden">Your note</label>
          <textarea id="note" className="textarea" rows={3} autoFocus={!selection.box} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Your note…" />
          <div className="popover-actions">
            <label className="check-label" style={{ flex: 1 }}>
              <input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} />
              Share with future classes
            </label>
            <button type="submit" className="btn primary" disabled={busy || !note.trim() || selection.readingBox}>{busy ? 'Saving…' : 'Save note'}</button>
          </div>
          <ErrorNotice error={error} title="Couldn't save your note" />
        </form>
      ) : (
        <form className="popover-body" onSubmit={ask}>
          <label htmlFor="question" className="muted small">
            {selection.quote.trim()
              ? <>Ask about <span className="quote-chip">{shorten(selection.quote)}</span></>
              : 'To ask, put the passage in the box above: classmates, sources and the AI all work from its text.'}
          </label>
          <textarea
            id="question"
            className="textarea"
            rows={2}
            autoFocus
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && question.trim() && selection.quote.trim()) ask(e); }}
          />
          <div className="popover-actions">
            <span className="muted small" style={{ flex: 1, lineHeight: 1.4 }}>Your question is posted to the class. Classmates come first, then sources, then AI if the charter allows.</span>
            <button type="submit" className="btn primary" disabled={!question.trim() || !selection.quote.trim()}>Ask</button>
          </div>
        </form>
      )}
    </div>
  );
}
