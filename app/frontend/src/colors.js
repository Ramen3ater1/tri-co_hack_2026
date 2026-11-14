// Person colours (ideas/02 *Visual style*): one per person, used for their highlight,
// avatar and margin card. The professor is always mint and the AI black; everyone else
// gets a colour from PALETTE by user id, so the same person keeps it everywhere.

const PROFESSOR = { bg: '#CFEFD9', ink: '#1E4D2E' }; // mint
const AI = { bg: '#22201C', ink: '#FFFFFF' };
const PALETTE = [
  { bg: '#D3E6FA', ink: '#1F3E66' }, // sky (DEMO: Ben, id 3)
  { bg: '#E4DBF7', ink: '#3D2A6B' }, // lavender (DEMO: Sam, id 4)
  { bg: '#FFDCCB', ink: '#6B2E14' }, // peach (DEMO: Ana, id 2)
];

// Peer results in an Ask answer carry the author's name but not their id: Login saves
// the user list so we can still find their colour.
const USERS_KEY = 'dialectic_users';

export function rememberUsers(users) {
  localStorage.setItem(USERS_KEY, JSON.stringify(users));
}

function userByName(name) {
  const users = JSON.parse(localStorage.getItem(USERS_KEY) || '[]');
  return users.find((u) => u.name === name);
}

// person: an annotation's `author` ({id, role, name}), or just {name} for a peer result.
export function colorFor(person) {
  if (!person) return PALETTE[0];
  const known = person.id ? person : userByName(person.name) || person;
  if (known.role === 'professor') return PROFESSOR;
  if (known.role === 'ai') return AI;
  if (!known.id) return PALETTE[0];
  return PALETTE[known.id % PALETTE.length];
}

export function initial(name) {
  if (!name) return '?';
  if (name.startsWith('Prof. ')) return name[6];
  return name[0].toUpperCase();
}
