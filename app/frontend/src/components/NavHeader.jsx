import { NavLink, Link } from 'react-router-dom';
import UserMenu from './UserMenu.jsx';

// The header on every page except the reader (which has its own): wordmark, four tabs, you.
const TABS = [
  { to: '/', label: 'Readings' },
  { to: '/charter', label: 'Charter' },
  { to: '/sources', label: 'Sources' },
  { to: '/search', label: 'Search' },
];

export default function NavHeader() {
  return (
    <header className="nav-header">
      <Link to="/" className="wordmark">Dialectic</Link>
      <nav aria-label="Course">
        {TABS.map((tab) => (
          <NavLink key={tab.to} to={tab.to} end className={({ isActive }) => (isActive ? 'active' : '')}>
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <div className="spacer" />
      <UserMenu />
    </header>
  );
}
