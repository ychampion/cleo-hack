import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Contract §6: dev proxy for /api + ADK-native routes → FastAPI on :8080.
const backend = 'http://127.0.0.1:8080';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': backend,
      '/run_sse': backend,
      '/apps': backend,
      '/list-apps': backend,
    },
  },
  build: { outDir: 'dist' },
});
