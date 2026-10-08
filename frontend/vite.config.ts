import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// VITE_TARGET=web → static GH Pages landing (hash router + fixed base /<repo>/)
// Anything else     → desktop / dev ( BrowserRouter + Vite proxy to :8000 )
const isWeb = process.env.VITE_TARGET === 'web';
const ghBase = '/unified-platform/'; // must match repo name for GH Pages

export default defineConfig({
  base: isWeb ? ghBase : '/',
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: isWeb ? 'build-web' : 'build',
    sourcemap: false,
  },
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
