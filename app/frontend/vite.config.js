import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The backend has no CORS: in development Vite forwards /api to it, so the browser
// only ever talks to one origin (in production FastAPI serves dist/ itself).
const BACKEND_URL = 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': BACKEND_URL },
  },
});
