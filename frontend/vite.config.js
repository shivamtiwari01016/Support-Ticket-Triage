import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// Proxying /api through the dev server means the browser only ever talks to the
// same origin, so CORS and the localhost/127.0.0.1 (IPv4 vs IPv6) split cannot
// break the connection. 127.0.0.1 is used literally to avoid DNS ambiguity.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const API_TARGET = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000'

  const proxy = { '/api': { target: API_TARGET, changeOrigin: true } }

  return {
    plugins: [react()],
    server: { host: true, port: 5173, strictPort: false, proxy, allowedHosts: true },
    preview: { host: true, port: 4173, proxy, allowedHosts: true },
  }
})
