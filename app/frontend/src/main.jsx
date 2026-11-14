import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { me } from './api.js';
import Login from './pages/Login.jsx';
import Course from './pages/Course.jsx';
import Reader from './pages/Reader.jsx';
import Charter from './pages/Charter.jsx';
import Sources from './pages/Sources.jsx';
import Search from './pages/Search.jsx';
import './styles.css';

// Every page but Login needs someone "logged in" (SPEC §3.1: no passwords).
function LoggedIn({ children }) {
  return me() ? children : <Navigate to="/login" replace />;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<LoggedIn><Course /></LoggedIn>} />
        <Route path="/readings/:id" element={<LoggedIn><Reader /></LoggedIn>} />
        <Route path="/charter" element={<LoggedIn><Charter /></LoggedIn>} />
        <Route path="/sources" element={<LoggedIn><Sources /></LoggedIn>} />
        <Route path="/search" element={<LoggedIn><Search /></LoggedIn>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

createRoot(document.getElementById('root')).render(<App />);
