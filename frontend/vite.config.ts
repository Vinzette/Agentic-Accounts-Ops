import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // In dev the API runs separately; in production FastAPI serves this bundle.
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
