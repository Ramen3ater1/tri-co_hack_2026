import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { get, logIn } from '../api.js';
import { rememberUsers } from '../colors.js';
import Avatar from '../components/Avatar.jsx';
import ErrorNotice from '../components/ErrorNotice.jsx';

// S01: pick who you are. No passwords (SPEC §3.1). TODO(edge): anyone can be anyone.
// People are grouped by course; each person is in one course. A big course shows its first
// few people (the professor, then the students the seed puts first) and folds the rest away.
const SHOWN_PER_COURSE = 4;

function roleLine(user, currentCohort) {
  if (user.role === 'professor') return 'Professor';
  if (user.cohort !== currentCohort) return `Past student · ${user.cohort}`;
  return `Student · ${user.cohort}`;
}

export default function Login() {
  const navigate = useNavigate();
  const [users, setUsers] = useState(null);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState({}); // course_id → showing everyone

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

  // GET /users is ordered by course, then id.
  const courses = [];
  for (const user of users || []) {
    let course = courses.find((c) => c.id === user.course_id);
    if (!course) {
      course = { id: user.course_id, title: user.course_title, currentCohort: user.current_cohort, people: [] };
      courses.push(course);
    }
    course.people.push(user);
  }

  function personRow(user, currentCohort) {
    return (
      <li key={user.id}>
        <Avatar person={user} size="large" />
        <button type="button" className="who" onClick={() => choose(user)}>
          <strong>{user.name}</strong>
          <span className="muted" style={{ fontSize: 13 }}>{roleLine(user, currentCohort)}</span>
        </button>
        <a href={`dialectic://login?user=${user.id}`} style={{ fontSize: 13, textDecoration: 'none', padding: '8px 10px' }}>Use on Mac</a>
      </li>
    );
  }

  return (
    <div className="login">
      <main>
        <div className="login-title">
          <h1>Dialectic</h1>
          <span className="muted">Choose who you are. No passwords in this demo.</span>
        </div>
        <ErrorNotice error={error} title="Couldn't load the people in these courses" />
        {courses.map((course) => {
          const showAll = expanded[course.id] || course.people.length <= SHOWN_PER_COURSE + 1;
          const shown = showAll ? course.people : course.people.slice(0, SHOWN_PER_COURSE);
          return (
            <section key={course.id} className="login-course">
              <h2>{course.title}</h2>
              <ul className="card raised">
                {shown.map((user) => personRow(user, course.currentCohort))}
                {!showAll && (
                  <li>
                    <button type="button" className="link-button" onClick={() => setExpanded({ ...expanded, [course.id]: true })}>
                      Show all {course.people.length} people
                    </button>
                  </li>
                )}
              </ul>
            </section>
          );
        })}
        <span className="muted small" style={{ textAlign: 'center' }}>“Use on Mac” opens the Dialectic menu-bar app as the same person.</span>
      </main>
    </div>
  );
}
