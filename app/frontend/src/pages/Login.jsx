import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { get, logIn } from '../api.js';
import { rememberUsers } from '../colors.js';
import Avatar from '../components/Avatar.jsx';
import ErrorNotice from '../components/ErrorNotice.jsx';

// S01: pick who you are. No passwords (SPEC §3.1). TODO(edge): anyone can be anyone.
const COURSE_TITLE = 'HIST 214: Black Intellectual Traditions'; // DEMO: GET /users comes before any course call

function roleLine(user, currentCohort) {
  if (user.role === 'professor') return 'Professor';
  if (user.cohort !== currentCohort) return `Past student · ${user.cohort}`;
  return `Student · ${user.cohort}`;
}

export default function Login() {
  const navigate = useNavigate();
  const [users, setUsers] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    get('/users').then((list) => {
      setUsers(list);
      rememberUsers(list);
    }).catch(setError);
  }, []);

  function choose(user) {
    logIn(user);
    navigate('/');
  }

  // The current class is the professor's cohort.
  const currentCohort = users?.find((u) => u.role === 'professor')?.cohort;

  return (
    <div className="login">
      <main>
        <div className="login-title">
          <strong style={{ fontSize: 22, letterSpacing: '-0.01em' }}>Dialectic</strong>
          <h1>{COURSE_TITLE}</h1>
          <span className="muted">Choose who you are. No passwords in this demo.</span>
        </div>
        <ErrorNotice error={error} title="Couldn't load the people in this course" />
        {users && (
          <ul className="card raised">
            {users.map((user) => (
              <li key={user.id}>
                <Avatar person={user} size="large" />
                <button type="button" className="who" onClick={() => choose(user)}>
                  <strong>{user.name}</strong>
                  <span className="muted" style={{ fontSize: 13 }}>{roleLine(user, currentCohort)}</span>
                </button>
                <a href={`dialectic://login?user=${user.id}`} style={{ fontSize: 13, textDecoration: 'none', padding: '8px 10px' }}>Use on Mac</a>
              </li>
            ))}
          </ul>
        )}
        <span className="muted small" style={{ textAlign: 'center' }}>“Use on Mac” opens the Dialectic menu-bar app as the same person.</span>
      </main>
    </div>
  );
}
