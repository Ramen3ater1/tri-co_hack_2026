// "Report a problem": opens a new GitHub issue with the page, the logged-in user and the
// browser already filled in, so a teammate only types what's wrong (DEPLOY.md, CLAUDE.md
// "Feedback issues"). Shown only on the dev copy and locally, never to judges or participants.
import React from 'react';
import { me } from '../api.js';

const NEW_ISSUE_URL = 'https://github.com/Ramen3ater1/tri-co_hack_2026/issues/new';

function shouldShow() {
  const host = window.location.hostname;
  return host === 'localhost' || host === '127.0.0.1' || host.startsWith('dev.') || host.includes('-dev.');
}

function issueLink() {
  const user = me();
  const params = new URLSearchParams({
    template: 'feedback.yml',
    title: `Feedback: ${window.location.pathname}`,
    page: window.location.href,
    user: user ? `${user.name} (${user.role})` : 'not logged in',
    browser: `${navigator.userAgent} · window ${window.innerWidth}×${window.innerHeight}`,
  });
  return `${NEW_ISSUE_URL}?${params}`;
}

export default function FeedbackButton() {
  if (!shouldShow()) return null;
  return (
    <button
      type="button"
      className="btn"
      // Built when clicked, so it has the current page and user.
      onClick={() => window.open(issueLink(), '_blank', 'noopener')}
      style={{ position: 'fixed', right: 16, bottom: 16, zIndex: 1000, boxShadow: 'var(--shadow)' }}
    >
      Report a problem
    </button>
  );
}
