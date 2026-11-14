import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { logOut, me, put } from '../api.js';
import Avatar from './Avatar.jsx';
import ErrorNotice from './ErrorNotice.jsx';
import { IS_MAC } from '../platform.js';

// The avatar in the header opens this (S19): share everything you've written with future
// classes or not (PUT /me/sharing), switch user, use on Mac (only shown on a Mac).
// TODO(edge): the switch starts "on"; the API has no per-user setting to read it from.
export default function UserMenu({ showName = true }) {
  const user = me();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [sharing, setSharing] = useState(true);
  const [confirmation, setConfirmation] = useState(null);
  const [error, setError] = useState(null);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    function closeOnOutsideClick(event) {
      if (!menuRef.current.contains(event.target)) setOpen(false);
    }
    document.addEventListener('mousedown', closeOnOutsideClick);
    return () => document.removeEventListener('mousedown', closeOnOutsideClick);
  }, [open]);

  async function toggleSharing() {
    const next = !sharing;
    setError(null);
    try {
      const result = await put('/me/sharing', { share_with_future: next });
      setSharing(result.share_with_future);
      const what = `${result.updated} notes and questions`;
      setConfirmation(result.share_with_future
        ? `${what} are shared with future classes again.`
        : `${what} are now hidden from future classes. Your own class can still see them.`);
    } catch (e) {
      setError(e);
    }
  }

  function switchUser() {
    logOut();
    navigate('/login');
  }

  return (
    <div className="user-menu" ref={menuRef}>
      <button type="button" className="user-button" aria-expanded={open} aria-haspopup="true" onClick={() => setOpen(!open)}>
        <Avatar person={user} />
        {showName && <span>{user.name}</span>}
      </button>
      {open && (
        <div className="user-menu-panel">
          <div className="menu-head">
            <Avatar person={user} size="large" />
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <strong>{user.name}</strong>
              <span className="muted small">{user.role === 'professor' ? 'Professor' : `Student · ${user.cohort}`}</span>
            </div>
          </div>
          <div className="menu-row">
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
              <strong id="share-label">Share my notes with future classes</strong>
              <span className="muted small">Applies to all the notes and questions you've written. You can still change single notes from their card in the margin.</span>
            </div>
            <button type="button" role="switch" className="switch" aria-checked={sharing} aria-labelledby="share-label" onClick={toggleSharing} />
          </div>
          {confirmation && <p className="menu-confirm" role="status">{confirmation}</p>}
          {error && <div style={{ margin: '0 10px 8px' }}><ErrorNotice error={error} title="Couldn't change sharing" /></div>}
          <button type="button" className="menu-row link" onClick={switchUser}>Switch user</button>
          {IS_MAC && <a className="menu-row link" href={`dialectic://login?user=${user.id}`}>Use on Mac</a>}
        </div>
      )}
    </div>
  );
}
