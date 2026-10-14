import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The API runs on :8000 (see Makefile). Vite proxies /api so the browser sees one origin.
// API_TARGET points the proxy at another API (e.g. a second local copy for testing sign-in).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: process.env.API_TARGET ?? 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
