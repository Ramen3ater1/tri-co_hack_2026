import { useState } from 'react';
import { me } from '../api.js';
import Avatar from './Avatar.jsx';
import { LockIcon } from './Icons.jsx';

// The right-hand column (S03, S05): cards for the current page in the order they sit on
// the page, top to bottom. Full annotations get a card with replies; locked ones (the
// engagement lock, SPEC §3.4) get one lock card per server `group`, with no author or text.

// Same idea as db.NEAR_DISTANCE on the server: only used here to tell a lock card that the
// passage you've selected is next to it ("Saving your note shows them.").
const NEAR_DISTANCE = 0.08;

function top(rects) {
  return rects && rects.length ? Math.min(...rects.map((r) => r.y)) : 0;
}

function bottom(rects) {
  return rects && rects.length ? Math.max(...rects.map((r) => r.y + r.h)) : 0;
}

function isNear(rectsA, rectsB) {
  const gap = Math.max(top(rectsA) - bottom(rectsB), top(rectsB) - bottom(rectsA), 0);
  return gap <= NEAR_DISTANCE;
}

// Locked annotations → one item per group, with every box in the group (for its position).
function lockGroups(locked) {
  const groups = new Map();
  for (const annotation of locked) {
    const key = annotation.group ?? annotation.id;
    if (!groups.has(key)) groups.set(key, { key, notes: annotation.group_notes ?? 1, rects: [] });
    groups.get(key).rects.push(...(annotation.rects || []));
  }
  return [...groups.values()];
}

function timeAgo(createdAt) {
  const minutes = Math.round((Date.now() - new Date(createdAt)) / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min`;
  if (minutes < 60 * 24) return `${Math.round(minutes / 60)} h`;
  return new Date(createdAt).toLocaleDateString([], { month: 'short', day: 'numeric' });
}

// "Answered: 2 classmates, 1 source, AI context" (SPEC §3.5, from answer_summary).
function answeredLine(summary) {
  const parts = [];
  if (summary.peer_authors) parts.push(`${summary.peer_authors} classmate${summary.peer_authors === 1 ? '' : 's'}`);
  if (summary.sources) parts.push(`${summary.sources} source${summary.sources === 1 ? '' : 's'}`);
  if (summary.ai_answer) parts.push('AI context');
  return parts.length ? `Answered: ${parts.join(', ')}` : 'Answer: nothing found yet';
}

function AuthorLine({ annotation }) {
  const mine = annotation.author.id === me().id;
  const asked = annotation.kind === 'question';
  return (
    <span>
      <strong>{mine ? 'You' : annotation.author.name}</strong>
      {asked && ' asked'}
      {annotation.badge && (
        <>
          {' '}
          <span className={`pill ${annotation.badge === 'Professor' ? 'mint' : annotation.badge === 'AI' ? 'ai' : ''}`}>{annotation.badge}</span>
        </>
      )}
      <span className="muted">
        {annotation.via === 'hotkey' && ' · via the Mac hotkey'}
        {' · '}{timeAgo(annotation.created_at)}
      </span>
    </span>
  );
}

function Reply({ reply, onDelete }) {
  const mine = reply.author.id === me().id;
  return (
    <div className="reply">
      <Avatar person={reply.author} size="tiny" />
      <span className={`body${reply.kind === 'ai_answer' ? ' ai-body' : ''}`}>
        <strong>{mine ? 'You' : reply.author.name}</strong>
        {reply.badge === 'AI' && <> <span className="pill ai">AI</span></>}{' '}
        {reply.body}
      </span>
      {mine && <button type="button" className="link-button danger small" onClick={() => onDelete(reply)}>Delete</button>}
    </div>
  );
}

function AnnotationCard({ annotation, active, cardRef, onSelect, onReply, onDelete, onShare, onOpenAnswer }) {
  const [reply, setReply] = useState('');
  const [replying, setReplying] = useState(false);
  const mine = annotation.author.id === me().id;

  async function sendReply(event) {
    event.preventDefault();
    if (!reply.trim()) return;
    await onReply(annotation, reply.trim());
    setReply('');
  }

  return (
    <div ref={cardRef} className={`card margin-card${active ? ' active' : ''}`} onClick={() => onSelect(annotation)}>
      <Avatar person={annotation.author} size="small" />
      <div className="content">
        <AuthorLine annotation={annotation} />
        <span className="body">{annotation.body}</span>
        {annotation.kind === 'question' && annotation.answer_summary && (
          <button type="button" className="link-button small" style={{ alignSelf: 'flex-start' }} onClick={(e) => { e.stopPropagation(); onOpenAnswer(annotation); }}>
            {answeredLine(annotation.answer_summary)}
          </button>
        )}
        {mine && (
          <span className="meta">
            <label className="check-label" style={{ minHeight: 0, fontSize: 12 }} onClick={(e) => e.stopPropagation()}>
              <input type="checkbox" style={{ width: 14, height: 14 }} checked={annotation.share_with_future} onChange={(e) => onShare(annotation, e.target.checked)} />
              Shared with future classes
            </label>
            <span className="spacer" />
            <button type="button" className="link-button danger" onClick={(e) => { e.stopPropagation(); onDelete(annotation); }}>Delete</button>
          </span>
        )}
        {annotation.replies.map((r) => <Reply key={r.id} reply={r} onDelete={onDelete} />)}
        {replying || annotation.replies.length > 0 ? (
          <form className="reply-form" onSubmit={sendReply} onClick={(e) => e.stopPropagation()}>
            <label htmlFor={`reply-${annotation.id}`} className="visually-hidden">Reply to {annotation.author.name}</label>
            <input id={`reply-${annotation.id}`} className="input" type="text" placeholder="Reply…" autoFocus={replying} value={reply} onChange={(e) => setReply(e.target.value)} />
          </form>
        ) : (
          <button type="button" className="link-button" style={{ alignSelf: 'flex-start', fontSize: 13 }} onClick={(e) => { e.stopPropagation(); setReplying(true); }}>Reply</button>
        )}
      </div>
    </div>
  );
}

function LockCard({ group, nearSelection }) {
  return (
    <div className={`lock-card${nearSelection ? ' near-selection' : ''}`}>
      <span className="lock-icons" aria-hidden="true">
        <span />
        <span><LockIcon /></span>
      </span>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <strong>{group.notes} note{group.notes === 1 ? '' : 's'} near here.</strong>
        <span style={{ color: nearSelection ? 'var(--accent-dark)' : 'var(--soft-ink)' }}>
          {nearSelection ? 'Saving a note or asking about this passage shows them.' : 'Add a note or ask a question to see them.'}
        </span>
      </div>
    </div>
  );
}

export default function Margin({ page, annotations, activeId, selection, cardRefs, onSelect, onReply, onDelete, onShare, onOpenAnswer }) {
  const onPage = annotations.filter((a) => a.page === page);
  const items = [
    ...onPage.filter((a) => !a.locked).map((a) => ({ kind: 'card', y: top(a.rects), annotation: a })),
    ...lockGroups(onPage.filter((a) => a.locked)).map((g) => ({ kind: 'lock', y: top(g.rects), group: g })),
  ].sort((a, b) => a.y - b.y);

  return (
    <aside className="margin" aria-label="Margin">
      <div className="margin-head">
        <h2 className="section-label">Margin · p. {page}</h2>
      </div>
      {items.length === 0 && (
        <div className="empty" style={{ fontSize: 13 }}>No notes on this page yet. Select some text to write the first one or ask a question.</div>
      )}
      {items.map((item) =>
        item.kind === 'lock' ? (
          <LockCard
            key={`lock-${item.group.key}`}
            group={item.group}
            nearSelection={selection && selection.page === page && isNear(selection.rects, item.group.rects)}
          />
        ) : (
          <AnnotationCard
            key={item.annotation.id}
            annotation={item.annotation}
            active={item.annotation.id === activeId}
            cardRef={(el) => { cardRefs.current[item.annotation.id] = el; }}
            onSelect={onSelect}
            onReply={onReply}
            onDelete={onDelete}
            onShare={onShare}
            onOpenAnswer={onOpenAnswer}
          />
        ),
      )}
    </aside>
  );
}
