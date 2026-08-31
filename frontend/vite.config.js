import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Dev: Vite serves the SPA and proxies API + Django-owned paths to the
// backend so everything is one origin (no CORS, cookies just work).
// Prod: Django + whitenoise serves the built bundle from dist/ — single
// origin there too — so this proxy block is dev-only.
const target = process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000'
const proxied = ['/api', '/admin', '/accounts', '/static', '/media']

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      proxied.map((path) => [path, { target, changeOrigin: true }])
    ),
  },
})
